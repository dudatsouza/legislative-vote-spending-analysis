"""Etapa 5: figuras do relatório e dos slides.

    python -m src.visualizacao.graficos

Grava em figuras/relatorio/ os PDFs (estilo SciencePlots/IEEE) e em
figuras/interativas/ as versões em Plotly. O espectro usa roxo, água e
laranja (nunca o par vermelho/azul), cada um com um marcador próprio.
"""
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402

from src import config  # noqa: E402

DADOS = config.DATA_PROCESSED
ANALISE = DADOS / "analise"
FIG = config.FIGURAS_RELATORIO
INTERATIVAS = config.FIGURAS_INTERATIVAS

COLUNA, PAGINA = 3.5, 7.16  # larguras IEEE em polegadas

COR_ESPECTRO = {"esquerda": "#7b3294", "centro": "#1baf7a", "direita": "#e66101"}
MARCADOR_ESPECTRO = {"esquerda": "o", "centro": "s", "direita": "^"}
NOME_ESPECTRO = {"esquerda": "Esquerda", "centro": "Centro", "direita": "Direita"}
DESTAQUE = "#2a78d6"        # quadrante de interesse
DESTAQUE_FORTE = "#104281"  # casos extremos
CONTEXTO = "#b5b4ad"        # demais deputados
TINTA, TINTA_2, MUDO = "#0b0b0b", "#52514e", "#898781"
GRADE, EIXO, SEM_DADO = "#e1e0d9", "#c3c2b7", "#f0efec"

ROTULO_CURTO = {
    "maioridade_penal": "Maioridade\npenal",
    "teto_gastos": "Teto de\ngastos",
    "reforma_trabalhista": "Reforma\ntrabalhista",
    "reforma_previdencia": "Reforma\nPrevidência",
    "pec_precatorios": "PEC\nPrecatórios",
    "igualdade_salarial": "Igualdade\nsalarial",
    "marco_temporal": "Marco\ntemporal",
    "fim_escala_6x1": "Fim da\nescala 6x1",
}
VOTACOES = sorted(config.VOTACOES, key=lambda v: v["data"])
MIN_VALIDOS = config.RICE_MIN_VOTOS_VALIDOS


# --- Estilo e utilitários ------------------------------------------------------
def aplicar_estilo() -> str:
    """SciencePlots (IEEE), sem LaTeX se ele não estiver instalado."""
    try:
        import scienceplots  # noqa: F401  (registra os estilos)
        estilo = config.ESTILO_GRAFICOS if shutil.which("latex") else config.ESTILO_GRAFICOS_SEM_LATEX
        plt.style.use(estilo)
        usado = "+".join(estilo)
    except ImportError:
        plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
                             "font.size": 8, "mathtext.fontset": "stix"})
        usado = "fallback serifado (SciencePlots ausente)"
    plt.rcParams.update({
        "axes.prop_cycle": matplotlib.cycler(color=[TINTA]),
        "axes.edgecolor": EIXO, "axes.labelcolor": TINTA, "axes.linewidth": 0.6,
        "xtick.color": TINTA_2, "ytick.color": TINTA_2, "xtick.labelcolor": TINTA, "ytick.labelcolor": TINTA,
        "xtick.minor.visible": False, "ytick.minor.visible": False,
        "xtick.top": False, "ytick.right": False, "xtick.direction": "out", "ytick.direction": "out",
        "grid.color": GRADE, "grid.linewidth": 0.5, "grid.linestyle": "-",
        "legend.frameon": False, "legend.fontsize": 7, "axes.titlesize": 8,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })
    return usado


def _salvar(fig, nome: str) -> None:
    fig.savefig(FIG / f"{nome}.pdf")
    plt.close(fig)


def _limpar_eixos(ax, grade_y=False, grade_x=False) -> None:
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    if grade_y:
        ax.yaxis.grid(True)
    if grade_x:
        ax.xaxis.grid(True)
    ax.set_axisbelow(True)


def _texto_sobre(cor) -> str:
    """Tinta legível sobre uma célula colorida (branco ou quase preto)."""
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(cor))
    return TINTA if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.30 else "white"


def _ordem_partidos() -> pd.DataFrame:
    """Partidos da esquerda para a direita pelo escore de Bolognesi et al. (2023)."""
    esp = pd.read_csv(config.ESPECTRO_CSV)
    esp["espectro"] = esp["categoria_artigo"].map(config.MAPA_ESPECTRO)
    esp["escore"] = pd.to_numeric(esp["escore_artigo"], errors="coerce").fillna(10.0)
    esp["_e"] = esp["espectro"].map({e: i for i, e in enumerate(config.ESPECTROS)})
    return esp.sort_values(["_e", "escore"])[["partido_id", "espectro", "escore"]].reset_index(drop=True)


def _validos(votos: pd.DataFrame) -> pd.DataFrame:
    v = votos[votos["voto_valido"].isin(["Sim", "Não"]) & votos["partido_id"].notna()].copy()
    v["pro_pauta"] = v["pro_pauta"].astype("boolean")
    return v


def _rotulo_votacao(v: dict, com_direcao=True) -> str:
    rot = ROTULO_CURTO[v["chave"]]
    if com_direcao and v["direcao_pro_pauta"]:
        rot += f"\n(pró: {v['direcao_pro_pauta']})"
    return rot


# --- V1: heatmap partido × votação ---------------------------------------------
def _heatmap(tabela: pd.DataFrame, votacoes: list[dict], cmap, vmin, vmax, rotulo_barra: str,
             nome: str, ticks_barra=None) -> None:
    ordem = _ordem_partidos()
    ordem = ordem[ordem["partido_id"].isin(tabela.index)]
    tabela = tabela.loc[ordem["partido_id"], [v["chave"] for v in votacoes]]
    tabela = pd.DataFrame(tabela.to_numpy(dtype=float, na_value=np.nan), index=tabela.index,
                          columns=tabela.columns)
    n_lin, n_col = tabela.shape

    fig, ax = plt.subplots(figsize=(COLUNA, 0.135 * n_lin + 1.15))
    cmap = plt.get_cmap(cmap).copy()
    cmap.set_bad(SEM_DADO)
    im = ax.imshow(np.ma.masked_invalid(tabela.to_numpy(dtype=float)), cmap=cmap, vmin=vmin, vmax=vmax,
                   aspect="auto", interpolation="nearest")
    for i in range(n_lin):
        for j in range(n_col):
            val = tabela.iat[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=4.6,
                        color=_texto_sobre(cmap((val - vmin) / (vmax - vmin))))
    ax.set_xticks(np.arange(-0.5, n_col), minor=True)
    ax.set_yticks(np.arange(-0.5, n_lin), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.9)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)

    ax.set_xticks(range(n_col), [_rotulo_votacao(v) for v in votacoes], fontsize=5.2)
    ax.xaxis.tick_top()
    ax.set_yticks(range(n_lin), tabela.index, fontsize=5.6)
    legs = [v["legislatura"] for v in votacoes]
    for j in range(1, n_col):
        if legs[j] != legs[j - 1]:
            ax.axvline(j - 0.5, color=TINTA, linewidth=0.9)
    inicio = 0
    for e, bloco in ordem.groupby("espectro", sort=False):
        fim = inicio + len(bloco)
        if fim < n_lin:
            ax.axhline(fim - 0.5, color=TINTA, linewidth=0.9)
        ax.annotate(NOME_ESPECTRO[e], xy=(1.01, 1 - (inicio + fim) / 2 / n_lin), xycoords="axes fraction",
                    rotation=270, va="center", ha="left", fontsize=6, color=TINTA_2)
        inicio = fim
    for leg in sorted(set(legs)):
        cols = [j for j, l in enumerate(legs) if l == leg]
        ax.annotate(f"{leg}ª legislatura", xy=((np.mean(cols) + 0.5) / n_col, -0.012), xycoords="axes fraction",
                    ha="center", va="top", fontsize=5.6, color=TINTA_2)

    barra = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.025, pad=0.045, aspect=40,
                         ticks=ticks_barra)
    barra.set_label(rotulo_barra, fontsize=6)
    barra.ax.tick_params(labelsize=5.5, length=2)
    barra.outline.set_visible(False)
    _salvar(fig, nome)


def v1_heatmap_pro_pauta(validos: pd.DataFrame) -> None:
    """% pró-pauta por partido × votação (sem os Precatórios, de direção ambígua)."""
    com_dir = [v for v in VOTACOES if v["direcao_pro_pauta"]]
    d = validos[validos["direcao_pro_pauta"].notna()]
    g = d.groupby(["partido_id", "chave_votacao"])["pro_pauta"].agg(["size", "sum"])
    pct = (g["sum"] / g["size"] * 100).where(g["size"] >= MIN_VALIDOS).unstack()
    pct = pct.dropna(how="all")
    _heatmap(pct, com_dir, config.COLORMAP_DIVERGENTE, 0, 100,
             "% dos votos válidos do partido a favor da pauta social", "v1_heatmap_pro_pauta",
             ticks_barra=[0, 25, 50, 75, 100])


# --- V7: Spearman gasto × produtividade ----------------------------------------
def v7_spearman(f3: pd.DataFrame) -> None:
    metricas = (("prod_bruta_mensal", "Produtividade bruta mensal"),
                ("prod_qualificada", "Produtividade qualificada"))
    estratos = f3[["legislatura", "faixa"]].drop_duplicates().sort_values(["legislatura", "faixa"])
    estratos = estratos.reset_index(drop=True)
    y = {(l, f): len(estratos) - 1 - i - 0.6 * (l - estratos["legislatura"].min())
         for i, (l, f) in enumerate(zip(estratos["legislatura"], estratos["faixa"]))}

    fig, eixos = plt.subplots(1, 2, figsize=(COLUNA, 2.7), sharey=True)
    for ax, (m, titulo) in zip(eixos, metricas):
        s = f3[f3["produtividade"] == m]
        yy = [y[(l, f)] for l, f in zip(s["legislatura"], s["faixa"])]
        ax.axvline(0, color=TINTA_2, linewidth=0.6)
        ax.hlines(yy, s["ic_inf"], s["ic_sup"], color=TINTA_2, linewidth=1.0)
        sig = s["significativo"].astype(bool).to_numpy()
        ax.scatter(s["estatistica"][sig], np.array(yy)[sig], s=14, color=TINTA, zorder=3)
        ax.scatter(s["estatistica"][~sig], np.array(yy)[~sig], s=14, facecolors="white",
                   edgecolors=TINTA, linewidths=0.8, zorder=3)
        ax.set(xlim=(-0.8, 0.8), title=titulo, xlabel=r"$\rho$ de Spearman (IC 95%)")
        ax.set_xticks([-0.5, 0, 0.5], ["−0,5", "0", "0,5"])
        _limpar_eixos(ax, grade_x=True)
        ax.tick_params(axis="y", length=0)
    n = f3[f3["produtividade"] == "prod_bruta_mensal"].set_index(["legislatura", "faixa"])["n"]
    eixos[0].set_yticks(list(y.values()),
                        [f"{l}ª · faixa {f} (n={int(n[(l, f)])})" for l, f in y], fontsize=6)
    fig.tight_layout(w_pad=0.6)
    fig.text(0.99, -0.01, "Círculo vazio = não significativo; cheio = significativo (Holm, α = 0,05)",
             ha="right", va="top", fontsize=5.5, color=TINTA_2)
    _salvar(fig, "v7_spearman")


# --- V8: % da bancada no quadrante de interesse --------------------------------
def v8_quadrante_partido(comp: pd.DataFrame) -> None:
    c = comp[comp["nivel"] == "partido"].copy()
    c = c[c["n_amostra"] >= MIN_VALIDOS]
    esp = _ordem_partidos().set_index("partido_id")["espectro"]
    c["espectro"] = c["grupo"].map(esp)
    legs = sorted(c["legislatura"].unique())
    altura = 0.14 * c.groupby("legislatura").size().max() + 0.9

    fig, eixos = plt.subplots(1, len(legs), figsize=(PAGINA, altura))
    for ax, leg in zip(eixos, legs):
        s = c[c["legislatura"] == leg].sort_values("pct_no_quadrante")
        tot = comp[(comp["nivel"] == "partido") & (comp["legislatura"] == leg)]
        geral = tot["n_quadrante"].sum() / tot["n_amostra"].sum() * 100
        yy = np.arange(len(s))
        ax.barh(yy, s["pct_no_quadrante"], height=0.55, color=s["espectro"].map(COR_ESPECTRO), zorder=2)
        ax.hlines(yy, s["ic_inf"], s["ic_sup"], color=TINTA_2, linewidth=0.6, zorder=3)
        ax.axvline(geral, color=TINTA, linewidth=0.7, zorder=4)
        ax.text(geral, 1.0, f"média {geral:.0f}%", transform=ax.get_xaxis_transform(), fontsize=5.8,
                color=TINTA, ha="center", va="bottom")
        ax.set_yticks(yy, [f"{r} ({n})" for r, n in zip(s["rotulo"], s["n_amostra"])], fontsize=5.8)
        ax.set(xlim=(0, 100), ylim=(-0.6, len(s) - 0.4), xlabel="% da bancada no quadrante (IC 95%)")
        ax.set_title(f"{leg}ª legislatura", pad=10)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.tick_params(axis="y", length=0)
        _limpar_eixos(ax, grade_x=True)
    alcas = [plt.Rectangle((0, 0), 1, 1, color=COR_ESPECTRO[e]) for e in config.ESPECTROS]
    fig.legend(alcas, [NOME_ESPECTRO[e] for e in config.ESPECTROS], loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(w_pad=1.2)
    _salvar(fig, "v8_quadrante_partido")


# --- V13: razão de chances do quadrante, sem e com controle do espectro --------
def v13_controle_espectro(f5: pd.DataFrame, f5e: pd.DataFrame) -> None:
    ordem = {v["chave"]: i for i, v in enumerate(VOTACOES)}
    chaves = sorted(f5["chave_votacao"], key=ordem.get, reverse=True)
    yy = {c: i for i, c in enumerate(chaves)}
    fig, ax = plt.subplots(figsize=(COLUNA, 2.7))
    ax.axvline(1, color=TINTA_2, linewidth=0.6)
    series = ((f5, +0.17, TINTA_2, "o", "sem controle"),
              (f5e, -0.17, DESTAQUE, "D", "controlado pelo espectro (Mantel-Haenszel)"))
    for df, desloc, cor, marca, rotulo in series:
        d = df.set_index("chave_votacao").loc[chaves]
        y = np.array([yy[c] for c in chaves]) + desloc
        ax.hlines(y, d["ic_inf"].clip(lower=0.05), d["ic_sup"].clip(upper=40), color=cor, linewidth=0.9)
        sig = d["significativo"].fillna(False).astype(bool).to_numpy()
        ax.scatter(d["valor_efeito"][sig], y[sig], s=16, color=cor, marker=marca, zorder=3, label=rotulo)
        ax.scatter(d["valor_efeito"][~sig], y[~sig], s=16, facecolors="white", edgecolors=cor, marker=marca,
                   linewidths=0.8, zorder=3)
    rot = [ROTULO_CURTO[c].replace("\n", " ") + (" (voto Sim)" if c in {v["chave"] for v in VOTACOES
                                                                     if not v["direcao_pro_pauta"]} else "")
           for c in chaves]
    ax.set_yticks(list(yy.values()), rot, fontsize=6)
    ax.tick_params(axis="y", length=0)
    ax.set_xscale("log")
    ax.set_xlim(0.1, 40)
    ax.set_xticks([0.1, 0.25, 0.5, 1, 2, 4, 10, 25], ["0,1", "0,25", "0,5", "1", "2", "4", "10", "25"])
    ax.minorticks_off()
    ax.set_xlabel("Razão de chances do voto pró-pauta (IC 95%)")
    _limpar_eixos(ax, grade_x=True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.2), ncol=1, handletextpad=0.3, fontsize=6)
    ax.text(1.0, -0.47, "Marcador cheio = significativo (Holm, α = 0,05). OR > 1: quem está no quadrante "
                        "vota mais a favor da pauta.", transform=ax.transAxes, ha="right", fontsize=5.2,
            color=TINTA_2, wrap=True)
    _salvar(fig, "v13_controle_espectro")


# --- Dispersão interativa ------------------------------------------------------
def dispersao_interativa(base: pd.DataFrame) -> None:
    pop = base[base["no_quadrante_interesse"].notna()].copy()
    pop["q"] = pop["no_quadrante_interesse"].astype(bool)
    pop["ext"] = pop["caso_extremo"].astype("boolean").fillna(False).astype(bool)
    pop["gasto_pct"] = pop["gasto_relativo"] * 100
    estratos = sorted(pop.groupby(["legislatura", "faixa"]).groups)
    grupos = (("demais deputados", lambda s: ~s["q"], CONTEXTO, 7),
              ("gasto alto / produtividade baixa", lambda s: s["q"] & ~s["ext"], DESTAQUE, 8),
              ("caso extremo (gasto > P80 e produtividade ≤ P20)", lambda s: s["ext"], DESTAQUE_FORTE, 11))
    faixa_txt = {"A": "36 meses ou mais", "B": "24 a 35 meses", "C": "12 a 23 meses"}

    fig, botoes, padrao = go.Figure(), [], len(estratos) - 3  # 57ª, faixa A
    for i, (leg, faixa) in enumerate(estratos):
        s = pop[(pop["legislatura"] == leg) & (pop["faixa"] == faixa)]
        for nome, filtro, cor, tam in grupos:
            p = s[filtro(s)]
            fig.add_trace(go.Scatter(
                x=p["gasto_pct"], y=p["prod_bruta_mensal"], mode="markers", name=nome, legendgroup=nome,
                visible=(i == padrao), showlegend=True,
                marker=dict(size=tam, color=cor, line=dict(color="white", width=1.5)),
                customdata=np.stack([p["nome"], p["partido"], p["uf"], p["meses_exercicio"],
                                     p["n_normativas"]], axis=-1) if len(p) else None,
                hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]}-%{customdata[2]})"
                               "<br>Gasto: %{x:.1f}% da cota"
                               "<br>Produtividade: %{y:.2f} proposições/mês"
                               "<br>%{customdata[4]} proposições em %{customdata[3]:.0f} meses<extra></extra>")))
        med_x, med_y = s["gasto_pct"].median(), s["prod_bruta_mensal"].median()
        linhas = [dict(type="line", xref="x", yref="paper", x0=med_x, x1=med_x, y0=0, y1=1,
                       line=dict(color=MUDO, width=1)),
                  dict(type="line", xref="paper", yref="y", x0=0, x1=1, y0=med_y, y1=med_y,
                       line=dict(color=MUDO, width=1))]
        # Vista inicial até ~P97; o duplo clique mostra todos os pontos.
        y_max = float(s["prod_bruta_mensal"].quantile(0.97)) * 1.25
        acima = int((s["prod_bruta_mensal"] > y_max).sum())
        nota = [dict(text=(f"{acima} deputado(s) acima da área visível — duplo clique para ver todos"
                           if acima else ""), xref="paper", yref="paper", x=0.99, y=0.99, xanchor="right",
                     yanchor="top", showarrow=False, bgcolor="rgba(255,255,255,0.85)",
                     font=dict(size=11, color=TINTA_2))]
        layout_estrato = {"shapes": linhas, "annotations": nota, "yaxis.range": [-0.04 * y_max, y_max],
                          "yaxis.autorange": False}
        vis = [False] * (len(estratos) * len(grupos))
        vis[i * len(grupos):(i + 1) * len(grupos)] = [True] * len(grupos)
        botoes.append(dict(label=f"{leg}ª legislatura · faixa {faixa} (n={len(s)})",
                           method="update", args=[{"visible": vis}, layout_estrato]))
        if i == padrao:
            fig.update_layout(shapes=linhas, annotations=nota, yaxis_range=[-0.04 * y_max, y_max])
    fig.update_layout(
        title=dict(text="Gasto da CEAP × produtividade legislativa"
                        "<br><sup>Cada ponto é um deputado; linhas cinza são as medianas do estrato. "
                        "Faixas: " + "; ".join(f"{k} = {v}" for k, v in faixa_txt.items()) + ".</sup>"),
        xaxis=dict(title="Gasto da CEAP (% do teto da cota da UF)", ticksuffix="%", gridcolor=GRADE,
                   zeroline=False),
        yaxis=dict(title="Proposições normativas por mês de exercício", gridcolor=GRADE, zeroline=False),
        template="simple_white", hovermode="closest", height=620,
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=TINTA),
        legend=dict(orientation="h", y=-0.15),
        updatemenus=[dict(buttons=botoes, active=padrao, x=0, xanchor="left", y=1.12, yanchor="top")],
        margin=dict(t=130))
    fig.write_html(INTERATIVAS / "dispersao_gasto_produtividade.html", include_plotlyjs="cdn")


# --- Execução ------------------------------------------------------------------
if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    INTERATIVAS.mkdir(parents=True, exist_ok=True)
    estilo = aplicar_estilo()
    votos = pd.read_csv(DADOS / "votos.csv")
    validos = _validos(votos)
    base = pd.read_csv(DADOS / "base_deputado_legislatura.csv")

    v1_heatmap_pro_pauta(validos)
    v7_spearman(pd.read_csv(ANALISE / "f3_spearman.csv"))
    v8_quadrante_partido(pd.read_csv(ANALISE / "composicao_quadrante.csv"))
    v13_controle_espectro(pd.read_csv(ANALISE / "f5_quadrante_voto.csv"),
                          pd.read_csv(ANALISE / "f5e_quadrante_voto_espectro.csv"))
    dispersao_interativa(base)
    from src.visualizacao.mapa_hemiciclo import gerar_todas
    gerar_todas(base, votos)
    print(f"Figuras gravadas em {config.FIGURAS} (estilo: {estilo})")
