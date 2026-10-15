"""Configurações centrais do projeto "O custo do Não".

Tudo que é parâmetro de pesquisa (votações, recorte temporal, tipos de
proposição) fica aqui, para que as etapas do pipeline não tenham valores
espalhados pelo código.
"""
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DATA_RAW = RAIZ / "data" / "raw"            # não versionado (.gitignore)
DATA_PROCESSED = RAIZ / "data" / "processed"  # versionado
FIGURAS = RAIZ / "figuras"

# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------
API_CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
ARQUIVOS_CAMARA = "https://dadosabertos.camara.leg.br/arquivos"
ARQUIVOS_CEAP = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"

INTERVALO_REQUISICOES = 0.5  # segundos entre chamadas, para respeitar a API
ITENS_POR_PAGINA = 100       # máximo aceito pela API

# ---------------------------------------------------------------------------
# Recorte temporal (Seção 8): legislaturas 51ª a 57ª
# ---------------------------------------------------------------------------
LEGISLATURAS = {
    51: (date(1999, 2, 1), date(2003, 1, 31)),
    52: (date(2003, 2, 1), date(2007, 1, 31)),
    53: (date(2007, 2, 1), date(2011, 1, 31)),
    54: (date(2011, 2, 1), date(2015, 1, 31)),
    55: (date(2015, 2, 1), date(2019, 1, 31)),
    56: (date(2019, 2, 1), date(2023, 1, 31)),
    57: (date(2023, 2, 1), date(2027, 1, 31)),
}
ANO_INICIO, ANO_FIM = 2000, 2026

# A CEAP só existe a partir de 2009 (o arquivo de 2008 está praticamente
# vazio). Legislaturas 51 e 52 ficam sem dado de gasto.
ANO_INICIO_CEAP = 2009


def legislatura_da_data(d) -> int | None:
    """Retorna o número da legislatura que contém a data `d`."""
    if hasattr(d, "date"):
        d = d.date()
    for leg, (ini, fim) in LEGISLATURAS.items():
        if ini <= d <= fim:
            return leg
    return None


# ---------------------------------------------------------------------------
# Votações selecionadas (Seção 6.1)
#
# id_votacao: id da votação nominal em Plenário. Quando None, o script
#   01 tenta localizá-la a partir da proposição.
# nominal: False quando a matéria foi aprovada por votação simbólica no
#   Plenário da Câmara — nesse caso a API não registra voto individual e a
#   votação não entra nas análises de voto.
# ---------------------------------------------------------------------------
VOTACOES = [
    {
        "chave": "estatuto_desarmamento",
        "nome": "Estatuto do Desarmamento",
        "proposicao": ("PL", 1555, 2003),
        "id_votacao": None,
        "nominal": False,  # aprovado em votação simbólica (23/10/2003)
    },
    {
        "chave": "maria_da_penha",
        "nome": "Lei Maria da Penha",
        "proposicao": ("PL", 4559, 2004),
        "id_votacao": None,
        "nominal": False,  # aprovado em votação simbólica (22/03/2006)
    },
    {
        "chave": "maioridade_penal",
        "nome": "Redução da maioridade penal (2º turno)",
        "proposicao": ("PEC", 171, 1993),
        "id_votacao": "14493-536",
        "nominal": True,
    },
    {
        "chave": "reforma_trabalhista",
        "nome": "Reforma Trabalhista (texto-base)",
        "proposicao": ("PL", 6787, 2016),
        "id_votacao": "2122076-348",
        "nominal": True,
    },
    {
        "chave": "fim_escala_6x1",
        "nome": "PEC do fim da escala 6x1 (2º turno)",
        "proposicao": ("PEC", 221, 2019),
        "id_votacao": "2233802-438",
        "nominal": True,
    },
]

# ---------------------------------------------------------------------------
# Tratamento (Seção 6.2)
# ---------------------------------------------------------------------------
# Votos que entram no índice de Rice. Abstenção, obstrução, "Artigo 17"
# (presidente da sessão) e ausência ficam de fora do cálculo, mas são
# mantidos na base como categorias próprias.
VOTOS_RICE = {"Sim", "Não"}
CATEGORIA_AUSENCIA = "Ausente"

# Tipos de proposição contados como produção legislativa.
TIPOS_PROPOSICAO = ["PL", "PLP", "PEC", "PDL", "PDC", "REQ", "RIC", "INC"]

# Situações (ultimoStatus_descricaoSituacao) que significam que a proposição
# NÃO avançou. Status vazio é tratado como desconhecido e sai do denominador
# da produtividade qualificada.
SITUACOES_NAO_AVANCOU = {
    "Arquivada",
    "Retirado pelo(a) Autor(a)",
    "Devolvida ao(à) Autor(a)",
    "Perdeu a Eficácia",
}
