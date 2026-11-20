"""Mapa por UF e hemiciclo das votações, em PDF (V11, V12) e em Plotly.

O mapa em grade (uma UF = um quadrado) ao lado do geográfico corrige o viés
de área: no mapa do IBGE, AM e PA dominam e o DF quase não aparece.
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from matplotlib import colormaps
from matplotlib.colors import Normalize, to_hex
from matplotlib.ticker import MaxNLocator
from plotly.subplots import make_subplots

from src import config
from src.visualizacao.graficos import (ANALISE, COLUNA, DADOS, EIXO, FIG, GRADE, INTERATIVAS, MUDO, NOME_ESPECTRO, PAGINA,
                                       ROTULO_CURTO, TINTA, TINTA_2, VOTACOES, _ordem_partidos, _salvar,
                                       _texto_sobre)

FONTE_WEB = "system-ui, -apple-system, 'Segoe UI', sans-serif"

# (coluna, linha) de cada UF no mapa em grade, linha 0 no topo.
GRADE_UF = {
    "RR": (2, 0), "AP": (4, 0),
    "AM": (1, 1), "PA": (3, 1), "MA": (4, 1), "CE": (5, 1), "RN": (6, 1),
    "AC": (0, 2), "RO": (1, 2), "MT": (2, 2), "TO": (3, 2), "PI": (4, 2), "PE": (5, 2), "PB": (6, 2),
    "MS": (2, 3), "GO": (3, 3), "DF": (4, 3), "BA": (5, 3), "AL": (6, 3),
    "PR": (2, 4), "SP": (3, 4), "MG": (4, 4), "ES": (5, 4), "SE": (6, 4),
    "SC": (2, 5), "RJ": (4, 5),
    "RS": (2, 6),
}

# Azul × laranja: seguro para daltonismo e sem o vermelho/azul partidário.
COR_VOTO = {"Sim": "#2a78d6", "Não": "#e66101", "Abstenção": "#898781", "Ausente": "#ffffff"}
BORDA_VOTO = {"Sim": "#2a78d6", "Não": "#e66101", "Abstenção": "#898781", "Ausente": "#b5b4ad"}
ORDEM_VOTO = ("Sim", "Não", "Abstenção", "Ausente")


# --- Dados por UF --------------------------------------------------------------
def _populacao(base: pd.DataFrame) -> pd.DataFrame:
    """Mesma população dos quadrantes."""
    pop = base[base["no_quadrante_interesse"].notna()].copy()
    pop["q"] = pop["no_quadrante_interesse"].astype(bool)
    return pop


def metricas_uf(base: pd.DataFrame, indice: pd.DataFrame, votos: pd.DataFrame) -> tuple[dict, dict]:
    """(dados, meta), com dados[leg][métrica][uf] = [valor, n]."""
    pop = _populacao(base)
    meta = {
        "gasto_rel": dict(nome="Gasto relativo da CEAP", unidade="% do teto da UF", fmt=".0f", sufixo="%",
                          escala="cividis", n="deputados",
                          nota="Mediana do gasto em relação ao teto da cota da UF."),
        "gasto_rs": dict(nome="Gasto mensal em reais", unidade="R$ mil por mês", fmt=".1f", sufixo=" mil",
                         escala="cividis", n="deputados",
                         nota="Mediana do gasto médio mensal, sem ajuste pelo teto: acompanha o custo das "
                              "passagens de cada UF, e por isso a análise usa o gasto relativo."),
        "quadrante": dict(nome="No quadrante de interesse", unidade="% dos deputados", fmt=".0f", sufixo="%",
                          escala="cividis", n="deputados",
                          nota="% dos deputados da UF no quadrante gasto alto / produtividade baixa "
                               "(medianas da legislatura × faixa)."),
        "pro_pauta": dict(nome="Índice pró-pauta", unidade="% dos votos a favor da pauta social", fmt=".0f",
                          sufixo="%", escala="PuOr", n="deputados",
                          nota="Média do índice pró-pauta dos deputados da UF (sem os Precatórios)."),
    }
    linhas = []
    for (leg, uf), g in pop.groupby(["legislatura", "uf"]):
        linhas += [(leg, "gasto_rel", uf, g["gasto_relativo"].median() * 100, len(g)),
                   (leg, "gasto_rs", uf, g["gasto_medio_mensal"].median() / 1000, len(g)),
                   (leg, "quadrante", uf, g["q"].mean() * 100, len(g))]
    for (leg, uf), g in indice.dropna(subset=["indice_pro_pauta"]).groupby(["legislatura", "uf"]):
        linhas.append((leg, "pro_pauta", uf, g["indice_pro_pauta"].mean(), len(g)))
    validos = votos[votos["pro_pauta"].notna()]
    for v in VOTACOES:
        if not v["direcao_pro_pauta"]:
            continue
        mid = f"voto_{v['chave']}"
        meta[mid] = dict(nome=f"{v['nome']} ({pd.Timestamp(v['data']).year})",
                         unidade="% dos votos válidos a favor da pauta", fmt=".0f", sufixo="%",
                         escala="PuOr", n="votos válidos", legislatura=v["legislatura"],
                         nota=f"% dos votos Sim/Não da UF a favor da pauta social (pró-pauta: "
                              f"{v['direcao_pro_pauta']}).")
        vv = validos[validos["chave_votacao"] == v["chave"]]
        for uf, g in vv.groupby("uf"):
            linhas.append((v["legislatura"], mid, uf, g["pro_pauta"].astype(bool).mean() * 100, len(g)))

    df = pd.DataFrame(linhas, columns=["legislatura", "metrica", "uf", "valor", "n"])
    dados: dict = {}
    for (leg, m), g in df.groupby(["legislatura", "metrica"]):
        dados.setdefault(str(leg), {})[m] = {r.uf: [round(float(r.valor), 2), int(r.n)] for r in g.itertuples()}
    # Mesma escala em todas as legislaturas.
    for m, d in meta.items():
        vals = df.loc[df["metrica"] == m, "valor"]
        if d["escala"] == "PuOr":
            d["cmin"], d["cmax"] = 0.0, 100.0
        else:
            d["cmin"], d["cmax"] = float(np.floor(vals.min())), float(np.ceil(vals.max()))
    return dados, meta


# --- Mapa interativo -----------------------------------------------------------
def _area_assinada(anel: list) -> float:
    x, y = np.asarray(anel, dtype=float).T
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def _orientar_d3(geometria: dict) -> dict:
    """Inverte os anéis para a orientação do d3-geo (o IBGE segue o RFC 7946)."""
    def poligono(aneis):
        return [anel if (_area_assinada(anel) < 0) == (i == 0) else anel[::-1] for i, anel in enumerate(aneis)]
    if geometria["type"] == "Polygon":
        return {**geometria, "coordinates": poligono(geometria["coordinates"])}
    if geometria["type"] == "MultiPolygon":
        return {**geometria, "coordinates": [poligono(p) for p in geometria["coordinates"]]}
    return geometria


def _malha() -> dict:
    # Sem data/raw/ (painel publicado), usa a cópia versionada.
    caminho = config.MALHA_UF_GEOJSON
    if not caminho.exists():
        caminho = config.DATA_REFERENCIA / "malha_uf.geojson"
    malha = json.loads(caminho.read_text(encoding="utf-8"))
    for f in malha["features"]:
        f["properties"]["sigla"] = config.COD_IBGE_UF[f["properties"]["codarea"]]
        f["geometry"] = _orientar_d3(f["geometry"])
    return malha


def _escala_plotly(nome: str) -> list:
    cmap = colormaps[nome]
    return [[t, to_hex(cmap(t))] for t in np.linspace(0, 1, 11)]


def _cor_texto(nome: str, cmin: float, cmax: float, valor) -> str:
    if valor is None:
        return TINTA_2
    return _texto_sobre(colormaps[nome](Normalize(cmin, cmax, clip=True)(valor)))


def mapa_interativo(base, indice, votos) -> None:
    dados, meta = metricas_uf(base, indice, votos)
    texto = {leg: {m: {uf: _cor_texto(meta[m]["escala"], meta[m]["cmin"], meta[m]["cmax"], v[0])
                       for uf, v in ms.items()} for m, ms in d.items()} for leg, d in dados.items()}
    ufs = sorted(GRADE_UF)
    leg0, m0 = "57", "gasto_rel"
    z0 = [dados[leg0][m0].get(uf, [None])[0] for uf in ufs]

    fig = make_subplots(rows=1, cols=2, column_widths=[0.55, 0.45], horizontal_spacing=0.02,
                        specs=[[{"type": "geo"}, {"type": "xy"}]],
                        subplot_titles=("Mapa geográfico (IBGE)", "Mapa em grade (UFs do mesmo tamanho)"))
    fig.add_trace(go.Choropleth(
        geojson=_malha(), featureidkey="properties.sigla", locations=ufs, z=z0, coloraxis="coloraxis",
        marker=dict(line=dict(color="white", width=0.8)), hovertemplate="%{customdata}<extra></extra>",
        customdata=[""] * len(ufs)), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=[GRADE_UF[uf][0] for uf in ufs], y=[-GRADE_UF[uf][1] for uf in ufs], mode="markers+text",
        text=ufs, textfont=dict(size=12, color=[TINTA] * len(ufs), family=FONTE_WEB),
        marker=dict(symbol="square", size=40, color=z0, coloraxis="coloraxis", line=dict(color="white", width=1)),
        hovertemplate="%{customdata}<extra></extra>", customdata=[""] * len(ufs), showlegend=False),
        row=1, col=2)
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_xaxes(visible=False, range=[-0.7, 6.7], row=1, col=2)
    fig.update_yaxes(visible=False, range=[-6.7, 0.7], scaleanchor="x2", scaleratio=1, row=1, col=2)
    fig.update_layout(
        template="simple_white", height=600, margin=dict(t=95, l=10, r=10, b=60),
        font=dict(family=FONTE_WEB, color=TINTA),
        title=dict(text="", x=0.01, y=0.97, yanchor="top"),
        coloraxis=dict(colorbar=dict(orientation="h", y=-0.06, len=0.6, thickness=12, x=0.5, xanchor="center")))

    plot_id = "mapa-uf"
    script = """
const gd = document.getElementById('%(plot_id)s');
const DADOS = %(dados)s, META = %(meta)s, TEXTO = %(texto)s, UFS = %(ufs)s, ESCALAS = %(escalas)s;
const nomeLeg = l => l + 'ª legislatura';
const controles = document.createElement('div');
controles.style.cssText = 'display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin:8px 12px 0;' +
  'font:14px system-ui,-apple-system,"Segoe UI",sans-serif;color:#0b0b0b';
controles.innerHTML = '<label>Legislatura <select id="sel-leg"></select></label>' +
  '<label>Métrica <select id="sel-met"></select></label>' +
  '<span id="nota-met" style="color:#52514e;flex-basis:100%%"></span>';
gd.parentNode.insertBefore(controles, gd);
const selLeg = document.getElementById('sel-leg'), selMet = document.getElementById('sel-met');
Object.keys(DADOS).sort().forEach(l => selLeg.add(new Option(nomeLeg(l), l)));
selLeg.value = '%(leg0)s';
function opcoes() {
  const atual = selMet.value; selMet.innerHTML = '';
  Object.keys(META).forEach(m => {
    if (DADOS[selLeg.value][m]) selMet.add(new Option(META[m].legislatura ? 'Votação: ' + META[m].nome : META[m].nome, m));
  });
  selMet.value = DADOS[selLeg.value][atual] ? atual : '%(m0)s';
}
function fmt(v, m) {
  const d = META[m].fmt === '.1f' ? 1 : 0;
  return v.toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d}) + META[m].sufixo;
}
function atualizar() {
  const l = selLeg.value, m = selMet.value, d = DADOS[l][m], meta = META[m];
  const z = UFS.map(u => d[u] ? d[u][0] : null);
  const hover = UFS.map(u => d[u] ? '<b>' + u + '</b><br>' + meta.nome + ': ' + fmt(d[u][0], m) +
                                    '<br>n = ' + d[u][1] + ' ' + meta.n : '<b>' + u + '</b><br>sem dados');
  const txt = UFS.map(u => d[u] ? u + '<br>' + fmt(d[u][0], m).replace(' mil', '') : u);
  Plotly.restyle(gd, {z: [z], customdata: [hover]}, [0]);
  Plotly.restyle(gd, {'marker.color': [z], customdata: [hover], text: [txt],
                      'textfont.color': [UFS.map(u => (TEXTO[l][m] || {})[u] || '#52514e')]}, [1]);
  Plotly.relayout(gd, {
    'coloraxis.colorscale': ESCALAS[meta.escala], 'coloraxis.cmin': meta.cmin, 'coloraxis.cmax': meta.cmax,
    'coloraxis.colorbar.title.text': meta.unidade, 'coloraxis.colorbar.title.side': 'top',
    'coloraxis.colorbar.ticksuffix': meta.sufixo.trim() === '%%' ? '%%' : '',
    'title.text': '<b>' + meta.nome + ' por UF</b> · ' + nomeLeg(l) +
                  '<br><sup>Escala igual nas três legislaturas. Passe o mouse para ver o valor e o n.</sup>'});
  document.getElementById('nota-met').textContent = meta.nota;
}
selLeg.addEventListener('change', () => { opcoes(); atualizar(); });
selMet.addEventListener('change', atualizar);
opcoes(); atualizar();
""" % dict(plot_id=plot_id, dados=json.dumps(dados), meta=json.dumps(meta, ensure_ascii=False),
           texto=json.dumps(texto), ufs=json.dumps(ufs), leg0=leg0, m0=m0,
           escalas=json.dumps({e: _escala_plotly(e) for e in ("cividis", "PuOr")}))
    fig.write_html(INTERATIVAS / "mapa_uf.html", include_plotlyjs="cdn", div_id=plot_id, post_script=script,
                   config={"displaylogo": False, "responsive": True})


def figura_mapa_uf(dados: dict, meta: dict, legislatura: int, metrica: str, altura: int = 520) -> go.Figure:
    """Mapa geográfico e em grade de uma legislatura × métrica (usado pelo painel)."""
    m, d = meta[metrica], dados[str(legislatura)][metrica]
    ufs = sorted(GRADE_UF)
    z = [d.get(uf, [None])[0] for uf in ufs]
    casas = 1 if m["fmt"] == ".1f" else 0
    fmt = lambda v: f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") + m["sufixo"]
    hover = [f"<b>{uf}</b><br>{m['nome']}: {fmt(d[uf][0])}<br>n = {d[uf][1]} {m['n']}" if uf in d
             else f"<b>{uf}</b><br>sem dados" for uf in ufs]
    texto = [f"{uf}<br>{fmt(d[uf][0]).replace(' mil', '')}" if uf in d else uf for uf in ufs]
    cores = [_cor_texto(m["escala"], m["cmin"], m["cmax"], d[uf][0] if uf in d else None) for uf in ufs]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.55, 0.45], horizontal_spacing=0.02,
                        specs=[[{"type": "geo"}, {"type": "xy"}]],
                        subplot_titles=("Mapa geográfico (IBGE)", "Mapa em grade (UFs do mesmo tamanho)"))
    fig.add_trace(go.Choropleth(geojson=_malha(), featureidkey="properties.sigla", locations=ufs, z=z,
                                coloraxis="coloraxis", marker=dict(line=dict(color="white", width=0.8)),
                                customdata=hover, hovertemplate="%{customdata}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=[GRADE_UF[uf][0] for uf in ufs], y=[-GRADE_UF[uf][1] for uf in ufs], mode="markers+text", text=texto,
        textfont=dict(size=11, color=cores, family=FONTE_WEB),
        marker=dict(symbol="square", size=40, color=z, coloraxis="coloraxis", line=dict(color="white", width=1)),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False), row=1, col=2)
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_xaxes(visible=False, range=[-0.7, 6.7], row=1, col=2)
    fig.update_yaxes(visible=False, range=[-6.7, 0.7], scaleanchor="x2", scaleratio=1, row=1, col=2)
    fig.update_layout(
        template="simple_white", height=altura, margin=dict(t=40, l=10, r=10, b=50),
        font=dict(family=FONTE_WEB, color=TINTA),
        coloraxis=dict(colorscale=_escala_plotly(m["escala"]), cmin=m["cmin"], cmax=m["cmax"],
                       colorbar=dict(orientation="h", y=-0.08, len=0.6, thickness=12, x=0.5, xanchor="center",
                                     title=dict(text=m["unidade"], side="top"),
                                     ticksuffix="%" if m["sufixo"] == "%" else "")))
    return fig


# --- V11: mapa estático --------------------------------------------------------
def _mapa_grade(ax, valores: dict, cmap: str, vmin: float, vmax: float, fmt) -> None:
    norm = Normalize(vmin, vmax)
    for uf, (c, l) in GRADE_UF.items():
        v = valores.get(uf)
        cor = colormaps[cmap](norm(v)) if v is not None else "#f0efec"
        ax.add_patch(plt.Rectangle((c - 0.46, -l - 0.46), 0.92, 0.92, facecolor=cor, edgecolor="none"))
        tinta = _texto_sobre(cor) if v is not None else TINTA_2
        ax.text(c, -l + 0.13, uf, ha="center", va="center", fontsize=5.5, color=tinta, fontweight="bold")
        if v is not None:
            ax.text(c, -l - 0.2, fmt(v), ha="center", va="center", fontsize=4.6, color=tinta)
    ax.set_xlim(-0.6, 6.6)
    ax.set_ylim(-6.6, 0.6)
    ax.set_aspect("equal")
    ax.axis("off")


def v11_mapa_gasto_uf(base: pd.DataFrame) -> None:
    pop = _populacao(base)
    por_uf = pop.groupby("uf").agg(gasto_rs=("gasto_medio_mensal", "median"),
                                   gasto_rel=("gasto_relativo", "median"), quadrante=("q", "mean"))
    paineis = [
        ("(a) Gasto mensal em reais\n(mediana, R\\$ mil)", por_uf["gasto_rs"] / 1000, lambda v: f"{v:.0f}"),
        ("(b) Gasto relativo ao teto da UF\n(mediana, %)", por_uf["gasto_rel"] * 100, lambda v: f"{v:.0f}"),
        ("(c) No quadrante gasto alto /\nprodutividade baixa (%)", por_uf["quadrante"] * 100, lambda v: f"{v:.0f}"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(PAGINA, 2.85))
    for ax, (titulo, serie, fmt) in zip(axes, paineis):
        vmin, vmax = float(serie.min()), float(serie.max())
        _mapa_grade(ax, serie.to_dict(), "cividis", vmin, vmax, fmt)
        amp = (f"maior UF = {vmax / vmin:.1f}× a menor".replace(".", ",") if vmin > 0
               else f"de {vmin:.0f} a {vmax:.0f}")
        ax.set_title(titulo, fontsize=7, pad=9)
        ax.text(0.5, 1.012, amp, transform=ax.transAxes, ha="center", va="bottom", fontsize=5.8, color=TINTA_2)
        sm = plt.cm.ScalarMappable(norm=Normalize(vmin, vmax), cmap="cividis")
        barra = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.05, pad=0.02, aspect=25)
        barra.outline.set_visible(False)
        barra.ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        barra.ax.tick_params(labelsize=5.5, length=2, color=EIXO)
    fig.text(0.5, -0.01, "Deputados da população de análise (≥ 12 meses de exercício) nas legislaturas 55ª a 57ª, "
                         "agregadas. Cada quadrado é uma UF; a posição aproxima a geografia.",
             ha="center", va="top", fontsize=5.5, color=MUDO)
    fig.subplots_adjust(wspace=0.08)
    _salvar(fig, "v11_mapa_gasto_uf")


# --- Hemiciclo -----------------------------------------------------------------
def _assentos(n: int, fileiras: int | None = None, r0: float = 0.38) -> pd.DataFrame:
    """Posições de n assentos num semicírculo, da esquerda para a direita."""
    fileiras = fileiras or max(3, int(round(np.sqrt(n / 5))))
    raios = np.linspace(r0, 1.0, fileiras)
    por_fileira = np.floor(n * raios / raios.sum()).astype(int)
    por_fileira[-1] += n - por_fileira.sum()
    pos = []
    for r, k in zip(raios, por_fileira):
        angulos = np.linspace(np.pi, 0, k) if k > 1 else np.array([np.pi / 2])
        pos += [(r * np.cos(a), r * np.sin(a), a, r) for a in angulos]
    df = pd.DataFrame(pos, columns=["x", "y", "angulo", "raio"])
    return df.sort_values(["angulo", "raio"], ascending=[False, True], kind="stable").reset_index(drop=True)


def _ordenar_plenario(vv: pd.DataFrame, ordem: pd.DataFrame) -> pd.DataFrame:
    """Deputados da esquerda para a direita pelo partido; dentro dele, pelo voto."""
    pos = {p: i for i, p in enumerate(ordem["partido_id"])}
    vv = vv.copy()
    vv["_p"] = vv["partido_id"].map(pos).fillna(len(pos))
    vv["_v"] = vv["voto_original"].map({v: i for i, v in enumerate(ORDEM_VOTO)})
    return vv.sort_values(["_p", "partido", "_v", "nome"], kind="stable").reset_index(drop=True)


def _plenario(votos: pd.DataFrame, chave: str, ordem: pd.DataFrame) -> pd.DataFrame:
    vv = _ordenar_plenario(votos[votos["chave_votacao"] == chave], ordem)
    return pd.concat([vv, _assentos(len(vv))], axis=1)


def _limites_espectro(p: pd.DataFrame) -> list[tuple[str, float, float]]:
    """(espectro, ângulo inicial, ângulo final) de cada bloco no plenário."""
    blocos = []
    for e in config.ESPECTROS:
        a = p.loc[p["espectro"] == e, "angulo"]
        if len(a):
            blocos.append((e, float(a.max()), float(a.min())))
    return blocos


def _placar(p: pd.DataFrame) -> str:
    c = p["voto_original"].value_counts()
    return f"Sim {c.get('Sim', 0)} × Não {c.get('Não', 0)}"


def _tracos_hemiciclo(p: pd.DataFrame, visivel: bool = True, tamanho: int = 9) -> list:
    """Pontos (um por deputado), arcos e rótulos dos blocos de espectro."""
    tracos = []
    for voto in ORDEM_VOTO:
        s = p[p["voto_original"] == voto]
        tracos.append(go.Scatter(
            x=s["x"], y=s["y"], mode="markers", name=voto, legendgroup=voto, visible=visivel,
            marker=dict(size=tamanho, color=COR_VOTO[voto], line=dict(color=BORDA_VOTO[voto], width=1.2)),
            customdata=np.stack([s["nome"], s["partido"].fillna("S.PART."), s["uf"],
                                 s["espectro"].map(NOME_ESPECTRO).fillna("sem partido"),
                                 s["orientacao_partido"].fillna("—"),
                                 s["orientacao_governo"].fillna("—")], axis=-1) if len(s) else None,
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]}-%{customdata[2]})"
                           "<br>Espectro do partido: %{customdata[3]}"
                           f"<br>Voto: {voto}"
                           "<br>Orientação do partido: %{customdata[4]}"
                           "<br>Orientação do Governo: %{customdata[5]}<extra></extra>")))
    for e, a_ini, a_fim in _limites_espectro(p):
        t = np.linspace(a_ini, a_fim, 40)
        tracos.append(go.Scatter(x=1.07 * np.cos(t), y=1.07 * np.sin(t), mode="lines", hoverinfo="skip",
                                 line=dict(color=TINTA_2, width=2), showlegend=False, visible=visivel))
        meio = (a_ini + a_fim) / 2
        x, y = 1.1 * np.cos(meio), 1.1 * np.sin(meio)
        lado = "top left" if x < -0.15 else "top right" if x > 0.15 else "top center"
        tracos.append(go.Scatter(x=[x], y=[y], mode="text", text=[NOME_ESPECTRO[e]], textposition=lado,
                                 textfont=dict(size=13, color=TINTA_2),
                                 hoverinfo="skip", showlegend=False, visible=visivel))
    return tracos


def _titulo_hemiciclo(v: dict, p: pd.DataFrame) -> str:
    pro = (f"Pró-pauta social: <b>{v['direcao_pro_pauta']}</b>" if v["direcao_pro_pauta"]
           else "Sem direção pró-pauta definida (estudo de caso governo × ideologia)")
    return (f"<b>{v['nome']}</b><br><sup>{pd.Timestamp(v['data']).strftime('%d/%m/%Y')} · "
            f"{v['legislatura']}ª legislatura · {_placar(p)} · {pro}<br>Partidos ordenados da esquerda "
            f"para a direita (Bolognesi, Ribeiro e Codato, 2023)</sup>")


def _layout_hemiciclo(fig: go.Figure, titulo: str, altura: int, topo: int) -> None:
    fig.update_layout(
        title=dict(text=titulo, x=0.01, y=0.98, yanchor="top"),
        template="simple_white", height=altura, font=dict(family=FONTE_WEB, color=TINTA),
        xaxis=dict(visible=False, range=[-1.45, 1.45]),
        yaxis=dict(visible=False, range=[-0.08, 1.25], scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", y=0.02, x=0.5, xanchor="center", title_text="Voto: "),
        margin=dict(t=topo, l=10, r=10, b=10), hovermode="closest")


def figura_hemiciclo(votos: pd.DataFrame, chave: str, altura: int = 560) -> go.Figure:
    """Hemiciclo de uma votação (usado pelo painel)."""
    v = next(x for x in VOTACOES if x["chave"] == chave)
    p = _plenario(votos, chave, _ordem_partidos())
    fig = go.Figure(_tracos_hemiciclo(p))
    _layout_hemiciclo(fig, _titulo_hemiciclo(v, p), altura, topo=100)
    return fig


def hemiciclo_interativo(votos: pd.DataFrame) -> None:
    ordem = _ordem_partidos()
    fig, botoes = go.Figure(), []
    n_por_votacao = []
    padrao = len(VOTACOES) - 1  # a mais recente
    for i, v in enumerate(VOTACOES):
        p = _plenario(votos, v["chave"], ordem)
        n0 = len(fig.data)
        fig.add_traces(_tracos_hemiciclo(p, visivel=(i == padrao)))
        n_por_votacao.append((n0, len(fig.data)))
        botoes.append((v, _titulo_hemiciclo(v, p)))

    total = len(fig.data)
    menu = []
    for (v, titulo), (a, b) in zip(botoes, n_por_votacao):
        vis = [a <= k < b for k in range(total)]
        menu.append(dict(label=f"{v['nome']} ({pd.Timestamp(v['data']).year})", method="update",
                         args=[{"visible": vis}, {"title.text": titulo}]))
    _layout_hemiciclo(fig, botoes[padrao][1], altura=620, topo=150)
    fig.update_layout(updatemenus=[dict(buttons=menu, active=padrao, x=0.01, xanchor="left", y=1.02,
                                        yanchor="bottom")])
    fig.write_html(INTERATIVAS / "hemiciclo_votacoes.html", include_plotlyjs="cdn",
                   config={"displaylogo": False, "responsive": True})


def v12_hemiciclo_previdencia_precatorios(votos: pd.DataFrame) -> None:
    ordem = _ordem_partidos()
    chaves = ("reforma_previdencia", "pec_precatorios")
    fig, axes = plt.subplots(1, 2, figsize=(PAGINA, 2.35))
    for ax, chave in zip(axes, chaves):
        v = next(x for x in VOTACOES if x["chave"] == chave)
        p = _plenario(votos, chave, ordem)
        for voto in ORDEM_VOTO:
            s = p[p["voto_original"] == voto]
            ax.scatter(s["x"], s["y"], s=5.5, c=COR_VOTO[voto], edgecolors=BORDA_VOTO[voto], linewidths=0.35,
                       label=voto, zorder=3)
        blocos = _limites_espectro(p)
        for k, (e, a_ini, a_fim) in enumerate(blocos):
            t = np.linspace(a_ini, a_fim, 50)
            ax.plot(1.06 * np.cos(t), 1.06 * np.sin(t), color=TINTA_2, lw=0.8, solid_capstyle="butt")
            if k:  # fronteira com o bloco anterior
                a = (blocos[k - 1][2] + a_ini) / 2
                ax.plot([1.02 * np.cos(a), 1.12 * np.cos(a)], [1.02 * np.sin(a), 1.12 * np.sin(a)],
                        color=TINTA_2, lw=0.8)
            meio = (a_ini + a_fim) / 2
            x, y = 1.1 * np.cos(meio), 1.1 * np.sin(meio)
            ha = "right" if x < -0.15 else "left" if x > 0.15 else "center"
            ax.text(x, y, NOME_ESPECTRO[e], ha=ha, va="bottom", fontsize=6, color=TINTA_2)
        pro = f"pró-pauta: {v['direcao_pro_pauta']}" if v["direcao_pro_pauta"] else "sem direção pró-pauta"
        ax.set_title(f"{ROTULO_CURTO[chave].replace(chr(10), ' ')} ({pd.Timestamp(v['data']).year}) — {pro}",
                     fontsize=7, pad=1)
        ax.text(0, 0.06, _placar(p), ha="center", va="bottom", fontsize=7, color=TINTA)
        ax.set_xlim(-1.42, 1.42)
        ax.set_ylim(-0.05, 1.28)
        ax.set_aspect("equal")
        ax.axis("off")
    alcas = [plt.Line2D([], [], ls="", marker="o", ms=4, mfc=COR_VOTO[v], mec=BORDA_VOTO[v], mew=0.6, label=v)
             for v in ORDEM_VOTO]
    fig.legend(handles=alcas, loc="lower center", ncol=4, fontsize=6.5, bbox_to_anchor=(0.5, -0.05),
               handletextpad=0.3, columnspacing=1.2)
    fig.subplots_adjust(wspace=0.02, left=0.01, right=0.99, top=0.9, bottom=0.08)
    _salvar(fig, "v12_hemiciclo_previdencia_precatorios")


# --- Execução ------------------------------------------------------------------
def gerar_todas(base: pd.DataFrame, votos: pd.DataFrame) -> None:
    indice = pd.read_csv(ANALISE / "indice_pro_pauta_deputado.csv")
    v11_mapa_gasto_uf(base)
    v12_hemiciclo_previdencia_precatorios(votos)
    mapa_interativo(base, indice, votos)
    hemiciclo_interativo(votos)


if __name__ == "__main__":
    from src.visualizacao.graficos import aplicar_estilo
    FIG.mkdir(parents=True, exist_ok=True)
    INTERATIVAS.mkdir(parents=True, exist_ok=True)
    aplicar_estilo()
    gerar_todas(pd.read_csv(DADOS / "base_deputado_legislatura.csv"), pd.read_csv(DADOS / "votos.csv"))
    print(f"Mapa e hemiciclo gravados em {config.FIGURAS}")
