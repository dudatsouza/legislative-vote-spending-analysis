"""Etapa 3 — Análise estatística (D6, D10, D11, D16, D18).

Uso:
    python -m src.analise.analisar

Lê as saídas de src.tratamento.tratar (votos, coesao_rice,
base_deputado_legislatura) e grava em data/processed/analise/:

Descritivas
    populacao_resumo.csv           população do D3 por legislatura × faixa e excluídos (< 12 meses)
    votacao_resumo.csv             registros, válidos, ausentes e amostras de cada votação
    tabulacao_partido_voto.csv     partido × voto_original por votação
    pro_pauta_partido_votacao.csv  % pró-pauta (ou % Sim nos Precatórios) por partido × votação  [V1]
    pro_pauta_grupo_legislatura.csv índice pró-pauta por espectro e família × legislatura      [V4]
    indice_pro_pauta_deputado.csv  índice pró-pauta por deputado × legislatura (D6)
    rice_agregado.csv              Rice ponderado por votação, legislatura e partido × legislatura (D10)
    rice_desposato.csv             Rice bruto × corrigido (Desposato, 2005) por partido × votação
    rice_desposato_ordem.csv       a ordenação dos partidos muda com a correção?
    fidelidade_deputado.csv        fidelidade ao partido e alinhamento ao Governo por deputado (D11)
    fidelidade_grupo.csv           idem por partido e espectro × legislatura, separado por fonte
    composicao_quadrante.csv       % de cada partido e espectro no quadrante de interesse      [V8]

Testes (D18; Holm dentro de cada família)
    f1_partido_voto.csv            qui-quadrado partido × voto por votação, V de Cramér
    f2_espectro_voto.csv           qui-quadrado espectro × voto por votação, V de Cramér
    f3_spearman.csv                Spearman gasto relativo × produtividade por legislatura × faixa [V7]
    f4_produtividade_voto.csv      Mann-Whitney da produtividade mensal entre Sim e Não
    f5_quadrante_voto.csv          quadrante de interesse × voto (2×2), razão de chances         [V10]
    testes_resumo.csv              as cinco famílias numa tabela só
    robustez.csv                   F2 sem classificação manual; F3 com "só Norma Jurídica";
                                   fidelidade só com orientação própria do partido

Tudo é associação, nunca causalidade (D18.9).
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats.contingency import odds_ratio

from src import config

DADOS = config.DATA_PROCESSED
OUT = DADOS / "analise"

VOTOS_VALIDOS = ("Sim", "Não")
Z = stats.norm.ppf(0.5 + config.NIVEL_CONFIANCA / 2)

# Convenção de Cohen (1988) para r, ρ, V de Cramér com gl* = 1 e rank-bisserial.
CORTES_COHEN_R = (0.1, 0.3, 0.5)
# Razão de chances: equivalentes aos d de Cohen 0,2 / 0,5 / 0,8
# (Chen, Cohen e Chen, 2010, Commun. Stat. Simul. Comput.).
CORTES_OR = (1.68, 3.47, 6.71)


# ===========================================================================
# Utilitários estatísticos
# ===========================================================================
def wilson(k, n):
    """IC de Wilson (D18.7) para k sucessos em n; aceita escalares ou arrays."""
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = k / n
        den = 1 + Z**2 / n
        centro = (p + Z**2 / (2 * n)) / den
        meia = Z * np.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / den
    return centro - meia, centro + meia


def holm(p):
    """p-valores ajustados por Holm (1979); NaN fica de fora e continua NaN."""
    p = np.asarray(p, dtype=float)
    ajust = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    m = len(pv)
    if m == 0:
        return ajust
    ordem = np.argsort(pv)
    passo = np.maximum.accumulate((m - np.arange(m)) * pv[ordem])
    res = np.empty(m)
    res[ordem] = np.minimum(passo, 1.0)
    ajust[ok] = res
    return ajust


def magnitude(valor, cortes=CORTES_COHEN_R) -> str | None:
    if valor is None or np.isnan(valor):
        return None
    v = abs(valor)
    if cortes is CORTES_OR and v < 1:
        v = 1 / v if v > 0 else np.inf
    rotulos = ("desprezível", "pequeno", "médio", "grande")
    return rotulos[int(np.searchsorted(cortes, v, side="right"))]


def _qui2_de_contagens(sim_por_grupo, n_grupo, n_sim, n):
    """Qui-quadrado de Pearson de uma tabela grupo × {Sim, Não}, vetorizado na
    primeira dimensão de `sim_por_grupo` (permutações)."""
    e_sim = n_grupo * n_sim / n
    e_nao = n_grupo * (n - n_sim) / n
    nao = n_grupo - sim_por_grupo
    return (((sim_por_grupo - e_sim) ** 2 / e_sim).sum(axis=-1)
            + ((nao - e_nao) ** 2 / e_nao).sum(axis=-1))


def qui2_grupo_voto(grupo: pd.Series, voto: pd.Series) -> dict:
    """Independência grupo × voto (Sim/Não) numa tabela r×2.

    Se a menor frequência esperada for < FREQ_ESPERADA_MIN, o p-valor reportado
    é o de permutação de Monte Carlo (D18.4): os votos são embaralhados entre
    os deputados, mantendo as margens, e o p-valor é (b + 1) / (B + 1). Cada
    teste usa um gerador novo com a SEMENTE (D18.8), para que o p-valor não
    dependa da ordem em que os testes rodam e a robustez seja pareada.
    Efeito: V de Cramér (com 2 colunas, gl* = 1).
    """
    codigos, niveis = pd.factorize(grupo, sort=True)
    y = (voto.to_numpy() == "Sim").astype(np.int8)
    n, r = len(y), len(niveis)
    n_grupo = np.bincount(codigos, minlength=r).astype(float)
    sim = np.bincount(codigos, weights=y, minlength=r)
    n_sim = y.sum()
    base = {"n": n, "n_grupos": r, "n_sim": int(n_sim), "n_nao": int(n - n_sim)}
    if r < 2 or n_sim in (0, n):
        return base | {"metodo": "não testável (um só grupo ou voto unânime)"}
    chi2 = float(_qui2_de_contagens(sim, n_grupo, n_sim, n))
    gl = r - 1
    menor_esp = float(min((n_grupo * n_sim / n).min(), (n_grupo * (n - n_sim) / n).min()))
    p_assint = float(stats.chi2.sf(chi2, gl))
    if menor_esp < config.FREQ_ESPERADA_MIN:
        rng = np.random.default_rng(config.SEMENTE)
        perms = rng.permuted(np.broadcast_to(y, (config.N_PERMUTACOES, n)), axis=1)
        um_hot = np.zeros((n, r))
        um_hot[np.arange(n), codigos] = 1
        chi2_perm = _qui2_de_contagens(perms @ um_hot, n_grupo, n_sim, n)
        b = int((chi2_perm >= chi2 - 1e-9).sum())
        p, metodo = (b + 1) / (config.N_PERMUTACOES + 1), "permutação Monte Carlo"
    else:
        p, metodo = p_assint, "qui-quadrado"
    v = np.sqrt(chi2 / n)  # min(r, 2) − 1 = 1
    return base | {"estatistica": chi2, "gl": gl, "menor_esperado": menor_esp,
                   "p_assintotico": p_assint, "metodo": metodo, "p_valor": p,
                   "efeito": "V de Cramér", "valor_efeito": v,
                   "magnitude": magnitude(v)}


def ic_spearman(rho, n):
    """IC de ρ pela transformação de Fisher com o erro-padrão de Bonett e
    Wright (2000), indicado para Spearman: sqrt((1 + ρ²/2) / (n − 3))."""
    if n < 4 or np.isnan(rho) or abs(rho) >= 1:
        return np.nan, np.nan
    z = np.arctanh(rho)
    ep = np.sqrt((1 + rho**2 / 2) / (n - 3))
    return np.tanh(z - Z * ep), np.tanh(z + Z * ep)


def _aplicar_holm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["p_holm"] = holm(df["p_valor"]) if "p_valor" in df else np.nan
    df["significativo"] = df["p_holm"] < config.ALPHA
    return df


# ===========================================================================
# Leitura
# ===========================================================================
def carregar():
    votos = pd.read_csv(DADOS / "votos.csv")
    rice = pd.read_csv(DADOS / "coesao_rice.csv")
    base = pd.read_csv(DADOS / "base_deputado_legislatura.csv")
    base["no_quadrante_interesse"] = base["no_quadrante_interesse"].astype("boolean")
    espectro = pd.read_csv(config.ESPECTRO_CSV)
    meta = pd.DataFrame(config.VOTACOES)[["chave", "nome", "data", "legislatura",
                                          "direcao_pro_pauta"]]
    ordem = {v["chave"]: i for i, v in enumerate(sorted(config.VOTACOES, key=lambda v: v["data"]))}
    return votos, rice, base, espectro, meta, ordem


def _validos(votos: pd.DataFrame) -> pd.DataFrame:
    return votos[votos["voto_valido"].isin(VOTOS_VALIDOS)].copy()


def _com_pop_d3(validos: pd.DataFrame, base: pd.DataFrame, colunas) -> tuple[pd.DataFrame, int]:
    """Votos válidos de quem está na população do D3 (≥ 12 meses e com gasto);
    devolve também quantos votos válidos ficaram de fora."""
    pop = base[base["no_quadrante_interesse"].notna()]
    df = validos.merge(pop[["id_deputado", "legislatura", *colunas]],
                       on=["id_deputado", "legislatura"], how="inner")
    return df, len(validos) - len(df)


# ===========================================================================
# Descritivas
# ===========================================================================
def resumo_populacao(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for leg, g in base.groupby("legislatura"):
        pop = g[g["na_populacao"]]
        linhas.append({
            "legislatura": leg,
            "deputados_com_exercicio": len(g),
            "excluidos_menos_12_meses": int((~g["na_populacao"]).sum()),
            "na_populacao_d3": len(pop),
            "faixa_A": int((pop["faixa"] == "A").sum()),
            "faixa_B": int((pop["faixa"] == "B").sum()),
            "faixa_C": int((pop["faixa"] == "C").sum()),
            "sem_gasto_ceap": int(pop["gasto_relativo"].isna().sum()),
            "no_quadrante_interesse": int(g["no_quadrante_interesse"].sum()),
            "casos_extremos": int(g["caso_extremo"].astype("boolean").sum()),
        })
    return pd.DataFrame(linhas)


def resumo_votacoes(votos, base, meta, ordem) -> pd.DataFrame:
    pop = base.loc[base["no_quadrante_interesse"].notna(), ["id_deputado", "legislatura"]]
    pop = set(map(tuple, pop.to_numpy()))
    linhas = []
    for chave, g in votos.groupby("chave_votacao"):
        val = g[g["voto_valido"].isin(VOTOS_VALIDOS)]
        na_pop = [(i, l) in pop for i, l in zip(val["id_deputado"], val["legislatura"])]
        linhas.append({
            "chave_votacao": chave, "votacao": g["votacao"].iat[0],
            "legislatura": g["legislatura"].iat[0],
            "registros": len(g), "sim": int((val["voto_valido"] == "Sim").sum()),
            "nao": int((val["voto_valido"] == "Não").sum()),
            "abstencao": int((g["voto_original"] == "Abstenção").sum()),
            "ausente": int((g["voto_original"] == config.CATEGORIA_AUSENCIA).sum()),
            "validos_sem_partido": int((val["partido"].isin(config.SEM_PARTIDO)).sum()),
            "validos_na_pop_d3": int(sum(na_pop)),
            "validos_fora_pop_d3": int(len(val) - sum(na_pop)),
        })
    df = pd.DataFrame(linhas).merge(meta.rename(columns={"chave": "chave_votacao"})[
        ["chave_votacao", "data", "direcao_pro_pauta"]], on="chave_votacao")
    return df.sort_values("chave_votacao", key=lambda s: s.map(ordem)).reset_index(drop=True)


def tabulacao_partido_voto(votos, ordem) -> pd.DataFrame:
    tab = (pd.crosstab([votos["chave_votacao"], votos["legislatura"], votos["partido"]],
                       votos["voto_original"]).reset_index())
    tab.columns.name = None
    return tab.sort_values(["chave_votacao", "partido"],
                           key=lambda s: s.map(ordem) if s.name == "chave_votacao" else s)


def _evento_pro(validos: pd.DataFrame) -> pd.Series:
    """True quando o voto é pró-pauta (D6); nos Precatórios (direção ambígua),
    True quando é Sim, para as análises por votação."""
    return validos["pro_pauta"].where(validos["direcao_pro_pauta"].notna(),
                                      validos["voto_valido"] == "Sim").astype(bool)


def pro_pauta_partido_votacao(validos, ordem) -> pd.DataFrame:
    df = validos.assign(evento=_evento_pro(validos))
    g = (df.groupby(["chave_votacao", "votacao", "legislatura", "partido", "espectro"], dropna=False)
         .agg(validos=("evento", "size"), n_evento=("evento", "sum")).reset_index())
    g["medida"] = np.where(g["chave_votacao"].isin(_chaves_sem_direcao()), "% Sim", "% pró-pauta")
    g["pct"] = g["n_evento"] / g["validos"] * 100
    lo, hi = wilson(g["n_evento"], g["validos"])
    g["ic_inf"], g["ic_sup"] = lo * 100, hi * 100
    g["n_menor_5"] = g["validos"] < config.RICE_MIN_VOTOS_VALIDOS
    return g.sort_values(["chave_votacao", "partido"],
                         key=lambda s: s.map(ordem) if s.name == "chave_votacao" else s)


def _chaves_sem_direcao():
    return {v["chave"] for v in config.VOTACOES if v["direcao_pro_pauta"] is None}


def indice_pro_pauta(validos) -> tuple[pd.DataFrame, pd.DataFrame]:
    """D6: índice = votos pró-pauta / votos válidos nas votações com direção
    definida (Precatórios fora). Por deputado × legislatura e, somando os votos,
    por espectro e por família × legislatura (D8-ii: família só no temporal)."""
    df = validos[validos["direcao_pro_pauta"].notna()].copy()
    df["pro_pauta"] = df["pro_pauta"].astype(bool)
    dep = (df.groupby(["id_deputado", "legislatura"])
           .agg(nome=("nome", "first"), uf=("uf", "first"),
                partido_ultimo_voto=("partido", "last"), espectro=("espectro", "last"),
                validos=("pro_pauta", "size"), n_pro=("pro_pauta", "sum")).reset_index())
    dep["indice_pro_pauta"] = dep["n_pro"] / dep["validos"] * 100
    linhas = []
    for nivel in ("espectro", "familia"):
        g = (df.groupby(["legislatura", nivel]).agg(validos=("pro_pauta", "size"),
                                                    n_pro=("pro_pauta", "sum"),
                                                    n_votacoes=("chave_votacao", "nunique"),
                                                    deputados=("id_deputado", "nunique"))
             .reset_index().rename(columns={nivel: "grupo"}))
        g.insert(1, "nivel", nivel)
        linhas.append(g)
    grp = pd.concat(linhas, ignore_index=True)
    grp["indice_pro_pauta"] = grp["n_pro"] / grp["validos"] * 100
    lo, hi = wilson(grp["n_pro"], grp["validos"])
    grp["ic_inf"], grp["ic_sup"] = lo * 100, hi * 100
    return dep, grp


# ===========================================================================
# D10 — Rice agregado e correção de Desposato
# ===========================================================================
def rice_agregado(rice: pd.DataFrame) -> pd.DataFrame:
    r = rice[rice["rice"].notna() & ~rice["partido"].isin(config.SEM_PARTIDO)]
    partes = []
    for nivel, chaves in (("votacao", ["chave_votacao", "legislatura"]),
                          ("legislatura", ["legislatura"]),
                          ("partido_legislatura", ["legislatura", "partido"])):
        g = (r.groupby(chaves)
             .apply(lambda x: pd.Series({
                 "rice_ponderado": np.average(x["rice"], weights=x["validos"]),
                 "validos": x["validos"].sum(), "n_pares": len(x)}), include_groups=False)
             .reset_index())
        g.insert(0, "nivel", nivel)
        partes.append(g)
    return pd.concat(partes, ignore_index=True)


def _rice_esperado_subamostra(sim: int, validos: int, k: int) -> float:
    """E[Rice] numa subamostra de k deputados sorteados sem reposição do
    partido (hipergeométrica). É a correção de Desposato (2005) por
    reamostragem até o tamanho do menor grupo, calculada de forma exata."""
    x = np.arange(max(0, k - (validos - sim)), min(k, sim) + 1)
    pmf = stats.hypergeom.pmf(x, validos, sim, k)
    return float((pmf * np.abs(2 * x - k) / k).sum() * 100)


def rice_desposato(rice: pd.DataFrame, ordem_vot: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    k = config.RICE_MIN_VOTOS_VALIDOS
    r = rice[rice["rice"].notna() & ~rice["partido"].isin(config.SEM_PARTIDO)].copy()
    r["rice_desposato"] = [_rice_esperado_subamostra(int(s), int(v), k)
                           for s, v in zip(r["sim"], r["validos"])]
    r["posto_bruto"] = r.groupby("chave_votacao")["rice"].rank(ascending=False)
    r["posto_desposato"] = r.groupby("chave_votacao")["rice_desposato"].rank(ascending=False)
    ordem = []
    for chave, g in sorted(r.groupby("chave_votacao"), key=lambda t: ordem_vot[t[0]]):
        tau = stats.kendalltau(g["rice"], g["rice_desposato"]).statistic if len(g) > 1 else np.nan
        mudou = (g["posto_bruto"] != g["posto_desposato"]).sum()
        ordem.append({"chave_votacao": chave, "n_partidos": len(g), "tau_kendall": tau,
                      "partidos_que_mudam_de_posto": int(mudou),
                      "maior_salto_de_posto": float((g["posto_bruto"] - g["posto_desposato"]).abs().max())})
    cols = ["chave_votacao", "legislatura", "partido", "sim", "nao", "validos", "rice",
            "rice_desposato", "posto_bruto", "posto_desposato"]
    return r[cols], pd.DataFrame(ordem)


# ===========================================================================
# D11 — Fidelidade à orientação e alinhamento ao Governo
# ===========================================================================
def _taxa(df: pd.DataFrame, chaves, coluna: str) -> pd.DataFrame:
    d = df[df[coluna].notna()]
    g = (d.groupby(chaves, dropna=False)[coluna]
         .agg(n="size", k=lambda s: s.astype(bool).sum()).reset_index())
    g["taxa"] = g["k"] / g["n"] * 100
    lo, hi = wilson(g["k"], g["n"])
    g["ic_inf"], g["ic_sup"] = lo * 100, hi * 100
    return g


def fidelidade(validos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Por deputado × legislatura e por partido/espectro × legislatura.

    `fonte`: "todas" (orientação do partido ou herdada do bloco), "partido"
    (só orientação própria; robustez) e "bloco" (só herdada). Alinhamento ao
    Governo não depende da fonte e aparece só em "todas".
    """
    recortes = {"todas": validos,
                "partido": validos[validos["fonte_orientacao"] == "partido"],
                "bloco": validos[validos["fonte_orientacao"] == "bloco"]}
    dep, grp = [], []
    for fonte, d in recortes.items():
        f = _taxa(d, ["id_deputado", "legislatura"], "fiel_partido").assign(medida="fidelidade_partido")
        dep.append(f.assign(fonte=fonte))
        for nivel in ("partido", "espectro"):
            g = _taxa(d, ["legislatura", nivel], "fiel_partido").rename(columns={nivel: "grupo"})
            grp.append(g.assign(nivel=nivel, medida="fidelidade_partido", fonte=fonte))
    dep.append(_taxa(validos, ["id_deputado", "legislatura"], "alinhado_governo")
               .assign(medida="alinhamento_governo", fonte="todas"))
    for nivel in ("partido", "espectro"):
        g = _taxa(validos, ["legislatura", nivel], "alinhado_governo").rename(columns={nivel: "grupo"})
        grp.append(g.assign(nivel=nivel, medida="alinhamento_governo", fonte="todas"))
    nomes = validos.groupby(["id_deputado", "legislatura"]).agg(
        nome=("nome", "first"), partido_ultimo_voto=("partido", "last")).reset_index()
    dep = pd.concat(dep, ignore_index=True).merge(nomes, on=["id_deputado", "legislatura"])
    dep = dep[["id_deputado", "legislatura", "nome", "partido_ultimo_voto", "medida", "fonte",
               "n", "k", "taxa", "ic_inf", "ic_sup"]]
    grp = pd.concat(grp, ignore_index=True)[["legislatura", "nivel", "grupo", "medida", "fonte",
                                             "n", "k", "taxa", "ic_inf", "ic_sup"]]
    return dep, grp


# ===========================================================================
# D16 — Composição do quadrante de interesse
# ===========================================================================
def composicao_quadrante(base: pd.DataFrame) -> pd.DataFrame:
    pop = base[base["no_quadrante_interesse"].notna()].copy()
    pop["q"] = pop["no_quadrante_interesse"].astype(bool)
    partes = []
    for nivel in ("partido", "espectro"):
        g = (pop.groupby(["legislatura", nivel])["q"].agg(n_amostra="size", n_quadrante="sum")
             .reset_index().rename(columns={nivel: "grupo"}))
        tot = g.groupby("legislatura")[["n_amostra", "n_quadrante"]].transform("sum")
        g["pct_da_amostra"] = g["n_amostra"] / tot["n_amostra"] * 100
        g["pct_do_quadrante"] = g["n_quadrante"] / tot["n_quadrante"] * 100
        g["pct_no_quadrante"] = g["n_quadrante"] / g["n_amostra"] * 100
        lo, hi = wilson(g["n_quadrante"], g["n_amostra"])
        g["ic_inf"], g["ic_sup"] = lo * 100, hi * 100
        g.insert(1, "nivel", nivel)
        partes.append(g)
    return pd.concat(partes, ignore_index=True)


# ===========================================================================
# Testes (D18)
# ===========================================================================
def f1_partido_voto(validos, ordem) -> pd.DataFrame:
    """F1: partido (vigente na data) × voto, só partidos com ≥ 5 válidos e sem
    S.PART. (D18.5, mesmo filtro do D10)."""
    linhas = []
    for chave in sorted(validos["chave_votacao"].unique(), key=ordem.get):
        g = validos[(validos["chave_votacao"] == chave) & ~validos["partido"].isin(config.SEM_PARTIDO)]
        n_part = g["partido"].map(g["partido"].value_counts())
        ok = g[n_part >= config.RICE_MIN_VOTOS_VALIDOS]
        res = qui2_grupo_voto(ok["partido"], ok["voto_valido"])
        linhas.append({"familia": "F1", "chave_votacao": chave,
                       "votos_excluidos_n_menor_5": len(g) - len(ok)} | res)
    return _aplicar_holm(pd.DataFrame(linhas))


def f2_espectro_voto(validos, ordem, familia="F2") -> pd.DataFrame:
    linhas = []
    for chave in sorted(validos["chave_votacao"].unique(), key=ordem.get):
        g = validos[(validos["chave_votacao"] == chave)]
        ok = g[g["espectro"].notna()]
        res = qui2_grupo_voto(ok["espectro"], ok["voto_valido"])
        pct = ok.groupby("espectro")["voto_valido"].apply(lambda s: (s == "Sim").mean() * 100)
        linhas.append({"familia": familia, "chave_votacao": chave,
                       "votos_sem_espectro": len(g) - len(ok)} | res
                      | {f"pct_sim_{e}": pct.get(e, np.nan) for e in config.ESPECTROS})
    return _aplicar_holm(pd.DataFrame(linhas))


def f3_spearman(base, metricas=("prod_bruta_mensal", "prod_qualificada"), familia="F3") -> pd.DataFrame:
    """F3: gasto relativo × produtividade dentro de legislatura × faixa (D3)."""
    pop = base[base["no_quadrante_interesse"].notna()]
    linhas = []
    for (leg, faixa), g in pop.groupby(["legislatura", "faixa"]):
        for m in metricas:
            gg = g.dropna(subset=["gasto_relativo", m])
            n = len(gg)
            res = stats.spearmanr(gg["gasto_relativo"], gg[m]) if n >= 3 else None
            rho = float(res.statistic) if res is not None else np.nan
            lo, hi = ic_spearman(rho, n)
            linhas.append({"familia": familia, "legislatura": leg, "faixa": faixa,
                           "produtividade": m, "n": n,
                           "prop_zeros_produtividade": float((gg[m] == 0).mean()) if n else np.nan,
                           "estatistica": rho, "ic_inf": lo, "ic_sup": hi,
                           "p_valor": float(res.pvalue) if res is not None else np.nan,
                           "metodo": "Spearman", "efeito": "ρ", "valor_efeito": rho,
                           "magnitude": magnitude(rho)})
    return _aplicar_holm(pd.DataFrame(linhas))


def f4_produtividade_voto(validos, base, ordem) -> tuple[pd.DataFrame, int]:
    """F4: produtividade bruta mensal de quem votou Sim × quem votou Não, só
    com a população do D3. rank-bisserial > 0 ⇒ Sim tem produtividade maior;
    `rb_pro_pauta` reorienta para pró-pauta (> 0 ⇒ pró-pauta maior)."""
    df, fora = _com_pop_d3(validos, base, ["prod_bruta_mensal"])
    direcao = {v["chave"]: v["direcao_pro_pauta"] for v in config.VOTACOES}
    linhas = []
    for chave in sorted(df["chave_votacao"].unique(), key=ordem.get):
        g = df[df["chave_votacao"] == chave]
        x = g.loc[g["voto_valido"] == "Sim", "prod_bruta_mensal"]
        y = g.loc[g["voto_valido"] == "Não", "prod_bruta_mensal"]
        u = stats.mannwhitneyu(x, y, alternative="two-sided")
        rb = 2 * u.statistic / (len(x) * len(y)) - 1
        d = direcao[chave]
        rb_pro = rb if d == "Sim" else (-rb if d == "Não" else np.nan)
        linhas.append({"familia": "F4", "chave_votacao": chave, "n_sim": len(x), "n_nao": len(y),
                       "mediana_sim": x.median(), "mediana_nao": y.median(),
                       "direcao_pro_pauta": d, "estatistica": u.statistic,
                       "p_valor": u.pvalue, "metodo": "Mann-Whitney",
                       "efeito": "rank-bisserial (Sim − Não)", "valor_efeito": rb,
                       "rb_pro_pauta": rb_pro, "magnitude": magnitude(rb)})
    return _aplicar_holm(pd.DataFrame(linhas)), fora


def f5_quadrante_voto(validos, base, ordem) -> tuple[pd.DataFrame, int]:
    """F5: (no quadrante de interesse?) × (voto pró-pauta?) em 2×2, todos os
    deputados da votação num teste só (D16). Nos Precatórios, o evento é "Sim".
    Pearson sem correção de Yates; Fisher se o menor esperado < 5 (D18.3).
    Razão de chances condicional (a do Fisher), IC exato:
    OR > 1 ⇒ quem está no quadrante tem mais chance do evento."""
    df, fora = _com_pop_d3(validos, base, ["no_quadrante_interesse"])
    df["evento"] = _evento_pro(df)
    df["q"] = df["no_quadrante_interesse"].astype(bool)
    sem_dir = _chaves_sem_direcao()
    linhas = []
    for chave in sorted(df["chave_votacao"].unique(), key=ordem.get):
        g = df[df["chave_votacao"] == chave]
        tab = np.array([[((g.q) & (g.evento)).sum(), ((g.q) & (~g.evento)).sum()],
                        [((~g.q) & (g.evento)).sum(), ((~g.q) & (~g.evento)).sum()]])
        esperado = stats.contingency.expected_freq(tab)
        if esperado.min() < config.FREQ_ESPERADA_MIN:
            p, est, metodo = stats.fisher_exact(tab).pvalue, np.nan, "Fisher exato"
        else:
            c = stats.chi2_contingency(tab, correction=False)
            p, est, metodo = c.pvalue, c.statistic, "qui-quadrado"
        orr = odds_ratio(tab)
        ic = orr.confidence_interval(confidence_level=config.NIVEL_CONFIANCA)
        linhas.append({"familia": "F5", "chave_votacao": chave,
                       "evento": "Sim" if chave in sem_dir else "pró-pauta",
                       "n": int(tab.sum()), "n_quadrante": int(tab[0].sum()),
                       "pct_evento_quadrante": tab[0, 0] / tab[0].sum() * 100,
                       "pct_evento_fora": tab[1, 0] / tab[1].sum() * 100,
                       "menor_esperado": esperado.min(), "estatistica": est, "metodo": metodo,
                       "p_valor": p, "efeito": "razão de chances", "valor_efeito": orr.statistic,
                       "ic_inf": ic.low, "ic_sup": ic.high,
                       "magnitude": magnitude(orr.statistic, CORTES_OR)})
    return _aplicar_holm(pd.DataFrame(linhas)), fora


def resumo_testes(*familias: pd.DataFrame) -> pd.DataFrame:
    cols = ["familia", "chave_votacao", "legislatura", "faixa", "produtividade", "n", "metodo",
            "estatistica", "p_valor", "p_holm", "significativo", "efeito", "valor_efeito",
            "ic_inf", "ic_sup", "magnitude"]
    return pd.concat([f.reindex(columns=cols) for f in familias], ignore_index=True)


# ===========================================================================
# Robustez
# ===========================================================================
def robustez(validos, base, espectro_ref, f2, f3, ordem, fid_grp) -> pd.DataFrame:
    """Compara cada teste principal com a sua versão de robustez."""
    linhas = []
    # (1) F2 sem os partidos classificados manualmente (D9)
    manuais = set(espectro_ref.loc[espectro_ref["metodo"] == "manual", "partido_id"])
    v2 = validos.copy()
    v2.loc[v2["partido_id"].isin(manuais), "espectro"] = np.nan
    f2r = f2_espectro_voto(v2, ordem, familia="F2-sem-manuais")
    afetados = validos[validos["partido_id"].isin(manuais)].groupby("chave_votacao").size()
    for (_, a), (_, b) in zip(f2.iterrows(), f2r.iterrows()):
        linhas.append({"teste": "F2 sem classificação manual", "recorte": a["chave_votacao"],
                       "efeito_principal": a["valor_efeito"], "efeito_robustez": b["valor_efeito"],
                       "p_holm_principal": a["p_holm"], "p_holm_robustez": b["p_holm"],
                       "conclusao_mantida": a["significativo"] == b["significativo"],
                       "n_afetados": int(afetados.get(a["chave_votacao"], 0))})
    # (2) F3 com "só Norma Jurídica" no lugar de "aprovada na Câmara" (D14)
    f3r = f3_spearman(base, metricas=("prod_bruta_mensal", "prod_qualificada_norma"),
                      familia="F3-norma")
    a = f3[f3["produtividade"] == "prod_qualificada"].reset_index(drop=True)
    b = f3r[f3r["produtividade"] == "prod_qualificada_norma"].reset_index(drop=True)
    for i in range(len(a)):
        linhas.append({"teste": "F3 qualificada só Norma Jurídica",
                       "recorte": f"leg {a.at[i, 'legislatura']} faixa {a.at[i, 'faixa']}",
                       "efeito_principal": a.at[i, "valor_efeito"], "efeito_robustez": b.at[i, "valor_efeito"],
                       "p_holm_principal": a.at[i, "p_holm"], "p_holm_robustez": b.at[i, "p_holm"],
                       "conclusao_mantida": a.at[i, "significativo"] == b.at[i, "significativo"]})
    # (3) Fidelidade por partido só com orientação própria (D11)
    fp = fid_grp[(fid_grp["nivel"] == "partido") & (fid_grp["medida"] == "fidelidade_partido")]
    todas = fp[fp["fonte"] == "todas"].set_index(["legislatura", "grupo"])
    propria = fp[fp["fonte"] == "partido"].set_index(["legislatura", "grupo"])
    for (leg, part), row in todas.iterrows():
        alt = propria.loc[(leg, part)] if (leg, part) in propria.index else None
        linhas.append({"teste": "Fidelidade só com orientação própria",
                       "recorte": f"leg {leg} {part}",
                       "efeito_principal": row["taxa"],
                       "efeito_robustez": alt["taxa"] if alt is not None else np.nan,
                       "n_principal": row["n"], "n_robustez": alt["n"] if alt is not None else 0})
    return pd.DataFrame(linhas)


# ===========================================================================
# Execução
# ===========================================================================
def _gravar(df: pd.DataFrame, nome: str) -> None:
    df.to_csv(OUT / nome, index=False)


def _imprimir(titulo, df, cols):
    print(f"\n== {titulo}")
    print(df[cols].to_string(index=False, float_format=lambda x: f"{x:.3g}"))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    votos, rice, base, espectro_ref, meta, ordem = carregar()
    validos = _validos(votos)

    pop = resumo_populacao(base)
    _gravar(pop, "populacao_resumo.csv")
    _gravar(resumo_votacoes(votos, base, meta, ordem), "votacao_resumo.csv")
    _gravar(tabulacao_partido_voto(votos, ordem), "tabulacao_partido_voto.csv")
    _gravar(pro_pauta_partido_votacao(validos, ordem), "pro_pauta_partido_votacao.csv")
    dep, grp = indice_pro_pauta(validos)
    _gravar(dep, "indice_pro_pauta_deputado.csv")
    _gravar(grp, "pro_pauta_grupo_legislatura.csv")
    _gravar(rice_agregado(rice), "rice_agregado.csv")
    rd, rd_ordem = rice_desposato(rice, ordem)
    _gravar(rd, "rice_desposato.csv")
    _gravar(rd_ordem, "rice_desposato_ordem.csv")
    fid_dep, fid_grp = fidelidade(validos)
    _gravar(fid_dep, "fidelidade_deputado.csv")
    _gravar(fid_grp, "fidelidade_grupo.csv")
    _gravar(composicao_quadrante(base), "composicao_quadrante.csv")

    f1 = f1_partido_voto(validos, ordem)
    f2 = f2_espectro_voto(validos, ordem)
    f3 = f3_spearman(base)
    f4, fora4 = f4_produtividade_voto(validos, base, ordem)
    f5, fora5 = f5_quadrante_voto(validos, base, ordem)
    for df, nome in ((f1, "f1_partido_voto"), (f2, "f2_espectro_voto"), (f3, "f3_spearman"),
                     (f4, "f4_produtividade_voto"), (f5, "f5_quadrante_voto")):
        _gravar(df, f"{nome}.csv")
    _gravar(resumo_testes(f1, f2, f3, f4, f5), "testes_resumo.csv")
    _gravar(robustez(validos, base, espectro_ref, f2, f3, ordem, fid_grp), "robustez.csv")

    _imprimir("População (D3)", pop, list(pop.columns))
    cols_q = ["chave_votacao", "n", "n_grupos", "metodo", "p_valor", "p_holm", "valor_efeito", "magnitude"]
    _imprimir("F1 partido × voto", f1, cols_q)
    _imprimir("F2 espectro × voto", f2, cols_q)
    _imprimir("F3 Spearman gasto × produtividade", f3,
              ["legislatura", "faixa", "produtividade", "n", "estatistica", "ic_inf", "ic_sup", "p_holm"])
    _imprimir(f"F4 produtividade × voto ({fora4} votos válidos fora da população do D3)", f4,
              ["chave_votacao", "n_sim", "n_nao", "mediana_sim", "mediana_nao", "p_holm", "rb_pro_pauta"])
    _imprimir(f"F5 quadrante × voto ({fora5} votos válidos fora da população do D3)", f5,
              ["chave_votacao", "n", "pct_evento_quadrante", "pct_evento_fora", "metodo",
               "p_holm", "valor_efeito", "ic_inf", "ic_sup"])
    _imprimir("Desposato: a ordem dos partidos muda?", rd_ordem, list(rd_ordem.columns))
    print("\nResultados gravados em", OUT)
