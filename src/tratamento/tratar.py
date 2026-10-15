"""Etapa 2 — Tratamento e junção das bases (Seção 6.2).

Uso:
    python -m src.tratamento.tratar

Lê data/raw e grava em data/processed:
    votos.csv                      um registro por deputado × votação (inclui ausentes)
    coesao_rice.csv                índice de Rice por partido × votação
    deputados.csv                  partido, UF e sexo por deputado × legislatura
    produtividade.csv              produtividade bruta e qualificada por deputado × legislatura
    gastos_ceap.csv                gasto da CEAP por deputado × legislatura
    base_deputado_legislatura.csv  junção das três bases pelo id do deputado
"""
import pandas as pd

from src import config
from src.extracao import camara_api as api

OUT = config.DATA_PROCESSED


# ---------------------------------------------------------------------------
# Votos
# ---------------------------------------------------------------------------
def tratar_votos() -> pd.DataFrame:
    linhas = []
    for v in config.VOTACOES:
        if not v["nominal"] or v["id_votacao"] is None:
            continue
        meta = api.get(f"votacoes/{v['id_votacao']}")["dados"]
        dia = meta["data"]
        votos = api.get(f"votacoes/{v['id_votacao']}/votos")["dados"]
        em_exercicio = api.get_paginado("deputados", {"dataInicio": dia, "dataFim": dia})
        mulheres = {d["id"] for d in api.get_paginado(
            "deputados", {"dataInicio": dia, "dataFim": dia, "siglaSexo": "F"})}

        base = {"chave_votacao": v["chave"], "votacao": v["nome"],
                "id_votacao": v["id_votacao"], "data": dia,
                "legislatura": config.legislatura_da_data(pd.Timestamp(dia))}
        def linha(dep, voto):
            return {**base, "id_deputado": dep["id"], "nome": dep["nome"],
                    "partido": dep["siglaPartido"], "uf": dep["siglaUf"],
                    "sexo": "F" if dep["id"] in mulheres else "M", "voto": voto}

        votaram = set()
        for x in votos:
            votaram.add(x["deputado_"]["id"])
            linhas.append(linha(x["deputado_"], x["tipoVoto"]))
        # Ausência é categoria própria, não dado faltante.
        for dep in em_exercicio:
            if dep["id"] not in votaram:
                linhas.append(linha(dep, config.CATEGORIA_AUSENCIA))

    df = pd.DataFrame(linhas).drop_duplicates(["id_votacao", "id_deputado"])
    df.to_csv(OUT / "votos.csv", index=False)
    return df


def indice_rice(votos: pd.DataFrame) -> pd.DataFrame:
    """Rice = |Sim − Não| / (Sim + Não) × 100, por partido e votação."""
    tab = (votos.assign(n=1)
           .pivot_table(index=["chave_votacao", "votacao", "legislatura", "partido"],
                        columns="voto", values="n", aggfunc="sum", fill_value=0)
           .reset_index())
    for col in ("Sim", "Não"):
        if col not in tab:
            tab[col] = 0
    validos = tab["Sim"] + tab["Não"]
    tab["n_deputados"] = tab.drop(columns=["chave_votacao", "votacao", "legislatura",
                                           "partido"]).sum(axis=1)
    tab["rice"] = ((tab["Sim"] - tab["Não"]).abs() / validos * 100).where(validos > 0)
    tab.columns.name = None
    tab.to_csv(OUT / "coesao_rice.csv", index=False)
    return tab


# ---------------------------------------------------------------------------
# Deputados
# ---------------------------------------------------------------------------
def tratar_deputados() -> pd.DataFrame:
    linhas = []
    for leg in config.LEGISLATURAS:
        mulheres = {d["id"] for d in api.get_paginado(
            "deputados", {"idLegislatura": leg, "siglaSexo": "F"})}
        for d in api.get_paginado("deputados", {"idLegislatura": leg}):
            linhas.append({"id_deputado": d["id"], "legislatura": leg, "nome": d["nome"],
                           "partido": d["siglaPartido"], "uf": d["siglaUf"],
                           "sexo": "F" if d["id"] in mulheres else "M"})
    # A API pode repetir o deputado; fica o último registro (filiação mais recente).
    df = pd.DataFrame(linhas).drop_duplicates(["id_deputado", "legislatura"], keep="last")
    df.to_csv(OUT / "deputados.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# Produtividade legislativa
# ---------------------------------------------------------------------------
def tratar_produtividade() -> pd.DataFrame:
    props, autores = [], []
    for arq in sorted((config.DATA_RAW / "proposicoes").glob("proposicoes-*.csv")):
        props.append(pd.read_csv(
            arq, sep=";", encoding="utf-8-sig", low_memory=False,
            usecols=["id", "siglaTipo", "dataApresentacao", "ultimoStatus_descricaoSituacao"]))
    for arq in sorted((config.DATA_RAW / "proposicoesAutores").glob("proposicoesAutores-*.csv")):
        autores.append(pd.read_csv(
            arq, sep=";", encoding="utf-8-sig", low_memory=False,
            usecols=["idProposicao", "idDeputadoAutor", "proponente"]))
    props = pd.concat(props).drop_duplicates("id")
    autores = pd.concat(autores).dropna(subset=["idDeputadoAutor"])

    props = props[props["siglaTipo"].isin(config.TIPOS_PROPOSICAO)].copy()
    props["dataApresentacao"] = pd.to_datetime(props["dataApresentacao"], errors="coerce")
    props["legislatura"] = props["dataApresentacao"].map(
        lambda d: config.legislatura_da_data(d) if pd.notna(d) else None)
    situacao = props["ultimoStatus_descricaoSituacao"].fillna("")
    props["status_conhecido"] = situacao != ""
    props["avancou"] = props["status_conhecido"] & ~situacao.isin(config.SITUACOES_NAO_AVANCOU)

    # Conta apenas autoria proponente (exclui apoiamentos).
    autores = autores[autores["proponente"] == 1]
    df = autores.merge(props, left_on="idProposicao", right_on="id")
    df["id_deputado"] = df["idDeputadoAutor"].astype(int)

    prod = (df.groupby(["id_deputado", "legislatura"])
            .agg(prod_bruta=("id", "nunique"),
                 n_status_conhecido=("status_conhecido", "sum"),
                 n_avancou=("avancou", "sum"))
            .reset_index())
    prod["prod_qualificada"] = (prod["n_avancou"] / prod["n_status_conhecido"]).where(
        prod["n_status_conhecido"] > 0)
    prod["legislatura"] = prod["legislatura"].astype(int)
    prod.to_csv(OUT / "produtividade.csv", index=False)
    return prod


# ---------------------------------------------------------------------------
# Gastos da CEAP
# ---------------------------------------------------------------------------
def tratar_gastos() -> pd.DataFrame:
    partes = []
    for arq in sorted((config.DATA_RAW / "ceap").glob("Ano-*.csv.zip")):
        # usecols descarta CPF e demais dados pessoais já na leitura.
        partes.append(pd.read_csv(
            arq, sep=";", encoding="utf-8-sig", compression="zip", low_memory=False,
            usecols=["ideCadastro", "codLegislatura", "numAno", "numMes", "vlrLiquido"]))
    df = pd.concat(partes).dropna(subset=["ideCadastro"])  # sem id = lideranças
    df["id_deputado"] = df["ideCadastro"].astype(int)
    df["legislatura"] = df["codLegislatura"].astype(int)
    df["vlrLiquido"] = pd.to_numeric(df["vlrLiquido"], errors="coerce")

    df["ano_mes"] = df["numAno"] * 100 + df["numMes"]

    gastos = (df.groupby(["id_deputado", "legislatura"])
              .agg(gasto_total=("vlrLiquido", "sum"),
                   meses_com_gasto=("ano_mes", "nunique"))
              .reset_index())
    # Gasto médio mensal neutraliza diferenças de tempo de mandato.
    gastos["gasto_medio_mensal"] = gastos["gasto_total"] / gastos["meses_com_gasto"]
    gastos.to_csv(OUT / "gastos_ceap.csv", index=False)
    return gastos


def consolidar(deputados, produtividade, gastos) -> pd.DataFrame:
    base = (deputados
            .merge(produtividade, on=["id_deputado", "legislatura"], how="left")
            .merge(gastos, on=["id_deputado", "legislatura"], how="left"))
    base[["prod_bruta", "n_status_conhecido", "n_avancou"]] = (
        base[["prod_bruta", "n_status_conhecido", "n_avancou"]].fillna(0).astype(int))
    base.to_csv(OUT / "base_deputado_legislatura.csv", index=False)
    return base


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    votos = tratar_votos()
    print(f"votos: {len(votos)} linhas")
    print(f"rice: {len(indice_rice(votos))} linhas")
    deps = tratar_deputados()
    print(f"deputados: {len(deps)} linhas")
    prod = tratar_produtividade()
    print(f"produtividade: {len(prod)} linhas")
    gastos = tratar_gastos()
    print(f"gastos: {len(gastos)} linhas")
    print(f"base consolidada: {len(consolidar(deps, prod, gastos))} linhas")
