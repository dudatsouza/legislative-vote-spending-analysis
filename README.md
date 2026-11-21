# O custo do Não

Uma análise de dados sobre gasto, produção e voto da Câmara dos Deputados em pautas sociais.

Trabalho final de Ciência dos Dados, Engenharia de Computação, UFCIMG, Campus V, Divinópolis.
Alunos: Joaquim Cézar Santana da Cruz e Maria Eduarda Teixeira Souza. Professor: Higor Alexandre Duarte Mascarenhas.

**Painel on-line:** https://legislative-vote-spending-analysis-4ignabvfueef24bd6et3hx.streamlit.app

## Pergunta

O voto dos deputados federais em pautas sociais segue o partido? E ele tem relação com a produtividade legislativa e com o uso da cota parlamentar (CEAP)?

- **Recorte:** legislaturas 55ª a 57ª, de 01/02/2015 a 20/11/2026 (a 57ª é parcial).
- **Votações (8, nominais de Plenário):**
  - Redução da maioridade penal
  - Teto de gastos
  - Reforma Trabalhista
  - Reforma da Previdência
  - PEC dos Precatórios
  - Igualdade salarial entre mulheres e homens
  - Marco temporal das terras indígenas
  - Fim da escala 6x1
- **Tipo de análise:** descritiva e correlacional, com testes de hipótese e correção de Holm. Não há modelos preditivos nem machine learning.

## Principais resultados

1. **O voto segue o partido e o espectro.** O partido está associado ao voto em 7 das 8 votações (V de Cramér entre 0,72 e 0,85).
2. **Gasto e produtividade não andam juntos.** Nenhuma das 18 correlações de Spearman foi significativa. O gasto é medido em relação ao teto da cota de cada UF.
3. **O perfil de gasto quase não muda o voto.** Sem controle, estar no quadrante "gasto alto / produtividade baixa" se associa ao voto em 2 votações. Comparando deputados do mesmo espectro, sobra só 1 (PEC dos Precatórios).

## Como executar

Requer Python 3.10 ou superior. Os dados tratados já estão no repositório, então não é preciso baixar nada para reproduzir a análise e as figuras:

```bash
git clone https://github.com/dudatsouza/legislative-vote-spending-analysis.git
cd legislative-vote-spending-analysis
./pipeline.sh --de analise
```

O script cria o ambiente `.venv`, instala o `requirements.txt` e roda a análise e os gráficos: alguns segundos, mais a instalação das dependências na primeira vez. A saída também fica em `logs/`.

Para abrir o painel localmente (http://localhost:8501):

```bash
.venv/bin/streamlit run src/visualizacao/painel.py
```

Para refazer tudo desde a coleta (baixa cerca de 1,4 GB da Câmara e leva algumas horas):

```bash
./pipeline.sh
```

Outras opções:

| Opção | Efeito |
|---|---|
| `--de ETAPA` | começa na etapa |
| `--ate ETAPA` | para depois da etapa |
| `--so ETAPA` | roda só a etapa |
| `--sem-coleta` | reaproveita `data/raw/` |
| `--sem-perfil` | pula o ydata-profiling |
| `-h` | ajuda |

## Pipeline

| Etapa | Comando | O que faz |
|---|---|---|
| 1. coleta | `python -m src.extracao.coletar tudo` | API da Câmara e arquivos em lote (proposições, CEAP), com cache em `data/raw/` |
| 2. validação | `python -m src.validar_config` | confere a configuração, as tabelas de referência e o sha256 dos dados brutos |
| 3. tratamento | `python -m src.tratamento.tratar` | junta votos, exercício, produtividade e gasto por deputado e legislatura |
| 4. perfil | `src/visualizacao/perfil_dados.py` | relatório exploratório (ydata-profiling, ambiente próprio `.venv_perfil`) |
| 5. análise | `python -m src.analise.analisar` | testes, controles pelo espectro, regressão logística e robustez |
| 6. gráficos | `python -m src.visualizacao.graficos` | figuras do relatório (PDF) e versões interativas (HTML) |

Todos os parâmetros (votações, datas, limiares) ficam em [`src/config.py`](src/config.py).

## Estrutura

```
src/
  config.py           parâmetros do projeto
  validar_config.py   validação da configuração e dos dados brutos
  extracao/           coleta (API e arquivos em lote)
  tratamento/         limpeza e integração das bases
  analise/            testes estatísticos
  visualizacao/       figuras, mapa, hemiciclo, perfil e painel Streamlit
data/
  raw/                dados brutos (não versionados)
  referencia/         tabelas manuais com fonte: partidos, espectro, blocos, tetos da CEAP
  processed/          bases tratadas e resultados (analise/)
figuras/
  relatorio/          figuras do relatório e dos slides (PDF)
  interativas/        dispersão, mapa por UF e hemiciclo (HTML, abrem no navegador)
  perfil/             relatórios do ydata-profiling (HTML)
pipeline.sh           executa o pipeline completo
```

## Fontes

- **Câmara dos Deputados.** Votos, orientações, deputados, proposições e CEAP, pela [API de Dados Abertos](https://dadosabertos.camara.leg.br) e pelos arquivos em lote.
- **Espectro ideológico.** Bolognesi, Ribeiro e Codato (2023).
- **Tetos da CEAP por UF.** Atos da Mesa da Câmara.
- **Malha das UFs.** IBGE.
