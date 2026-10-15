#!/usr/bin/env bash
# Executa as quatro etapas do pipeline em ordem (Seção 6).
set -euo pipefail
cd "$(dirname "$0")"
python -m src.extracao.coletar tudo
python -m src.tratamento.tratar
python -m src.analise.analisar
python -m src.visualizacao.graficos
