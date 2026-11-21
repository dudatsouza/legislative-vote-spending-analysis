<a name="readme-topo"></a>

<h1 align='center'>
  O custo do Não: gasto, produção e voto da Câmara dos Deputados em pautas sociais
</h1>

<div align='center'>

[![IDE][vscode-badge]][vscode-url]
[![Python][Python-badge]][Python-url]
[![Streamlit][streamlit-badge]][painel-url]

<b>
  Joaquim Cézar Santana da Cruz<br>
  Maria Eduarda Teixeira Souza<br>
</b>

<br>
Ciência dos Dados <br>
Engenharia de Computação <br>
UFCIMG Campus V <br>
2026/2

<br><br>

[![Abrir o painel interativo](https://img.shields.io/badge/Abrir_o_painel_interativo-2EA44F?style=for-the-badge&logo=streamlit&logoColor=white)][painel-url]

</div>

## Introdução

Este projeto é o trabalho final da disciplina de Ciência dos Dados. Ele investiga se o voto dos deputados federais em **pautas sociais** segue o partido e se ele tem relação com a **produtividade legislativa** e com o uso da **cota parlamentar (CEAP)**.

O trabalho percorre todo o ciclo de dados:

1. coleta automatizada da API da Câmara;
2. tratamento e integração de bases heterogêneas;
3. análise estatística;
4. visualização, com figuras estáticas, páginas interativas e um painel em Streamlit.

A análise é **descritiva e correlacional**. Não há modelos preditivos nem aprendizado de máquina.

## 📄 Artigo e Slides

- [**Artigo (IEEE)**](./docs/artigo.pdf): relatório completo, com metodologia, resultados e discussão.
- [**Slides**](./docs/slides.pdf): apresentação final.

## Base de Dados

**Recorte:** legislaturas 55ª a 57ª, de 01/02/2015 a 20/11/2026. A 57ª ainda está em curso e entra como dado parcial.

**Votações analisadas:** 8 votações nominais de Plenário.

- Redução da maioridade penal
- Teto de gastos
- Reforma Trabalhista
- Reforma da Previdência
- PEC dos Precatórios
- Igualdade salarial entre mulheres e homens
- Marco temporal das terras indígenas
- Fim da escala 6x1

| Dado | Origem |
|---|---|
| Votos, orientações e deputados | [API de Dados Abertos da Câmara](https://dadosabertos.camara.leg.br) |
| Proposições e autores | arquivos em lote da Câmara |
| CEAP (cota parlamentar) | arquivos em lote da Câmara e API (passagens) |
| Teto da CEAP por UF | Atos da Mesa ([`tetos_ceap.csv`](./data/referencia/tetos_ceap.csv)) |
| Espectro ideológico | Bolognesi, Ribeiro e Codato (2023) ([`espectro_partidos.csv`](./data/referencia/espectro_partidos.csv)) |
| Malha das UFs | IBGE |

> [!NOTE]
> O gasto é medido em relação ao teto da cota de cada UF, porque o teto varia com o custo das passagens. A produtividade conta as proposições normativas (PL, PLP, PEC e PDL) de que o deputado é o primeiro autor, por mês em exercício. Ela é comparada só entre deputados da mesma legislatura e com tempo de exercício parecido.

## Principais Resultados

1. **O voto segue o partido e o espectro.** O partido está associado ao voto em 7 das 8 votações (V de Cramér entre 0,72 e 0,85).
2. **Gasto e produtividade não andam juntos.** Nenhuma das 18 correlações de Spearman foi significativa após a correção de Holm.
3. **O perfil de gasto quase não muda o voto.** Sem controle, estar no quadrante "gasto alto / produtividade baixa" se associa ao voto em 2 votações. Comparando deputados do mesmo espectro, sobra só 1, a PEC dos Precatórios.

Os resultados podem ser explorados no [painel interativo][painel-url].

## 📚 O Projeto

O projeto foi desenvolvido em Python. O script [`pipeline.sh`](./pipeline.sh) executa as seis etapas em ordem:

| Etapa | Módulo | O que faz |
|---|---|---|
| 1. Coleta | [`src/extracao/`](./src/extracao/) | baixa da API e dos arquivos em lote, com cache em `data/raw/` |
| 2. Validação | [`src/validar_config.py`](./src/validar_config.py) | confere a configuração, as tabelas de referência e o sha256 dos dados brutos |
| 3. Tratamento | [`src/tratamento/`](./src/tratamento/) | integra votos, exercício, produtividade e gasto por deputado e legislatura |
| 4. Perfil | [`src/visualizacao/perfil_dados.py`](./src/visualizacao/perfil_dados.py) | relatório exploratório das bases (ydata-profiling) |
| 5. Análise | [`src/analise/`](./src/analise/) | testes com correção de Holm, controle pelo espectro, regressão logística e robustez |
| 6. Gráficos | [`src/visualizacao/`](./src/visualizacao/) | figuras do relatório (PDF) e versões interativas (HTML) |

Todos os parâmetros (votações, datas e limiares) ficam em [`src/config.py`](./src/config.py).

Os arquivos estão organizados assim:

* 📁 **[`data/`](./data/)**
  * 📁 **`raw/`**: dados brutos (não versionados, cerca de 1,4 GB)
  * 📁 **[`referencia/`](./data/referencia/)**: tabelas montadas à mão (partidos, espectro, blocos, tetos da CEAP, malha)
  * 📁 **[`processed/`](./data/processed/)**: bases tratadas
    * 📄 [`base_deputado_legislatura.csv`](./data/processed/base_deputado_legislatura.csv): base consolidada
    * 📄 [`votos.csv`](./data/processed/votos.csv): um voto por deputado e votação
    * 📄 [`manifesto_coleta.json`](./data/processed/manifesto_coleta.json): sha256 de cada arquivo bruto
    * 📁 **[`analise/`](./data/processed/analise/)**: resultados dos testes ([`testes_resumo.csv`](./data/processed/analise/testes_resumo.csv))
* 📁 **[`docs/`](./docs/)**
  * 📄 [`artigo.pdf`](./docs/artigo.pdf): artigo no formato IEEE
  * 📄 [`slides.pdf`](./docs/slides.pdf): slides da apresentação
* 📁 **[`figuras/`](./figuras/)**
  * 📁 **[`relatorio/`](./figuras/relatorio/)**: figuras do relatório e dos slides (PDF)
  * 📁 **[`interativas/`](./figuras/interativas/)**: dispersão, mapa por UF e hemiciclo (HTML)
  * 📁 **[`perfil/`](./figuras/perfil/)**: relatórios do ydata-profiling (HTML)
* 📁 **[`src/`](./src/)**
  * 📁 **[`extracao/`](./src/extracao/)**: [`camara_api.py`](./src/extracao/camara_api.py), [`coletar.py`](./src/extracao/coletar.py)
  * 📁 **[`tratamento/`](./src/tratamento/)**: [`tratar.py`](./src/tratamento/tratar.py)
  * 📁 **[`analise/`](./src/analise/)**: [`analisar.py`](./src/analise/analisar.py)
  * 📁 **[`visualizacao/`](./src/visualizacao/)**: [`graficos.py`](./src/visualizacao/graficos.py), [`mapa_hemiciclo.py`](./src/visualizacao/mapa_hemiciclo.py), [`perfil_dados.py`](./src/visualizacao/perfil_dados.py), [`painel.py`](./src/visualizacao/painel.py)
  * 📄 [`config.py`](./src/config.py)
  * 📄 [`validar_config.py`](./src/validar_config.py)
* 📄 [`pipeline.sh`](./pipeline.sh)
* 📄 [`requirements.txt`](./requirements.txt)
* 📄 [`requirements-perfil.txt`](./requirements-perfil.txt)

## Instalando e Executando

É preciso ter o [Python](https://www.python.org/downloads/) 3.10 ou superior instalado.

1. Clone o repositório:
```console
git clone https://github.com/dudatsouza/legislative-vote-spending-analysis.git
cd legislative-vote-spending-analysis
```

2. Rode a análise e os gráficos. As bases tratadas já estão no repositório, então não é preciso baixar nada. O script cria o ambiente `.venv` e instala as dependências sozinho:
```console
./pipeline.sh --de analise
```

3. Abra o painel localmente, em http://localhost:8501:
```console
.venv/bin/streamlit run src/visualizacao/painel.py
```

4. (Opcional) Refaça tudo desde a coleta. Isso baixa cerca de 1,4 GB da Câmara e leva algumas horas:
```console
./pipeline.sh
```

> [!TIP]
> `./pipeline.sh -h` lista as opções. Por exemplo, `--so graficos` roda uma etapa só e `--sem-coleta` reaproveita `data/raw/`. Cada execução grava um log em `logs/`.

## Dependências

As principais bibliotecas são:

- **requests e pandas:** coleta e tratamento.
- **scipy e statsmodels:** testes estatísticos e regressão logística.
- **matplotlib e SciencePlots:** figuras no padrão IEEE.
- **plotly:** páginas interativas.
- **streamlit:** painel.

> [!NOTE]
> O relatório exploratório usa o **ydata-profiling**, que ainda não roda no Python 3.14. Por isso ele tem um ambiente próprio, o `.venv_perfil`, com o [`requirements-perfil.txt`](./requirements-perfil.txt). O `pipeline.sh` cria esse ambiente automaticamente.

<p align="right">(<a href="#readme-topo">voltar ao topo</a>)</p>

## 🧪 Ambiente de Execução

O trabalho foi desenvolvido e testado no ambiente abaixo:

<div align='center'>

| *Hardware* | *Especificações* |
|:------------:|:-------------------:|
| *Laptop* | MacBook Air (M1, 2020) |
| *Processador* | Apple M1 |
| *Memória RAM* | 8 GB |
| *Sistema Operacional* | macOS 27 |
| *IDE* | Visual Studio Code |
| *Python* | 3.14 (e 3.9 no ambiente do ydata-profiling) |

</div>

> [!IMPORTANT]
> A Câmara atualiza os arquivos em lote com o tempo. Para obter os mesmos números, use as bases de `data/processed/` ou valide os dados brutos contra o [`manifesto_coleta.json`](./data/processed/manifesto_coleta.json).

<p align="right">(<a href="#readme-topo">voltar ao topo</a>)</p>

## 📨 Contato

<div align="center">
  <br><br>
     <i>Joaquim Cézar Santana da Cruz - Graduando - 8º Período de Engenharia de Computação @ UFCIMG</i>
  <br><br>

  [![Gmail][gmail-badge]][gmail-autor1]
  [![Linkedin][linkedin-badge]][linkedin-autor1]
  [![Telegram][telegram-badge]][telegram-autor1]
  
  <br><br>
     <i>Maria Eduarda Teixeira Souza - Graduando - 8º Período de Engenharia de Computação @ UFCIMG</i>
  <br><br>

  [![Gmail][gmail-badge]][gmail-autor2]
  [![Linkedin][linkedin-badge]][linkedin-autor2]
  [![Telegram][telegram-badge]][telegram-autor2]

</div>

<p align="right">(<a href="#readme-topo">voltar ao topo</a>)</p>

## 📚 Referências

1. CÂMARA DOS DEPUTADOS. **Dados Abertos da Câmara dos Deputados**. Disponível em: <https://dadosabertos.camara.leg.br>. Acesso em: 20 nov. 2026.

2. BOLOGNESI, B.; RIBEIRO, E.; CODATO, A. Uma nova classificação ideológica dos partidos políticos brasileiros. *Dados*, v. 66, n. 2, 2023.

3. RICE, S. A. The behavior of legislative groups: a method of measurement. *Political Science Quarterly*, v. 40, n. 1, p. 60-72, 1925.

4. DESPOSATO, S. W. Correcting for small group inflation of roll-call cohesion scores. *British Journal of Political Science*, v. 35, n. 4, p. 731-744, 2005.

5. HOLM, S. A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, v. 6, n. 2, p. 65-70, 1979.

6. MANTEL, N.; HAENSZEL, W. Statistical aspects of the analysis of data from retrospective studies of disease. *JNCI*, v. 22, n. 4, p. 719-748, 1959.

7. VAN ELTEREN, P. H. On the combination of independent two-sample tests of Wilcoxon. *Bulletin of the International Statistical Institute*, v. 37, n. 3, p. 351-361, 1960.

8. SEABOLD, S.; PERKTOLD, J. Statsmodels: econometric and statistical modeling with Python. In: *Proceedings of the 9th Python in Science Conference*, 2010.

9. RACIONAIS MC'S. **Sobrevivendo no Inferno**. São Paulo: Cosa Nostra, 1997. Álbum.

[macos-badge]: https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white
[macos-url]: https://www.apple.com/macos/
[vscode-badge]: https://img.shields.io/badge/Visual%20Studio%20Code-0078d7.svg?style=for-the-badge&logo=visual-studio-code&logoColor=white
[vscode-url]: https://code.visualstudio.com/
[Python-badge]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[streamlit-badge]: https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white
[painel-url]: https://legislative-vote-spending-analysis-4ignabvfueef24bd6et3hx.streamlit.app

[linkedin-autor1]: https://www.linkedin.com/in/joaquim-cruz-b760bb350/
[telegram-autor1]: https://t.me/joaquim1333
[gmail-autor1]: mailto:joaquimcezar930@gmail.com

[linkedin-autor2]: https://www.linkedin.com/in/dudatsouza/
[telegram-autor2]: https://t.me/dudat_18
[gmail-autor2]: mailto:dudateixeirasouza@gmail.com

[linkedin-badge]: https://img.shields.io/badge/-LinkedIn-0077B5?style=for-the-badge&logo=Linkedin&logoColor=white
[telegram-badge]: https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white
[gmail-badge]: https://img.shields.io/badge/-Gmail-D14836?style=for-the-badge&logo=Gmail&logoColor=white
