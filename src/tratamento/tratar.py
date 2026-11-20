"""Etapa 2: tratamento e junção das bases.

    python -m src.tratamento.tratar

Lê data/raw e data/referencia e grava em data/processed: exercicio, votos,
coesao_rice, produtividade, gasto_ceap e base_deputado_legislatura. No fim,
roda verificações de consistência e para com erro se alguma falhar.
"""
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src import config
from src.extracao import camara_api as api

OUT = config.DATA_PROCESSED


# --- Tabelas de referência -----------------------------------------------------
def carregar_referencias():
    ler = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)
    partidos = ler(config.PARTIDOS_CSV).set_index("sigla_api")
    espectro = ler(config.ESPECTRO_CSV).set_index("partido_id")
    espectro["espectro"] = espectro["categoria_artigo"].map(config.MAPA_ESPECTRO)
    blocos = ler(config.BLOCOS_CSV)
    tetos = pd.read_csv(config.TETOS_CEAP_CSV, parse_dates=["vigencia_inicio", "vigencia_fim"])
    return partidos, espectro, blocos, tetos


def harmonizar_partido(sigla_api: str, partidos: pd.DataFrame, espectro: pd.DataFrame) -> dict:
    """Rótulo, identidade, família e espectro de uma sigla da API."""
    s = sigla_api if sigla_api in partidos.index else re.sub(config.SUFIXO_ESPURIO, "", sigla_api)
    if s not in partidos.index:
        raise KeyError(f"sigla sem linha em partidos.csv: {sigla_api!r}")
    p = partidos.loc[s]
    pid = p["partido_id"] or None
    return {"partido": p["sigla"], "partido_id": pid, "familia": p["familia"] or None,
            "espectro": espectro.loc[pid, "espectro"] if pid else None}


# --- Exercício: estado diário a partir do histórico ----------------------------
def _deputados_por_legislatura() -> dict[int, list[dict]]:
    return {leg: api.get_paginado("deputados", {"idLegislatura": leg}) for leg in config.LEGISLATURAS}


def _historico(id_dep: int, leg: int) -> pd.DataFrame:
    """Histórico do deputado na legislatura, ordenado."""
    hist = pd.DataFrame(api.get(f"deputados/{id_dep}/historico")["dados"])
    hist = hist[(hist["idLegislatura"] == leg) & hist["situacao"].notna()].copy()
    if hist.empty:
        return hist
    hist.loc[hist["descricaoStatus"].str.contains("Efetivação", na=False), "situacao"] = config.SITUACAO_EXERCICIO
    # Unidade fixa: o merge_asof de estado_diario exige a mesma resolução.
    momento = pd.to_datetime(hist["dataHora"]).dt.as_unit("ns")
    return hist.assign(momento=momento).sort_values("momento", kind="stable")


def em_exercicio_no_momento(leg: int, momento: pd.Timestamp) -> pd.DataFrame:
    """Deputados em exercício num instante exato, com partido e UF daquele instante."""
    linhas = []
    for id_dep in sorted({d["id"] for d in api.get_paginado("deputados", {"idLegislatura": leg})}):
        hist = _historico(id_dep, leg)
        antes = hist[hist["momento"] <= momento] if not hist.empty else hist
        if not antes.empty and antes["situacao"].iat[-1] == config.SITUACAO_EXERCICIO:
            linhas.append({"id_deputado": id_dep, "siglaPartido": antes["siglaPartido"].iat[-1],
                           "siglaUf": antes["siglaUf"].iat[-1]})
    return pd.DataFrame(linhas)


def estado_diario(partidos, espectro) -> pd.DataFrame:
    """Uma linha por deputado × legislatura × dia, com situação e partido no fim do dia.
    O dia conta como de exercício se o deputado esteve em exercício em algum momento dele."""
    linhas = []
    for leg, deps in _deputados_por_legislatura().items():
        ini, fim = config.LEGISLATURAS[leg][0], config.fim_efetivo(leg)
        dias = pd.DataFrame({"dia": pd.date_range(ini, fim, freq="D", unit="ns")})
        dias["fim_do_dia"] = dias["dia"] + pd.Timedelta(hours=23, minutes=59, seconds=59)
        for id_dep in sorted({d["id"] for d in deps}):
            hist = _historico(id_dep, leg)
            if hist.empty:
                continue
            campos = ["momento", "situacao", "siglaPartido", "siglaUf"]
            d = pd.merge_asof(dias, hist[campos], left_on="fim_do_dia", right_on="momento", direction="backward")
            inicio = pd.merge_asof(dias, hist[["momento", "situacao"]], left_on="dia", right_on="momento",
                                   direction="backward")["situacao"]
            dias_com_registro_ex = set(hist.loc[hist["situacao"] == config.SITUACAO_EXERCICIO, "momento"].dt.normalize())
            d["em_exercicio"] = ((d["situacao"] == config.SITUACAO_EXERCICIO)
                                 | (inicio == config.SITUACAO_EXERCICIO)
                                 | d["dia"].isin(dias_com_registro_ex))
            d = d[d["situacao"].notna()]
            linhas.append(d.assign(id_deputado=id_dep, legislatura=leg)[
                ["id_deputado", "legislatura", "dia", "situacao", "siglaPartido", "siglaUf", "em_exercicio"]])
    diario = pd.concat(linhas, ignore_index=True)
    siglas = {s: harmonizar_partido(s, partidos, espectro) for s in diario["siglaPartido"].dropna().unique()}
    diario["partido_id"] = diario["siglaPartido"].map(lambda s: siglas[s]["partido_id"] if s in siglas else None)
    return diario


def tratar_exercicio(diario, partidos, espectro) -> pd.DataFrame:
    deps = _deputados_por_legislatura()
    nomes = {(leg, d["id"]): d["nome"] for leg, ds in deps.items() for d in ds}
    mulheres = {(leg, d["id"]) for leg in config.LEGISLATURAS
                for d in api.get_paginado("deputados", {"idLegislatura": leg, "siglaSexo": "F"})}
    ex = diario[diario["em_exercicio"]]
    base = (ex.groupby(["id_deputado", "legislatura"])
            .agg(inicio_exercicio=("dia", "min"), fim_exercicio=("dia", "max"),
                 dias_exercicio=("dia", "size"), uf=("siglaUf", lambda s: s.mode().iat[0]))
            .reset_index())
    base["meses_exercicio"] = (base["dias_exercicio"] / config.DIAS_POR_MES).round(2)
    base["faixa"] = base["meses_exercicio"].map(config.faixa_de_exercicio)
    base["na_populacao"] = base["meses_exercicio"] >= config.MESES_MINIMOS

    # Partido principal: o com mais dias de exercício (quem nunca teve fica S.PART.).
    dias_partido = ex.groupby(["id_deputado", "legislatura", "partido_id"]).size().rename("dias").reset_index()
    dias_partido = dias_partido.sort_values(["id_deputado", "legislatura", "dias"], ascending=[True, True, False])
    principal = dias_partido.drop_duplicates(["id_deputado", "legislatura"])
    n_partidos = dias_partido.groupby(["id_deputado", "legislatura"]).size().rename("n_partidos")
    base = base.merge(principal[["id_deputado", "legislatura", "partido_id"]], on=["id_deputado", "legislatura"],
                      how="left")
    base = base.merge(n_partidos, on=["id_deputado", "legislatura"], how="left")
    base["n_partidos"] = base["n_partidos"].fillna(0).astype(int)
    rot = (ex.merge(principal[["id_deputado", "legislatura", "partido_id"]])
           .groupby(["id_deputado", "legislatura"])["siglaPartido"].agg(lambda s: s.mode().iat[0]))
    base["partido"] = [harmonizar_partido(rot[(i, l)], partidos, espectro)["partido"] if (i, l) in rot.index
                       else config.SIGLA_SEM_PARTIDO
                       for i, l in zip(base["id_deputado"], base["legislatura"])]
    familia = partidos[partidos["partido_id"] != ""].drop_duplicates("partido_id").set_index("partido_id")["familia"]
    base["familia"] = base["partido_id"].map(familia)
    base["espectro"] = base["partido_id"].map(espectro["espectro"])
    base["nome"] = [nomes.get((l, i)) for i, l in zip(base["id_deputado"], base["legislatura"])]
    base["sexo"] = ["F" if (l, i) in mulheres else "M" for i, l in zip(base["id_deputado"], base["legislatura"])]
    for c in ("inicio_exercicio", "fim_exercicio"):
        base[c] = base[c].dt.date
    cols = ["id_deputado", "legislatura", "nome", "sexo", "uf", "partido", "partido_id", "familia", "espectro",
            "n_partidos", "inicio_exercicio", "fim_exercicio", "dias_exercicio", "meses_exercicio",
            "faixa", "na_populacao"]
    base = base[cols].sort_values(["legislatura", "nome"])
    base.to_csv(OUT / "exercicio.csv", index=False)
    return base


# --- Votos e coesão ------------------------------------------------------------
def _orientacoes(id_votacao, partidos, blocos) -> tuple[dict, str | None]:
    """partido_id → (orientação, fonte "partido"|"bloco") e a orientação do Governo."""
    composicao = {b["bloco_api"]: [s for s in b["partidos"].split(";") if s] for _, b in blocos.iterrows()}
    por_partido, por_bloco, governo = {}, {}, None
    for o in api.get(f"votacoes/{id_votacao}/orientacoes")["dados"]:
        nome, valor = o["siglaPartidoBloco"], config.MAPA_ORIENTACAO.get(o["orientacaoVoto"])
        if nome == config.ORIENTACAO_GOVERNO:
            governo = valor
        elif nome in config.ORIENTACOES_IGNORADAS:
            continue
        elif o["codTipoLideranca"] == config.LIDERANCA_PARTIDO:
            por_partido[partidos.loc[nome, "partido_id"]] = (valor, "partido")
        else:
            for s in composicao[nome]:
                por_bloco[partidos.loc[s, "partido_id"]] = (valor, "bloco")
    return {**por_bloco, **por_partido}, governo  # orientação própria prevalece


def tratar_votos(diario, exercicio, partidos, espectro, blocos) -> pd.DataFrame:
    info = exercicio.set_index(["id_deputado", "legislatura"])
    linhas, removidos_art17, orientacoes = [], 0, {}
    for v in config.VOTACOES:
        leg = v["legislatura"]
        votos = api.get(f"votacoes/{v['id_votacao']}/votos")["dados"]
        orientacoes[v["chave"]] = _orientacoes(v["id_votacao"], partidos, blocos)
        base = {"chave_votacao": v["chave"], "votacao": v["nome"], "id_votacao": v["id_votacao"],
                "data": v["data"], "legislatura": leg, "direcao_pro_pauta": v["direcao_pro_pauta"]}
        votaram = set()
        for x in votos:
            dep = x["deputado_"]
            votaram.add(dep["id"])
            if x["tipoVoto"] == config.CATEGORIA_PRESIDENTE:
                removidos_art17 += 1
                continue
            linhas.append({**base, "id_deputado": dep["id"], "sigla_api": dep["siglaPartido"],
                           "uf": dep["siglaUf"], "voto_original": x["tipoVoto"]})
        # Ausente: em exercício no instante da votação e sem voto registrado.
        momento = pd.Timestamp(api.get(f"votacoes/{v['id_votacao']}")["dados"]["dataHoraRegistro"])
        no_momento = em_exercicio_no_momento(leg, momento)
        for r in no_momento[~no_momento["id_deputado"].isin(votaram)].itertuples():
            linhas.append({**base, "id_deputado": r.id_deputado, "sigla_api": r.siglaPartido,
                           "uf": r.siglaUf, "voto_original": config.CATEGORIA_AUSENCIA})

    df = pd.DataFrame(linhas)
    harm = {s: harmonizar_partido(s, partidos, espectro) for s in df["sigla_api"].unique()}
    for campo in ("partido", "partido_id", "familia", "espectro"):
        df[campo] = df["sigla_api"].map(lambda s: harm[s][campo])
    df["nome"] = [info["nome"].get((i, l)) for i, l in zip(df["id_deputado"], df["legislatura"])]
    df["sexo"] = [info["sexo"].get((i, l)) for i, l in zip(df["id_deputado"], df["legislatura"])]
    df["voto_valido"] = df["voto_original"].map(config.MAPA_VOTO_VALIDO)
    tem_direcao = df["direcao_pro_pauta"].notna() & df["voto_valido"].notna()
    df["pro_pauta"] = pd.array(np.where(tem_direcao, df["voto_valido"] == df["direcao_pro_pauta"], pd.NA),
                               dtype="boolean")
    orient = [orientacoes[c][0].get(p, (None, None)) for c, p in zip(df["chave_votacao"], df["partido_id"])]
    df["orientacao_partido"] = [o[0] for o in orient]
    df["fonte_orientacao"] = [o[1] for o in orient]
    df["orientacao_governo"] = df["chave_votacao"].map(lambda c: orientacoes[c][1])
    for col_or, col_out in (("orientacao_partido", "fiel_partido"), ("orientacao_governo", "alinhado_governo")):
        ok = df[col_or].notna() & df["voto_valido"].notna()
        df[col_out] = pd.array(np.where(ok, df["voto_valido"] == df[col_or], pd.NA), dtype="boolean")
    df["na_populacao"] = [bool(info["na_populacao"].get((i, l), False))
                          for i, l in zip(df["id_deputado"], df["legislatura"])]
    cols = ["chave_votacao", "votacao", "id_votacao", "data", "legislatura", "id_deputado", "nome", "sexo", "uf",
            "partido", "partido_id", "familia", "espectro", "voto_original", "voto_valido",
            "direcao_pro_pauta", "pro_pauta", "orientacao_partido", "fonte_orientacao", "fiel_partido",
            "orientacao_governo", "alinhado_governo", "na_populacao"]
    df = df[cols].sort_values(["data", "partido", "nome"])
    df.to_csv(OUT / "votos.csv", index=False)
    print(f"  {removidos_art17} registros 'Artigo 17' (presidente da sessão) fora da população")
    return df


def tratar_rice(votos) -> pd.DataFrame:
    """Índice de Rice por partido × votação."""
    v = votos[votos["partido_id"].notna()]
    tab = (v.groupby(["chave_votacao", "votacao", "legislatura", "partido", "partido_id", "espectro"])
           .agg(sim=("voto_valido", lambda s: (s == "Sim").sum()),
                nao=("voto_valido", lambda s: (s == "Não").sum()),
                abstencao=("voto_original", lambda s: (s == "Abstenção").sum()),
                ausente=("voto_original", lambda s: (s == config.CATEGORIA_AUSENCIA).sum()),
                n_deputados=("id_deputado", "size"))
           .reset_index())
    tab["validos"] = tab["sim"] + tab["nao"]
    tab["rice"] = ((tab["sim"] - tab["nao"]).abs() / tab["validos"] * 100).where(
        tab["validos"] >= config.RICE_MIN_VOTOS_VALIDOS).round(2)
    tab.to_csv(OUT / "coesao_rice.csv", index=False)
    return tab


# --- Produtividade -------------------------------------------------------------
def tratar_produtividade(exercicio) -> pd.DataFrame:
    anos = range(config.ANO_INICIO, config.ANO_FIM + 1)
    props = pd.concat(pd.read_csv(config.DATA_RAW / "proposicoes" / f"proposicoes-{a}.csv", sep=";",
                                  encoding="utf-8-sig", low_memory=False,
                                  usecols=["id", "siglaTipo", "dataApresentacao", "ultimoStatus_descricaoSituacao"])
                      for a in anos).drop_duplicates("id")
    props = props[props["siglaTipo"].isin(config.TIPOS_NORMATIVOS)].copy()
    props["dataApresentacao"] = pd.to_datetime(props["dataApresentacao"], errors="coerce")
    props["legislatura"] = props["dataApresentacao"].map(lambda d: config.legislatura_da_data(d) if pd.notna(d) else None)
    props = props[props["legislatura"].notna()]
    sit = props["ultimoStatus_descricaoSituacao"].fillna("")
    props["com_situacao"] = ~sit.isin(config.SITUACOES_SEM_INFORMACAO)
    props["aprovada_camara"] = sit.isin(config.SITUACOES_APROVADA_CAMARA)
    props["norma"] = sit == config.SITUACAO_NORMA
    props["apensada"] = sit == config.SITUACAO_APENSADA
    props["decreto"] = props["siglaTipo"].isin(config.TIPOS_DECRETO)

    autores = pd.concat(pd.read_csv(config.DATA_RAW / "proposicoesAutores" / f"proposicoesAutores-{a}.csv", sep=";",
                                    encoding="utf-8-sig", low_memory=False,
                                    usecols=["idProposicao", "idDeputadoAutor", "ordemAssinatura", "proponente"])
                        for a in anos)
    primeiro = autores[(autores["ordemAssinatura"] == config.ORDEM_PRIMEIRO_AUTOR) & (autores["proponente"] == 1)
                       & autores["idDeputadoAutor"].notna()].drop_duplicates("idProposicao")
    df = props.merge(primeiro, left_on="id", right_on="idProposicao")
    df["id_deputado"] = df["idDeputadoAutor"].astype(int)
    df["legislatura"] = df["legislatura"].astype(int)
    agg = (df.groupby(["id_deputado", "legislatura"])
           .agg(n_normativas=("id", "size"), n_com_situacao=("com_situacao", "sum"),
                n_aprovada_camara=("aprovada_camara", "sum"), n_norma=("norma", "sum"),
                n_apensadas=("apensada", "sum"), n_decreto=("decreto", "sum"))
           .reset_index())
    prod = exercicio[["id_deputado", "legislatura", "meses_exercicio"]].merge(
        agg, on=["id_deputado", "legislatura"], how="left")
    contagens = ["n_normativas", "n_com_situacao", "n_aprovada_camara", "n_norma", "n_apensadas", "n_decreto"]
    prod[contagens] = prod[contagens].fillna(0).astype(int)
    prod["prod_bruta_mensal"] = (prod["n_normativas"] / prod["meses_exercicio"]).round(4)
    prod["prod_bruta_mensal_sem_pdl"] = ((prod["n_normativas"] - prod["n_decreto"]) / prod["meses_exercicio"]).round(4)
    prod["prod_qualificada"] = (prod["n_aprovada_camara"] / prod["n_com_situacao"]).where(prod["n_com_situacao"] > 0).round(4)
    prod["prod_qualificada_norma"] = (prod["n_norma"] / prod["n_com_situacao"]).where(prod["n_com_situacao"] > 0).round(4)
    prod = prod.drop(columns="meses_exercicio")
    prod.to_csv(OUT / "produtividade.csv", index=False)
    sem_deputado = len(df) - prod["n_normativas"].sum()
    print(f"  {len(df)} proposições normativas com deputado como primeiro autor; "
          f"{sem_deputado} de autores fora da tabela de exercício")
    return prod


# --- Gasto relativo da CEAP ----------------------------------------------------
def _teto_mensal(tetos: pd.DataFrame) -> pd.DataFrame:
    """Teto de cada UF × mês, ponderado pelos dias de cada vigência no mês."""
    dias = pd.DataFrame({"dia": pd.date_range(config.DATA_INICIO, config.DATA_CORTE, freq="D")})
    linhas = []
    for uf, t in tetos.groupby("uf"):
        fim = t["vigencia_fim"].fillna(pd.Timestamp(config.DATA_CORTE))
        valor = np.select([(dias["dia"] >= i) & (dias["dia"] <= f) for i, f in zip(t["vigencia_inicio"], fim)],
                          list(t["valor_mensal"]), default=np.nan)
        linhas.append(pd.DataFrame({"uf": uf, "dia": dias["dia"], "teto": valor}))
    d = pd.concat(linhas)
    d["ano"], d["mes"] = d["dia"].dt.year, d["dia"].dt.month
    return d.groupby(["uf", "ano", "mes"])["teto"].mean().rename("teto_mes").reset_index()


def tratar_gasto(diario, exercicio, tetos) -> pd.DataFrame:
    ult = config.CEAP_ULTIMA_COMPETENCIA
    competencia = lambda a, m: a * 100 + m
    lim, desde_api = competencia(*ult), competencia(*config.SIGEPA_API_DESDE)
    inicio = competencia(config.DATA_INICIO.year, config.DATA_INICIO.month)

    d = diario.assign(ano=diario["dia"].dt.year, mes=diario["dia"].dt.month)
    mensal = (d.groupby(["id_deputado", "legislatura", "ano", "mes"])
              .agg(dias_exercicio=("em_exercicio", "sum")).reset_index())
    mensal["dias_no_mes"] = pd.to_datetime(dict(year=mensal["ano"], month=mensal["mes"], day=1)).dt.days_in_month
    mensal = mensal[(mensal["dias_exercicio"] > 0) & (competencia(mensal["ano"], mensal["mes"]) <= lim)]
    mensal = mensal.merge(exercicio[["id_deputado", "legislatura", "uf"]], on=["id_deputado", "legislatura"])
    mensal = mensal.merge(_teto_mensal(tetos), on=["uf", "ano", "mes"], how="left")
    assert mensal["teto_mes"].notna().all(), "mês sem teto da CEAP"
    mensal["fracao_mes"] = mensal["dias_exercicio"] / mensal["dias_no_mes"]
    mensal["teto_exercicio"] = mensal["teto_mes"] * mensal["fracao_mes"]

    ceap = pd.concat(pd.read_csv(config.DATA_RAW / "ceap" / f"Ano-{a}.csv.zip", sep=";", encoding="utf-8-sig",
                                 compression="zip", low_memory=False,
                                 usecols=["ideCadastro", "txtDescricao", config.CAMPO_VALOR_CEAP, "numMes", "numAno"])
                     for a in range(config.ANO_INICIO_CEAP, ult[0] + 1))
    ceap = ceap[ceap["ideCadastro"].notna()]
    ceap = ceap.rename(columns={"ideCadastro": "id_deputado", "numAno": "ano", "numMes": "mes",
                                config.CAMPO_VALOR_CEAP: "valor"})
    ceap["valor"] = pd.to_numeric(ceap["valor"], errors="coerce")
    comp = competencia(ceap["ano"], ceap["mes"])
    lacuna = (ceap["txtDescricao"] == config.CATEGORIA_SIGEPA) & (comp >= desde_api)
    ceap = ceap[~lacuna & (comp >= inicio) & (comp <= lim)]
    sig = pd.read_csv(config.SIGEPA_API_CSV)
    sig = sig[(competencia(sig["ano"], sig["mes"]) >= desde_api) & (competencia(sig["ano"], sig["mes"]) <= lim)]
    sig = sig.rename(columns={"valorLiquido": "valor"}).assign(txtDescricao=config.CATEGORIA_SIGEPA)
    despesas = pd.concat([ceap[["id_deputado", "ano", "mes", "valor"]].assign(fonte="arquivo"),
                          sig[["id_deputado", "ano", "mes", "valor"]].assign(fonte="api_sigepa")])
    despesas["id_deputado"] = despesas["id_deputado"].astype(int)
    por_mes = despesas.groupby(["id_deputado", "ano", "mes", "fonte"])["valor"].sum().unstack(fill_value=0)
    por_mes = por_mes.reindex(columns=["arquivo", "api_sigepa"], fill_value=0).reset_index()

    g = mensal.merge(por_mes, on=["id_deputado", "ano", "mes"], how="left").fillna({"arquivo": 0, "api_sigepa": 0})
    fora = por_mes.merge(mensal[["id_deputado", "ano", "mes"]], how="left", indicator=True)
    valor_fora = (fora.loc[fora["_merge"] == "left_only", ["arquivo", "api_sigepa"]].sum().sum())
    gasto = (g.groupby(["id_deputado", "legislatura"])
             .agg(meses_ceap=("fracao_mes", "sum"), teto_total=("teto_exercicio", "sum"),
                  gasto_arquivo=("arquivo", "sum"), gasto_sigepa_api=("api_sigepa", "sum"))
             .reset_index())
    gasto["gasto_total"] = gasto["gasto_arquivo"] + gasto["gasto_sigepa_api"]
    gasto["gasto_relativo"] = (gasto["gasto_total"] / gasto["teto_total"]).round(4)
    gasto["gasto_medio_mensal"] = (gasto["gasto_total"] / gasto["meses_ceap"]).round(2)
    for c in ("meses_ceap", "teto_total", "gasto_arquivo", "gasto_sigepa_api", "gasto_total"):
        gasto[c] = gasto[c].round(2)
    gasto = gasto[["id_deputado", "legislatura", "meses_ceap", "gasto_total", "gasto_arquivo", "gasto_sigepa_api",
                   "teto_total", "gasto_relativo", "gasto_medio_mensal"]]
    gasto.to_csv(OUT / "gasto_ceap.csv", index=False)
    print(f"  competência até {ult[1]:02d}/{ult[0]}; SIGEPA da API: R$ {gasto['gasto_sigepa_api'].sum():,.2f}; "
          f"despesas em meses sem exercício (excluídas): R$ {valor_fora:,.2f}")
    return gasto


# --- Base consolidada, quadrantes e casos extremos -----------------------------
def consolidar(exercicio, prod, gasto) -> pd.DataFrame:
    base = (exercicio.merge(prod, on=["id_deputado", "legislatura"], how="left")
            .merge(gasto, on=["id_deputado", "legislatura"], how="left"))
    pop = base["na_populacao"] & base["gasto_relativo"].notna()
    estrato = base[pop].groupby(["legislatura", "faixa"])
    med = estrato[["gasto_relativo", "prod_bruta_mensal"]].transform("median")
    p_gasto = estrato["gasto_relativo"].transform(lambda s: s.quantile(config.PERCENTIL_GASTO_EXTREMO))
    p_prod = estrato["prod_bruta_mensal"].transform(lambda s: s.quantile(config.PERCENTIL_PROD_EXTREMO))
    gasto_alto = base.loc[pop, "gasto_relativo"] > med["gasto_relativo"]
    prod_alta = base.loc[pop, "prod_bruta_mensal"] > med["prod_bruta_mensal"]
    base.loc[pop, "quadrante"] = (gasto_alto.map({True: "gasto alto", False: "gasto baixo"}) + " / "
                                  + prod_alta.map({True: "produtividade alta", False: "produtividade baixa"}))
    base["no_quadrante_interesse"] = pd.array(
        np.where(pop, base["quadrante"] == config.QUADRANTE_INTERESSE, pd.NA), dtype="boolean")
    extremo = (base.loc[pop, "gasto_relativo"] > p_gasto) & (base.loc[pop, "prod_bruta_mensal"] <= p_prod)
    base["caso_extremo"] = pd.array(np.where(pop, False, pd.NA), dtype="boolean")
    base.loc[extremo[extremo].index, "caso_extremo"] = True
    base.to_csv(OUT / "base_deputado_legislatura.csv", index=False)
    return base


# --- Verificações de consistência ----------------------------------------------
def verificar(diario, exercicio, votos, rice, prod, gasto, base) -> None:
    erros = []
    # Quem votou tem de estar em exercício no dia.
    em_ex = set(zip(diario.loc[diario["em_exercicio"], "id_deputado"], diario.loc[diario["em_exercicio"], "dia"]))
    votantes = votos[votos["voto_original"] != config.CATEGORIA_AUSENCIA]
    inconsistentes = [(i, d) for i, d in zip(votantes["id_deputado"], pd.to_datetime(votantes["data"]))
                      if (i, d) not in em_ex]
    if inconsistentes:
        erros.append(f"{len(inconsistentes)} votantes fora de exercício no dia da votação: {inconsistentes[:5]}")
    max_dias = {l: (config.fim_efetivo(l) - config.LEGISLATURAS[l][0]).days + 1 for l in config.LEGISLATURAS}
    if (exercicio["dias_exercicio"] > exercicio["legislatura"].map(max_dias)).any():
        erros.append("dias de exercício acima da duração da legislatura")
    for v in config.VOTACOES:
        vv = votos[votos["chave_votacao"] == v["chave"]]
        sim = (vv["voto_original"] == "Sim").sum()
        nao = (vv["voto_original"] == "Não").sum()
        if (sim, nao) != (v["placar_oficial"]["Sim"], v["placar_oficial"]["Não"]):
            erros.append(f"{v['chave']}: placar reconstruído {sim}×{nao} difere do oficial")
        if len(vv) > 513:
            erros.append(f"{v['chave']}: {len(vv)} deputados na votação (> 513 cadeiras)")
    if votos.duplicated(["chave_votacao", "id_deputado"]).any():
        erros.append("deputado repetido numa votação")
    if exercicio.duplicated(["id_deputado", "legislatura"]).any():
        erros.append("deputado × legislatura repetido em exercicio.csv")
    meses = gasto.merge(exercicio[["id_deputado", "legislatura", "meses_exercicio"]])
    if (meses["meses_ceap"] > meses["meses_exercicio"] + 0.5).any():  # 0,5: mês de 30,44 dias × calendário
        erros.append("meses_ceap acima de meses_exercicio")
    if (gasto["teto_total"] <= 0).any():
        erros.append("teto total não positivo")
    if votos["partido_id"].isna().sum() != votos["partido"].eq(config.SIGLA_SEM_PARTIDO).sum():
        erros.append("partido_id vazio para quem tem partido")
    if erros:
        raise AssertionError("Verificações falharam:\n  - " + "\n  - ".join(erros))
    print("\nVerificações: votantes em exercício no dia; placares reconstruídos = oficiais; ≤ 513 por votação; "
          "sem duplicatas; dias ≤ legislatura; meses_ceap ≤ meses_exercicio; tetos positivos — OK")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    partidos, espectro, blocos, tetos = carregar_referencias()
    print("== Exercício (histórico, estado diário)")
    diario = estado_diario(partidos, espectro)
    exercicio = tratar_exercicio(diario, partidos, espectro)
    print(f"  {len(exercicio)} deputado×legislatura; na população (≥ {config.MESES_MINIMOS} meses): "
          f"{exercicio['na_populacao'].sum()}")
    print("== Votos")
    votos = tratar_votos(diario, exercicio, partidos, espectro, blocos)
    print(f"  {len(votos)} registros deputado×votação")
    rice = tratar_rice(votos)
    print(f"== Rice: {rice['rice'].notna().sum()} de {len(rice)} partido×votação com ≥ {config.RICE_MIN_VOTOS_VALIDOS} válidos")
    print("== Produtividade")
    prod = tratar_produtividade(exercicio)
    print("== Gasto (CEAP)")
    gasto = tratar_gasto(diario, exercicio, tetos)
    base = consolidar(exercicio, prod, gasto)
    print(f"== Base consolidada: {len(base)} linhas; casos extremos: {int(base['caso_extremo'].sum())}")
    verificar(diario, exercicio, votos, rice, prod, gasto, base)
