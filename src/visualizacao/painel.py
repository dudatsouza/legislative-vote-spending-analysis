"""Painel interativo do projeto "O custo do Não" (Streamlit).

    streamlit run src/visualizacao/painel.py

Só lê os CSVs de data/processed/; rode o pipeline antes.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:  # o Streamlit só põe a pasta do script no path
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import plotly.io as pio  # noqa: E402
import streamlit as st  # noqa: E402

from src import config  # noqa: E402
from src.visualizacao.graficos import (CONTEXTO, COR_ESPECTRO, DESTAQUE, DESTAQUE_FORTE, EIXO,  # noqa: E402
                                       GRADE, MUDO, NOME_ESPECTRO, ROTULO_CURTO, TINTA, TINTA_2, VOTACOES,
                                       _ordem_partidos)
from src.analise.analisar import wilson  # noqa: E402
from src.visualizacao.mapa_hemiciclo import FONTE_WEB, figura_hemiciclo, figura_mapa_uf, metricas_uf  # noqa: E402

DADOS = config.DATA_PROCESSED
ANALISE = DADOS / "analise"
REPO = "https://github.com/dudatsouza/legislative-vote-spending-analysis"
FAIXAS = {"A": "36 meses ou mais", "B": "24 a 35 meses", "C": "12 a 23 meses"}
FAMILIAS = {
    "F1": ("Partido × voto", "Qui-quadrado (permutação de Monte Carlo quando há caselas pequenas) e V de Cramér, "
                             "por votação."),
    "F2": ("Espectro × voto", "Qui-quadrado e V de Cramér, por votação (esquerda, centro e direita)."),
    "F3": ("Gasto × produtividade", "Correlação de Spearman entre o gasto relativo e a produtividade, por "
                                    "legislatura × faixa de exercício, com IC de Bonett–Wright."),
    "F4": ("Produtividade × voto", "Mann-Whitney entre a produtividade de quem votou Sim e Não, com "
                                   "correlação rank-bisserial."),
    "F5": ("Quadrante × voto", "Qui-quadrado ou Fisher entre estar no quadrante gasto alto / produtividade "
                               "baixa e votar a favor da pauta, com razão de chances."),
    "F4E": ("Produtividade × voto, controlada pelo espectro",
            "Teste de van Elteren: o Mann-Whitney feito dentro de cada espectro e combinado."),
    "F5E": ("Quadrante × voto, controlada pelo espectro",
            "Razão de chances de Mantel-Haenszel e teste de Cochran-Mantel-Haenszel sobre as tabelas de "
            "cada espectro."),
}

LEGENDA_ESPECTRO = ":violet[■ Esquerda] :green[■ Centro] :orange[■ Direita]"
LEGISLATURAS = [55, 56, 57]

st.set_page_config(page_title="O custo do Não", page_icon="🏛️", layout="wide")

# Tema único dos gráficos: grade e eixos discretos, tooltip branco, barras
# com cantos arredondados, sem a barra de ferramentas inteira do Plotly.
pio.templates["custo"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONTE_WEB, color=TINTA, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor=GRADE, linecolor=EIXO, tickcolor=EIXO, ticks="outside", zeroline=False,
                   title_font=dict(color=TINTA_2, size=12), tickfont=dict(color=TINTA_2)),
        yaxis=dict(gridcolor=GRADE, linecolor=EIXO, tickcolor=EIXO, ticks="outside", zeroline=False,
                   title_font=dict(color=TINTA_2, size=12), tickfont=dict(color=TINTA_2)),
        hoverlabel=dict(bgcolor="white", bordercolor=EIXO, font=dict(family=FONTE_WEB, color=TINTA, size=13)),
        legend=dict(font=dict(color=TINTA_2)), barcornerradius=4))
CONFIG_PLOTLY = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
                 "toImageButtonOptions": {"format": "png", "scale": 2}}

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px;}
  [data-testid="stMetric"] {background: #f7f7f5; border: 1px solid #e1e0d9; border-radius: 10px;
                            padding: 0.7rem 0.9rem;}
  [data-testid="stMetricValue"] {font-size: 1.9rem;}
  h1 {font-size: 2.1rem !important;}
  .lead {color: #52514e; font-size: 1.05rem; margin: -0.6rem 0 1.2rem 0; max-width: 60rem;}
</style>
""", unsafe_allow_html=True)


def grafico(fig: go.Figure, alvo=st) -> None:
    """Mostra um gráfico Plotly com o tema e a configuração do painel."""
    fig.update_layout(template="custo")
    alvo.plotly_chart(fig, width="stretch", config=CONFIG_PLOTLY)


def cabecalho(titulo: str, lead: str) -> None:
    st.title(titulo)
    st.markdown(f'<p class="lead">{lead}</p>', unsafe_allow_html=True)


# --- Dados ---------------------------------------------------------------------
def assinatura() -> tuple:
    """Nome e data de modificação dos CSVs: chave dos caches, para o painel
    reler os dados quando o pipeline os regrava."""
    return tuple(sorted((str(p.relative_to(DADOS)), p.stat().st_mtime_ns)
                        for p in [*DADOS.glob("*.csv"), *ANALISE.glob("*.csv")]))


def carregar() -> dict:
    return _carregar(assinatura())


@st.cache_data(max_entries=2)
def _carregar(versao: tuple) -> dict:
    ler = lambda p: pd.read_csv(p)
    opcional = lambda p: pd.read_csv(p) if p.exists() else None
    d = {
        "base": ler(DADOS / "base_deputado_legislatura.csv"),
        "votos": ler(DADOS / "votos.csv"),
        "rice": ler(DADOS / "coesao_rice.csv"),
        "indice": ler(ANALISE / "indice_pro_pauta_deputado.csv"),
        "populacao": ler(ANALISE / "populacao_resumo.csv"),
        "votacoes": ler(ANALISE / "votacao_resumo.csv"),
        "testes": ler(ANALISE / "testes_resumo.csv"),
        "f2": ler(ANALISE / "f2_espectro_voto.csv"),
        "f3": ler(ANALISE / "f3_spearman.csv"),
        "f4": ler(ANALISE / "f4_produtividade_voto.csv"),
        "f5": ler(ANALISE / "f5_quadrante_voto.csv"),
        "f4e": opcional(ANALISE / "f4e_produtividade_voto_espectro.csv"),
        "f5e": opcional(ANALISE / "f5e_quadrante_voto_espectro.csv"),
        "logit": opcional(ANALISE / "modelo_logistico.csv"),
        "robustez": ler(ANALISE / "robustez.csv"),
        "pro_partido": ler(ANALISE / "pro_pauta_partido_votacao.csv"),
        "composicao": ler(ANALISE / "composicao_quadrante.csv"),
        "fid_grupo": ler(ANALISE / "fidelidade_grupo.csv"),
        "fid_dep": ler(ANALISE / "fidelidade_deputado.csv"),
    }
    d["mapa"] = metricas_uf(d["base"], d["indice"], d["votos"])
    return d


def num(v, casas=0, sufixo="") -> str:
    """Número no formato brasileiro."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") + sufixo


def p_txt(p: float) -> str:
    return "< 0,001" if p < 0.001 else num(p, 3)


def p_holm_txt(p: float) -> str:
    """'p (Holm) < 0,001' ou 'p (Holm) = 0,104'."""
    return "p (Holm) < 0,001" if p < 0.001 else f"p (Holm) = {num(p, 3)}"


def layout(fig: go.Figure, altura: int = 480, **kw) -> go.Figure:
    fig.update_layout(template="custo", height=altura, margin=kw.pop("margin", dict(t=30, l=10, r=10, b=10)), **kw)
    return fig


SEM_D19 = ("Os testes controlados pelo espectro e a regressão logística ainda não foram gerados. Rode a análise "
           "de novo (`./pipeline.sh --de analise`) para vê-los.")


@st.cache_data
def fig_hemiciclo(chave: str, versao: tuple = ()) -> go.Figure:
    fig = figura_hemiciclo(carregar()["votos"], chave)
    fig.update_layout(title_font_size=20, margin=dict(t=110))
    return fig


@st.cache_data
def fig_mapa(leg: int, metrica: str, versao: tuple = ()) -> go.Figure:
    dados, meta = carregar()["mapa"]
    return figura_mapa_uf(dados, meta, leg, metrica)


def classificar(s: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Quadrante e caso extremo de cada deputado do estrato, com a produtividade escolhida."""
    med_g, med_p = s["gasto_relativo"].median(), s[coluna].median()
    p_g = s["gasto_relativo"].quantile(config.PERCENTIL_GASTO_EXTREMO)
    p_p = s[coluna].quantile(config.PERCENTIL_PROD_EXTREMO)
    return s.assign(alto=s["gasto_relativo"] > med_g, baixa=~(s[coluna] > med_p),
                    q=(s["gasto_relativo"] > med_g) & ~(s[coluna] > med_p),
                    ext=(s["gasto_relativo"] > p_g) & (s[coluna] <= p_p), prod=s[coluna])


SIMBOLO_ESPECTRO = {"esquerda": "circle", "centro": "square", "direita": "triangle-up"}
CHAVES_SEM_DIRECAO = {v["chave"] for v in VOTACOES if not v["direcao_pro_pauta"]}


@st.cache_data
def fig_espectro_votacoes(versao: tuple = ()) -> go.Figure:
    """% pró-pauta (% Sim nos Precatórios) por espectro em cada votação, com IC de Wilson."""
    v = carregar()["votos"]
    v = v[v["voto_valido"].isin(["Sim", "Não"]) & v["espectro"].notna()].copy()
    v["evento"] = np.where(v["chave_votacao"].isin(CHAVES_SEM_DIRECAO), v["voto_valido"] == "Sim",
                           v["pro_pauta"].astype("boolean").fillna(False))
    g = v.groupby(["chave_votacao", "espectro"])["evento"].agg(["sum", "size"]).reset_index()
    g["pct"] = g["sum"] / g["size"] * 100
    lo, hi = wilson(g["sum"], g["size"])
    g["lo"], g["hi"] = lo * 100, hi * 100
    ordem = [x["chave"] for x in VOTACOES][::-1]
    rot = {x["chave"]: f"{ROTULO_CURTO[x['chave']].replace(chr(10), ' ')} ({pd.Timestamp(x['data']).year})"
           + (" · % Sim" if x["chave"] in CHAVES_SEM_DIRECAO else "") for x in VOTACOES}
    fig = go.Figure()
    for i, e in enumerate(config.ESPECTROS):
        s = g[g["espectro"] == e].set_index("chave_votacao").reindex(ordem).dropna(subset=["pct"])
        y = [ordem.index(c) + (i - 1) * 0.18 for c in s.index]
        fig.add_trace(go.Scatter(
            x=s["pct"], y=y, mode="markers", name=NOME_ESPECTRO[e],
            marker=dict(size=11, color=COR_ESPECTRO[e], symbol=SIMBOLO_ESPECTRO[e],
                        line=dict(color="white", width=1.5)),
            error_x=dict(type="data", symmetric=False, array=s["hi"] - s["pct"], arrayminus=s["pct"] - s["lo"],
                         color=COR_ESPECTRO[e], thickness=1.2, width=0),
            customdata=np.stack([[rot[c] for c in s.index], s["size"].astype(int)], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>" + NOME_ESPECTRO[e] + ": %{x:.0f}% "
                          "(%{customdata[1]} votos válidos)<extra></extra>"))
    layout(fig, 430, xaxis=dict(title="% dos votos válidos a favor da pauta social (IC 95%)", range=[-3, 103],
                                ticksuffix="%"),
           yaxis=dict(tickvals=list(range(len(ordem))), ticktext=[rot[c] for c in ordem], title=None,
                      showgrid=False),
           legend=dict(orientation="h", y=1.08, x=0), margin=dict(t=40, l=10, r=10, b=10))
    return fig


@st.cache_data
def tabela_caso(versao: tuple = ()) -> pd.DataFrame:
    """% Sim de cada partido na Reforma da Previdência e na PEC dos Precatórios."""
    v = carregar()["votos"]
    v = v[v["voto_valido"].isin(["Sim", "Não"]) & v["partido_id"].notna()
          & v["chave_votacao"].isin(["reforma_previdencia", "pec_precatorios"])]
    g = (v.assign(sim=v["voto_valido"] == "Sim")
         .groupby(["partido_id", "chave_votacao"])["sim"].agg(["mean", "size"]).unstack())
    g = g[(g["size"] >= config.RICE_MIN_VOTOS_VALIDOS).all(axis=1)]
    rotulo = (v.sort_values("data").groupby("partido_id")["partido"].last())
    esp = v.groupby("partido_id")["espectro"].first()
    return pd.DataFrame({"partido": rotulo.reindex(g.index), "espectro": esp.reindex(g.index),
                         "sim_previdencia": g[("mean", "reforma_previdencia")] * 100,
                         "sim_precatorios": g[("mean", "pec_precatorios")] * 100,
                         "n": g[("size", "reforma_previdencia")] + g[("size", "pec_precatorios")]}).reset_index()


GOVERNO_NAS_DUAS = 85  # % Sim nas duas votações a partir do qual o partido entra no grupo "com o governo"


def fig_caso(t: pd.DataFrame) -> go.Figure:
    """Previdência × Precatórios por partido; os que votaram com o governo nas
    duas vão para uma nota, para não sobrepor os rótulos no canto."""
    fig = go.Figure()
    fig.add_shape(type="line", x0=0, y0=0, x1=100, y1=100, line=dict(color=EIXO, width=1))
    canto = (t["sim_previdencia"] >= GOVERNO_NAS_DUAS) & (t["sim_precatorios"] >= GOVERNO_NAS_DUAS)
    contra = (t["sim_previdencia"] <= 100 - GOVERNO_NAS_DUAS) & (t["sim_precatorios"] <= 100 - GOVERNO_NAS_DUAS)
    for e in config.ESPECTROS:
        s = t[t["espectro"] == e]
        fig.add_trace(go.Scatter(
            x=s["sim_previdencia"], y=s["sim_precatorios"], mode="markers+text", name=NOME_ESPECTRO[e],
            text=s["partido"].where(~(canto | contra).loc[s.index], ""), textposition="top center",
            textfont=dict(size=11, color=TINTA_2),
            marker=dict(size=np.sqrt(s["n"]) * 2.4, color=COR_ESPECTRO[e], symbol=SIMBOLO_ESPECTRO[e],
                        opacity=0.85, line=dict(color="white", width=1.5)),
            customdata=np.stack([s["partido"], s["n"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>Previdência: %{x:.0f}% Sim<br>Precatórios: %{y:.0f}% Sim"
                          "<br>%{customdata[1]} votos válidos nas duas<extra></extra>"))
    for grupo, titulo, x, y, xa, ya, al in ((canto, "com o governo nas duas", GOVERNO_NAS_DUAS - 2, 99, "right",
                                             "top", "right"),
                                            (contra, "contra o governo nas duas", 100 - GOVERNO_NAS_DUAS + 2, 1,
                                             "left", "bottom", "left")):
        nomes = sorted(t.loc[grupo, "partido"])
        if nomes:
            linhas = [", ".join(nomes[i:i + 4]) for i in range(0, len(nomes), 4)]
            fig.add_annotation(x=x, y=y, xanchor=xa, yanchor=ya, align=al, showarrow=False,
                               font=dict(size=11, color=TINTA_2),
                               text=f"<b>{titulo} ({len(nomes)})</b><br>" + "<br>".join(linhas))
    for x, y, texto, xa, ya in ((98, 3, "a favor da Previdência,<br>contra os Precatórios", "right", "bottom"),
                                (2, 60, "contra a Previdência,<br>a favor dos Precatórios", "left", "top")):
        fig.add_annotation(x=x, y=y, text=texto, showarrow=False, xanchor=xa, yanchor=ya,
                           font=dict(size=11, color=MUDO))
    layout(fig, 560, xaxis=dict(title="Reforma da Previdência (2019): % de votos Sim", range=[-5, 105],
                                ticksuffix="%"),
           yaxis=dict(title="PEC dos Precatórios (2021): % de votos Sim", range=[-5, 108], ticksuffix="%"),
           legend=dict(orientation="h", y=1.06, x=0), hovermode="closest", margin=dict(t=40, l=10, r=10, b=10))
    return fig


def votacoes_da(leg: int) -> list[dict]:
    return [v for v in VOTACOES if v["legislatura"] == leg]


def rotulo_votacao(v: dict) -> str:
    return f"{v['nome']} ({pd.Timestamp(v['data']).year})"


# --- Abas ----------------------------------------------------------------------
def aba_visao_geral(d: dict, leg: int) -> None:
    pop = d["populacao"].set_index("legislatura").loc[leg]
    st.markdown(f"##### Números da {leg}ª legislatura")
    c = st.columns(5)
    c[0].metric("Deputados com exercício", num(pop["deputados_com_exercicio"]))
    c[1].metric("Na população", num(pop["na_populacao_d3"]),
                help=f"Deputados com 12 meses ou mais de exercício; {num(pop['excluidos_menos_12_meses'])} "
                     f"excluídos por terem menos.")
    c[2].metric("No quadrante", num(pop["no_quadrante_interesse"]),
                help="Gasto alto / produtividade baixa: acima da mediana de gasto relativo e abaixo da mediana "
                     "de produtividade, dentro da legislatura × faixa.")
    c[3].metric("Casos extremos", num(pop["casos_extremos"]), help="Gasto > P80 e produtividade ≤ P20 do estrato.")
    c[4].metric("Votações analisadas", len(votacoes_da(leg)))

    st.markdown("##### O que os dados mostram (todas as legislaturas)")
    t = d["testes"]
    f1, f2, f3, f4, f5, f4e, f5e = (t[t["familia"] == f] for f in ("F1", "F2", "F3", "F4", "F5", "F4E", "F5E"))
    sig = lambda df: int(df["significativo"].sum())
    achados = [
        ("Partido e espectro explicam o voto",
         f"{sig(f1)} de {len(f1)}",
         f"votações com associação entre partido e voto (V de Cramér de {num(f1['valor_efeito'].min(), 2)} a "
         f"{num(f1['valor_efeito'].max(), 2)}); espectro × voto em {sig(f2)} de {len(f2)}.", "votacoes"),
        ("Gasto e produtividade não andam juntos",
         f"{sig(f3)} de {len(f3)}",
         "correlações de Spearman entre gasto relativo e produtividade foram significativas, em nenhuma "
         "legislatura ou faixa de exercício." if sig(f3) == 0 else
         "correlações de Spearman entre gasto relativo e produtividade foram significativas.", "dispersao"),
    ]
    if d["logit"] is not None and len(f4e) and len(f5e):
        m2 = d["logit"][(d["logit"]["modelo"].str.startswith("M2")) & (d["logit"]["termo"] == "quadrante")].iloc[0]
        achados.append((
            "O quadrante quase não muda o voto",
            f"{sig(f5e)} de {len(f5e)}",
            f"votações com efeito do quadrante quando se comparam deputados do mesmo espectro (eram {sig(f5)} sem "
            f"o controle). Na regressão logística, OR = {num(m2['razao_chances'], 2)} "
            f"(IC 95% {num(m2['ic_inf'], 2)} a {num(m2['ic_sup'], 2)}).", "controles"))
    else:
        achados.append(("O quadrante pesa pouco no voto", f"{sig(f5)} de {len(f5)}",
                        "votações com associação entre estar no quadrante e votar a favor da pauta.", "controles"))
    for col, (titulo, numero, texto, destino) in zip(st.columns(len(achados)), achados):
        with col.container(border=True, height="stretch"):
            st.markdown(f"**{titulo}**")
            st.markdown(f"<div style='font-size:2rem;font-weight:600;line-height:1.1'>{numero}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<span style='color:{TINTA_2}'>{texto}</span>", unsafe_allow_html=True)
            if destino in PAGINAS:
                st.page_link(PAGINAS[destino], label="Ver detalhes", icon=":material/arrow_forward:")
    st.caption("Testes com correção de Holm dentro de cada família, α = 5%. Associação, não causalidade.")

    st.markdown("##### Como cada espectro votou")
    grafico(fig_espectro_votacoes(assinatura()))
    st.caption("Esquerda e direita ficam em lados opostos em quase todas as votações; as exceções são a "
               "Igualdade salarial e a 6x1, aprovadas por ampla maioria. Nos Precatórios, que não têm direção "
               "pró-pauta, o gráfico mostra o % de votos Sim.")

    st.markdown(f"##### Votações da {leg}ª legislatura")
    vr = d["votacoes"][d["votacoes"]["legislatura"] == leg]
    tabela = pd.DataFrame({
        "Votação": vr["votacao"], "Data": pd.to_datetime(vr["data"]).dt.strftime("%d/%m/%Y"),
        "Sim": vr["sim"], "Não": vr["nao"], "Abstenção": vr["abstencao"], "Ausentes": vr["ausente"],
        "Voto pró-pauta social": vr["direcao_pro_pauta"].fillna("indefinido (estudo de caso)")})
    st.dataframe(tabela, hide_index=True, width="stretch")


def aba_dispersao(d: dict, leg: int) -> None:
    base = d["base"]
    pop = base[(base["legislatura"] == leg) & base["no_quadrante_interesse"].notna()].copy()
    c1, c2, c3 = st.columns([1, 2, 2])
    faixa = c1.radio("Faixa de exercício", list(FAIXAS), format_func=lambda f: f"{f} · {FAIXAS[f]}")
    partidos = c2.multiselect("Destacar partidos", sorted(pop["partido"].dropna().unique()),
                              placeholder="Escolha um ou mais partidos")
    busca = c3.text_input("Procurar deputado", placeholder="parte do nome")
    c4, c5 = st.columns(2)
    cor_por = c4.radio("Cor", ["Quadrante", "Espectro"], horizontal=True)
    medidas = {"prod_bruta_mensal": "Todas as proposições normativas"}
    if "prod_bruta_mensal_sem_pdl" in pop:
        medidas["prod_bruta_mensal_sem_pdl"] = "Sem PDL (robustez)"
    coluna = c5.radio("Produtividade", list(medidas), format_func=medidas.get, horizontal=True,
                      help="Os PDLs incluem muitos pedidos de sustação de decretos do Executivo, típicos da "
                           "oposição. Sem eles, o quadrante é refeito com a mesma regra.")
    s = classificar(pop[pop["faixa"] == faixa].copy(), coluna)
    s["gasto_pct"] = s["gasto_relativo"] * 100
    foco = pd.Series(True, index=s.index)
    if partidos:
        foco &= s["partido"].isin(partidos)
    if busca:
        foco &= s["nome"].str.contains(busca, case=False, na=False)
    filtrando = bool(partidos or busca)

    fig = go.Figure()
    if cor_por == "Quadrante":
        grupos = [("demais deputados", ~s["q"], CONTEXTO, 7),
                  ("gasto alto / produtividade baixa", s["q"] & ~s["ext"], DESTAQUE, 8),
                  ("caso extremo", s["ext"], DESTAQUE_FORTE, 11)]
    else:
        grupos = [(NOME_ESPECTRO[e], s["espectro"] == e, COR_ESPECTRO[e], 8) for e in config.ESPECTROS]
        grupos.append(("sem partido", s["espectro"].isna(), MUDO, 7))
    for nome, filtro, cor, tam in grupos:
        for em_foco in ((True, False) if filtrando else (True,)):
            p = s[filtro & (foco if em_foco else ~foco)]
            if p.empty:
                continue
            fig.add_trace(go.Scatter(
                x=p["gasto_pct"], y=p["prod"], mode="markers", name=nome, legendgroup=nome,
                showlegend=em_foco, opacity=1.0 if em_foco else 0.15,
                marker=dict(size=tam if not filtrando or not em_foco else tam + 3, color=cor,
                            line=dict(color="white", width=1)),
                customdata=np.stack([p["nome"], p["partido"].fillna("S.PART."), p["uf"], p["meses_exercicio"],
                                     p["n_normativas"]], axis=-1),
                hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]}-%{customdata[2]})"
                               "<br>Gasto: %{x:.1f}% da cota<br>Produtividade: %{y:.2f} proposições/mês"
                               "<br>%{customdata[4]} proposições em %{customdata[3]:.0f} meses<extra></extra>")))
    med_x, med_y = s["gasto_pct"].median(), s["prod"].median()
    fig.add_vline(med_x, line=dict(color=MUDO, width=1))
    fig.add_hline(med_y, line=dict(color=MUDO, width=1))
    y_max = float(s["prod"].quantile(0.97)) * 1.25
    # Quantos deputados em cada quadrante (acima do gráfico, para não cobrir os pontos).
    quadrantes = []
    for alto, baixa in ((False, False), (True, False), (False, True), (True, True)):
        n = int((s["alto"].eq(alto) & s["baixa"].eq(baixa)).sum())
        rotulo = f"{'gasto alto' if alto else 'gasto baixo'} / {'produtividade baixa' if baixa else 'produtividade alta'}"
        texto = f"{rotulo}: **{n}** ({num(n / len(s) * 100, 0, '%')})"
        quadrantes.append(f":blue[{texto}]" if alto and baixa else texto)
    st.caption("Quadrantes — " + " · ".join(quadrantes))
    layout(fig, 560, xaxis=dict(title="Gasto da CEAP (% do teto da cota da UF)", ticksuffix="%", gridcolor=GRADE),
           yaxis=dict(title=("Proposições normativas por mês" if coluna == "prod_bruta_mensal"
                             else "Proposições por mês, sem PDL"), gridcolor=GRADE, range=[-0.04 * y_max, y_max]),
           legend=dict(orientation="h", y=-0.15), hovermode="closest")
    grafico(fig)
    acima = int((s["prod"] > y_max).sum())
    st.caption(f"{len(s)} deputados; linhas cinza = medianas do estrato "
               f"(gasto {num(med_x, 1, '%')}, produtividade {num(med_y, 2)} por mês)."
               + (f" {acima} deputado(s) acima da área visível: dê duplo clique no gráfico para ver todos."
                  if acima else ""))

    f3 = d["f3"][(d["f3"]["legislatura"] == leg) & (d["f3"]["faixa"] == faixa)]
    cols = st.columns(len(f3))
    for col, r in zip(cols, f3.itertuples()):
        medida = "produtividade bruta" if r.produtividade == "prod_bruta_mensal" else "produtividade qualificada"
        col.metric(f"Spearman ρ · gasto × {medida}", num(r.valor_efeito, 2),
                   help=f"IC 95%: {num(r.ic_inf, 2)} a {num(r.ic_sup, 2)}; {p_holm_txt(r.p_holm)}; "
                        f"n = {r.n}.")

    with st.expander(f"Deputados no quadrante gasto alto / produtividade baixa ({int(s['q'].sum())})"):
        q = s[s["q"]].sort_values("gasto_relativo", ascending=False)
        st.dataframe(pd.DataFrame({
            "Deputado": q["nome"], "Partido": q["partido"], "UF": q["uf"],
            "Gasto (% do teto)": q["gasto_pct"].round(1), "Proposições/mês": q["prod"].round(2),
            "Proposições": q["n_normativas"], "Caso extremo": q["ext"].map({True: "sim", False: ""})}),
            hide_index=True, width="stretch")


def aba_mapa(d: dict, leg: int) -> None:
    dados, meta = d["mapa"]
    opcoes = [m for m in meta if m in dados[str(leg)]]
    nome = lambda m: ("Votação: " if meta[m].get("legislatura") else "") + meta[m]["nome"]
    metrica = st.selectbox("Métrica", opcoes, format_func=nome)
    st.caption(meta[metrica]["nota"] + " Escala igual nas três legislaturas.")
    grafico(fig_mapa(leg, metrica, assinatura()))
    m = meta[metrica]
    tab = (pd.DataFrame([(uf, v[0], v[1]) for uf, v in dados[str(leg)][metrica].items()],
                        columns=["UF", m["nome"], f"n ({m['n']})"])
           .sort_values(m["nome"], ascending=False))
    with st.expander("Ranking das UFs"):
        st.dataframe(tab.round(1), hide_index=True, width="stretch")


def aba_votacoes(d: dict, leg: int) -> None:
    vs = votacoes_da(leg)
    v = st.selectbox("Votação", vs, index=len(vs) - 1, format_func=rotulo_votacao)
    grafico(fig_hemiciclo(v["chave"], assinatura()))

    c1, c2 = st.columns([3, 2])
    pp = d["pro_partido"][(d["pro_partido"]["chave_votacao"] == v["chave"]) & ~d["pro_partido"]["n_menor_5"]]
    ordem = {p: i for i, p in enumerate(_ordem_partidos()["partido_id"])}
    pp = pp.assign(_o=pp["partido"].map(ordem).fillna(99)).sort_values(["_o", "partido"])
    medida = pp["medida"].iat[0] if len(pp) else "%"
    fig = go.Figure(go.Bar(
        x=pp["pct"], y=pp["partido"], orientation="h",
        marker_color=pp["espectro"].map(COR_ESPECTRO).fillna(MUDO),
        error_x=dict(type="data", symmetric=False, array=pp["ic_sup"] - pp["pct"],
                     arrayminus=pp["pct"] - pp["ic_inf"], color=MUDO, thickness=1),
        customdata=np.stack([pp["validos"], pp["espectro"].map(NOME_ESPECTRO).fillna("—")], axis=-1),
        hovertemplate="<b>%{y}</b> (%{customdata[1]})<br>" + medida +
                      ": %{x:.0f}%<br>%{customdata[0]} votos válidos<extra></extra>"))
    layout(fig, max(320, 24 * len(pp) + 60),
           xaxis=dict(title=f"{medida} (IC 95% de Wilson)", range=[0, 100], ticksuffix="%", gridcolor=GRADE),
           yaxis=dict(autorange="reversed", title=None))
    c1.markdown(f"**{medida} por partido** · partidos com 5 ou mais votos válidos, da esquerda para a direita · "
                + LEGENDA_ESPECTRO)
    grafico(fig, c1)

    c2.markdown("**Testes desta votação**")
    t = d["testes"][d["testes"]["chave_votacao"] == v["chave"]]
    for r in t.itertuples():
        titulo, _ = FAMILIAS[r.familia]
        sig = "significativo" if r.significativo else "não significativo"
        c2.markdown(f"**{r.familia} · {titulo}** — {r.efeito} = {num(r.valor_efeito, 2)} ({r.magnitude}); "
                    f"{p_holm_txt(r.p_holm)}, {sig}.")
    f2 = d["f2"][d["f2"]["chave_votacao"] == v["chave"]]
    if len(f2):
        r = f2.iloc[0]
        c2.markdown("% de votos Sim por espectro: " + " · ".join(
            f"{NOME_ESPECTRO[e]} {num(r[f'pct_sim_{e}'], 0, '%')}" for e in config.ESPECTROS))
    f5 = d["f5"][d["f5"]["chave_votacao"] == v["chave"]]
    if len(f5):
        r = f5.iloc[0]
        c2.markdown(f"Voto {r['evento']}: {num(r['pct_evento_quadrante'], 0, '%')} no quadrante × "
                    f"{num(r['pct_evento_fora'], 0, '%')} fora dele (razão de chances "
                    f"{num(r['valor_efeito'], 2)}).")


def aba_caso(d: dict) -> None:
    t = tabela_caso(assinatura())
    st.markdown(
        "As duas votações são propostas do mesmo governo, na mesma legislatura. Na **Reforma da Previdência**, "
        "o voto a favor da pauta social é o Não. A **PEC dos Precatórios** adiou dívidas judiciais da União e "
        "abriu espaço para o Auxílio Brasil: atinge dois grupos sociais em sentidos opostos, por isso não tem "
        "direção pró-pauta. Se os partidos votassem pelo conteúdo social, ficariam espalhados; se votam "
        "pela posição em relação ao governo, ficam perto da diagonal.")
    grafico(fig_caso(t))
    diag = (t["sim_previdencia"] - t["sim_precatorios"]).abs() <= 25
    r = np.corrcoef(t["sim_previdencia"], t["sim_precatorios"])[0, 1]
    c = st.columns(3)
    c[0].metric("Partidos comparados", len(t), help="Partidos com 5 ou mais votos válidos nas duas votações.")
    c[1].metric("Perto da diagonal", f"{int(diag.sum())} de {len(t)}",
                help="Diferença de até 25 pontos percentuais entre o % Sim nas duas votações.")
    c[2].metric("Correlação entre as duas votações", num(r, 2), help="Correlação de Pearson entre os % Sim dos "
                                                                     "partidos (descritiva, sem teste).")
    st.caption("Tamanho do marcador = votos válidos do partido nas duas votações. Linha diagonal = mesmo % Sim "
               "nas duas. PRB e REPUBLICANOS são o mesmo partido.")
    with st.expander("Tabela"):
        st.dataframe(t.sort_values("sim_previdencia", ascending=False).rename(columns={
            "partido": "Partido", "espectro": "Espectro", "sim_previdencia": "Previdência (% Sim)",
            "sim_precatorios": "Precatórios (% Sim)", "n": "Votos válidos"}).drop(columns="partido_id").round(0),
            hide_index=True, width="stretch")


def aba_partidos(d: dict, leg: int) -> None:
    c1, c2 = st.columns(2)
    comp = d["composicao"][(d["composicao"]["legislatura"] == leg) & (d["composicao"]["nivel"] == "partido")]
    comp = comp[comp["n_amostra"] >= 5].sort_values("pct_no_quadrante")
    esp = _ordem_partidos().set_index("partido_id")["espectro"]
    cor = comp["grupo"].map(esp).map(COR_ESPECTRO).fillna(MUDO)
    media = d["populacao"].set_index("legislatura").loc[leg]
    media = media["no_quadrante_interesse"] / media["na_populacao_d3"] * 100
    fig = go.Figure(go.Bar(
        x=comp["pct_no_quadrante"], y=comp["rotulo"], orientation="h", marker_color=cor,
        error_x=dict(type="data", symmetric=False, array=comp["ic_sup"] - comp["pct_no_quadrante"],
                     arrayminus=comp["pct_no_quadrante"] - comp["ic_inf"], color=MUDO, thickness=1),
        customdata=np.stack([comp["n_quadrante"], comp["n_amostra"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>%{x:.0f}% no quadrante (%{customdata[0]} de %{customdata[1]})"
                      "<extra></extra>"))
    fig.add_vline(media, line=dict(color=TINTA, width=1),
                  annotation_text=f"média {num(media, 0, '%')}", annotation_position="top")
    layout(fig, max(360, 22 * len(comp) + 80),
           xaxis=dict(title="% da bancada no quadrante de interesse (IC 95%)",
                      ticksuffix="%", gridcolor=GRADE), yaxis=dict(title=None))
    c1.markdown("**Quem está no quadrante de interesse** · partidos com 5 ou mais deputados · " + LEGENDA_ESPECTRO)
    grafico(fig, c1)

    rice = d["rice"][d["rice"]["legislatura"] == leg]
    vs = votacoes_da(leg)
    tab = rice.pivot_table(index="partido_id", columns="chave_votacao", values="rice")
    tab = tab.reindex(columns=[v["chave"] for v in vs])
    ordem = [p for p in _ordem_partidos()["partido_id"] if p in tab.index]
    tab = tab.loc[ordem].dropna(how="all")
    fig = go.Figure(go.Heatmap(
        z=tab.values, x=[ROTULO_CURTO[v["chave"]].replace("\n", "<br>") for v in vs], y=tab.index,
        colorscale="Cividis",
        zmin=0, zmax=100, colorbar=dict(title="Rice", thickness=12),
        text=[["" if np.isnan(x) else f"{x:.0f}" for x in linha] for linha in tab.to_numpy(dtype=float)],
        texttemplate="%{text}", hovertemplate="<b>%{y}</b> · %{x}<br>Rice = %{z:.0f}<extra></extra>"))
    layout(fig, max(360, 22 * len(tab) + 120), yaxis=dict(autorange="reversed", title=None),
           xaxis=dict(title=None, tickangle=0, side="top"))
    c2.markdown("**Coesão (índice de Rice)** · 100 = partido votou unido; vazio = menos de 5 votos válidos")
    grafico(fig, c2)

    fg = d["fid_grupo"][(d["fid_grupo"]["legislatura"] == leg) & (d["fid_grupo"]["nivel"] == "partido")
                        & (d["fid_grupo"]["fonte"] == "todas")]
    fg = fg.pivot_table(index="rotulo", columns="medida", values="taxa").round(1)
    fg.columns = [{"fidelidade_partido": "Fidelidade à orientação do partido (%)",
                   "alinhamento_governo": "Alinhamento ao Governo (%)"}.get(c, c) for c in fg.columns]
    with st.expander("Fidelidade e alinhamento ao Governo por partido"):
        st.dataframe(fg.reset_index().rename(columns={"rotulo": "Partido"}), hide_index=True,
                     width="stretch")


def _forest(linhas: list[tuple], titulo_x: str, log: bool, referencia: float) -> go.Figure:
    """Gráfico de pontos com IC: linhas = [(rótulo, série, cor, símbolo, deslocamento)]."""
    fig = go.Figure()
    for rotulo, df, cor, simbolo, desloc in linhas:
        y = np.arange(len(df))[::-1] + desloc
        sig = df["significativo"].fillna(False).astype(bool).to_numpy()
        fig.add_trace(go.Scatter(
            x=df["valor_efeito"], y=y, mode="markers", name=rotulo,
            error_x=dict(type="data", symmetric=False, array=df["ic_sup"] - df["valor_efeito"],
                         arrayminus=df["valor_efeito"] - df["ic_inf"], color=cor, thickness=1.5)
            if "ic_inf" in df else None,
            marker=dict(symbol=[simbolo if s_ else f"{simbolo}-open" for s_ in sig], size=11, color=cor,
                        line=dict(color=cor, width=1.5)),
            customdata=np.stack([df["rotulo"], df["p_holm"].map(p_txt)], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>" + rotulo + ": %{x:.2f}<br>p (Holm) = %{customdata[1]}"
                          "<extra></extra>"))
    rot = linhas[0][1]["rotulo"].tolist()
    fig.add_vline(referencia, line=dict(color=MUDO, width=1))
    layout(fig, 60 + 46 * len(rot),
           xaxis=dict(title=titulo_x, type="log" if log else "linear", gridcolor=GRADE),
           yaxis=dict(tickvals=np.arange(len(rot))[::-1], ticktext=rot, title=None),
           legend=dict(orientation="h", y=-0.25), hovermode="closest")
    return fig


def aba_controles(d: dict) -> None:
    st.markdown(
        "O voto depende muito do espectro, e a oposição de cada época tende a propor mais. Então um efeito do "
        "quadrante ou da produtividade no voto pode ser só efeito de ser governo ou oposição. Aqui cada teste é "
        "refeito **comparando deputados do mesmo espectro**. Marcador cheio = significativo (Holm, α = 5%).")
    if d["f5e"] is None or d["f4e"] is None or d["logit"] is None:
        st.info(SEM_D19)
        return
    ordem = {v["chave"]: i for i, v in enumerate(VOTACOES)}
    nomes = {v["chave"]: rotulo_votacao(v) for v in VOTACOES}
    prep = lambda df: (df.assign(rotulo=df["chave_votacao"].map(nomes), _o=df["chave_votacao"].map(ordem))
                       .sort_values("_o").reset_index(drop=True))

    st.subheader("Quadrante gasto alto / produtividade baixa × voto pró-pauta")
    f5, f5e = prep(d["f5"]), prep(d["f5e"])
    grafico(_forest([("sem controle", f5, MUDO, "circle", 0.15),
                             ("controlado pelo espectro (Mantel-Haenszel)", f5e, DESTAQUE, "diamond", -0.15)],
                            "Razão de chances (IC 95%); > 1: quem está no quadrante vota mais a favor da pauta",
                            log=True, referencia=1))
    st.caption("Nos Precatórios, que não têm direção pró-pauta, o evento é o voto Sim.")

    st.subheader("Produtividade × voto pró-pauta")
    f4, f4e = prep(d["f4"]), prep(d["f4e"])
    f4 = f4.assign(valor_efeito=f4["rb_pro_pauta"])
    f4e = f4e.assign(valor_efeito=f4e["rb_pro_pauta"])
    com_dir = f4["valor_efeito"].notna()
    grafico(_forest([("sem controle (Mann-Whitney)", f4[com_dir].reset_index(drop=True), MUDO, "circle", 0.15),
                             ("controlado pelo espectro (van Elteren)", f4e[com_dir].reset_index(drop=True),
                              DESTAQUE, "diamond", -0.15)],
                            "Rank-bisserial; > 0: quem votou a favor da pauta tem produtividade maior",
                            log=False, referencia=0))

    st.subheader("Regressão logística do voto pró-pauta")
    st.markdown("Votações com direção pró-pauta agrupadas (sem os Precatórios); erro-padrão agrupado por deputado. "
                "Em M2 e M3, cada combinação votação × espectro tem o seu intercepto, e as combinações em que "
                "todos votaram igual saem do modelo. Razão de chances > 1: mais chance de votar a favor da pauta.")
    lg = d["logit"]
    termos = {"quadrante": "no quadrante gasto alto / produtividade baixa",
              "log_prod": "log(1 + proposições por mês)", "gasto_10pp": "+10 pontos percentuais de gasto relativo"}
    st.dataframe(pd.DataFrame({
        "Modelo": lg["modelo"], "Termo": lg["termo"].map(termos), "Razão de chances": lg["razao_chances"].round(2),
        "IC 95%": [f"{num(a, 2)} a {num(b, 2)}" for a, b in zip(lg["ic_inf"], lg["ic_sup"])],
        "p": lg["p_valor"].round(3), "Votos": lg["n_votos"], "Deputados": lg["n_deputados"]}),
        hide_index=True, width="stretch")


def aba_deputado(d: dict, leg: int) -> None:
    base = d["base"][d["base"]["legislatura"] == leg].sort_values("nome")
    opcoes = base["id_deputado"].tolist()
    rotulo = dict(zip(base["id_deputado"], base["nome"] + " (" + base["partido"].fillna("S.PART.") + "-"
                      + base["uf"] + ")"))
    dep = st.selectbox("Deputado", opcoes, format_func=rotulo.get, index=None, placeholder="Digite um nome")
    if dep is None:
        st.info("Escolha um deputado para ver o exercício, o gasto, a produtividade e os votos.")
        return
    r = base[base["id_deputado"] == dep].iloc[0]
    st.subheader(rotulo[dep])
    # Comparação com os deputados do mesmo estrato (legislatura × faixa).
    estrato = base[(base["faixa"] == r["faixa"]) & base["no_quadrante_interesse"].notna()]
    comparar = r["na_populacao"] and len(estrato) > 1

    def rel(col, fator=1.0, casas=1, sufixo=""):
        if not comparar or pd.isna(r[col]):
            return None, None
        med = estrato[col].median() * fator
        pct = (estrato[col] < r[col]).mean() * 100
        return (f"{num(r[col] * fator - med, casas, sufixo)} vs. mediana",
                f"Mediana do estrato: {num(med, casas, sufixo)}; maior que {num(pct, 0, '%')} dos "
                f"{len(estrato)} deputados da {leg}ª, faixa {r['faixa']}.")

    c = st.columns(4)
    c[0].metric("Meses de exercício", num(r["meses_exercicio"], 1), help=f"Faixa {r['faixa']}")
    delta, ajuda = rel("gasto_relativo", 100, 1, " p.p.")
    c[1].metric("Gasto da CEAP (% do teto)", num(r["gasto_relativo"] * 100, 1, "%")
                if pd.notna(r["gasto_relativo"]) else "—", delta=delta, delta_color="off",
                help=(ajuda or "") + f" R$ {num(r['gasto_total'], 2)} no total; "
                                     f"R$ {num(r['gasto_medio_mensal'], 2)} por mês.")
    delta, ajuda = rel("prod_bruta_mensal", 1, 2)
    c[2].metric("Proposições por mês", num(r["prod_bruta_mensal"], 2), delta=delta, delta_color="off",
                help=(ajuda or "") + f" {int(r['n_normativas'])} proposições normativas como primeiro autor.")
    c[3].metric("Aprovadas na Câmara", num(r["prod_qualificada"] * 100, 0, "%")
                if pd.notna(r["prod_qualificada"]) else "—",
                help=f"{num(r['n_aprovada_camara'])} de {num(r['n_com_situacao'])} com situação registrada.")
    if not r["na_populacao"]:
        quad = "fora da população de análise (menos de 12 meses de exercício)"
    else:
        quad = r["quadrante"] if pd.notna(r["quadrante"]) else "—"
        if str(r["caso_extremo"]) == "True":
            quad += " · **caso extremo** (gasto > P80 e produtividade ≤ P20 do estrato)"
    st.markdown(f"**Quadrante:** {quad} (medianas da {leg}ª legislatura, faixa {r['faixa']})")
    if comparar and pd.notna(r["gasto_relativo"]):
        outros = estrato[estrato["id_deputado"] != dep]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=outros["gasto_relativo"] * 100, y=outros["prod_bruta_mensal"], mode="markers",
            name=f"outros deputados da faixa {r['faixa']}", marker=dict(size=7, color=CONTEXTO),
            customdata=np.stack([outros["nome"], outros["partido"].fillna("S.PART.")], axis=-1),
            hovertemplate="%{customdata[0]} (%{customdata[1]})<br>%{x:.1f}% da cota · %{y:.2f} por mês"
                          "<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=[r["gasto_relativo"] * 100], y=[r["prod_bruta_mensal"]], mode="markers+text", name=r["nome"],
            text=[r["nome"]], textposition="top center", textfont=dict(color=TINTA, size=13),
            marker=dict(size=16, color=DESTAQUE, line=dict(color="white", width=2)),
            hovertemplate=f"<b>{r['nome']}</b><br>%{{x:.1f}}% da cota · %{{y:.2f}} por mês<extra></extra>"))
        fig.add_vline(estrato["gasto_relativo"].median() * 100, line=dict(color=MUDO, width=1))
        fig.add_hline(estrato["prod_bruta_mensal"].median(), line=dict(color=MUDO, width=1))
        y_max = max(float(estrato["prod_bruta_mensal"].quantile(0.97)) * 1.25, r["prod_bruta_mensal"] * 1.15)
        layout(fig, 380, xaxis=dict(title="Gasto da CEAP (% do teto)", ticksuffix="%"),
               yaxis=dict(title="Proposições por mês", range=[-0.04 * y_max, y_max]),
               legend=dict(orientation="h", y=-0.2), hovermode="closest")
        grafico(fig)

    v = d["votos"][(d["votos"]["id_deputado"] == dep) & (d["votos"]["legislatura"] == leg)]
    if v.empty:
        st.caption("Sem votos nas votações analisadas desta legislatura.")
        return
    st.markdown("**Votos**")
    st.dataframe(pd.DataFrame({
        "Votação": v["votacao"], "Data": pd.to_datetime(v["data"]).dt.strftime("%d/%m/%Y"),
        "Partido no dia": v["partido"], "Voto": v["voto_original"],
        "A favor da pauta?": v["pro_pauta"].map({True: "sim", False: "não"}).fillna("—"),
        "Orientação do partido": v["orientacao_partido"].fillna("—"),
        "Orientação do Governo": v["orientacao_governo"].fillna("—")}), hide_index=True, width="stretch")
    ind = d["indice"][(d["indice"]["id_deputado"] == dep) & (d["indice"]["legislatura"] == leg)]
    fid = d["fid_dep"][(d["fid_dep"]["id_deputado"] == dep) & (d["fid_dep"]["legislatura"] == leg)
                       & (d["fid_dep"]["fonte"] == "todas")].set_index("medida")
    partes = []
    if len(ind):
        partes.append(f"índice pró-pauta de {num(ind['indice_pro_pauta'].iat[0], 0, '%')} "
                      f"({int(ind['validos'].iat[0])} votos válidos)")
    for medida, texto in (("fidelidade_partido", "seguiu a orientação do partido"),
                          ("alinhamento_governo", "votou com o Governo")):
        if medida in fid.index:
            f = fid.loc[medida]
            partes.append(f"{texto} em {int(f['k'])} de {int(f['n'])} votos")
    if partes:
        st.caption("Nesta legislatura: " + "; ".join(partes) + ".")


def aba_testes(d: dict) -> None:
    for f, (titulo, desc) in FAMILIAS.items():
        st.markdown(f"**{f} · {titulo}** — {desc}")
    familias = st.multiselect("Famílias", list(FAMILIAS), default=list(FAMILIAS))
    so_sig = st.toggle("Só os significativos")
    t = d["testes"][d["testes"]["familia"].isin(familias)]
    if so_sig:
        t = t[t["significativo"]]
    nomes = {v["chave"]: v["nome"] for v in VOTACOES}
    st.dataframe(pd.DataFrame({
        "Família": t["familia"], "Votação": t["chave_votacao"].map(nomes).fillna("—"),
        "Legislatura": t["legislatura"].map(lambda x: f"{x:.0f}ª" if pd.notna(x) else "—"),
        "Faixa": t["faixa"].fillna("—"),
        "Produtividade": t["produtividade"].map({"prod_bruta_mensal": "bruta",
                                                 "prod_qualificada": "qualificada"}).fillna("—"),
        "n": t["n"].astype("Int64"), "Método": t["metodo"], "Efeito": t["efeito"],
        "Valor": t["valor_efeito"].round(3), "Magnitude": t["magnitude"], "p": t["p_valor"],
        "p (Holm)": t["p_holm"], "Significativo": t["significativo"]}),
        hide_index=True, width="stretch",
        column_config={"p": st.column_config.NumberColumn(format="%.4f"),
                       "p (Holm)": st.column_config.NumberColumn(format="%.4f", help="p-valor corrigido por Holm "
                                                                  "dentro da família"),
                       "Valor": st.column_config.NumberColumn(format="%.2f"),
                       "Significativo": st.column_config.CheckboxColumn(help="p (Holm) < 0,05")})
    st.caption("p-valores de permutação têm resolução 1/(N+1); 0,0001 equivale a p < 0,001.")

    st.subheader("Robustez")
    st.caption("Cada teste refeito com outra versão de uma decisão; conta quantas conclusões (significativo ou "
               "não, após Holm) se mantiveram.")
    rb = d["robustez"].dropna(subset=["conclusao_mantida"])
    rb = rb.assign(m=rb["conclusao_mantida"].astype(bool).astype(int))
    st.dataframe(rb.groupby("teste")["m"].agg(["sum", "size"]).reset_index()
                 .rename(columns={"teste": "Versão alternativa", "sum": "Conclusões mantidas", "size": "Testes"}),
                 hide_index=True, width="stretch")


def aba_dados(d: dict) -> None:
    st.markdown("##### Como os dados foram produzidos")
    etapas = [("1. Coleta", "API e arquivos em lote da Câmara; cache em disco e manifesto com sha256."),
              ("2. Validação", "Confere config, tabelas de referência e os dados brutos contra o manifesto."),
              ("3. Tratamento", "Estado diário de cada deputado, votos, Rice, produtividade e gasto relativo."),
              ("4. Análise", "Testes F1 a F5, controles pelo espectro, regressão logística e robustez."),
              ("5. Visualização", "Figuras do relatório (IEEE), páginas interativas e este painel.")]
    for col, (titulo, texto) in zip(st.columns(len(etapas)), etapas):
        with col.container(border=True, height="stretch"):
            st.markdown(f"**{titulo}**")
            st.caption(texto)

    st.markdown("##### Definições")
    st.markdown(
        f"- **Recorte:** legislaturas 55ª a 57ª, de 01/02/2015 a {config.DATA_CORTE.strftime('%d/%m/%Y')} "
        "(a 57ª está em curso).\n"
        "- **População:** deputados com 12 meses ou mais de exercício, em três faixas: A (36 ou mais), "
        "B (24 a 35) e C (12 a 23 meses).\n"
        "- **Gasto relativo:** gasto da CEAP ÷ teto da cota da UF vigente em cada mês, proporcional aos dias "
        "em exercício.\n"
        "- **Produtividade bruta:** PL, PLP, PEC e PDL apresentados como primeiro autor, por mês de exercício. "
        "**Qualificada:** proporção aprovada na Câmara.\n"
        "- **Quadrantes:** medianas de gasto e de produtividade dentro de legislatura × faixa.\n"
        "- **Pró-pauta:** voto a favor do grupo social afetado, definido votação a votação; a PEC dos "
        "Precatórios não tem direção e é tratada como estudo de caso.\n"
        "- **Espectro:** classificação de Bolognesi, Ribeiro e Codato (2023), agregada em esquerda, centro e "
        "direita.")

    st.markdown("##### Limitações")
    st.markdown(
        "- Os resultados são **associações, não relações de causa e efeito**.\n"
        "- Oito votações; a 56ª tem uma só no índice pró-pauta.\n"
        "- A classificação ideológica é de 2018 e alguns partidos foram classificados manualmente.\n"
        "- Os arquivos da Câmara mudam com o tempo: os números valem para a data de corte.")

    st.markdown("##### Fontes e dados")
    st.markdown(
        "[API de Dados Abertos da Câmara](https://dadosabertos.camara.leg.br) (votações, deputados, histórico, "
        "despesas), arquivos em lote de proposições e da CEAP, malha das UFs do IBGE e Bolognesi, Ribeiro e "
        f"Codato (2023). Código: [repositório]({REPO}).")
    bases = {
        "base_deputado_legislatura.csv": ("Base consolidada", "uma linha por deputado × legislatura", DADOS),
        "votos.csv": ("Votos", "uma linha por deputado × votação", DADOS),
        "coesao_rice.csv": ("Coesão", "Rice por partido × votação", DADOS),
        "testes_resumo.csv": ("Testes", "todas as famílias de testes", ANALISE),
        "indice_pro_pauta_deputado.csv": ("Índice pró-pauta", "por deputado × legislatura", ANALISE),
    }
    for arquivo, (titulo, desc, pasta) in bases.items():
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        c1.markdown(f"**{titulo}** · `{arquivo}` — {desc}")
        c2.download_button("Baixar CSV", (pasta / arquivo).read_bytes(), file_name=arquivo, mime="text/csv",
                           key=arquivo, icon=":material/download:", width="stretch")
    st.caption("O relatório de exploração de cada base (ydata-profiling) fica em figuras/perfil/ no repositório.")


# --- Página --------------------------------------------------------------------
PAGINAS: dict = {}  # chave → st.Page, preenchido em main() (usado pelos links da visão geral)


def _legislatura() -> int:
    return st.session_state.get("leg", 57)


def _pagina(funcao, titulo: str, lead: str, por_legislatura: bool = True):
    """Envolve uma aba numa página com cabeçalho."""
    def rodar():
        d = carregar()
        leg = _legislatura()
        cabecalho(titulo, lead + (f" Legislatura selecionada: <b>{leg}ª</b>." if por_legislatura else ""))
        if por_legislatura:
            funcao(d, leg)
        else:
            funcao(d)
    rodar.__name__ = f"pagina_{funcao.__name__}"
    return rodar


def main() -> None:
    try:
        carregar()
    except FileNotFoundError as erro:
        st.error(f"Arquivo não encontrado: {erro.filename}. Rode o pipeline antes (./pipeline.sh).")
        st.stop()

    defs = {
        "visao": (aba_visao_geral, "O custo do Não", "Deputados que gastam mais da cota parlamentar e produzem "
                  "menos votam de forma diferente em pautas sociais? E esse padrão se concentra em algum partido "
                  "ou espectro?", True, "Visão geral", ":material/home:"),
        "dispersao": (aba_dispersao, "Gasto × produtividade", "Cada ponto é um deputado. O quadrante de "
                      "interesse é o de gasto acima e produtividade abaixo das medianas do estrato.", True,
                      "Gasto × produtividade", ":material/scatter_plot:"),
        "votacoes": (aba_votacoes, "Votações", "Como cada deputado votou, ordenado da esquerda para a direita, "
                     "e os testes de cada votação.", True, "Votações", ":material/how_to_vote:"),
        "caso": (aba_caso, "Governo × ideologia", "Estudo de caso: como os partidos votaram em duas propostas do "
                 "mesmo governo, a Reforma da Previdência e a PEC dos Precatórios.", False, "Governo × ideologia",
                 ":material/compare_arrows:"),
        "controles": (aba_controles, "Controle do espectro", "O efeito do quadrante e da produtividade no voto "
                      "resiste quando se comparam deputados do mesmo espectro?", False, "Controles",
                      ":material/tune:"),
        "mapa": (aba_mapa, "Mapa por UF", "Gasto, quadrante e voto agregados por estado.", True, "Mapa por UF",
                 ":material/map:"),
        "partidos": (aba_partidos, "Partidos", "Quem está no quadrante de interesse, coesão e fidelidade.", True,
                     "Partidos", ":material/groups:"),
        "deputado": (aba_deputado, "Ficha do deputado", "Exercício, gasto, produtividade e votos de um deputado, "
                     "comparados com os colegas do mesmo estrato.", True, "Deputado", ":material/person_search:"),
        "testes": (aba_testes, "Testes estatísticos", "Todas as famílias de testes e a robustez.", False, "Testes",
                   ":material/science:"),
        "dados": (aba_dados, "Dados e método", "De onde vêm os dados, o que cada medida significa e os limites "
                  "da análise.", False, "Dados e método", ":material/dataset:"),
    }
    for chave, (funcao, titulo, lead, por_leg, rotulo, icone) in defs.items():
        PAGINAS[chave] = st.Page(_pagina(funcao, titulo, lead, por_leg), title=rotulo, icon=icone,
                                 url_path=chave, default=(chave == "visao"))
    grupos = {"Resultados": [PAGINAS[k] for k in ("visao", "dispersao", "votacoes", "caso", "controles")],
              "Explorar": [PAGINAS[k] for k in ("mapa", "partidos", "deputado")],
              "Método": [PAGINAS[k] for k in ("testes", "dados")]}
    navegacao = st.navigation(grupos)

    with st.sidebar:
        # A legislatura fica no endereço (?leg=56), para compartilhar um link já filtrado.
        try:
            inicial = int(st.query_params.get("leg", 57))
        except ValueError:
            inicial = 57
        leg = st.radio("Legislatura", LEGISLATURAS, index=LEGISLATURAS.index(inicial) if inicial in LEGISLATURAS
                       else 2, key="leg", format_func=lambda l: f"{l}ª ({config.LEGISLATURAS[l][0].year}–"
                                                              f"{config.LEGISLATURAS[l][0].year + 4})")
        st.query_params["leg"] = str(leg)
        with st.expander("Como ler", icon=":material/help:"):
            st.markdown(
                "- **Gasto relativo:** gasto da CEAP ÷ teto da cota da UF.\n"
                "- **Produtividade:** proposições normativas (PL, PLP, PEC, PDL) como primeiro autor, por mês.\n"
                "- **Quadrantes:** medianas dentro da legislatura × faixa de exercício.\n"
                "- **Pró-pauta:** voto a favor do grupo social afetado.")
        st.caption(f"Dados até {config.DATA_CORTE.strftime('%d/%m/%Y')} · UFCIMG · Ciência dos Dados · "
                   f"Joaquim Cézar Santana da Cruz e Maria Eduarda Teixeira Souza · [código]({REPO})")

    navegacao.run()


if __name__ == "__main__":
    main()
