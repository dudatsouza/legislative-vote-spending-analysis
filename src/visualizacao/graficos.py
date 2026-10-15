"""Etapa 4 — Visualização (Seção 6.4).

Uso:
    python -m src.visualizacao.graficos

Gera em figuras/:
    heatmap_coesao_rice.png            coesão partidária, partido × votação
    barras_coesao_legislatura.png      coesão média por votação/legislatura
    barras_partido_quadrante.png       % de cada partido no quadrante gasto alto / produt. baixa
    dispersao_gasto_produtividade.html dispersão interativa (plotly)
"""
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns

from src import config

DADOS, FIG = config.DATA_PROCESSED, config.FIGURAS

AZUL = "#2a78d6"        # série única / destaque
CINZA = "#b5b4ad"       # contexto
TEXTO = "#52514e"
MIN_DEPUTADOS = 5       # partidos menores poluem o heatmap e distorcem proporções

sns.set_theme(style="white", font_scale=0.95)
plt.rcParams.update({"axes.edgecolor": CINZA, "axes.labelcolor": TEXTO,
                     "xtick.color": TEXTO, "ytick.color": TEXTO,
                     "axes.spines.top": False, "axes.spines.right": False})


def heatmap_coesao(rice: pd.DataFrame) -> None:
    r = rice[rice["n_deputados"] >= MIN_DEPUTADOS]
    tabela = r.pivot_table(index="partido", columns="votacao", values="rice")
    tabela = tabela.loc[tabela.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(1.9 * tabela.shape[1] + 3, 0.32 * len(tabela) + 1.5))
    sns.heatmap(tabela, cmap="Blues", vmin=0, vmax=100, annot=True, fmt=".0f",
                linewidths=2, linecolor="white", cbar_kws={"label": "Índice de Rice"}, ax=ax)
    ax.set(title="Coesão partidária por votação (0 = dividido, 100 = unânime)",
           xlabel="", ylabel="")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(FIG / "heatmap_coesao_rice.png", dpi=200)
    plt.close(fig)


def barras_legislatura(rice: pd.DataFrame) -> None:
    """Coesão média ponderada pelo tamanho da bancada em cada votação."""
    r = rice.dropna(subset=["rice"])
    validos = r["Sim"] + r["Não"]
    media = ((r["rice"] * validos).groupby([r["legislatura"], r["votacao"]]).sum()
             / validos.groupby([r["legislatura"], r["votacao"]]).sum()).reset_index(name="rice")
    media["rotulo"] = media["votacao"] + "\n(" + media["legislatura"].astype(str) + "ª leg.)"
    media = media.sort_values("legislatura")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    barras = ax.bar(media["rotulo"], media["rice"], color=AZUL, width=0.6)
    ax.bar_label(barras, fmt="%.0f", color=TEXTO, padding=3)
    ax.set(ylim=(0, 100), ylabel="Rice médio ponderado",
           title="Coesão partidária média por votação e legislatura")
    ax.yaxis.grid(True, color="#e8e7e2")
    fig.tight_layout()
    fig.savefig(FIG / "barras_coesao_legislatura.png", dpi=200)
    plt.close(fig)


def barras_partido_quadrante(comp: pd.DataFrame) -> None:
    """Uma figura por legislatura: proporção da bancada que cai no quadrante
    gasto alto / produtividade baixa. A linha tracejada é a proporção na
    amostra inteira — barras acima dela indicam concentração."""
    for leg, c in comp.groupby("legislatura"):
        c = c[c["n_amostra"] >= MIN_DEPUTADOS].sort_values("prop_partido_no_quadrante")
        if c.empty:
            continue
        geral = c["n_quadrante"].sum() / c["n_amostra"].sum() * 100
        fig, ax = plt.subplots(figsize=(7, 0.3 * len(c) + 1.5))
        ax.barh(c["partido"], c["prop_partido_no_quadrante"], color=AZUL, height=0.6)
        ax.axvline(geral, color=TEXTO, linestyle="--", linewidth=1)
        ax.text(geral, len(c) - 0.4, f" média {geral:.0f}%", color=TEXTO, fontsize=8)
        ax.set(xlabel="% da bancada no quadrante", xlim=(0, 100),
               title=f"Gasto alto e produtividade baixa por partido — {leg}ª legislatura")
        fig.tight_layout()
        fig.savefig(FIG / f"barras_partido_quadrante_leg{leg}.png", dpi=200)
        plt.close(fig)


def dispersao_interativa(quad: pd.DataFrame) -> None:
    """Dispersão gasto × produtividade, com seletor de legislatura. A cor
    marca apenas o quadrante de interesse; o partido aparece no hover."""
    fig = go.Figure()
    legislaturas = sorted(quad["legislatura"].unique())
    for i, leg in enumerate(legislaturas):
        q = quad[quad["legislatura"] == leg]
        for destaque, cor, nome in ((False, CINZA, "demais"),
                                    (True, AZUL, "gasto alto / produt. baixa")):
            s = q[q["no_quadrante_interesse"] == destaque]
            fig.add_trace(go.Scatter(
                x=s["gasto_medio_mensal"], y=s["prod_bruta"], mode="markers", name=nome,
                visible=(i == len(legislaturas) - 1), legendgroup=nome,
                marker=dict(size=9, color=cor, line=dict(color="white", width=1)),
                customdata=s[["nome", "partido", "uf"]],
                hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]}-%{customdata[2]})"
                               "<br>Gasto médio mensal: R$ %{x:,.0f}"
                               "<br>Proposições: %{y}<extra></extra>")))
    botoes = []
    for i, leg in enumerate(legislaturas):
        vis = [False] * len(fig.data)
        vis[2 * i] = vis[2 * i + 1] = True
        botoes.append(dict(label=f"{leg}ª legislatura", method="update", args=[{"visible": vis}]))
    fig.update_layout(
        title="Gasto da CEAP × produtividade legislativa",
        xaxis_title="Gasto médio mensal da CEAP (R$)", yaxis_title="Proposições apresentadas",
        template="simple_white", hovermode="closest",
        updatemenus=[dict(buttons=botoes, active=len(legislaturas) - 1, x=1, y=1.15)])
    fig.write_html(FIG / "dispersao_gasto_produtividade.html", include_plotlyjs="cdn")


if __name__ == "__main__":
    FIG.mkdir(exist_ok=True)
    rice = pd.read_csv(DADOS / "coesao_rice.csv")
    heatmap_coesao(rice)
    barras_legislatura(rice)
    barras_partido_quadrante(pd.read_csv(DADOS / "composicao_partidaria.csv"))
    dispersao_interativa(pd.read_csv(DADOS / "quadrantes.csv"))
    print("Figuras gravadas em", FIG)
