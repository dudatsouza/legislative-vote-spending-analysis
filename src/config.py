"""
Todo parâmetro de pesquisa fica aqui, com o código da decisão que o
justifica (D1–D18). A explicação completa de cada decisão está em
docs/decisoes_metodologicas.md.

Tabelas de referência que precisam de fonte citável (siglas partidárias,
espectro ideológico, tetos da CEAP, composição de blocos) ficam em CSV em
data/referencia/, para poderem ser preenchidas e conferidas numa planilha.
Este módulo só guarda os caminhos para elas.

Para conferir a consistência de tudo:
    python -m src.validar_config            (com consultas à API, usa cache)
    python -m src.validar_config --sem-api  (só verificações locais)
"""
from datetime import date, timedelta
from pathlib import Path

# ===========================================================================
# Caminhos
# ===========================================================================
RAIZ = Path(__file__).resolve().parent.parent
DATA_RAW = RAIZ / "data" / "raw"                # não versionado (.gitignore)
DATA_PROCESSED = RAIZ / "data" / "processed"    # versionado
DATA_REFERENCIA = RAIZ / "data" / "referencia"  # versionado; tabelas com fonte
FIGURAS = RAIZ / "figuras"

PARTIDOS_CSV = DATA_REFERENCIA / "partidos.csv"                   # D7/D8
ESPECTRO_CSV = DATA_REFERENCIA / "espectro_partidos.csv"          # D9
BLOCOS_CSV = DATA_REFERENCIA / "blocos_orientacao.csv"            # D11
TETOS_CEAP_CSV = DATA_REFERENCIA / "tetos_ceap.csv"               # D15

MALHA_UF_GEOJSON = DATA_RAW / "ibge" / "malha_uf.geojson"         # mapa
MANIFESTO_COLETA = DATA_PROCESSED / "manifesto_coleta.json"       # o que foi coletado e quando


API_CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
ARQUIVOS_CAMARA = "https://dadosabertos.camara.leg.br/arquivos"
ARQUIVOS_CEAP = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
MALHA_IBGE_UF = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
                 "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")

INTERVALO_REQUISICOES = 0.5  # segundos entre chamadas, para respeitar a API
ITENS_POR_PAGINA = 100       # máximo aceito pela API

UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO")

# ===========================================================================
# D1 — Janela temporal: legislaturas 55ª a 57ª
# ===========================================================================
DATA_INICIO = date(2015, 2, 1)
# Data de corte da coleta. A 57ª legislatura está em curso: tudo que depende
# de tempo (meses de exercício, gasto, proposições) é contado até aqui.
# Atualizar na coleta definitiva e citar no relatório.
DATA_CORTE = date(2026, 11, 14)

LEGISLATURAS = {
    55: (date(2015, 2, 1), date(2019, 1, 31)),
    56: (date(2019, 2, 1), date(2023, 1, 31)),
    57: (date(2023, 2, 1), date(2027, 1, 31)),
}
ANO_INICIO, ANO_FIM = DATA_INICIO.year, DATA_CORTE.year
ANO_INICIO_CEAP = ANO_INICIO  # a CEAP existe desde 2009; a janela começa em 2015


def legislatura_da_data(d) -> int | None:
    """Número da legislatura (55–57) que contém a data `d`; None fora da janela."""
    if hasattr(d, "date"):
        d = d.date()
    if d < DATA_INICIO or d > DATA_CORTE:
        return None
    for leg, (ini, fim) in LEGISLATURAS.items():
        if ini <= d <= fim:
            return leg
    return None


def fim_efetivo(leg: int) -> date:
    """Último dia considerado na legislatura (a 57ª termina na data de corte)."""
    return min(LEGISLATURAS[leg][1], DATA_CORTE)


# ===========================================================================
# Votações (seção 2.1) e direção pró-pauta (D6)
#
# id_votacao        id da votação nominal de mérito no Plenário (API).
# data/legislatura  conferidos contra a API por src.validar_config.
# placar_oficial    Sim e Não da descrição oficial da votação (sem abstenções).
# direcao_pro_pauta voto que amplia ou preserva o direito do grupo afetado:
#                   "Sim", "Não", ou None quando a direção é ambígua.
#                   Votações com None ficam fora do índice pró-pauta, mas
#                   entram em todas as análises por votação.
# ===========================================================================
VOTACOES = [
    {
        "chave": "maioridade_penal",
        "nome": "Redução da maioridade penal (2º turno)",
        "proposicao": ("PEC", 171, 1993),
        "id_votacao": "14493-536",
        "data": date(2015, 8, 19),
        "legislatura": 55,
        "placar_oficial": {"Sim": 320, "Não": 152},
        "tema": "Segurança pública",
        "grupo_afetado": "Adolescentes (proteção do ECA)",
        "efeito_sim": "Reduz a idade penal",
        "direcao_pro_pauta": "Não",
    },
    {
        "chave": "teto_gastos",
        "nome": "Teto de gastos (2º turno)",
        "proposicao": ("PEC", 241, 2016),
        "id_votacao": "2088351-324",
        "data": date(2016, 10, 25),
        "legislatura": 55,
        "placar_oficial": {"Sim": 359, "Não": 116},
        "tema": "Gasto social (saúde e educação)",
        "grupo_afetado": "Usuários de saúde e educação públicas",
        "efeito_sim": "Limita o crescimento do gasto social",
        "direcao_pro_pauta": "Não",
    },
    {
        "chave": "reforma_trabalhista",
        "nome": "Reforma Trabalhista (texto-base)",
        "proposicao": ("PL", 6787, 2016),
        "id_votacao": "2122076-348",
        "data": date(2017, 4, 26),
        "legislatura": 55,
        "placar_oficial": {"Sim": 296, "Não": 177},
        "tema": "Trabalho",
        "grupo_afetado": "Trabalhadores",
        "efeito_sim": "Flexibiliza a CLT",
        "direcao_pro_pauta": "Não",
    },
    {
        "chave": "reforma_previdencia",
        "nome": "Reforma da Previdência (2º turno)",
        "proposicao": ("PEC", 6, 2019),
        "id_votacao": "2192459-786",
        "data": date(2019, 8, 6),
        "legislatura": 56,
        "placar_oficial": {"Sim": 370, "Não": 124},
        "tema": "Previdência",
        "grupo_afetado": "Segurados e aposentados",
        "efeito_sim": "Endurece o acesso a benefícios",
        "direcao_pro_pauta": "Não",
    },
    {
        "chave": "pec_precatorios",
        "nome": "PEC dos Precatórios (2º turno)",
        "proposicao": ("PEC", 23, 2021),
        "id_votacao": "2293449-241",
        "data": date(2021, 11, 9),
        "legislatura": 56,
        "placar_oficial": {"Sim": 323, "Não": 172},
        "tema": "Assistência social / dívidas judiciais",
        "grupo_afetado": "Beneficiários do Auxílio Brasil × credores da União",
        "efeito_sim": "Amplia a transferência de renda e adia o pagamento de precatórios",
        "direcao_pro_pauta": None,  # ambígua: fora do índice agregado (D6)
    },
    {
        "chave": "igualdade_salarial",
        "nome": "Igualdade salarial entre mulheres e homens",
        "proposicao": ("PL", 1085, 2023),
        "id_votacao": "2351179-51",
        "data": date(2023, 5, 4),
        "legislatura": 57,
        "placar_oficial": {"Sim": 325, "Não": 36},
        "tema": "Trabalho / gênero",
        "grupo_afetado": "Mulheres trabalhadoras",
        "efeito_sim": "Garante igualdade salarial",
        "direcao_pro_pauta": "Sim",
    },
    {
        "chave": "marco_temporal",
        "nome": "Marco temporal das terras indígenas",
        "proposicao": ("PL", 490, 2007),
        "id_votacao": "345311-270",
        "data": date(2023, 5, 30),
        "legislatura": 57,
        "placar_oficial": {"Sim": 283, "Não": 155},
        "tema": "Direitos indígenas",
        "grupo_afetado": "Povos indígenas",
        "efeito_sim": "Restringe as demarcações",
        "direcao_pro_pauta": "Não",
    },
    {
        "chave": "fim_escala_6x1",
        "nome": "PEC do fim da escala 6x1 (2º turno)",
        "proposicao": ("PEC", 221, 2019),
        "id_votacao": "2233802-438",
        "data": date(2026, 5, 27),
        "legislatura": 57,
        "placar_oficial": {"Sim": 461, "Não": 19},
        "tema": "Trabalho",
        "grupo_afetado": "Trabalhadores",
        "efeito_sim": "Reduz a jornada",
        "direcao_pro_pauta": "Sim",
    },
]
for _v in VOTACOES:
    _v["nominal"] = True  # todas as selecionadas têm voto individual na API


def votacoes_no_indice() -> list[dict]:
    """Votações que entram no índice pró-pauta agregado (direção definida)."""
    return [v for v in VOTACOES if v["direcao_pro_pauta"] is not None]


# ===========================================================================
# D5 — Categorias de voto
# ===========================================================================
# voto_original -> voto_valido. O que não está no mapa não é voto válido.
MAPA_VOTO_VALIDO = {"Sim": "Sim", "Não": "Não", "Obstrução": "Não"}
CATEGORIA_AUSENCIA = "Ausente"        # em exercício na data e sem voto registrado
CATEGORIA_PRESIDENTE = "Artigo 17"    # presidente da sessão: sai da população

# ===========================================================================
# D11 — Orientações de bancada
# ===========================================================================
MAPA_ORIENTACAO = {"Sim": "Sim", "Não": "Não", "Obstrução": "Não"}
ORIENTACOES_SEM_DIRECAO = {"Liberado", ""}  # tiram o deputado do cálculo
ORIENTACAO_GOVERNO = "Governo"
ORIENTACOES_IGNORADAS = {"Maioria", "Minoria", "Oposição"}
# codTipoLideranca na API: "P" = partido (prevalece), "B" = bloco ou federação.
LIDERANCA_PARTIDO, LIDERANCA_BLOCO = "P", "B"

# ===========================================================================
# D3 — População e faixas de tempo de exercício
# ===========================================================================
MESES_MINIMOS = 12
# (rótulo, limite inferior inclusivo, limite superior exclusivo; None = sem teto)
FAIXAS_EXERCICIO = (("C", 12, 24), ("B", 24, 36), ("A", 36, None))
PERCENTIL_GASTO_EXTREMO = 0.80   # caso extremo: gasto relativo > P80 do estrato
PERCENTIL_PROD_EXTREMO = 0.20    # ... e produtividade mensal <= P20 do estrato


def faixa_de_exercicio(meses: float) -> str | None:
    """Faixa C/B/A para `meses` de exercício; None abaixo do mínimo."""
    for rotulo, ini, fim in FAIXAS_EXERCICIO:
        if meses >= ini and (fim is None or meses < fim):
            return rotulo
    return None


# ===========================================================================
# D12 — Meses de exercício (histórico oficial do deputado)
# ===========================================================================
SITUACAO_EXERCICIO = "Exercício"
DIAS_POR_MES = 30.44

# ===========================================================================
# D7/D8 — Partidos
# ===========================================================================
SEM_PARTIDO = {"S.PART."}
SUFIXO_ESPURIO = r"\*+$"  # PP** -> PP (aplicado antes de consultar PARTIDOS_CSV)

# ===========================================================================
# D9 — Espectro ideológico (Bolognesi, Ribeiro e Codato, 2023)
# ===========================================================================
ESPECTROS = ("esquerda", "centro", "direita")  # ordem usada em todas as figuras
MAPA_ESPECTRO = {
    "extrema-esquerda": "esquerda",
    "esquerda": "esquerda",
    "centro-esquerda": "esquerda",
    "centro": "centro",
    "centro-direita": "direita",
    "direita": "direita",
    "extrema-direita": "direita",
}
# Cortes do artigo (p. 16) sobre a média 0–10 da Tabela 1: (limite superior
# inclusivo, categoria). Usados para classificar escores derivados, como a
# média das origens numa fusão.
CORTES_BOLOGNESI = (
    (1.50, "extrema-esquerda"),
    (3.00, "esquerda"),
    (4.49, "centro-esquerda"),
    (5.50, "centro"),
    (7.00, "centro-direita"),
    (8.50, "direita"),
    (10.0, "extrema-direita"),
)


def categoria_bolognesi(escore: float) -> str:
    """Categoria (7 níveis) de um escore 0–10, pelos cortes do artigo.

    Os cortes do artigo têm buracos de 0,01 (ex.: 1,50 → 1,51). Escores com
    mais casas decimais são arredondados para 2 casas antes da comparação.
    """
    escore = round(escore, 2)
    for limite, categoria in CORTES_BOLOGNESI:
        if escore <= limite:
            return categoria
    raise ValueError(f"escore fora da escala 0–10: {escore}")

# ===========================================================================
# D10 — Coesão partidária (Rice)
# ===========================================================================
RICE_MIN_VOTOS_VALIDOS = 5

# ===========================================================================
# D13 — Produtividade bruta
# ===========================================================================
# PDC era a sigla do projeto de decreto legislativo até 2018; a partir de
# 2019 passou a PDL (arquivos de 2015: 310 PDC e 3 PDL; 2020: 0 PDC e 469 PDL).
# É o mesmo tipo, então as duas entram.
TIPOS_NORMATIVOS = ("PL", "PLP", "PEC", "PDL", "PDC")
ORDEM_PRIMEIRO_AUTOR = 1  # ordemAssinatura == 1 e proponente == 1

# ===========================================================================
# D14 — Produtividade qualificada: "aprovada na Câmara"
# Lista fechada a partir de todas as situações (ultimoStatus_descricaoSituacao)
# das proposições normativas de 2015 a 2026.
# ===========================================================================
SITUACOES_APROVADA_CAMARA = {
    "Aguardando Envio à Redação Final",   # mérito aprovado; falta a redação final
    "Aguardando Redação Final",           # idem
    "Aguardando Autógrafos na Mesa",
    "Aguardando Envio ao Senado Federal",
    "Aguardando Apreciação pelo Senado Federal",
    "Aguardando Sanção",
    "Aguardando Apreciação do Veto",
    "Vetado totalmente",                  # aprovada nas duas Casas e vetada
    "Transformado em Norma Jurídica",
}
SITUACAO_NORMA = "Transformado em Norma Jurídica"  # métrica de robustez
SITUACAO_APENSADA = "Tramitando em Conjunto"       # conta como "não atingiu"
SITUACOES_SEM_INFORMACAO = {"", "<Não Definido>"}  # saem do denominador

# ===========================================================================
# D15 — Gasto relativo da CEAP
# ===========================================================================
CAMPO_VALOR_CEAP = "vlrLiquido"

# Corte da CEAP: o deputado tem 90 dias para apresentar as notas, então os
# meses mais recentes ainda estão incompletos. Entra só a competência até o
# último mês inteiro anterior a DATA_CORTE − 90 dias. Numerador e teto usam
# os mesmos meses.
CEAP_DIAS_PRAZO_NOTAS = 90


def _ultima_competencia_ceap() -> tuple[int, int]:
    limite = DATA_CORTE - timedelta(days=CEAP_DIAS_PRAZO_NOTAS)
    primeiro_do_mes = limite.replace(day=1)
    anterior = primeiro_do_mes - timedelta(days=1)
    return anterior.year, anterior.month


CEAP_ULTIMA_COMPETENCIA = _ultima_competencia_ceap()  # (2026, 7) com a data de corte atual

# Lacuna do arquivo em lote: a partir de ago/2025, "PASSAGEM AÉREA - SIGEPA"
# não aparece em Ano-{ano}.csv.zip, mas está na API /deputados/{id}/despesas
# (os valores batem com o arquivo nos meses em que os dois têm o dado). Nessas
# competências, o SIGEPA do arquivo é descartado e substituído pelo da API.
# Só o SIGEPA vem da API: nas demais categorias ela devolve o valor com o
# sinal invertido.
CATEGORIA_SIGEPA = "PASSAGEM AÉREA - SIGEPA"
SIGEPA_API_DESDE = (2025, 8)
SIGEPA_API_CSV = DATA_RAW / "ceap" / "sigepa_api.csv"

# Teto em mês com mudança de vigência (fev/2016, fev/2026): média dos tetos
# vigentes no mês, ponderada pelos dias de cada vigência; depois multiplicada
# pela fração de dias em exercício (D12).
TETO_MES_PARCIAL = "ponderado_por_dias"

# ===========================================================================
# D16 — Quadrantes
# ===========================================================================
QUADRANTE_INTERESSE = "gasto alto / produtividade baixa"

# ===========================================================================
# D18 — Critérios estatísticos
# ===========================================================================
ALPHA = 0.05
CORRECAO_MULTIPLA = "holm"   # aplicada dentro de cada família
FREQ_ESPERADA_MIN = 5        # abaixo disso: Fisher (2×2) ou permutação (r×c)
N_PERMUTACOES = 10_000
N_BOOTSTRAP = 10_000
NIVEL_CONFIANCA = 0.95
METODO_IC_PROPORCAO = "wilson"
SEMENTE = 20260929           # data da apresentação do pré-projeto
FAMILIAS_TESTES = {
    "F1": "partido × voto (qui-quadrado por votação)",
    "F2": "espectro × voto (qui-quadrado por votação)",
    "F3": "gasto × produtividade (Spearman por legislatura × faixa)",
    "F4": "produtividade × voto (Mann-Whitney por votação)",
    "F5": "quadrante × voto (2×2 por votação)",
}

# ===========================================================================
# Visualização
# ===========================================================================
ESTILO_GRAFICOS = ["science", "ieee"]
ESTILO_GRAFICOS_SEM_LATEX = ["science", "ieee", "no-latex"]  # fallback automático
FORMATOS_FIGURA = ("pdf", "png")
DPI_PNG = 600
COLORMAP_SEQUENCIAL = "cividis"
COLORMAP_DIVERGENTE = "PuOr"  # neutro: evita o par vermelho/azul partidário

# ===========================================================================
# Compatibilidade temporária
# Nomes usados pelas etapas atuais do pipeline (tratar/analisar), que ainda
# serão reescritas. Remover quando cada etapa for atualizada.
# ===========================================================================
VOTOS_RICE = {"Sim", "Não"}
TIPOS_PROPOSICAO = list(TIPOS_NORMATIVOS)
SITUACOES_NAO_AVANCOU = {  # regra antiga do D14, substituída por SITUACOES_APROVADA_CAMARA
    "Arquivada",
    "Retirado pelo(a) Autor(a)",
    "Devolvida ao(à) Autor(a)",
    "Perdeu a Eficácia",
}
