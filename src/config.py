"""Parâmetros da pesquisa: caminhos, votações, critérios e constantes.

As tabelas que precisam de fonte citável (partidos, espectro, tetos da CEAP,
blocos) ficam em CSV em data/referencia/. Para conferir tudo:
    python -m src.validar_config [--sem-api]
"""
from datetime import date, timedelta
from pathlib import Path

# --- Caminhos ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DATA_RAW = RAIZ / "data" / "raw"                # não versionado
DATA_PROCESSED = RAIZ / "data" / "processed"
DATA_REFERENCIA = RAIZ / "data" / "referencia"
FIGURAS = RAIZ / "figuras"
FIGURAS_RELATORIO = FIGURAS / "relatorio"       # PDFs do relatório e dos slides
FIGURAS_INTERATIVAS = FIGURAS / "interativas"   # HTML (Plotly)
FIGURAS_PERFIL = FIGURAS / "perfil"             # relatórios do ydata-profiling

PARTIDOS_CSV = DATA_REFERENCIA / "partidos.csv"
ESPECTRO_CSV = DATA_REFERENCIA / "espectro_partidos.csv"
BLOCOS_CSV = DATA_REFERENCIA / "blocos_orientacao.csv"
TETOS_CEAP_CSV = DATA_REFERENCIA / "tetos_ceap.csv"
MALHA_UF_GEOJSON = DATA_RAW / "ibge" / "malha_uf.geojson"  # cópia versionada em data/referencia/
MANIFESTO_COLETA = DATA_PROCESSED / "manifesto_coleta.json"

API_CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
ARQUIVOS_CAMARA = "https://dadosabertos.camara.leg.br/arquivos"
ARQUIVOS_CEAP = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
MALHA_IBGE_UF = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
                 "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")

INTERVALO_REQUISICOES = 0.5  # segundos entre chamadas à API
ITENS_POR_PAGINA = 100       # máximo aceito pela API

UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO")
COD_IBGE_UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
               "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
               "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
               "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}

# --- Janela temporal: legislaturas 55ª a 57ª -------------------------------
DATA_INICIO = date(2015, 2, 1)
# A 57ª está em curso: tudo que depende de tempo é contado até a data de corte.
DATA_CORTE = date(2026, 11, 20)

LEGISLATURAS = {
    55: (date(2015, 2, 1), date(2019, 1, 31)),
    56: (date(2019, 2, 1), date(2023, 1, 31)),
    57: (date(2023, 2, 1), date(2027, 1, 31)),
}
ANO_INICIO, ANO_FIM = DATA_INICIO.year, DATA_CORTE.year
ANO_INICIO_CEAP = ANO_INICIO


def legislatura_da_data(d) -> int | None:
    """Legislatura (55–57) que contém a data `d`; None fora da janela."""
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


# --- Votações ---------------------------------------------------------------
# placar_oficial: Sim e Não da descrição oficial (sem abstenções).
# direcao_pro_pauta: voto que amplia ou preserva o direito do grupo afetado;
# None quando é ambígua (a votação fica fora do índice pró-pauta agregado).
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
        "direcao_pro_pauta": None,
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
    _v["nominal"] = True


def votacoes_no_indice() -> list[dict]:
    """Votações que entram no índice pró-pauta agregado (direção definida)."""
    return [v for v in VOTACOES if v["direcao_pro_pauta"] is not None]


# --- Votos e orientações ----------------------------------------------------
MAPA_VOTO_VALIDO = {"Sim": "Sim", "Não": "Não", "Obstrução": "Não"}
CATEGORIA_AUSENCIA = "Ausente"        # em exercício e sem voto registrado
CATEGORIA_PRESIDENTE = "Artigo 17"    # presidente da sessão: sai da população

MAPA_ORIENTACAO = {"Sim": "Sim", "Não": "Não", "Obstrução": "Não"}
ORIENTACOES_SEM_DIRECAO = {"Liberado", ""}
ORIENTACAO_GOVERNO = "Governo"
ORIENTACOES_IGNORADAS = {"Maioria", "Minoria", "Oposição"}
LIDERANCA_PARTIDO, LIDERANCA_BLOCO = "P", "B"  # codTipoLideranca; partido prevalece

# --- População e faixas de exercício ----------------------------------------
MESES_MINIMOS = 12
FAIXAS_EXERCICIO = (("C", 12, 24), ("B", 24, 36), ("A", 36, None))  # [ini, fim)
PERCENTIL_GASTO_EXTREMO = 0.80   # caso extremo: gasto > P80 do estrato
PERCENTIL_PROD_EXTREMO = 0.20    # ... e produtividade <= P20 do estrato
SITUACAO_EXERCICIO = "Exercício"
DIAS_POR_MES = 30.44


def faixa_de_exercicio(meses: float) -> str | None:
    """Faixa C/B/A para `meses` de exercício; None abaixo do mínimo."""
    for rotulo, ini, fim in FAIXAS_EXERCICIO:
        if meses >= ini and (fim is None or meses < fim):
            return rotulo
    return None


# --- Partidos e espectro (Bolognesi, Ribeiro e Codato, 2023) ---------------
SIGLA_SEM_PARTIDO = "S.PART."
SEM_PARTIDO = {SIGLA_SEM_PARTIDO}
SUFIXO_ESPURIO = r"\*+$"  # PP** -> PP

ESPECTROS = ("esquerda", "centro", "direita")
MAPA_ESPECTRO = {
    "extrema-esquerda": "esquerda",
    "esquerda": "esquerda",
    "centro-esquerda": "esquerda",
    "centro": "centro",
    "centro-direita": "direita",
    "direita": "direita",
    "extrema-direita": "direita",
}
# Cortes do artigo (p. 16) sobre a média 0–10: (limite superior inclusivo, categoria).
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
    """Categoria (7 níveis) de um escore 0–10; arredonda a 2 casas por causa dos buracos entre cortes."""
    escore = round(escore, 2)
    for limite, categoria in CORTES_BOLOGNESI:
        if escore <= limite:
            return categoria
    raise ValueError(f"escore fora da escala 0–10: {escore}")


# --- Coesão e produtividade -------------------------------------------------
RICE_MIN_VOTOS_VALIDOS = 5
PROD_QUALIFICADA_MIN_PROPOSICOES = 5  # robustez: denominador mínimo da razão

# PDC virou PDL em 2019; é o mesmo tipo.
TIPOS_NORMATIVOS = ("PL", "PLP", "PEC", "PDL", "PDC")
TIPOS_DECRETO = ("PDL", "PDC")  # robustez: produtividade sem decretos legislativos
ORDEM_PRIMEIRO_AUTOR = 1

# Situações que contam como "aprovada na Câmara".
SITUACOES_APROVADA_CAMARA = {
    "Aguardando Envio à Redação Final",   # mérito aprovado; falta a redação final
    "Aguardando Redação Final",
    "Aguardando Autógrafos na Mesa",
    "Aguardando Envio ao Senado Federal",
    "Aguardando Apreciação pelo Senado Federal",
    "Aguardando Sanção",
    "Aguardando Apreciação do Veto",
    "Vetado totalmente",
    "Transformado em Norma Jurídica",
}
SITUACAO_NORMA = "Transformado em Norma Jurídica"
SITUACAO_APENSADA = "Tramitando em Conjunto"
SITUACOES_SEM_INFORMACAO = {"", "<Não Definido>"}  # saem do denominador

# --- Gasto da CEAP ----------------------------------------------------------
CAMPO_VALOR_CEAP = "vlrLiquido"

# O deputado tem 90 dias para apresentar as notas: entra só até o último mês
# inteiro anterior a DATA_CORTE − 90 dias.
CEAP_DIAS_PRAZO_NOTAS = 90


def _ultima_competencia_ceap() -> tuple[int, int]:
    limite = DATA_CORTE - timedelta(days=CEAP_DIAS_PRAZO_NOTAS)
    anterior = limite.replace(day=1) - timedelta(days=1)
    return anterior.year, anterior.month


CEAP_ULTIMA_COMPETENCIA = _ultima_competencia_ceap()

# A partir de ago/2025 o SIGEPA some do arquivo em lote; vem da API nesses meses.
CATEGORIA_SIGEPA = "PASSAGEM AÉREA - SIGEPA"
SIGEPA_API_DESDE = (2025, 8)
SIGEPA_API_CSV = DATA_RAW / "ceap" / "sigepa_api.csv"

TETO_MES_PARCIAL = "ponderado_por_dias"
QUADRANTE_INTERESSE = "gasto alto / produtividade baixa"

# --- Estatística ------------------------------------------------------------
ALPHA = 0.05
CORRECAO_MULTIPLA = "holm"
FREQ_ESPERADA_MIN = 5        # abaixo disso: Fisher (2×2) ou permutação (r×c)
N_PERMUTACOES = 10_000
NIVEL_CONFIANCA = 0.95
METODO_IC_PROPORCAO = "wilson"
SEMENTE = 20260929
FAMILIAS_TESTES = {
    "F1": "partido × voto (qui-quadrado por votação)",
    "F2": "espectro × voto (qui-quadrado por votação)",
    "F3": "gasto × produtividade (Spearman por legislatura × faixa)",
    "F4": "produtividade × voto (Mann-Whitney por votação)",
    "F5": "quadrante × voto (2×2 por votação)",
}

# --- Visualização -----------------------------------------------------------
ESTILO_GRAFICOS = ["science", "ieee"]
ESTILO_GRAFICOS_SEM_LATEX = ["science", "ieee", "no-latex"]
COLORMAP_SEQUENCIAL = "cividis"
COLORMAP_DIVERGENTE = "PuOr"  # evita o par vermelho/azul partidário
