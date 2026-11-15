"""Etapa 1 — Extração de dados (Seção 6.1 e docs/decisoes_metodologicas.md).

Uso (a partir da raiz do projeto):
    python -m src.extracao.coletar votacoes     # votos, orientações e deputados em exercício (D5, D11)
    python -m src.extracao.coletar deputados    # deputados por legislatura e histórico de cada um (D7, D12)
    python -m src.extracao.coletar proposicoes  # proposições e autores, arquivos anuais (D13, D14)
    python -m src.extracao.coletar despesas     # CEAP, arquivos anuais (D15)
    python -m src.extracao.coletar sigepa       # passagens SIGEPA pela API, lacuna do arquivo desde ago/2025 (D15)
    python -m src.extracao.coletar malha        # contorno das UFs (IBGE), para o mapa
    python -m src.extracao.coletar tudo
    python -m src.extracao.coletar localizar PL 6787 2016

Tudo é salvo em data/raw (não versionado). Rodar de novo reaproveita o que
já foi baixado: respostas da API ficam em cache (data/raw/api) e arquivos já
existentes não são baixados de novo. Uma coleta interrompida pode ser
retomada rodando o mesmo comando.

Ao final, data/processed/manifesto_coleta.json registra o que foi coletado,
quando, quantos registros e o hash de cada arquivo em lote, para documentar
o estado dos dados usado na análise (D1, data de corte).

Votações, deputados e histórico vêm da API REST. Proposições e CEAP vêm dos
arquivos em lote do mesmo portal: a API não tem /deputados/{id}/proposicoes
e a CEAP por deputado exigiria dezenas de milhares de chamadas.
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from src import config
from src.extracao import camara_api as api


# ---------------------------------------------------------------------------
# Utilitário de busca de votações (usado na seleção, seção 2.1)
# ---------------------------------------------------------------------------
def localizar_votacao(sigla: str, numero: int, ano: int) -> list[dict]:
    """Lista as votações de Plenário de uma proposição e quantos votos
    individuais cada uma tem (0 = votação simbólica)."""
    props = api.get("proposicoes", {"siglaTipo": sigla, "numero": numero, "ano": ano})["dados"]
    if not props:
        print(f"Proposição {sigla} {numero}/{ano} não encontrada.")
        return []
    id_prop = props[0]["id"]
    votacoes = api.get(f"proposicoes/{id_prop}/votacoes")["dados"]
    candidatas = []
    for v in votacoes:
        if v["siglaOrgao"] != "PLEN":
            continue
        n_votos = len(api.get(f"votacoes/{v['id']}/votos")["dados"])
        candidatas.append({**v, "n_votos": n_votos})
        print(f"{v['id']:>14}  {v['data']}  votos={n_votos:>3}  {v['descricao'][:90]!r}")
    return candidatas


# ---------------------------------------------------------------------------
# Votações (D5, D11)
# ---------------------------------------------------------------------------
def coletar_votacoes() -> dict:
    """Metadados, votos individuais, orientações de bancada e deputados em
    exercício na data de cada votação. A lista de deputados em exercício é o
    que permite registrar a ausência como categoria própria (D5)."""
    print("\n== Votações")
    resumo = {}
    for v in config.VOTACOES:
        meta = api.get(f"votacoes/{v['id_votacao']}")["dados"]
        votos = api.get(f"votacoes/{v['id_votacao']}/votos")["dados"]
        orientacoes = api.get(f"votacoes/{v['id_votacao']}/orientacoes")["dados"]
        dia = meta["data"]
        em_exercicio = api.get_paginado("deputados", {"dataInicio": dia, "dataFim": dia})
        # A listagem não traz sexo; uma segunda consulta filtrada resolve.
        mulheres = api.get_paginado("deputados", {"dataInicio": dia, "dataFim": dia, "siglaSexo": "F"})
        resumo[v["chave"]] = {"id_votacao": v["id_votacao"], "data": dia, "votos": len(votos),
                              "orientacoes": len(orientacoes), "em_exercicio": len(em_exercicio),
                              "mulheres_em_exercicio": len(mulheres)}
        print(f"  [ok] {v['chave']:<22} {dia}  {len(votos):>3} votos, {len(orientacoes):>2} orientações, "
              f"{len(em_exercicio)} em exercício")
    return resumo


def _ids_das_votacoes() -> set[int]:
    """Deputados que aparecem nas votações (votantes ou em exercício na data)."""
    ids = set()
    for v in config.VOTACOES:
        dia = api.get(f"votacoes/{v['id_votacao']}")["dados"]["data"]
        ids |= {x["deputado_"]["id"] for x in api.get(f"votacoes/{v['id_votacao']}/votos")["dados"]}
        ids |= {d["id"] for d in api.get_paginado("deputados", {"dataInicio": dia, "dataFim": dia})}
    return ids


# ---------------------------------------------------------------------------
# Deputados e histórico (D7, D12)
# ---------------------------------------------------------------------------
def coletar_deputados() -> dict:
    """Deputados de cada legislatura (e quais são mulheres) e o histórico de
    cada um, de onde saem os períodos de exercício e as filiações com data."""
    print("\n== Deputados por legislatura")
    ids, por_leg = set(), {}
    for leg in config.LEGISLATURAS:
        todos = api.get_paginado("deputados", {"idLegislatura": leg})
        mulheres = api.get_paginado("deputados", {"idLegislatura": leg, "siglaSexo": "F"})
        ids |= {d["id"] for d in todos}
        por_leg[leg] = {"registros": len(todos), "deputados": len({d["id"] for d in todos}),
                        "mulheres": len({d["id"] for d in mulheres})}
        print(f"  [ok] legislatura {leg}: {por_leg[leg]['deputados']} deputados "
              f"({por_leg[leg]['mulheres']} mulheres)")
    fora = _ids_das_votacoes() - ids
    if fora:
        print(f"  [aviso] {len(fora)} deputados das votações não estão nas listas por legislatura; incluídos")
        ids |= fora

    print(f"\n== Histórico de {len(ids)} deputados (cache em data/raw/api)")
    falhas, registros = [], 0
    for n, id_dep in enumerate(sorted(ids), 1):
        try:
            registros += len(api.get(f"deputados/{id_dep}/historico")["dados"])
        except Exception as erro:  # uma falha não interrompe a coleta; rodar de novo retoma
            falhas.append(id_dep)
            print(f"  [falha] deputado {id_dep}: {erro.__class__.__name__}")
        if n % 100 == 0 or n == len(ids):
            print(f"  {n}/{len(ids)} deputados", flush=True)
    if falhas:
        print(f"  [aviso] {len(falhas)} históricos falharam; rode `coletar deputados` de novo para retomar")
    return {"por_legislatura": por_leg, "deputados_unicos": len(ids),
            "registros_historico": registros, "falhas_historico": falhas}


# ---------------------------------------------------------------------------
# Arquivos em lote: proposições (D13, D14), CEAP (D15) e malha do IBGE
# ---------------------------------------------------------------------------
def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _registro_arquivo(caminho: Path, url: str) -> dict:
    return {"arquivo": str(caminho.relative_to(config.RAIZ)), "url": url,
            "bytes": caminho.stat().st_size,
            "baixado_em": datetime.fromtimestamp(caminho.stat().st_mtime).isoformat(timespec="seconds"),
            "sha256": _sha256(caminho)}


def coletar_proposicoes() -> list[dict]:
    print("\n== Proposições e autores")
    arquivos = []
    for ano in range(config.ANO_INICIO, config.ANO_FIM + 1):
        for nome in ("proposicoes", "proposicoesAutores"):
            url = f"{config.ARQUIVOS_CAMARA}/{nome}/csv/{nome}-{ano}.csv"
            destino = api.baixar_arquivo(url, config.DATA_RAW / nome / f"{nome}-{ano}.csv")
            arquivos.append(_registro_arquivo(destino, url))
        print(f"  [ok] {ano}", flush=True)
    return arquivos


def coletar_despesas() -> list[dict]:
    print("\n== CEAP")
    arquivos = []
    for ano in range(config.ANO_INICIO_CEAP, config.ANO_FIM + 1):
        url = config.ARQUIVOS_CEAP.format(ano=ano)
        destino = api.baixar_arquivo(url, config.DATA_RAW / "ceap" / f"Ano-{ano}.csv.zip")
        arquivos.append(_registro_arquivo(destino, url))
        print(f"  [ok] {ano} ({destino.stat().st_size / 1e6:.0f} MB)", flush=True)
    return arquivos


def coletar_sigepa() -> dict:
    """Passagens SIGEPA da API para os deputados da 57ª, cobrindo a lacuna do
    arquivo em lote (config.SIGEPA_API_DESDE em diante).

    Baixa os anos inteiros. Os meses anteriores à lacuna servem para validar a
    API contra o arquivo: a comparação deputado × mês tem de bater, senão a
    complementação não é confiável. Grava só os registros de SIGEPA em
    config.SIGEPA_API_CSV, sem CPF/CNPJ do fornecedor.
    """
    import pandas as pd

    print("\n== Passagens SIGEPA pela API (lacuna do arquivo em lote)")
    ano_ini = config.SIGEPA_API_DESDE[0]
    anos = range(ano_ini, config.CEAP_ULTIMA_COMPETENCIA[0] + 1)
    deputados = sorted({d["id"] for d in api.get_paginado("deputados", {"idLegislatura": 57})})
    linhas, falhas = [], []
    for n, id_dep in enumerate(deputados, 1):
        for ano in anos:
            try:
                for x in api.get_paginado(f"deputados/{id_dep}/despesas", {"ano": ano}):
                    if x["tipoDespesa"] == config.CATEGORIA_SIGEPA:
                        linhas.append({"id_deputado": id_dep, "ano": x["ano"], "mes": x["mes"],
                                       "codDocumento": x["codDocumento"], "dataDocumento": x["dataDocumento"],
                                       "valorDocumento": x["valorDocumento"], "valorGlosa": x["valorGlosa"],
                                       "valorLiquido": x["valorLiquido"], "codLote": x["codLote"],
                                       "parcela": x["parcela"], "nomeFornecedor": x["nomeFornecedor"]})
            except Exception as erro:
                falhas.append((id_dep, ano))
                print(f"  [falha] deputado {id_dep}, {ano}: {erro.__class__.__name__}")
        if n % 100 == 0 or n == len(deputados):
            print(f"  {n}/{len(deputados)} deputados", flush=True)
    api_df = pd.DataFrame(linhas)
    config.SIGEPA_API_CSV.parent.mkdir(parents=True, exist_ok=True)
    api_df.to_csv(config.SIGEPA_API_CSV, index=False)

    # Validação: meses em que o arquivo em lote ainda tem SIGEPA.
    arq = pd.read_csv(config.DATA_RAW / "ceap" / f"Ano-{ano_ini}.csv.zip", sep=";", encoding="utf-8-sig",
                      compression="zip", low_memory=False,
                      usecols=["ideCadastro", "txtDescricao", "vlrLiquido", "numMes"])
    arq = arq[(arq["txtDescricao"] == config.CATEGORIA_SIGEPA) & (arq["numMes"] < config.SIGEPA_API_DESDE[1])
              & arq["ideCadastro"].isin(deputados)]
    a = arq.groupby([arq["ideCadastro"].astype(int), "numMes"])["vlrLiquido"].sum()
    b = api_df[(api_df["ano"] == ano_ini) & (api_df["mes"] < config.SIGEPA_API_DESDE[1])] \
        .groupby(["id_deputado", "mes"])["valorLiquido"].sum()
    a.index.names = b.index.names = ["id", "mes"]
    cmp = pd.concat([a.rename("arquivo"), b.rename("api")], axis=1).fillna(0)
    iguais = (cmp["arquivo"] - cmp["api"]).abs() < 0.01
    validacao = {"deputado_mes_comparados": int(len(cmp)), "iguais": int(iguais.sum()),
                 "pct_iguais": round(float(iguais.mean() * 100), 2),
                 "total_arquivo": round(float(cmp["arquivo"].sum()), 2),
                 "total_api": round(float(cmp["api"].sum()), 2)}
    print(f"  validação jan–{config.SIGEPA_API_DESDE[1] - 1:02d}/{ano_ini} (API × arquivo): "
          f"{validacao['iguais']}/{validacao['deputado_mes_comparados']} deputado×mês iguais "
          f"({validacao['pct_iguais']}%); totais R$ {validacao['total_arquivo']:,.2f} × R$ {validacao['total_api']:,.2f}")
    lacuna = api_df[(api_df["ano"] * 100 + api_df["mes"])
                    >= config.SIGEPA_API_DESDE[0] * 100 + config.SIGEPA_API_DESDE[1]]
    print(f"  {len(lacuna)} registros SIGEPA na lacuna (R$ {lacuna['valorLiquido'].sum():,.2f}) → "
          f"{config.SIGEPA_API_CSV.relative_to(config.RAIZ)}")
    return {"deputados": len(deputados), "registros_sigepa": len(api_df),
            "registros_na_lacuna": int(len(lacuna)), "valor_na_lacuna": round(float(lacuna["valorLiquido"].sum()), 2),
            "validacao": validacao, "falhas": falhas,
            "arquivo": _registro_arquivo(config.SIGEPA_API_CSV, f"{config.API_CAMARA}/deputados/{{id}}/despesas")}


def coletar_malha() -> list[dict]:
    print("\n== Malha das UFs (IBGE)")
    destino = api.baixar_arquivo(config.MALHA_IBGE_UF, config.MALHA_UF_GEOJSON)
    n = len(json.loads(destino.read_text(encoding="utf-8")).get("features", []))
    print(f"  [ok] {n} UFs")
    return [_registro_arquivo(destino, config.MALHA_IBGE_UF)]


# ---------------------------------------------------------------------------
# Manifesto
# ---------------------------------------------------------------------------
def _atualizar_manifesto(secoes: dict) -> None:
    """Acrescenta ao manifesto as seções coletadas nesta execução, preservando
    as das execuções anteriores."""
    caminho = config.MANIFESTO_COLETA
    manifesto = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    manifesto.update({"data_corte": config.DATA_CORTE.isoformat(),
                      "janela": [config.DATA_INICIO.isoformat(), config.DATA_CORTE.isoformat()],
                      "atualizado_em": datetime.now().isoformat(timespec="seconds")})
    manifesto.setdefault("secoes", {}).update(
        {nome: {"coletado_em": datetime.now().isoformat(timespec="seconds"), "conteudo": conteudo}
         for nome, conteudo in secoes.items()})
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifesto atualizado: {caminho.relative_to(config.RAIZ)}")


ETAPAS = {
    "votacoes": coletar_votacoes,
    "deputados": coletar_deputados,
    "proposicoes": coletar_proposicoes,
    "despesas": coletar_despesas,
    "sigepa": coletar_sigepa,  # depende de "despesas" (usa o arquivo para validar)
    "malha": coletar_malha,
}


if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else "tudo"
    if etapa == "localizar":
        sigla, numero, ano = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        localizar_votacao(sigla, numero, ano)
        sys.exit(0)
    if etapa != "tudo" and etapa not in ETAPAS:
        sys.exit(f"Etapa desconhecida: {etapa}. Use uma de: {', '.join(ETAPAS)}, tudo, localizar")
    escolhidas = ETAPAS if etapa == "tudo" else {etapa: ETAPAS[etapa]}
    _atualizar_manifesto({nome: funcao() for nome, funcao in escolhidas.items()})
