"""Etapa 1 — Extração de dados (Seção 6.1).

Uso (a partir da raiz do projeto):
    python -m src.extracao.coletar votacoes
    python -m src.extracao.coletar deputados
    python -m src.extracao.coletar proposicoes
    python -m src.extracao.coletar despesas
    python -m src.extracao.coletar tudo
    python -m src.extracao.coletar localizar PL 6787 2016

Tudo é salvo em data/raw (não versionado). Rodar de novo reaproveita o
que já foi baixado.

Votações vêm da API REST. Proposições e CEAP vêm dos arquivos em lote do
mesmo portal: a API não tem /deputados/{id}/proposicoes e não devolve a
situação de tramitação na listagem, e a CEAP por deputado exigiria dezenas
de milhares de chamadas.
"""
import sys

from src import config
from src.extracao import camara_api as api


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


def coletar_votacoes() -> None:
    """Metadados, votos individuais e deputados em exercício na data de cada
    votação nominal. A lista de deputados em exercício é o que permite
    registrar a ausência como categoria própria."""
    for v in config.VOTACOES:
        if not v["nominal"]:
            print(f"[pula] {v['nome']}: votação simbólica, sem voto individual.")
            continue
        if v["id_votacao"] is None:
            print(f"[pendente] {v['nome']}: defina id_votacao em config.py "
                  f"(use `localizar {' '.join(map(str, v['proposicao']))}`).")
            continue
        meta = api.get(f"votacoes/{v['id_votacao']}")["dados"]
        votos = api.get(f"votacoes/{v['id_votacao']}/votos")["dados"]
        dia = meta["data"]
        em_exercicio = api.get_paginado("deputados", {"dataInicio": dia, "dataFim": dia})
        # A listagem não traz sexo; uma segunda consulta filtrada resolve.
        api.get_paginado("deputados", {"dataInicio": dia, "dataFim": dia, "siglaSexo": "F"})
        print(f"[ok] {v['nome']} ({v['id_votacao']}, {dia}): "
              f"{len(votos)} votos, {len(em_exercicio)} deputados em exercício")


def coletar_deputados() -> None:
    """Deputados de cada legislatura (partido e UF da última filiação
    registrada na API) e quais são mulheres."""
    for leg in config.LEGISLATURAS:
        todos = api.get_paginado("deputados", {"idLegislatura": leg})
        api.get_paginado("deputados", {"idLegislatura": leg, "siglaSexo": "F"})
        print(f"[ok] legislatura {leg}: {len(todos)} registros de deputados")


def coletar_proposicoes() -> None:
    ano_ini = config.ANO_INICIO
    for ano in range(ano_ini, config.ANO_FIM + 1):
        for nome in ("proposicoes", "proposicoesAutores"):
            url = f"{config.ARQUIVOS_CAMARA}/{nome}/csv/{nome}-{ano}.csv"
            destino = config.DATA_RAW / nome / f"{nome}-{ano}.csv"
            api.baixar_arquivo(url, destino)
        print(f"[ok] proposições {ano}")


def coletar_despesas() -> None:
    for ano in range(config.ANO_INICIO_CEAP, config.ANO_FIM + 1):
        destino = config.DATA_RAW / "ceap" / f"Ano-{ano}.csv.zip"
        api.baixar_arquivo(config.ARQUIVOS_CEAP.format(ano=ano), destino)
        print(f"[ok] CEAP {ano}")


if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else "tudo"
    if etapa == "localizar":
        sigla, numero, ano = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        localizar_votacao(sigla, numero, ano)
    else:
        if etapa in ("votacoes", "tudo"):
            coletar_votacoes()
        if etapa in ("deputados", "tudo"):
            coletar_deputados()
        if etapa in ("proposicoes", "tudo"):
            coletar_proposicoes()
        if etapa in ("despesas", "tudo"):
            coletar_despesas()
