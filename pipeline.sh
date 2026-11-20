#!/usr/bin/env bash
# Pipeline completo do projeto "O custo do Não".
#
#   coleta -> validacao -> tratamento -> perfil -> analise -> graficos
#
# Uso:
#   ./pipeline.sh                     roda tudo
#   ./pipeline.sh --sem-coleta        reaproveita data/raw/ (começa na validação)
#   ./pipeline.sh --de analise        começa na etapa indicada
#   ./pipeline.sh --ate tratamento    para depois da etapa indicada
#   ./pipeline.sh --so graficos       roda só uma etapa
#   ./pipeline.sh --sem-validacao     pula a validação de src/config.py
#   ./pipeline.sh --sem-api           valida sem consultar a API da Câmara
#   ./pipeline.sh --sem-perfil        pula o relatório de exploração (ydata-profiling)
#   ./pipeline.sh -h                  mostra esta ajuda
#
# Cria .venv (e .venv_perfil, para o ydata-profiling) na primeira execução.
# Falhas na validação ou no perfil não interrompem o pipeline. Log em logs/.

set -euo pipefail
cd "$(dirname "$0")"
RAIZ="$(pwd)"

ETAPAS="coleta validacao tratamento perfil analise graficos"
N_ETAPAS=6
DE="coleta"
ATE="graficos"
VALIDAR=1
PERFIL=1
ARGS_VALIDACAO=""

ajuda() { sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; }

indice() {  # posição da etapa na lista; 0 se não existir
    local i=1 e
    for e in $ETAPAS; do
        [ "$e" = "$1" ] && { echo "$i"; return; }
        i=$((i + 1))
    done
    echo 0
}

checar_etapa() {
    if [ "$(indice "$1")" -eq 0 ]; then
        echo "Etapa desconhecida: '$1'. Use uma de: $ETAPAS" >&2
        exit 2
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        --de)            checar_etapa "${2:-}"; DE="$2"; shift ;;
        --ate)           checar_etapa "${2:-}"; ATE="$2"; shift ;;
        --so)            checar_etapa "${2:-}"; DE="$2"; ATE="$2"; shift ;;
        --sem-coleta)    DE="validacao" ;;
        --sem-validacao) VALIDAR=0 ;;
        --sem-api)       ARGS_VALIDACAO="--sem-api" ;;
        --sem-perfil)    PERFIL=0 ;;
        -h|--help)       ajuda; exit 0 ;;
        *) echo "Opção desconhecida: $1 (use -h para ajuda)" >&2; exit 2 ;;
    esac
    shift
done

if [ "$(indice "$DE")" -gt "$(indice "$ATE")" ]; then
    echo "--de $DE vem depois de --ate $ATE" >&2
    exit 2
fi

# --- Log ---
mkdir -p logs
LOG="logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
: > "$LOG"
msg() { echo "$@" | tee -a "$LOG"; }

# --- Ambiente Python ---
PY="$RAIZ/.venv/bin/python"

if [ ! -x "$PY" ]; then
    BASE="$(command -v python3 || command -v python || true)"
    if [ -z "$BASE" ]; then
        msg "ERRO: Python 3 não encontrado. Instale o Python 3.10 ou superior."
        exit 1
    fi
    if ! "$BASE" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
        msg "ERRO: é preciso Python 3.10 ou superior (encontrado: $("$BASE" --version 2>&1))."
        exit 1
    fi
    msg "== Criando ambiente virtual em .venv ($("$BASE" --version 2>&1))"
    "$BASE" -m venv .venv
fi

# Instala as dependências se alguma estiver faltando ou desatualizada.
if ! "$PY" - <<'EOF' >/dev/null 2>&1
import importlib.metadata as md, re, sys
for linha in open("requirements.txt", encoding="utf-8"):
    req = linha.split("#")[0].strip()
    if not req:
        continue
    nome, _, minimo = re.split(r"(>=)", req) if ">=" in req else (req, "", "")
    versao = md.version(nome.strip())  # levanta erro se não instalado
    if minimo:
        atual = tuple(int(p) for p in re.findall(r"\d+", versao)[:3])
        pedido = tuple(int(p) for p in re.findall(r"\d+", minimo)[:3])
        if atual < pedido:
            sys.exit(1)
EOF
then
    msg "== Instalando dependências (requirements.txt)"
    "$PY" -m pip install --upgrade pip 2>&1 | tee -a "$LOG" >/dev/null
    "$PY" -m pip install -r requirements.txt 2>&1 | tee -a "$LOG"
fi

# O ydata-profiling exige Python < 3.14.
PY_PERFIL="$RAIZ/.venv_perfil/bin/python"
preparar_perfil() {
    if [ -x "$PY_PERFIL" ] && "$PY_PERFIL" -c 'import ydata_profiling' >/dev/null 2>&1; then
        return 0
    fi
    local cand base=""
    for cand in python3.13 python3.12 python3.11 python3.10 /usr/bin/python3 python3; do
        if command -v "$cand" >/dev/null 2>&1 &&
           "$cand" -c 'import sys; sys.exit(not (3, 9) <= sys.version_info < (3, 14))' 2>/dev/null; then
            base="$(command -v "$cand")"; break
        fi
    done
    if [ -z "$base" ]; then
        msg "Sem Python entre 3.9 e 3.13 para o ydata-profiling; instale um (ex.: python.org) ou use --sem-perfil."
        return 1
    fi
    msg "== Criando .venv_perfil ($("$base" --version 2>&1)) e instalando requirements-perfil.txt"
    "$base" -m venv .venv_perfil &&
        "$PY_PERFIL" -m pip install -q --upgrade pip 2>&1 | tee -a "$LOG" >/dev/null &&
        "$PY_PERFIL" -m pip install -q -r requirements-perfil.txt 2>&1 | tee -a "$LOG"
}

export MPLBACKEND=Agg       # figuras sem janela
export PYTHONUNBUFFERED=1   # saída em tempo real no terminal e no log
export PYTHONDONTWRITEBYTECODE=1

# --- Etapas ---
comando() {
    case "$1" in
        coleta)     echo "-m src.extracao.coletar tudo" ;;
        validacao)  echo "-m src.validar_config $ARGS_VALIDACAO" ;;
        tratamento) echo "-m src.tratamento.tratar" ;;
        perfil)     echo "src/visualizacao/perfil_dados.py" ;;
        analise)    echo "-m src.analise.analisar" ;;
        graficos)   echo "-m src.visualizacao.graficos" ;;
    esac
}

if [ "$(indice "$DE")" -gt "$(indice coleta)" ] && [ "$(indice "$DE")" -le "$(indice tratamento)" ]; then
    if [ ! -d data/raw/api ] || [ -z "$(ls -A data/raw/api 2>/dev/null)" ]; then
        msg "ERRO: data/raw/ está vazio. Rode a coleta antes (./pipeline.sh sem --sem-coleta)."
        exit 1
    fi
fi

msg "Pipeline 'O custo do Não' — $(date '+%d/%m/%Y %H:%M:%S')"
msg "Python: $("$PY" --version 2>&1) | etapas: $DE → $ATE | log: $LOG"

RESUMO=""
AVISOS=0
INICIO_TOTAL=$(date +%s)

for etapa in $ETAPAS; do
    i=$(indice "$etapa")
    [ "$i" -lt "$(indice "$DE")" ] && continue
    [ "$i" -gt "$(indice "$ATE")" ] && break
    if { [ "$etapa" = "validacao" ] && [ "$VALIDAR" -eq 0 ]; } ||
       { [ "$etapa" = "perfil" ] && [ "$PERFIL" -eq 0 ]; }; then
        RESUMO="$RESUMO\n  $(printf '%-11s' "$etapa") pulada"
        continue
    fi

    interp="$PY"
    [ "$etapa" = "perfil" ] && interp="$PY_PERFIL"
    msg ""
    msg "=================================================================="
    msg "  [$i/$N_ETAPAS] $etapa   (${interp#"$RAIZ"/} $(comando "$etapa"))"
    msg "=================================================================="
    t0=$(date +%s)
    set +e
    if [ "$etapa" = "perfil" ] && ! preparar_perfil; then
        status=1
    else
        # shellcheck disable=SC2046
        "$interp" $(comando "$etapa") 2>&1 | tee -a "$LOG"
        status=${PIPESTATUS[0]}
    fi
    set -e
    dt=$(( $(date +%s) - t0 ))
    tempo="$((dt / 60))min $((dt % 60))s"

    if [ "$status" -ne 0 ]; then
        if [ "$etapa" = "validacao" ] || [ "$etapa" = "perfil" ]; then
            AVISOS=1
            RESUMO="$RESUMO\n  $(printf '%-11s' "$etapa") COM ERROS ($tempo) — ver o log"
            continue
        fi
        RESUMO="$RESUMO\n  $(printf '%-11s' "$etapa") FALHOU ($tempo)"
        msg ""
        msg "Resumo:$(printf "$RESUMO")"
        msg ""
        msg "A etapa '$etapa' falhou (código $status). Log completo: $LOG"
        msg "Para retomar dela: ./pipeline.sh --de $etapa"
        exit "$status"
    fi
    RESUMO="$RESUMO\n  $(printf '%-11s' "$etapa") ok ($tempo)"
done

dt=$(( $(date +%s) - INICIO_TOTAL ))
msg ""
msg "Resumo:$(printf "$RESUMO")"
msg ""
msg "Concluído em $((dt / 60))min $((dt % 60))s."
[ "$AVISOS" -eq 1 ] && msg "Atenção: a validação ou o perfil terminaram com erro (ver o resumo e o log)."
if [ "$(indice "$ATE")" -ge "$(indice analise)" ]; then
    msg "Resultados: data/processed/ (bases) e data/processed/analise/ (testes)."
fi
if [ "$PERFIL" -eq 1 ] && [ "$(indice "$DE")" -le "$(indice perfil)" ] && [ "$(indice "$ATE")" -ge "$(indice perfil)" ]; then
    msg "Perfil:     figuras/perfil/ (relatórios do ydata-profiling)."
fi
if [ "$(indice "$ATE")" -ge "$(indice graficos)" ]; then
    msg "Figuras:    figuras/relatorio/ (PDF) e figuras/interativas/ (HTML)."
fi
msg "Log:        $LOG"
