"""Confere src/config.py, as tabelas de data/referencia e os dados brutos.

    python -m src.validar_config [--sem-api]

Cada verificação imprime [OK], [AVISO] (pendência, não impede rodar) ou
[ERRO] (o script termina com código 1).
"""
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from src import config

_contagem = {"OK": 0, "AVISO": 0, "ERRO": 0}


def _log(nivel: str, msg: str) -> None:
    _contagem[nivel] += 1
    print(f"  [{nivel}] {msg}")


def checar(condicao: bool, msg_ok: str, msg_falha: str, nivel_falha: str = "ERRO") -> bool:
    _log("OK", msg_ok) if condicao else _log(nivel_falha, msg_falha)
    return condicao


def _secao(titulo: str) -> None:
    print(f"\n== {titulo}")


def _ler_csv(caminho) -> pd.DataFrame | None:
    if not caminho.exists():
        _log("ERRO", f"arquivo ausente: {caminho.relative_to(config.RAIZ)}")
        return None
    return pd.read_csv(caminho, dtype=str, keep_default_na=False)


# --- 1. Parâmetros do config.py ---
def validar_janela() -> None:
    _secao("janela temporal")
    legs = sorted(config.LEGISLATURAS)
    checar(legs == [55, 56, 57], "legislaturas 55, 56 e 57", f"legislaturas inesperadas: {legs}")
    checar(config.DATA_INICIO == config.LEGISLATURAS[55][0],
           "DATA_INICIO coincide com o início da 55ª", "DATA_INICIO difere do início da 55ª")
    contiguas = all(config.LEGISLATURAS[a][1] + timedelta(days=1) == config.LEGISLATURAS[b][0]
                    for a, b in zip(legs, legs[1:]))
    checar(contiguas, "legislaturas contíguas, sem lacuna", "há lacuna ou sobreposição entre legislaturas")
    ini57, fim57 = config.LEGISLATURAS[57]
    checar(ini57 <= config.DATA_CORTE <= fim57, f"DATA_CORTE ({config.DATA_CORTE}) dentro da 57ª",
           "DATA_CORTE fora da 57ª")
    checar(config.ANO_FIM == config.DATA_CORTE.year and config.ANO_INICIO == 2015,
           f"anos de coleta {config.ANO_INICIO}–{config.ANO_FIM}", "ANO_INICIO/ANO_FIM incoerentes")
    casos = {date(2015, 1, 31): None, date(2015, 2, 1): 55, date(2019, 1, 31): 55,
             date(2019, 2, 1): 56, date(2023, 2, 1): 57, config.DATA_CORTE: 57,
             config.DATA_CORTE + timedelta(days=1): None}
    erros = {d: (config.legislatura_da_data(d), esp) for d, esp in casos.items()
             if config.legislatura_da_data(d) != esp}
    checar(not erros, "legislatura_da_data: 7 casos de borda corretos", f"legislatura_da_data falhou: {erros}")
    checar(config.fim_efetivo(57) == config.DATA_CORTE and config.fim_efetivo(55) == date(2019, 1, 31),
           "fim_efetivo correto (57ª termina na data de corte)", "fim_efetivo incorreto")


def validar_votacoes() -> None:
    _secao("votações e direção pró-pauta")
    campos = {"chave", "nome", "proposicao", "id_votacao", "data", "legislatura",
              "placar_oficial", "tema", "grupo_afetado", "efeito_sim", "direcao_pro_pauta", "nominal"}
    faltando = {v.get("chave", "?"): campos - v.keys() for v in config.VOTACOES if campos - v.keys()}
    checar(not faltando, f"{len(config.VOTACOES)} votações com todos os campos", f"campos ausentes: {faltando}")
    chaves = [v["chave"] for v in config.VOTACOES]
    ids = [v["id_votacao"] for v in config.VOTACOES]
    checar(len(set(chaves)) == len(chaves) and len(set(ids)) == len(ids),
           "chaves e ids únicos", "chave ou id_votacao repetido")
    incoerentes = [v["chave"] for v in config.VOTACOES
                   if config.legislatura_da_data(v["data"]) != v["legislatura"]]
    checar(not incoerentes, "data de cada votação cai na legislatura declarada",
           f"data fora da legislatura declarada: {incoerentes}")
    direcoes_invalidas = [v["chave"] for v in config.VOTACOES if v["direcao_pro_pauta"] not in ("Sim", "Não", None)]
    checar(not direcoes_invalidas, "direções pró-pauta válidas (Sim, Não ou None)",
           f"direção inválida: {direcoes_invalidas}")
    placar_ruim = [v["chave"] for v in config.VOTACOES
                   if set(v["placar_oficial"]) != {"Sim", "Não"}
                   or not all(isinstance(n, int) and n >= 0 for n in v["placar_oficial"].values())]
    checar(not placar_ruim, "placares oficiais bem formados", f"placar malformado: {placar_ruim}")
    por_leg = pd.Series([v["legislatura"] for v in config.VOTACOES]).value_counts().to_dict()
    checar(all(por_leg.get(l, 0) >= 2 for l in config.LEGISLATURAS),
           f"todas as legislaturas com ≥ 2 votações {dict(sorted(por_leg.items()))}",
           f"legislatura com menos de 2 votações: {por_leg}")
    no_indice = config.votacoes_no_indice()
    ambiguas = [v["chave"] for v in config.VOTACOES if v["direcao_pro_pauta"] is None]
    checar(ambiguas == ["pec_precatorios"] and len(no_indice) == 7,
           "índice pró-pauta com 7 votações; Precatórios fora (ambígua)",
           f"conjunto do índice inesperado; ambíguas = {ambiguas}")
    idx_leg = pd.Series([v["legislatura"] for v in no_indice]).value_counts().to_dict()
    checar(idx_leg.get(56, 0) >= 2, "56ª com ≥ 2 votações no índice",
           f"56ª tem {idx_leg.get(56, 0)} votação no índice (manter e declarar)", "AVISO")


def validar_parametros() -> None:
    _secao("parâmetros")
    checar(set(config.MAPA_VOTO_VALIDO.values()) <= {"Sim", "Não"}
           and config.MAPA_VOTO_VALIDO.get("Obstrução") == "Não",
           "votos válidos Sim/Não, obstrução = Não", "MAPA_VOTO_VALIDO incoerente")
    checar(config.MAPA_ORIENTACAO == config.MAPA_VOTO_VALIDO,
           "orientações seguem a mesma regra dos votos", "MAPA_ORIENTACAO difere de MAPA_VOTO_VALIDO")

    faixas = config.FAIXAS_EXERCICIO
    contiguas = all(a[2] == b[1] for a, b in zip(faixas, faixas[1:]))
    checar(faixas[0][1] == config.MESES_MINIMOS and faixas[-1][2] is None and contiguas,
           "faixas contíguas a partir de 12 meses, a última sem teto", "faixas incoerentes")
    casos = {11.99: None, 12: "C", 23.99: "C", 24: "B", 35.99: "B", 36: "A", 48: "A"}
    erros = {m: config.faixa_de_exercicio(m) for m, esp in casos.items() if config.faixa_de_exercicio(m) != esp}
    checar(not erros, "faixa_de_exercicio correta nas bordas", f"faixa_de_exercicio falhou: {erros}")
    checar(0.5 < config.PERCENTIL_GASTO_EXTREMO < 1 and 0 < config.PERCENTIL_PROD_EXTREMO < 0.5,
           f"percentis P{config.PERCENTIL_GASTO_EXTREMO*100:.0f}/P{config.PERCENTIL_PROD_EXTREMO*100:.0f}",
           "percentis fora do intervalo esperado")

    checar(len(config.MAPA_ESPECTRO) == 7 and set(config.MAPA_ESPECTRO.values()) == set(config.ESPECTROS),
           "7 categorias do artigo → 3 espectros", "MAPA_ESPECTRO incompleto")
    checar(config.RICE_MIN_VOTOS_VALIDOS == 5, "corte do Rice = 5 votos válidos", "corte diferente de 5")
    checar({"PDC", "PDL"} <= set(config.TIPOS_NORMATIVOS),
           "PDC (até 2018) e PDL (desde 2019) incluídos", "falta PDC ou PDL")
    checar(config.SITUACAO_NORMA in config.SITUACOES_APROVADA_CAMARA
           and config.SITUACAO_APENSADA not in config.SITUACOES_APROVADA_CAMARA,
           "norma conta como aprovada; apensada não conta", "conjuntos de situação incoerentes")
    corte = config.CEAP_ULTIMA_COMPETENCIA
    fim_corte = date(corte[0] + (corte[1] == 12), corte[1] % 12 + 1, 1) - timedelta(days=1)
    checar(fim_corte <= config.DATA_CORTE - timedelta(days=config.CEAP_DIAS_PRAZO_NOTAS)
           and (fim_corte + timedelta(days=1)) > config.DATA_CORTE - timedelta(days=config.CEAP_DIAS_PRAZO_NOTAS + 31),
           f"competência da CEAP até {corte[1]:02d}/{corte[0]} (último mês inteiro antes de corte − 90 dias)",
           f"CEAP_ULTIMA_COMPETENCIA incoerente: {corte}")
    checar(config.SIGEPA_API_DESDE <= corte and config.TETO_MES_PARCIAL == "ponderado_por_dias",
           f"SIGEPA pela API desde {config.SIGEPA_API_DESDE[1]:02d}/{config.SIGEPA_API_DESDE[0]}; "
           f"teto do mês ponderado por dias", "parâmetros de SIGEPA/teto incoerentes")
    checar(config.ALPHA == 0.05 and config.CORRECAO_MULTIPLA == "holm" and len(config.FAMILIAS_TESTES) == 5,
           "α = 0,05, Holm, 5 famílias", "parâmetros estatísticos divergem do decidido")


# --- 2. Tabelas de referência ---
def validar_partidos() -> pd.DataFrame | None:
    _secao("data/referencia/partidos.csv")
    df = _ler_csv(config.PARTIDOS_CSV)
    if df is None:
        return None
    colunas = ["sigla_api", "sigla", "partido_id", "familia", "evento", "data_evento",
               "processo_tse", "fonte", "observacao", "conferido_tse"]
    checar(list(df.columns) == colunas, "colunas corretas", f"colunas: {list(df.columns)}")
    checar(df["sigla_api"].is_unique, f"{len(df)} siglas da API, sem repetição", "sigla_api repetida")
    sem = df["sigla_api"].isin(config.SEM_PARTIDO)
    checar((df.loc[~sem, ["partido_id", "familia"]] != "").all().all(),
           "todo partido tem partido_id e família", "partido sem partido_id ou família")
    ids = set(df.loc[~sem, "partido_id"])
    checar(set(df.loc[~sem, "familia"]) <= ids, "toda família é um partido_id existente",
           f"famílias sem linha própria: {set(df.loc[~sem, 'familia']) - ids}")
    eventos_validos = {"", "renomeacao", "fusao", "incorporacao", "grafia"}
    checar(set(df["evento"]) <= eventos_validos, "eventos válidos", f"evento inválido: {set(df['evento']) - eventos_validos}")
    com_data = df["evento"].isin({"renomeacao", "fusao", "incorporacao"})
    datas = pd.to_datetime(df.loc[com_data, "data_evento"], format="%Y-%m-%d", errors="coerce")
    checar(datas.notna().all(), f"{com_data.sum()} renomeações/fusões/incorporações com data válida (AAAA-MM-DD)",
           f"evento sem data válida: {list(df.loc[com_data, 'sigla_api'][datas.isna()])}")
    sem_fonte = df.loc[com_data & ((df["processo_tse"] == "") | (df["fonte"] == "")), "sigla_api"]
    checar(sem_fonte.empty, "todo evento com processo do TSE e fonte", f"evento sem processo ou fonte: {list(sem_fonte)}")
    origem_fusao = df[df["evento"] == "fusao"].groupby("familia")["data_evento"].nunique()
    checar((origem_fusao == 1).all(), "partidos de uma mesma fusão com a mesma data",
           f"fusão com datas diferentes entre as origens: {origem_fusao[origem_fusao > 1].to_dict()}")
    renomeadas = df[df["evento"] == "renomeacao"]
    checar((renomeadas["partido_id"] != renomeadas["sigla"]).all(),
           "renomeações apontam para a identidade atual", "renomeação com partido_id igual à sigla antiga")
    pend = (df.loc[~sem & (df["evento"] != "") & (df["evento"] != "grafia"), "conferido_tse"] != "sim").sum()
    checar(pend == 0, "datas de eventos conferidas no TSE",
           f"{pend} eventos (renomeação/fusão) ainda não conferidos no TSE", "AVISO")
    return df


def validar_espectro(partidos: pd.DataFrame | None) -> None:
    _secao("data/referencia/espectro_partidos.csv")
    df = _ler_csv(config.ESPECTRO_CSV)
    if df is None:
        return
    colunas = ["partido_id", "sigla_no_artigo", "categoria_artigo", "escore_artigo",
               "metodo", "origens", "justificativa", "fonte"]
    checar(list(df.columns) == colunas, "colunas corretas", f"colunas: {list(df.columns)}")
    if partidos is not None:
        ids = set(partidos.loc[partidos["partido_id"] != "", "partido_id"])
        checar(set(df["partido_id"]) == ids, f"cobre os {len(ids)} partido_id de partidos.csv",
               f"diferença: faltam {ids - set(df['partido_id'])}, sobram {set(df['partido_id']) - ids}")
    checar(set(df["metodo"]) <= {"artigo", "heranca_fusao", "manual"}, "métodos válidos",
           f"método inválido: {set(df['metodo'])}")
    fusoes = df[df["metodo"] == "heranca_fusao"]
    origens = {o for lista in fusoes["origens"] for o in lista.split(";") if o}
    checar(origens <= set(df["partido_id"]) and (fusoes["origens"] != "").all(),
           f"fusões com origens válidas ({', '.join(fusoes['partido_id'])})", "fusão com origem inválida")
    artigo = df[df["metodo"] == "artigo"]
    preenchidas = artigo["categoria_artigo"] != ""
    invalidas = set(artigo.loc[preenchidas, "categoria_artigo"]) - set(config.MAPA_ESPECTRO)
    checar(not invalidas, "categorias preenchidas são válidas", f"categoria inválida: {invalidas}")
    escores = pd.to_numeric(artigo.loc[artigo["escore_artigo"] != "", "escore_artigo"], errors="coerce")
    checar(escores.between(0, 10).all(), "escores preenchidos entre 0 e 10", "escore fora de 0–10 ou não numérico")
    com_escore = df[(df["escore_artigo"] != "") & (df["categoria_artigo"] != "")]
    divergentes = [f"{r.partido_id} ({r.escore_artigo} → {config.categoria_bolognesi(float(r.escore_artigo))}, "
                   f"tabela diz {r.categoria_artigo})"
                   for r in com_escore.itertuples()
                   if config.categoria_bolognesi(float(r.escore_artigo)) != r.categoria_artigo]
    checar(not divergentes, f"categoria coerente com o escore pelos cortes do artigo ({len(com_escore)} partidos)",
           f"categoria não bate com o escore: {divergentes}")
    escore = dict(zip(df["partido_id"], pd.to_numeric(df["escore_artigo"], errors="coerce")))
    medias_erradas = [r.partido_id for r in fusoes.itertuples()
                      if r.escore_artigo != "" and abs(float(r.escore_artigo)
                         - sum(escore[o] for o in r.origens.split(";")) / len(r.origens.split(";"))) > 1e-9]
    checar(not medias_erradas, "escore das fusões = média das origens", f"média errada em: {medias_erradas}")
    checar(preenchidas.all(), "classificação do artigo preenchida para todos",
           f"{(~preenchidas).sum()} de {len(artigo)} partidos aguardando a tabela de Bolognesi et al. (2023)", "AVISO")
    manuais = df[df["metodo"] == "manual"]
    sem_categoria = manuais.loc[(manuais["categoria_artigo"] == "") | (manuais["justificativa"] == ""), "partido_id"]
    checar(sem_categoria.empty, f"classificações manuais com categoria e justificativa ({', '.join(manuais['partido_id'])})",
           f"classificação manual pendente: {', '.join(sem_categoria)}", "AVISO")
    sem_fonte = manuais.loc[manuais["fonte"] == "", "partido_id"]
    checar(sem_fonte.empty, "classificações manuais com fonte documental",
           f"fonte documental pendente (estatuto, programa ou manifesto): {', '.join(sem_fonte)}", "AVISO")


def validar_blocos(partidos: pd.DataFrame | None) -> None:
    _secao("data/referencia/blocos_orientacao.csv")
    df = _ler_csv(config.BLOCOS_CSV)
    if df is None:
        return
    colunas = ["bloco_api", "votacoes", "partidos", "origem_composicao", "situacao",
               "vigencia_inicio", "fonte", "observacao"]
    checar(list(df.columns) == colunas, "colunas corretas", f"colunas: {list(df.columns)}")
    chaves = {v["chave"] for v in config.VOTACOES}
    votacoes = {c for lista in df["votacoes"] for c in lista.split(";")}
    checar(votacoes <= chaves, "votações referenciadas existem", f"votação desconhecida: {votacoes - chaves}")
    data_votacao = {v["chave"]: v["data"] for v in config.VOTACOES}
    com_vigencia = df[df["vigencia_inicio"] != ""]
    anteriores = [f"{b.bloco_api} ({c})" for b in com_vigencia.itertuples() for c in b.votacoes.split(";")
                  if c in data_votacao and data_votacao[c] < date.fromisoformat(b.vigencia_inicio)]
    checar(not anteriores, f"blocos com vigência já existiam nas votações que orientaram ({len(com_vigencia)})",
           f"votação anterior à formação do bloco: {anteriores}")
    sem_fonte = df.loc[(df["situacao"] == "ok") & (df["fonte"] == ""), "bloco_api"]
    checar(sem_fonte.empty, "blocos confirmados com fonte", f"bloco 'ok' sem fonte: {list(sem_fonte)}")
    if partidos is not None:
        conhecidas = set(partidos["sigla_api"])
        siglas = {s for lista in df["partidos"] for s in lista.split(";") if s}
        checar(siglas <= conhecidas, "siglas dos blocos existem em partidos.csv",
               f"sigla desconhecida: {siglas - conhecidas}")
    checar(set(df["situacao"]) <= {"ok", "a_confirmar", "pendente"}, "situações válidas", "situação inválida")
    for _, b in df[df["situacao"] != "ok"].iterrows():
        _log("AVISO", f"bloco '{b['bloco_api']}' ({b['votacoes']}): {b['situacao']}")


def validar_tetos() -> None:
    _secao("data/referencia/tetos_ceap.csv")
    df = _ler_csv(config.TETOS_CEAP_CSV)
    if df is None:
        return
    colunas = ["uf", "vigencia_inicio", "vigencia_fim", "valor_mensal", "ato_normativo", "fonte_url"]
    checar(list(df.columns) == colunas, "colunas corretas", f"colunas: {list(df.columns)}")
    checar(set(df["uf"]) == set(config.UFS), "as 27 UFs presentes", f"UFs faltando: {set(config.UFS) - set(df['uf'])}")
    preenchidas = df[df["valor_mensal"] != ""]
    if preenchidas.empty:
        _log("AVISO", "tetos ainda não preenchidos (insumo pendente: atos da Mesa e reajustes)")
        return
    ini = pd.to_datetime(preenchidas["vigencia_inicio"], errors="coerce")
    fim = pd.to_datetime(preenchidas["vigencia_fim"].replace("", str(config.DATA_CORTE)), errors="coerce")
    valor = pd.to_numeric(preenchidas["valor_mensal"], errors="coerce")
    checar(ini.notna().all() and fim.notna().all() and (valor > 0).all() and (ini <= fim).all(),
           "datas e valores bem formados", "data ou valor inválido em tetos_ceap.csv")
    for uf in config.UFS:
        p = preenchidas.assign(ini=ini, fim=fim)[preenchidas["uf"] == uf].sort_values("ini")
        if p.empty:
            _log("AVISO", f"{uf}: sem teto preenchido")
            continue
        cobre = (p["ini"].iloc[0] <= pd.Timestamp(config.DATA_INICIO)
                 and p["fim"].iloc[-1] >= pd.Timestamp(config.DATA_CORTE)
                 and all(a + pd.Timedelta(days=1) == b for a, b in zip(p["fim"], p["ini"].iloc[1:])))
        checar(cobre, f"{uf}: vigências cobrem a janela sem lacuna",
               f"{uf}: vigências não cobrem {config.DATA_INICIO}–{config.DATA_CORTE} ou têm lacuna")


# --- 3. Conferência contra a API da Câmara (usa o cache em data/raw/api) ---
_PLACAR = re.compile(r"Sim:?\s*(\d+)\D{1,4}N[ãa]o:?\s*(\d+)", re.IGNORECASE)


def validar_api(partidos: pd.DataFrame | None) -> None:
    from src.extracao import camara_api as api

    _secao("API — votações conferidas contra a Câmara")
    siglas_api = set(partidos["sigla_api"]) if partidos is not None else set()
    blocos = _ler_csv(config.BLOCOS_CSV)
    blocos_conhecidos = set(blocos["bloco_api"]) if blocos is not None else set()
    for v in config.VOTACOES:
        meta = api.get(f"votacoes/{v['id_votacao']}")["dados"]
        votos = api.get(f"votacoes/{v['id_votacao']}/votos")["dados"]
        orient = api.get(f"votacoes/{v['id_votacao']}/orientacoes")["dados"]
        prop = api.get(f"proposicoes/{v['id_votacao'].split('-')[0]}")["dados"]
        tipo, num, ano = v["proposicao"]
        problemas = []
        if meta["data"] != v["data"].isoformat():
            problemas.append(f"data API {meta['data']}")
        if meta.get("siglaOrgao") != "PLEN":
            problemas.append(f"órgão {meta.get('siglaOrgao')}")
        if (prop["siglaTipo"], prop["numero"], prop["ano"]) != (tipo, num, ano):
            problemas.append(f"proposição API {prop['siglaTipo']} {prop['numero']}/{prop['ano']}")
        m = _PLACAR.search(meta.get("descricao") or "")
        if m and (int(m.group(1)), int(m.group(2))) != (v["placar_oficial"]["Sim"], v["placar_oficial"]["Não"]):
            problemas.append(f"descrição diz {m.group(1)}×{m.group(2)}")
        contagem = pd.Series([x["tipoVoto"] for x in votos]).value_counts()
        api_sim, api_nao = int(contagem.get("Sim", 0)), int(contagem.get("Não", 0))
        if (api_sim, api_nao) != (v["placar_oficial"]["Sim"], v["placar_oficial"]["Não"]):
            problemas.append(f"votos individuais {api_sim}×{api_nao}")
        checar(not problemas,
               f"{v['chave']}: {tipo} {num}/{ano}, {v['data']}, PLEN, "
               f"{api_sim}×{api_nao} (descrição {'confere' if m else 'sem placar no texto'})",
               f"{v['chave']}: " + "; ".join(problemas))

        desconhecidas = {x["deputado_"]["siglaPartido"] for x in votos} - siglas_api
        checar(not desconhecidas, f"{v['chave']}: todas as siglas dos votos estão em partidos.csv",
               f"{v['chave']}: siglas sem linha em partidos.csv: {desconhecidas}")
        sem_regra = set()
        for o in orient:
            nome = o["siglaPartidoBloco"]
            if nome in config.ORIENTACOES_IGNORADAS or nome == config.ORIENTACAO_GOVERNO:
                continue
            if o["codTipoLideranca"] == config.LIDERANCA_BLOCO and nome not in blocos_conhecidos:
                sem_regra.add(nome)
            if o["codTipoLideranca"] == config.LIDERANCA_PARTIDO and nome not in siglas_api:
                sem_regra.add(nome)
        checar(not sem_regra, f"{v['chave']}: todas as orientações têm regra (partido ou bloco)",
               f"{v['chave']}: orientações sem regra: {sem_regra}")

    _secao("IBGE — malha das UFs")
    try:
        r = requests.get(config.MALHA_IBGE_UF, timeout=60)
        geo = r.json() if r.ok else {}
        n = len(geo.get("features", []))
        checar(n == 27, "malha do IBGE acessível, com 27 UFs", f"malha do IBGE com {n} feições (HTTP {r.status_code})")
    except (requests.RequestException, ValueError) as erro:
        _log("AVISO", f"malha do IBGE inacessível agora ({erro.__class__.__name__})")


# --- 4. Conferência contra os dados brutos já baixados (se existirem) ---
def validar_proposicoes_brutas() -> None:
    _secao("situações e tipos nos arquivos de proposições")
    arquivos = [config.DATA_RAW / "proposicoes" / f"proposicoes-{a}.csv"
                for a in range(config.ANO_INICIO, config.ANO_FIM + 1)]
    presentes = [a for a in arquivos if a.exists()]
    if not presentes:
        _log("AVISO", "arquivos de proposições ainda não baixados (python -m src.extracao.coletar proposicoes)")
        return
    checar(len(presentes) == len(arquivos), f"{len(presentes)} arquivos anuais ({config.ANO_INICIO}–{config.ANO_FIM})",
           f"faltam {len(arquivos) - len(presentes)} arquivos anuais", "AVISO")
    df = pd.concat(pd.read_csv(a, sep=";", encoding="utf-8-sig", low_memory=False,
                               usecols=["siglaTipo", "ultimoStatus_descricaoSituacao"]) for a in presentes)
    tipos = set(df["siglaTipo"].dropna())
    checar(set(config.TIPOS_NORMATIVOS) <= tipos, "todos os tipos normativos aparecem nos dados",
           f"tipos sem ocorrência: {set(config.TIPOS_NORMATIVOS) - tipos}", "AVISO")
    norm = df[df["siglaTipo"].isin(config.TIPOS_NORMATIVOS)]
    sit = norm["ultimoStatus_descricaoSituacao"].fillna("")
    existentes = set(sit)
    ausentes = config.SITUACOES_APROVADA_CAMARA - existentes
    checar(not ausentes, "todas as situações do marco de aprovação existem nos dados (grafia exata)",
           f"situações do marco sem ocorrência (grafia?): {ausentes}")
    com_info = ~sit.isin(config.SITUACOES_SEM_INFORMACAO)
    marco = sit.isin(config.SITUACOES_APROVADA_CAMARA)
    print(f"         proposições normativas: {len(norm):,} | sem situação: {(~com_info).mean():.1%} | "
          f"apensadas: {(sit == config.SITUACAO_APENSADA).mean():.1%} | "
          f"marco de aprovação (entre as com situação): {marco[com_info].mean():.1%} | "
          f"só norma jurídica: {(sit[com_info] == config.SITUACAO_NORMA).mean():.1%}")


def comparar_brutos_manifesto() -> dict | None:
    """Compara data/raw/ com o manifesto da coleta (sha256). None se não houver manifesto.

    Devolve a data de corte do manifesto, os arquivos registrados e os que estão
    ausentes, diferentes ou baixados antes da data de corte. Usado pela validação
    e pelo tratamento, que se recusa a rodar com brutos fora do manifesto."""
    if not config.MANIFESTO_COLETA.exists():
        return None
    manifesto = json.loads(config.MANIFESTO_COLETA.read_text(encoding="utf-8"))
    registros = []

    def percorrer(x):
        if isinstance(x, dict):
            if isinstance(x.get("arquivo"), str) and x.get("sha256"):
                registros.append(x)
            for v in x.values():
                percorrer(v)
        elif isinstance(x, list):
            for v in x:
                percorrer(v)
    percorrer(manifesto.get("secoes", {}))

    ausentes, diferentes, antigos = [], [], []
    for r in registros:
        caminho = config.RAIZ / r["arquivo"]
        if not caminho.exists():
            ausentes.append(r["arquivo"])
            continue
        h = hashlib.sha256()
        with open(caminho, "rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        if h.hexdigest() != r["sha256"]:
            diferentes.append(r["arquivo"])
        if (r.get("baixado_em") and "ibge" not in r["arquivo"]
                and datetime.fromisoformat(r["baixado_em"]).date() < config.DATA_CORTE):
            antigos.append(r["arquivo"])
    return {"data_corte": manifesto.get("data_corte"), "registros": registros,
            "ausentes": ausentes, "diferentes": diferentes, "antigos": antigos}


def resumir_arquivos(xs: list[str]) -> str:
    return ", ".join(Path(x).name for x in xs[:4]) + (f" e mais {len(xs) - 4}" if len(xs) > 4 else "")


def validar_brutos() -> None:
    """Confere se os arquivos de data/raw/ batem com o manifesto (sha256)."""
    _secao("Dados brutos × manifesto da coleta")
    comp = comparar_brutos_manifesto()
    if comp is None:
        _log("AVISO", "manifesto da coleta ausente; rode a coleta")
        return
    registros, ausentes, diferentes, antigos = (comp[k] for k in ("registros", "ausentes", "diferentes", "antigos"))
    resumir = resumir_arquivos
    checar(comp["data_corte"] == config.DATA_CORTE.isoformat(),
           f"manifesto com a mesma data de corte do config ({config.DATA_CORTE})",
           f"data de corte do manifesto ({comp['data_corte']}) ≠ config.DATA_CORTE ({config.DATA_CORTE})")
    checar(not ausentes, f"os {len(registros)} arquivos do manifesto existem em data/raw/",
           f"{len(ausentes)} arquivo(s) do manifesto ausente(s): {resumir(ausentes)}")
    checar(not diferentes, "arquivos brutos idênticos aos do manifesto (sha256)",
           f"{len(diferentes)} arquivo(s) diferente(s) do manifesto ({resumir(diferentes)}): os resultados não "
           f"vão reproduzir os versionados. Use os mesmos data/raw/ de quem gerou o manifesto ou rode a coleta "
           f"de novo e commite o manifesto novo.")
    checar(not antigos, f"arquivos baixados na data de corte ({config.DATA_CORTE}) ou depois",
           f"{len(antigos)} arquivo(s) baixado(s) antes da data de corte ({resumir(antigos)})", "AVISO")


def main() -> int:
    sem_api = "--sem-api" in sys.argv
    print(f"Validando src/config.py e data/referencia/ (data de corte {config.DATA_CORTE})")
    validar_janela()
    validar_votacoes()
    validar_parametros()
    partidos = validar_partidos()
    validar_espectro(partidos)
    validar_blocos(partidos)
    validar_tetos()
    if not sem_api:
        validar_api(partidos)
    validar_proposicoes_brutas()
    validar_brutos()
    print(f"\nResumo: {_contagem['OK']} OK, {_contagem['AVISO']} avisos, {_contagem['ERRO']} erros")
    return 1 if _contagem["ERRO"] else 0


if __name__ == "__main__":
    sys.exit(main())
