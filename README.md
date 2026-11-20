# O custo do Não

**Uma Análise de Dados sobre Gasto, Produção e Voto no Legislativo em pautas sociais**

Trabalho da disciplina de Ciência dos Dados, Engenharia de Computação, UFCIMG (Universidade Federal de Ciência e Inovação de Minas Gerais), Campus V, Divinópolis.
Alunos: Joaquim Cézar Santana da Cruz e Maria Eduarda Teixeira Souza. Professor: Higor Alexandre Duarte Mascarenhas.

## Pergunta de pesquisa

Existe relação entre o alinhamento partidário dos deputados federais e o padrão de voto em pautas de caráter social na Câmara dos Deputados? E esse padrão se associa à produtividade legislativa e ao uso da cota parlamentar (CEAP)?

**Recorte:** legislaturas 55ª a 57ª, de 01/02/2015 até a data de corte (**20/11/2026**, `DATA_CORTE` em [`src/config.py`](src/config.py)), com 8 votações nominais de Plenário. A 57ª está em curso e entra como dado parcial.

A análise é **descritiva e correlacional**. Não há modelos preditivos nem machine learning, conforme o escopo combinado com o professor.

## Estrutura

A estrutura de pastas segue as etapas do pipeline:

```
src/
  config.py                 votações selecionadas, recorte temporal e parâmetros
  validar_config.py         confere config, tabelas de referência e dados brutos × manifesto
  extracao/                 1. coleta via API da Câmara e arquivos em lote
    camara_api.py             cliente HTTP: paginação, intervalo entre chamadas, cache em JSON
    coletar.py
  tratamento/               2. limpeza e junção das bases pelo id do deputado
    tratar.py                 votos (com ausências), Rice, produtividade, CEAP, base consolidada
  analise/                  3. testes F1–F5, controles pelo espectro (F4E, F5E), regressão logística e robustez
    analisar.py
  visualizacao/             4. figuras do relatório e visualizações interativas
    graficos.py               V1, V7, V8, V13 (SciencePlots/IEEE) e dispersão interativa
    mapa_hemiciclo.py         V11 e V12, mapa por UF e hemiciclo interativos (Plotly)
    perfil_dados.py           relatório de exploração das bases (ydata-profiling)
    painel.py                 painel interativo (Streamlit)
data/
  raw/                      dados brutos (NÃO versionados)
  referencia/               tabelas montadas à mão, com fonte: partidos, espectro, blocos, tetos, malha
  processed/                bases tratadas, resultados e manifesto da coleta (versionados)
figuras/
  relatorio/                PDFs usados no relatório e nos slides
  interativas/              versões interativas (.html, Plotly)
  perfil/                   relatórios de exploração (ydata-profiling)
pipeline.sh                 roda tudo: coleta → validação → tratamento → perfil → análise → gráficos
```

### Visualizações

| Arquivo | O que mostra | Ferramenta |
|---|---|---|
| `figuras/relatorio/v1_heatmap_pro_pauta.pdf` | % dos votos de cada partido a favor da pauta social, por votação | Matplotlib + SciencePlots |
| `figuras/relatorio/v7_spearman.pdf` | correlação gasto × produtividade por legislatura e faixa | Matplotlib + SciencePlots |
| `figuras/relatorio/v8_quadrante_partido.pdf` | % de cada partido no quadrante gasto alto / produtividade baixa | Matplotlib + SciencePlots |
| `figuras/relatorio/v11_mapa_gasto_uf.pdf` | gasto em reais × gasto relativo × quadrante, por UF (mapa em grade) | Matplotlib + SciencePlots |
| `figuras/relatorio/v12_hemiciclo_previdencia_precatorios.pdf` | votos da Previdência e dos Precatórios no plenário, por espectro | Matplotlib + SciencePlots |
| `figuras/relatorio/v13_controle_espectro.pdf` | razão de chances do quadrante no voto, sem e com controle do espectro | Matplotlib + SciencePlots |
| `figuras/interativas/dispersao_gasto_produtividade.html` | dispersão interativa, com seletor de legislatura e faixa | Plotly |
| `figuras/interativas/mapa_uf.html` | mapa geográfico (malha do IBGE) e em grade, com seletor de legislatura e métrica | Plotly |
| `figuras/interativas/hemiciclo_votacoes.html` | um ponto por deputado em cada uma das 8 votações | Plotly |
| `figuras/perfil/*.html` | tipos, ausentes, distribuições e correlações das bases tratadas | ydata-profiling |

Os PDFs ficam em `figuras/relatorio/` e são os mesmos enviados ao Overleaf (pasta `figuras/`). Os arquivos `.html` abrem direto no navegador (o Plotly é carregado da internet).

### Painel interativo (Streamlit)

O painel tem dez páginas em três grupos, com a legislatura escolhida na barra lateral (ela fica no endereço, como `?leg=56`, para compartilhar um link já filtrado):

| Grupo | Página | Conteúdo |
|---|---|---|
| Resultados | Visão geral | números da legislatura, os três achados principais, o voto de cada espectro e as votações |
| | Gasto × produtividade | dispersão por faixa, com cor por quadrante ou espectro, produtividade com ou sem PDL e busca por deputado |
| | Votações | hemiciclo, % pró-pauta por partido e os testes da votação |
| | Governo × ideologia | estudo de caso: % Sim de cada partido na Reforma da Previdência e na PEC dos Precatórios |
| | Controles | efeito do quadrante e da produtividade sem e com controle do espectro; regressão logística |
| Explorar | Mapa por UF | mapa geográfico e em grade, com seletor de métrica |
| | Partidos | % no quadrante de interesse, coesão (Rice), fidelidade e alinhamento ao Governo |
| | Deputado | ficha de um deputado, com a posição dele entre os colegas do mesmo estrato |
| Método | Testes | todas as famílias de testes e a robustez |
| | Dados e método | etapas do pipeline, definições, limitações, fontes e download das bases |

Depois de rodar o pipeline:

```bash
.venv/bin/streamlit run src/visualizacao/painel.py
```

O painel abre em http://localhost:8501. Ele só lê os arquivos versionados (`data/processed/` e `data/referencia/`), então funciona sem a pasta `data/raw/`.

#### Publicar no Streamlit Community Cloud

1. Faça o push do repositório para o GitHub.
2. Em [share.streamlit.io](https://share.streamlit.io), entre com a conta do GitHub e escolha **Create app → Deploy a public app from GitHub**.
3. Preencha: repositório `dudatsouza/legislative-vote-spending-analysis`, branch `main`, arquivo `src/visualizacao/painel.py`.
4. Em **Advanced settings**, escolha Python 3.12 (o projeto funciona a partir da 3.10) e clique em **Deploy**.

O Cloud instala o `requirements.txt` da raiz e usa o `.streamlit/config.toml`. Cada push na `main` republica o painel. Apps sem visitas por alguns dias entram em repouso: abra o link alguns minutos antes de apresentar.

## Como rodar

Requer Python 3.10 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para rodar tudo de uma vez (coleta → validação → tratamento → perfil → análise → gráficos):

```bash
./pipeline.sh
```

O script cria o `.venv` e instala o `requirements.txt` se ainda não estiverem prontos, mostra o tempo de cada etapa e salva a saída em `logs/`. Opções úteis:

```bash
./pipeline.sh --sem-coleta      # reaproveita data/raw/ e começa na validação
./pipeline.sh --de analise      # começa na etapa indicada (também: --ate, --so)
./pipeline.sh --sem-api         # valida src/config.py sem consultar a API
./pipeline.sh --sem-perfil      # pula o relatório de exploração
./pipeline.sh -h                # lista todas as opções
```

A validação (`src/validar_config.py`) e o perfil não interrompem o pipeline: se falharem, o resumo final avisa.

O relatório de exploração usa o [ydata-profiling](https://docs.profiling.ydata.ai/latest/), que ainda não roda no Python 3.14. Por isso ele tem um ambiente próprio, `.venv_perfil`, que o `pipeline.sh` cria na primeira vez com um Python entre 3.9 e 3.13 encontrado na máquina e instala o `requirements-perfil.txt`.

Ou etapa por etapa, a partir da raiz do projeto e com o `.venv` ativado:

```bash
python -m src.extracao.coletar tudo        # ou: votacoes | deputados | proposicoes | despesas | sigepa | malha
python -m src.validar_config               # opcional: --sem-api
python -m src.tratamento.tratar
python -m src.analise.analisar
python -m src.visualizacao.graficos         # inclui o mapa e o hemiciclo
.venv_perfil/bin/python src/visualizacao/perfil_dados.py   # opcional: relatório de exploração
```

Para encontrar o id de uma nova votação nominal, rode o comando abaixo. Ele lista as votações de Plenário da proposição e quantos votos individuais cada uma tem (0 significa votação simbólica):

```bash
python -m src.extracao.coletar localizar PL 6787 2016
```

Depois adicione a votação em `VOTACOES`, no arquivo [`src/config.py`](src/config.py).

A primeira coleta baixa cerca de 1,4 GB (arquivos em lote de proposições e da CEAP de 2015 até o ano da data de corte, mais as respostas da API). As execuções seguintes usam o cache em `data/raw/`, que **nunca é atualizado sozinho**.

### Reprodutibilidade dos dados brutos

A pasta `data/raw/` não é versionada, e a Câmara atualiza os arquivos em lote com o tempo. Por isso:

- quem roda a coleta commita também o `data/processed/manifesto_coleta.json`, que registra o sha256 e a data de download de cada arquivo;
- quem só reproduz os resultados usa a mesma `data/raw/` e roda `./pipeline.sh --sem-coleta`;
- o `validar_config` compara cada arquivo de `data/raw/` com o manifesto e acusa erro se algum for diferente, e aviso se algum foi baixado antes da data de corte;
- para atualizar os dados, mude `DATA_CORTE`, apague (ou renomeie) `data/raw/` e rode `./pipeline.sh` completo.

## Fontes

| Dado | Origem | Observação |
|---|---|---|
| Votos e orientações | API `/votacoes/{id}/votos` e `/votacoes/{id}/orientacoes` | partido registrado no momento do voto; orientação de bloco herdada pelos partidos |
| Deputados e exercício | API `/deputados?idLegislatura=` e `/deputados/{id}/historico` | estado diário de cada deputado: exercício, partido e UF |
| Proposições e autores | arquivos `proposicoes-{ano}.csv` e `proposicoesAutores-{ano}.csv` | a API não tem `/deputados/{id}/proposicoes` (retorna 405) |
| CEAP | arquivos `camara.leg.br/cotas/Ano-{ano}.csv.zip` | CPF e outros dados pessoais são descartados na leitura |
| Passagens SIGEPA desde ago/2025 | API `/deputados/{id}/despesas` | lacuna do arquivo em lote; validada contra o arquivo nos meses anteriores |
| Tetos da CEAP por UF | ato da Mesa e atualizações (`data/referencia/tetos_ceap.csv`) | gasto relativo = gasto ÷ teto da UF |
| Partidos, fusões e espectro | TSE e Bolognesi, Ribeiro e Codato (2023) (`data/referencia/`) | siglas, fusões e classificação ideológica |
| Malha das UFs | API de malhas do IBGE | mapa por UF |

## Resultados (data/processed)

| Arquivo | Conteúdo |
|---|---|
| `exercicio.csv` | deputado × legislatura: exercício, partido com mais dias, faixa e população |
| `votos.csv` | deputado × votação: voto, direção pró-pauta, orientação do partido e do Governo |
| `coesao_rice.csv` | índice de Rice por partido × votação (≥ 5 votos válidos) |
| `produtividade.csv` | produtividade bruta mensal e qualificada |
| `gasto_ceap.csv` | gasto total, teto e gasto relativo da CEAP |
| `base_deputado_legislatura.csv` | base consolidada, com quadrante e casos extremos |
| `manifesto_coleta.json` | arquivos brutos usados, com sha256 e data de download |
| `analise/testes_resumo.csv` | todas as famílias de testes (F1 a F5, F4E e F5E) com correção de Holm |
| `analise/f1_…` a `analise/f5_…` | detalhes de cada família de testes |
| `analise/f4e_…`, `analise/f5e_…` | F4 e F5 controladas pelo espectro: van Elteren e Mantel-Haenszel |
| `analise/modelo_logistico.csv` | regressão logística do voto pró-pauta, com e sem controle do espectro |
| `analise/`, demais arquivos | índice pró-pauta, fidelidade, composição dos quadrantes, Rice agregado e robustez |
