"""Relatórios de exploração das bases tratadas (ydata-profiling).

Roda num ambiente separado (.venv_perfil), porque o ydata-profiling ainda não
suporta o Python do projeto; por isso não importa nada de src/.

    .venv_perfil/bin/python src/visualizacao/perfil_dados.py
"""
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("YDATA_SUPPRESS_BANNER", "1")
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import pandas as pd  # noqa: E402
from ydata_profiling import ProfileReport  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data" / "processed"
SAIDA = RAIZ / "figuras" / "perfil"

# Colunas que são códigos ou categorias, mesmo quando parecem números.
CATEGORICAS = {
    "id_deputado", "legislatura", "uf", "partido", "partido_id", "familia", "espectro", "sexo", "faixa",
    "quadrante", "chave_votacao", "votacao", "id_votacao", "voto_original", "voto_valido",
    "direcao_pro_pauta", "orientacao_partido", "fonte_orientacao", "orientacao_governo",
}
BOOLEANAS = {"na_populacao", "no_quadrante_interesse", "caso_extremo", "pro_pauta", "fiel_partido",
             "alinhado_governo"}

BASES = [
    ("base_deputado_legislatura",
     "Base deputado × legislatura",
     "Uma linha por deputado em cada legislatura (55ª a 57ª): exercício, partido, espectro, "
     "produtividade, gasto relativo da CEAP e quadrante."),
    ("votos",
     "Votos nas votações nominais",
     "Uma linha por deputado em cada uma das 8 votações: voto, direção pró-pauta, orientação do "
     "partido e do Governo, fidelidade e alinhamento."),
]


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if c in CATEGORICAS:
            df[c] = df[c].astype("string").astype("category")
        elif c in BOOLEANAS:
            df[c] = df[c].map({True: True, False: False, "True": True, "False": False}).astype("boolean")
    # nome identifica o deputado e não é variável de análise.
    return df.drop(columns=[c for c in ("nome",) if c in df.columns])


def gerar(arquivo: str, titulo: str, descricao: str) -> Path:
    df = preparar(pd.read_csv(DADOS / f"{arquivo}.csv"))
    tipos = {c: "categorical" for c in df.columns if c in CATEGORICAS}
    tipos.update({c: "boolean" for c in df.columns if c in BOOLEANAS})
    relatorio = ProfileReport(
        df,
        title=f"O custo do Não — {titulo}",
        dataset={"description": descricao,
                 "creator": "Joaquim Cézar Santana da Cruz e Maria Eduarda Teixeira Souza",
                 "url": "https://github.com/dudatsouza/legislative-vote-spending-analysis",
                 "copyright_holder": "Dados: Câmara dos Deputados (Dados Abertos)"},
        variables={"descriptions": {}},
        type_schema=tipos,
        correlations={"auto": {"calculate": True}, "pearson": {"calculate": False},
                      "spearman": {"calculate": False}, "kendall": {"calculate": False},
                      "phi_k": {"calculate": False}, "cramers": {"calculate": False}},
        interactions={"continuous": False},
        samples={"head": 5, "tail": 0, "random": 0},
        duplicates={"head": 0},
        progress_bar=False,
    )
    destino = SAIDA / f"perfil_{arquivo}.html"
    relatorio.to_file(destino)
    return destino


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    for arquivo, titulo, descricao in BASES:
        if not (DADOS / f"{arquivo}.csv").exists():
            sys.exit(f"{arquivo}.csv não existe; rode o tratamento antes")
        print(f"  {arquivo}: {gerar(arquivo, titulo, descricao).relative_to(RAIZ)}")
