"""Etapa 3 — Análise estatística (Seções 6.3 e 9).

Uso:
    python -m src.analise.analisar

Análise descritiva e correlacional, sem modelos preditivos. Grava em
data/processed:
    spearman_gasto_produtividade.csv  correlação por legislatura
    quadrantes.csv                    quadrante de cada deputado × legislatura
    quiquadrado_quadrante_voto.csv    teste de independência por votação
    composicao_partidaria.csv         partido no quadrante vs. amostra
    tabulacao_partido_voto.csv        tabulação cruzada partido × voto
"""
import pandas as pd
from scipy import stats

from src import config

DADOS = config.DATA_PROCESSED
QUADRANTE_INTERESSE = "gasto alto / produtividade baixa"


def spearman_por_legislatura(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for leg, g in base.dropna(subset=["gasto_medio_mensal"]).groupby("legislatura"):
        for metrica in ("prod_bruta", "prod_qualificada"):
            gg = g.dropna(subset=[metrica])
            rho, p = stats.spearmanr(gg["gasto_medio_mensal"], gg[metrica])
            linhas.append({"legislatura": leg, "produtividade": metrica,
                           "n": len(gg), "rho": rho, "p_valor": p})
    return pd.DataFrame(linhas)


def classificar_quadrantes(base: pd.DataFrame) -> pd.DataFrame:
    """Divide os deputados de cada legislatura pela mediana do gasto médio
    mensal e da produtividade bruta."""
    df = base.dropna(subset=["gasto_medio_mensal"]).copy()
    med = df.groupby("legislatura")[["gasto_medio_mensal", "prod_bruta"]].transform("median")
    gasto_alto = df["gasto_medio_mensal"] > med["gasto_medio_mensal"]
    prod_alta = df["prod_bruta"] > med["prod_bruta"]
    df["quadrante"] = (gasto_alto.map({True: "gasto alto", False: "gasto baixo"})
                       + " / "
                       + prod_alta.map({True: "produtividade alta", False: "produtividade baixa"}))
    df["no_quadrante_interesse"] = df["quadrante"] == QUADRANTE_INTERESSE
    return df


def quiquadrado_por_votacao(votos: pd.DataFrame, quad: pd.DataFrame) -> pd.DataFrame:
    """Testa independência entre (estar no quadrante de interesse) e (voto
    Sim/Não) em cada votação nominal."""
    df = votos[votos["voto"].isin(config.VOTOS_RICE)].merge(
        quad[["id_deputado", "legislatura", "no_quadrante_interesse"]],
        on=["id_deputado", "legislatura"])
    linhas = []
    for (chave, nome), g in df.groupby(["chave_votacao", "votacao"]):
        tabela = pd.crosstab(g["no_quadrante_interesse"], g["voto"])
        if tabela.shape != (2, 2):
            linhas.append({"chave_votacao": chave, "votacao": nome, "n": len(g),
                           "obs": "tabela incompleta (sem dado de gasto ou voto unânime)"})
            continue
        chi2, p, gl, esperado = stats.chi2_contingency(tabela)
        # Com frequência esperada < 5 o qui-quadrado não é confiável;
        # nesses casos o teste exato de Fisher é o reportado.
        p_fisher = stats.fisher_exact(tabela).pvalue if esperado.min() < 5 else None
        linhas.append({"chave_votacao": chave, "votacao": nome, "n": len(g),
                       "chi2": chi2, "gl": gl, "p_valor": p, "p_fisher": p_fisher,
                       "menor_esperado": esperado.min(),
                       "pct_nao_no_quadrante": (g.loc[g["no_quadrante_interesse"], "voto"]
                                                .eq("Não").mean() * 100),
                       "pct_nao_fora_quadrante": (g.loc[~g["no_quadrante_interesse"], "voto"]
                                                  .eq("Não").mean() * 100)})
    return pd.DataFrame(linhas)


def composicao_partidaria(quad: pd.DataFrame) -> pd.DataFrame:
    """Participação de cada partido no quadrante de interesse comparada à sua
    participação na amostra completa da legislatura."""
    amostra = quad.groupby(["legislatura", "partido"]).size().rename("n_amostra")
    no_quad = (quad[quad["no_quadrante_interesse"]]
               .groupby(["legislatura", "partido"]).size().rename("n_quadrante"))
    comp = pd.concat([amostra, no_quad], axis=1).fillna(0).reset_index()
    tot = comp.groupby("legislatura")[["n_amostra", "n_quadrante"]].transform("sum")
    comp["pct_amostra"] = comp["n_amostra"] / tot["n_amostra"] * 100
    comp["pct_quadrante"] = comp["n_quadrante"] / tot["n_quadrante"] * 100
    comp["prop_partido_no_quadrante"] = comp["n_quadrante"] / comp["n_amostra"] * 100
    return comp


def tabulacao_partido_voto(votos: pd.DataFrame) -> pd.DataFrame:
    return (pd.crosstab([votos["votacao"], votos["partido"]], votos["voto"])
            .reset_index())


if __name__ == "__main__":
    base = pd.read_csv(DADOS / "base_deputado_legislatura.csv")
    votos = pd.read_csv(DADOS / "votos.csv")

    sp = spearman_por_legislatura(base)
    sp.to_csv(DADOS / "spearman_gasto_produtividade.csv", index=False)
    print("Spearman gasto × produtividade:\n", sp.round(3).to_string(index=False), "\n")

    quad = classificar_quadrantes(base)
    quad.to_csv(DADOS / "quadrantes.csv", index=False)

    qq = quiquadrado_por_votacao(votos, quad)
    qq.to_csv(DADOS / "quiquadrado_quadrante_voto.csv", index=False)
    print("Qui-quadrado quadrante × voto:\n", qq.round(4).to_string(index=False), "\n")

    composicao_partidaria(quad).to_csv(DADOS / "composicao_partidaria.csv", index=False)
    tabulacao_partido_voto(votos).to_csv(DADOS / "tabulacao_partido_voto.csv", index=False)
    print("Resultados gravados em", DADOS)
