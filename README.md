# O custo do Não

**Uma Análise de Dados sobre Gasto, Produção e Voto no Legislativo em pautas sociais**

Trabalho da disciplina de Ciência dos Dados, Engenharia de Computação, CEFET-MG.
Alunos: Joaquim Cézar Santana da Cruz e Maria Eduarda Teixeira Souza. Professor: Higor Alexandre Duarte Mascarenhas.

O pré-projeto e os slides estão em [`docs/`](docs/).

## Pergunta de pesquisa

Existe relação entre o alinhamento partidário dos deputados federais e o padrão de voto em pautas de caráter social na Câmara dos Deputados, entre 2000 e 2026? E esse padrão se associa à produtividade legislativa e ao uso da cota parlamentar (CEAP)?

A análise é **descritiva e correlacional**. Não há modelos preditivos nem machine learning, conforme o escopo combinado com o professor.

## Estrutura

A estrutura de pastas segue as etapas do pipeline (Seção 6 do pré-projeto):

```
src/
  config.py                 votações selecionadas, recorte temporal e parâmetros
  extracao/                 1. coleta via API da Câmara e arquivos em lote
    camara_api.py             cliente HTTP: paginação, intervalo entre chamadas, cache em JSON
    coletar.py
  tratamento/               2. limpeza e junção das bases pelo id do deputado
    tratar.py                 votos (com ausências), Rice, produtividade, CEAP, base consolidada
  analise/                  3. Spearman, quadrantes pela mediana, qui-quadrado, composição partidária
    analisar.py
  visualizacao/             4. heatmap, barras e dispersão interativa
    graficos.py
data/
  raw/                      dados brutos (NÃO versionados)
  processed/                bases tratadas e resultados (versionados)
figuras/                    gráficos gerados
notebooks/                  exploração
docs/                       pré-projeto e slides
```

## Como rodar

Requer Python 3.10 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para rodar tudo de uma vez:

```bash
./pipeline.sh
```

Ou etapa por etapa, a partir da raiz do projeto:

```bash
python -m src.extracao.coletar tudo        # ou: votacoes | deputados | proposicoes | despesas
python -m src.tratamento.tratar
python -m src.analise.analisar
python -m src.visualizacao.graficos
```

Para encontrar o id de uma nova votação nominal, rode o comando abaixo. Ele lista as votações de Plenário da proposição e quantos votos individuais cada uma tem (0 significa votação simbólica):

```bash
python -m src.extracao.coletar localizar PL 6787 2016
```

Depois adicione a votação em `VOTACOES`, no arquivo [`src/config.py`](src/config.py).

A primeira coleta baixa cerca de 1 GB de arquivos em lote (proposições de 1999 a 2026 e CEAP de 2009 a 2026). As execuções seguintes usam o cache em `data/raw/`.

## Fontes

| Dado | Origem | Observação |
|---|---|---|
| Votos nominais | API `/votacoes/{id}`, `/votacoes/{id}/votos` | o partido vem registrado no momento do voto |
| Deputados em exercício na data | API `/deputados?dataInicio=&dataFim=` | usado para registrar a ausência como categoria própria |
| Partido, UF e sexo por legislatura | API `/deputados?idLegislatura=` | partido = última filiação registrada na API |
| Proposições e autores | arquivos `proposicoes-{ano}.csv` e `proposicoesAutores-{ano}.csv` | a API não tem `/deputados/{id}/proposicoes` (retorna 405) |
| CEAP | arquivos `camara.leg.br/cotas/Ano-{ano}.csv.zip` | CPF e outros dados pessoais são descartados na leitura |

## Decisões e limitações encontradas na coleta

Estes pontos diferem do pré-projeto e precisam ser discutidos pelo grupo:

1. **O Estatuto do Desarmamento (2003) e a Lei Maria da Penha (2006) foram aprovados por votação simbólica no Plenário da Câmara.** A API não tem voto individual para eles: as votações `125878-87`, `125878-112`, `272058-94` e `272058-97` retornam 0 votos. As duas matérias continuam em `config.py`, marcadas como `nominal: False`, e ficam fora das análises de voto. Para cobrir as legislaturas 51 a 54, o grupo precisa escolher outras votações nominais.
2. **A redução da maioridade penal (PEC 171/1993, 2º turno, `14493-536`) foi incluída.** Ela é citada na introdução e tem votação nominal (320 Sim, 152 Não).
3. **Para a Reforma Trabalhista foi usado o texto-base (`2122076-348`, Subemenda Substitutiva Global, 296 Sim e 177 Não).** A redação final (`2122076-411`) foi simbólica.
4. **A CEAP só existe a partir de 2009.** As legislaturas 51 e 52 não têm dado de gasto, e a 53 tem dado parcial. A análise de gasto × produtividade vale da 53ª à 57ª legislatura.
5. **Direção do voto.** O qui-quadrado é calculado por votação, com Sim e Não brutos. Para agregar várias votações num índice "pró-pauta social", o grupo precisa definir, em cada matéria, qual voto é favorável à pauta. Essa é uma decisão de pesquisa e não foi tomada no código.
6. **Produtividade.** Conta só a autoria proponente dos tipos listados em `TIPOS_PROPOSICAO`. A produtividade qualificada exclui do denominador as proposições sem situação registrada.
7. **Filiação partidária.** No voto, o partido é o do momento da votação. Na base por legislatura, é a última filiação registrada na API. O cruzamento com o TSE (fonte complementar) ainda não foi implementado.

## Resultados (data/processed)

| Arquivo | Conteúdo |
|---|---|
| `votos.csv` | deputado × votação, com Sim, Não, Abstenção, Obstrução, Artigo 17 e Ausente |
| `coesao_rice.csv` | índice de Rice por partido × votação |
| `base_deputado_legislatura.csv` | partido, UF, sexo, produtividade e gasto por deputado × legislatura |
| `spearman_gasto_produtividade.csv` | rho e p-valor por legislatura |
| `quadrantes.csv` | quadrante (pela mediana) de cada deputado |
| `quiquadrado_quadrante_voto.csv` | teste de independência entre quadrante e voto |
| `composicao_partidaria.csv` | peso do partido no quadrante vs. na amostra |
| `tabulacao_partido_voto.csv` | tabulação cruzada partido × voto |
