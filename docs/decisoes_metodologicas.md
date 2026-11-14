# Decisões metodológicas: *O custo do Não*

Este documento registra as decisões metodológicas que o grupo tomou depois da apresentação do pré-projeto (29/09/2026). Elas partiram de uma auditoria do código e das bases da primeira versão do pipeline, feita em 14/11/2026.

Cada decisão segue a mesma estrutura:

- **Contexto:** o problema encontrado ou a lacuna do pré-projeto;
- **Decisão:** a regra adotada, escrita de forma operacional, para ser implementada sem ambiguidade;
- **Justificativa:** por que essa opção, e não as alternativas;
- **Limitações:** o que a regra não resolve e precisa constar no relatório.

Os códigos **D1–D18** identificam cada definição. **D4** (critério de "pauta de cunho social") ainda está em aberto e será redigido para o relatório; as demais estão fechadas.

> **Status:** definições fechadas, implementação pendente. Os números citados nos contextos vêm das bases da primeira versão (`data/processed/`, commit `99b94de`) e de consultas à API da Câmara feitas em 14/11/2026.

---

## Sumário

| Código | Tema | Decisão em uma linha |
|---|---|---|
| D1 | Janela temporal | 2015–2026 (legislaturas 55ª a 57ª); a 57ª entra como dado parcial |
| D2 | Unidades de análise | deputado × votação e deputado × legislatura |
| D3 | População e faixas | ≥ 12 meses de exercício; faixas C/B/A; casos extremos por P80/P20 |
| D4 | Pauta de cunho social | *em aberto (texto do relatório)* |
| D5 | Categorias de voto | `voto_valido` = Sim/Não, com obstrução contada como Não; ausência é categoria própria |
| D6 | Direção pró-pauta | Definida por votação; Precatórios fora do índice agregado |
| D7 | Partido do deputado | No voto: o da data do voto. Na legislatura: o partido com mais dias |
| D8 | Harmonização de siglas | Mudança de nome = mesmo partido; fusões pela sigla vigente ou pela família, conforme a análise |
| D9 | Espectro ideológico | Bolognesi, Ribeiro e Codato (2023), agregado em esquerda, centro e direita |
| D10 | Coesão (Rice) | ≥ 5 votos válidos; média ponderada; correção de Desposato como robustez |
| D11 | Alinhamento partidário | Fidelidade à orientação do partido e do Governo |
| D12 | Meses de exercício | Dias em exercício pelo histórico oficial ÷ 30,44 |
| D13 | Produtividade bruta | Proposições normativas como primeiro autor, por mês |
| D14 | Produtividade qualificada | Proporção aprovada na Câmara |
| D15 | Gasto da CEAP | Gasto ÷ teto da cota da UF vigente em cada mês |
| D16 | Quadrantes | Mediana dentro de legislatura × faixa |
| D17 | Bancada | Retirada do escopo |
| D18 | Critérios estatísticos | α = 0,05; Holm por família; permutação; tamanhos de efeito |

---

## 1. Escopo

### D1. Janela temporal

**Contexto.** O pré-projeto propõe analisar de 2000 a 2026 (legislaturas 51ª a 57ª). A primeira versão do pipeline mostrou que essa janela não se sustenta:

- a CEAP só existe a partir de 2009, então as legislaturas 51ª e 52ª não têm dado de gasto e a 53ª tem dado parcial (22 a 24 meses);
- o Estatuto do Desarmamento (2003) e a Lei Maria da Penha (2006) foram aprovados por votação simbólica, sem voto individual registrado;
- as 3 votações efetivamente coletadas se concentravam na 55ª e na 57ª legislatura.

Com isso, as perguntas sobre gasto não valiam para metade do período, e a pergunta central dependia de votações de só duas legislaturas.

**Decisão.** O recorte vai de **01/02/2015 até a data da coleta**, cobrindo as **legislaturas 55ª, 56ª e 57ª**. A 57ª (que termina em 31/01/2027) está em curso e entra como dado parcial, com a data de corte declarada no relatório.

**Justificativa.**
- A CEAP está completa nas três legislaturas, então todas as perguntas valem para todo o recorte.
- As siglas partidárias do período são as atuais ou têm sucessoras conhecidas, o que reduz o trabalho de harmonização (D8).
- O período cobre quatro governos (Dilma 2, Temer, Bolsonaro e Lula 3) e o contexto de polarização descrito na introdução do pré-projeto.
- A consulta à API mostrou que há votações nominais de cunho social suficientes no período (ver 2.1).

**Limitações.**
- Diverge do pré-projeto (2000–2026), o que deve ser declarado.
- A 57ª legislatura está incompleta: medidas que dependem do tempo, como a produtividade qualificada (D14), ficam desfavorecidas nela. Isso é mitigado por comparar cada legislatura só consigo mesma.

### D2. Unidades de análise

**Contexto.** O projeto cruza dados de naturezas diferentes. O voto acontece em uma data; gasto e produtividade se acumulam ao longo da legislatura. Misturar as duas escalas sem regra explícita gera junções ambíguas.

**Decisão.** São duas unidades:
- **deputado × votação:** usada para voto, coesão, alinhamento e direção pró-pauta;
- **deputado × legislatura:** usada para gasto, produtividade, faixas e quadrantes.

A ligação entre as duas é feita pelo par (`id_deputado`, legislatura em que a votação ocorreu).

**Justificativa.** Gasto e produtividade só fazem sentido acumulados num período. Votos são eventos pontuais. A chave composta é a forma mais simples de cruzar os dois níveis sem duplicar informação.

**Limitações.** O quadrante de um deputado usa o gasto e a produtividade **da legislatura inteira**, inclusive o período depois da votação. Por exemplo, a votação do Teto (2016) é cruzada com o gasto de 2015 a 2019. A relação entre quadrante e voto é de associação, não de precedência temporal.

### D3. População e faixas de tempo de exercício

**Contexto.** Na primeira versão, a produtividade era uma **contagem total na legislatura** e o gasto era uma **média mensal**. Quem ficou 4 anos produz mais que um suplente que ficou 3 meses, e isso criava uma correlação artificial entre as duas variáveis. Recalculando o Spearman só com deputados de mandato completo, o resultado muda de sinal:

| Leg. | ρ original | ρ com ≥ 36 meses de exercício |
|---|---|---|
| 54ª | 0,386 | 0,113 |
| 55ª | 0,214 | −0,040 |
| 56ª | 0,097 | −0,116 |
| 57ª | 0,214 | −0,105 |

Além disso, 32% dos deputados do quadrante "gasto baixo / produtividade baixa" tinham menos de 12 meses de mandato: o quadrante refletia a duração do mandato, não o comportamento.

Uma alternativa avaliada foi comparar cada deputado só com quem ficou **exatamente** o mesmo número de meses. Ela se mostrou inviável: nas legislaturas 55ª–57ª, 65 das 101 combinações de legislatura × mês têm menos de 5 deputados.

**Decisão.**
1. Entram nas análises de gasto e produtividade os deputados com **≥ 12 meses de exercício** na legislatura, contados pelo histórico oficial (D12).
2. Cada deputado é classificado em uma faixa dentro da sua legislatura:
   - **Faixa C:** 12 a 23 meses;
   - **Faixa B:** 24 a 35 meses;
   - **Faixa A:** 36 meses ou mais (na 57ª, até a data de corte).
3. Medianas, quadrantes (D16) e correlações são calculados **dentro de cada legislatura × faixa**, com as métricas normalizadas por mês (D13, D15).
4. **Caso extremo:** deputado com gasto relativo **acima do P80** e produtividade **≤ P20** do seu estrato. Usa-se "≤" porque o P20 da produtividade pode ser zero nas faixas pequenas.
5. **Comparação ascendente:** cada caso extremo é recomparado com as faixas mais longas da mesma legislatura. O relatório informa o percentil que ele teria nessas distribuições. Exemplo: "com 14 meses de mandato, o deputado X estaria no percentil 97 de gasto entre os deputados de mandato completo".
6. O relatório informa quantos deputados foram excluídos (menos de 12 meses) em cada legislatura.

Tamanho aproximado dos estratos na primeira versão (usando meses com gasto como aproximação):

| Leg. | < 12 m (excluídos) | C: 12–23 | B: 24–35 | A: ≥ 36 |
|---|---|---|---|---|
| 55ª | 49 | 45 | 56 | 473 |
| 56ª | 62 | 29 | 26 | 494 |
| 57ª | 90 | 44 | 47 | 464 |

**Justificativa.**
- A estratificação compara cada deputado com pares de tempo de exercício semelhante.
- A normalização por mês permite a comparação ascendente (item 5).
- O corte de 12 meses elimina passagens curtas, em que médias mensais são instáveis.
- P80/P20 foi escolhido no lugar de P90/P10 porque gera casos também nas faixas pequenas. Supondo gasto e produtividade independentes, a regra marca cerca de 4% de cada estrato: uns 19 deputados por legislatura na faixa A e 1 a 2 nas faixas B e C. Com P90/P10, as faixas pequenas quase nunca teriam um caso.

**Limitações.**
- O termo "caso extremo" é operacional (definido pela regra acima), não um outlier estatístico no sentido clássico (IQR, z-score). A comparação ascendente é o que distingue o caso realmente excepcional.
- Cerca de 11% dos deputados (os com menos de 12 meses) ficam fora das análises de gasto e produtividade. Eles continuam nas análises de voto.

---

## 2. Votações

### 2.1 Seleção das votações (D4 em aberto)

**Contexto.**
- O pré-projeto citava o Estatuto do Desarmamento, a Lei Maria da Penha, a Reforma Trabalhista e a PEC 6x1, com a lista "a ampliar".
- Os dois primeiros foram votações simbólicas (a API retorna 0 votos individuais).
- A primeira versão do pipeline tinha só 3 votações nominais (maioridade penal, Reforma Trabalhista e PEC 6x1), e a 6x1 foi quase unânime (461 × 19).
- A consulta à API mostrou que **há votos individuais desde 2003**. A limitação era de seleção, não da fonte.
- Pautas relevantes também foram simbólicas: revisão da Lei de Cotas (2023), fim da "saidinha" (2024), Mais Médicos (2013), Estatuto da Pessoa com Deficiência (2015) e Feminicídio (2015).

**Decisão.** São 8 votações nominais de mérito no Plenário. Em PEC, usa-se o 2º turno:

| Leg. | Data | Matéria | `id_votacao` | Sim × Não | Divide o Plenário? |
|---|---|---|---|---|---|
| 55ª | 19/08/2015 | Redução da maioridade penal (PEC 171/1993, 2º turno) | `14493-536` | 320 × 152 | sim |
| 55ª | 25/10/2016 | Teto de gastos (PEC 241/2016, 2º turno) | `2088351-324` | 359 × 116 | sim |
| 55ª | 26/04/2017 | Reforma Trabalhista (PL 6787/2016, texto-base) | `2122076-348` | 296 × 177 | sim |
| 56ª | 06/08/2019 | Reforma da Previdência (PEC 6/2019, 2º turno) | `2192459-786` | 370 × 124 | sim |
| 56ª | 09/11/2021 | PEC dos Precatórios (PEC 23/2021, 2º turno) | `2293449-241` | 323 × 172 | sim |
| 57ª | 04/05/2023 | Igualdade salarial entre mulheres e homens (PL 1085/2023) | `2351179-51` | 325 × 36 | pouco |
| 57ª | 30/05/2023 | Marco temporal das terras indígenas (PL 490/2007) | `345311-270` | 283 × 155 | sim |
| 57ª | 27/05/2026 | PEC do fim da escala 6x1 (PEC 221/2019, 2º turno) | `2233802-438` | 461 × 19 | não |

**Justificativa.**
- Toda legislatura tem pelo menos duas votações, e 6 das 8 dividem o Plenário.
- As votações cobrem três governos (Temer, Bolsonaro e Lula 3) e vários temas: trabalho, previdência, gasto social, assistência, segurança, direitos indígenas e gênero.
- A direção do "Sim" varia (em umas amplia direitos, em outras restringe; ver D6). Isso impede que o resultado reflita só a tendência de votar Sim.
- As votações quase unânimes (Igualdade e 6x1) servem à parte descritiva e a testes específicos, como sexo × voto na Igualdade salarial.

**Limitações.**
- Três das oito matérias são fiscais (Teto, Previdência e Precatórios). O critério de "cunho social" (D4) precisa justificar a inclusão delas.
- A Lei de Cotas, que abre o pré-projeto, não tem votação nominal de mérito na Câmara e fica fora do estudo.

**D4 (em aberto).** Rascunho do critério a refinar no relatório: entra a votação que, ao mesmo tempo, (1) trata de matéria que altera direitos ou benefícios sociais (trabalho, previdência, assistência, educação e saúde, segurança pública ou direitos de grupos específicos); (2) é nominal e no Plenário da Câmara; (3) é de mérito (texto principal, sem requerimentos, destaques, emendas isoladas ou redação final); (4) está dentro do recorte D1.

### D5. Categorias de voto

**Contexto.** A API registra Sim, Não, Abstenção, Obstrução e "Artigo 17" (o presidente da sessão). A ausência não vem registrada e precisa ser deduzida da lista de deputados em exercício na data. O pré-projeto define o Rice só com Sim e Não e não diz nada sobre obstrução.

**Decisão.**
1. São guardadas duas variáveis:
   - `voto_original`: Sim, Não, Abstenção, Obstrução, Art. 17 ou Ausente;
   - `voto_valido`: Sim ou Não, com **Obstrução contada como Não**.
2. **Ausente:** deputado em exercício na data da votação sem voto registrado. É uma categoria própria, não dado faltante.
3. **Abstenção e Ausente** ficam fora dos votos válidos, mas permanecem na base.
4. **Art. 17:** o presidente da sessão sai da população daquela votação.
5. Rice, qui-quadrado, alinhamento e índice pró-pauta usam `voto_valido`. Tabelas descritivas e a análise de ausência usam `voto_original`.
6. Nas orientações de bancada (D11), "Obstrução" também equivale a "Não".

**Justificativa.** A obstrução é uma tática de quem se opõe à aprovação da matéria: o deputado tenta impedir o quórum ou adiar a votação. Tratá-la como Não respeita a intenção do voto.

**Limitações.** Hoje o impacto é nulo: nenhuma das 8 votações tem voto ou orientação de obstrução. A regra fica definida por robustez e para votações futuras. Pequenas imprecisões na lista de "em exercício na data" (por exemplo, 516 registros na Reforma Trabalhista, para 513 cadeiras) devem ser corrigidas com os períodos de exercício do D12.

### D6. Direção pró-pauta

**Contexto.** O botão Sim ou Não não tem sentido fixo em relação à pauta social. Na PEC 6x1, votar Sim amplia um direito; na Reforma Trabalhista, votar Sim reduz proteções. Somar os "Não" das duas votações soma posições opostas. A primeira versão do pipeline reportava "% de Não" em todas as votações, o que inverte a leitura em várias delas. O título *O custo do Não* também pressupõe que o "Não" é o voto contra a pauta, mas nas votações divisivas o voto contrário à pauta costuma ser o **Sim**.

**Decisão.**
1. Para cada votação, `direcao_pro_pauta ∈ {Sim, Não, ambígua}`. A direção pró-pauta é o voto que **amplia ou preserva o direito ou benefício do grupo diretamente afetado**, conforme a ementa e o texto votado.
2. `pro_pauta(d, v) = 1` se `voto_valido = direcao_pro_pauta`; `0` caso contrário. Abstenção e ausência não entram.
3. **Índice pró-pauta** do deputado = média de `pro_pauta` nos seus votos válidos, calculada por legislatura. A 56ª entra, mesmo tendo uma única votação no índice.
4. Votações ambíguas ficam **fora do índice agregado**, mas entram em todas as análises por votação.
5. O título *O custo do Não* é mantido. No relatório, "o Não" é definido como **o voto contrário à pauta social**, seja qual for o botão.

| Votação | Grupo diretamente afetado | Efeito do Sim | Voto pró-pauta |
|---|---|---|---|
| Maioridade penal | Adolescentes (proteção do ECA) | Reduz a idade penal | **Não** |
| Teto de gastos | Usuários de saúde e educação públicas | Limita o crescimento do gasto social | **Não** |
| Reforma Trabalhista | Trabalhadores | Flexibiliza a CLT | **Não** |
| Reforma da Previdência | Segurados e aposentados | Endurece o acesso a benefícios | **Não** |
| PEC dos Precatórios | Beneficiários do Auxílio Brasil × credores da União | Amplia a transferência de renda e adia precatórios | **ambígua** |
| Igualdade salarial | Mulheres trabalhadoras | Garante igualdade salarial | **Sim** |
| Marco temporal | Povos indígenas | Restringe as demarcações | **Não** |
| PEC 6x1 | Trabalhadores | Reduz a jornada | **Sim** |

**Por que a PEC dos Precatórios fica fora do índice.** A PEC limitou o pagamento anual de precatórios (dívidas judiciais da União, entre elas dívidas alimentares e valores ligados à educação) e, mudando o cálculo do teto, abriu espaço para o Auxílio Brasil. Com dois grupos afetados em sentidos opostos, o critério do item 1 dá duas respostas, e qualquer direção escolhida pesaria no índice de todos os deputados da 56ª. Ela continua no estudo como **estudo de caso governo × ideologia**: mostra se os partidos votam pelo conteúdo social da pauta ou pela posição em relação ao governo.

**Justificativa.** Uma direção por votação, com um critério único e escrito, torna o índice comparável entre votações. Também separa o que depende de juízo normativo (só o índice agregado) do que não depende (todas as análises por votação).

**Limitações.**
- A direção é uma decisão normativa. Para torná-la defensável, o relatório traz a tabela acima com a fonte de cada linha (ementa e texto aprovado) e, quando houver, a confronta com uma referência externa (por exemplo, a posição do DIAP nas votações trabalhistas).
- A maioridade penal é a classificação mais discutível, porque também pode ser lida como pauta de segurança pública.
- Na 56ª, o índice se apoia em uma única votação (a Previdência).

---

## 3. Partidos

### D7. Partido do deputado

**Contexto.** A primeira versão usava regras diferentes em cada base:
- **no voto:** o partido registrado no momento da votação;
- **na base por legislatura:** a última filiação registrada na API.

O partido do voto divergia do partido da base em **42% dos deputados** na maioridade penal e em **33%** na Reforma Trabalhista, pela soma de mudanças de nome e trocas de partido (janelas de 2016, 2018 e 2022). Partidos apareciam em legislaturas anteriores à sua fundação (o PROS, criado em 2013, aparecia na 54ª).

**Decisão.**
- **Nas análises por votação:** o partido registrado pela Câmara na data do voto.
- **Na base deputado × legislatura:** o partido em que o deputado passou **mais dias** naquela legislatura, calculado pelo histórico oficial (`/deputados/{id}/historico`, ver D12). Mudanças de nome são unificadas antes da contagem (D8).

**Justificativa.** O histórico oficial dá as filiações com data, e a regra de "mais dias" representa melhor o deputado na legislatura do que a última filiação. Essa fonte também torna desnecessário o cruzamento com o TSE previsto no pré-projeto.

**Limitações.** Um deputado que mudou de partido no meio da legislatura é representado por um só partido nas análises de gasto e produtividade.

### D8. Harmonização de siglas

**Contexto.** A API traz sufixos espúrios (`PP**` em 159 registros das legislaturas 52ª–54ª, `PL*`, `PSD*`). Na mesma votação, votantes aparecem como `PP` e ausentes como `PP**`, e `PP**` aparecia como partido próprio nas figuras. Entre 2015 e 2026 houve várias mudanças de nome e fusões, que impedem comparar partidos entre legislaturas sem uma tabela de correspondência.

**Decisão.**
1. **Limpeza:** remover sufixos (`PP**` → `PP`) e padronizar grafias (`SD` = `SOLIDARIEDADE`, `PATRI` = `PATRIOTA`).
2. **Mudança de nome = mesmo partido, em todas as análises.** A identidade do partido é uma só; nas análises por votação, o rótulo exibido é o vigente na data.

   | Antes | Depois | Ano |
   |---|---|---|
   | PMDB | MDB | 2018 |
   | PTN | PODE | 2017 |
   | PTdoB | AVANTE | 2017 |
   | PEN | PATRIOTA | 2018 |
   | PSDC | DC | 2018 |
   | PRB | REPUBLICANOS | 2019 |
   | PR | PL | 2019 |
   | PPS | CIDADANIA | 2019 |
   | PTC | AGIR | 2022 |

3. **Fusões e incorporações:**
   - **(i) Análises por votação:** a sigla vigente na data, sem retroagir.
   - **(ii) Comparação temporal entre legislaturas:** a família partidária, isto é, o partido resultante.

   | Origem | Família | Ano |
   |---|---|---|
   | PHS | PODE | 2019 |
   | PRP | PATRIOTA → PRD | 2019 |
   | PPL | PCdoB | 2019 |
   | DEM + PSL | UNIÃO | 2022 |
   | PROS | SOLIDARIEDADE | 2023 |
   | PSC | PODE | 2023 |
   | PTB + PATRIOTA | PRD | 2023 |

4. **Federações** (PT-PCdoB-PV, PSOL-REDE, PSDB-Cidadania) **não são fusões**: cada partido mantém sua sigla. Elas só importam nas orientações (D11).
5. Partidos novos que aparecem nos dados (por exemplo, MISSÃO) formam família própria.

**Justificativa.** A sigla vigente preserva o contexto de cada votação. A família permite a comparação temporal sem "partidos que somem".

**Limitações.**
- **A família acompanha a legenda, não os deputados.** O caso mais claro é o PSL: na regra (ii) ele entra na família UNIÃO, mas boa parte da bancada eleita pelo PSL em 2018 migrou para o PL em 2022. A comparação temporal descreve a trajetória das legendas, não dos grupos de deputados.
- **Datas conferidas no TSE (14/11/2026):** os 18 eventos estão em `data/referencia/partidos.csv` com a data exata da decisão do TSE, o número do processo e a fonte ([Partidos registrados no TSE](https://www.tse.jus.br/partidos/partidos-registrados-no-tse/registrados-no-tse), seção "Fusões, incorporações e mudanças de nomenclatura"). Os anos das tabelas acima são os das decisões do TSE. Dois casos:
  - **PMDB → MDB:** a convenção do partido foi em dezembro de 2017, mas a decisão do TSE é de 15/05/2018.
  - **PR → PL:** a resolução do partido é de 09/02/2019 (a data que aparece na tabela do TSE), mas o julgamento no TSE foi em 07/05/2019 ([notícia do TSE](https://www.tse.jus.br/comunicacao/noticias/2019/Maio/aprovada-alteracao-do-nome-do-partido-da-republica-pr-para-partido-liberal-pl)). Usa-se a data do julgamento, pelo mesmo critério dos demais eventos.

### D9. Espectro ideológico

**Contexto.** O objetivo específico (d) do pré-projeto pede verificar se o padrão "está disperso entre diferentes espectros políticos", mas a primeira versão não tinha nenhuma classificação ideológica dos partidos.

**Decisão.**
1. Cada partido é classificado segundo **Bolognesi, Ribeiro e Codato (2023)**, agregado em três categorias:
   - extrema-esquerda, esquerda e centro-esquerda → **esquerda**;
   - centro → **centro**;
   - centro-direita, direita e extrema-direita → **direita**.
2. Partidos que mudaram de nome mantêm a classificação (D8).
3. **Fusões e incorporações:**
   - se as origens têm a mesma categoria, o novo partido herda essa categoria;
   - se divergirem, usa-se a **média dos escores contínuos** das origens, agregada pela regra do item 1.
4. **Partidos criados depois do survey e sem origem classificável** são classificados manualmente pelo grupo, com base em fontes documentais (estatuto, programa, manifesto de fundação, origem dos fundadores). **Nunca** se usa o comportamento de voto nas votações analisadas, o que tornaria a análise circular. Cada caso vai para uma tabela no relatório com justificativa e fonte.
5. **Robustez:** as análises por espectro são rodadas com e sem os partidos classificados manualmente.

**Justificativa.** É uma classificação recente, baseada em survey com especialistas e citável. A agregação em três categorias segue a dos próprios autores, sem criar cortes do grupo.

**Tabela preenchida (14/11/2026, `data/referencia/espectro_partidos.csv`).** Os escores vêm da Tabela 1 do artigo (médias de 0 a 10, survey ABCP de julho de 2018, pp. 6–7). As categorias vêm dos cortes da p. 16: até 1,50 extrema-esquerda; 1,51–3,00 esquerda; 3,01–4,49 centro-esquerda; 4,50–5,50 centro; 5,51–7,00 centro-direita; 7,01–8,50 direita; a partir de 8,51 extrema-direita. Resultado nos partidos do período:
- **esquerda:** PSOL, PCdoB, PT, PDT, PSB;
- **centro:** REDE, CIDADANIA (ex-PPS), PV;
- **direita:** todos os demais.

O MDB (7,01) fica exatamente na fronteira entre centro-direita e direita; a nota 7 do artigo discute esse caso. Nas fusões, as origens divergem nas 7 categorias, então se usa a média: UNIÃO = (DEM 8,57 + PSL 8,11)/2 = 8,34; PRD = (PATRIOTA 8,55 + PTB 6,10)/2 = 7,325. Os dois ficam na direita. O validador confere a categoria contra o escore e a média das fusões.

**Limitações.**
- A classificação é **estática** (survey de 2018) e é aplicada a 2015–2026. Partidos que mudaram de perfil no período (o PSL antes e depois de 2018, o PL depois de 2021) ficam com uma única posição.
- O artigo indica que o centro é pouco povoado, então a categoria "centro" pode ficar pequena. Se ficar, isso é reportado como resultado, não corrigido.

---

## 4. Coesão e alinhamento

### D10. Coesão partidária (índice de Rice)

**Contexto.** O Rice já estava implementado com a fórmula correta, mas:
- o corte mínimo de tamanho contava ausentes;
- partidos com 1 ou 2 votos geram valores triviais (com 1 voto o Rice é sempre 100; com 2, só 0 ou 100);
- deputados "sem partido" (`S.PART.`) apareciam como se fossem um partido.

Efeito de cada corte nas 8 votações:

| Corte | Pares partido × votação excluídos | Votos válidos excluídos |
|---|---|---|
| ≥ 3 | 27 de 195 | 1,0% |
| ≥ 5 | 48 de 195 | 3,1% |
| ≥ 10 | 87 de 195 | 10,3% |

**Decisão.**

`Rice(p, v) = |Sim − Não| / (Sim + Não) × 100`

1. Usa os votos válidos do D5 e o partido vigente na data do voto (D8-i). Cada partido de uma federação é contado separadamente.
2. É calculado só para partidos com **≥ 5 votos válidos** na votação. Os abaixo do corte aparecem marcados como "n < 5" nas figuras e continuam nas demais análises.
3. Deputados sem partido são excluídos.
4. A agregação por votação e por legislatura é a **média ponderada pelos votos válidos** de cada partido.
5. **Robustez:** a correção de Desposato (2005) para grupos pequenos, para verificar se a ordenação dos partidos se mantém.

**Justificativa.** Com 3 ou 4 votos, o Rice só assume 2 ou 3 valores possíveis e não diz nada sobre coesão. A média ponderada representa o Plenário como um todo, que é o objeto da pergunta.

**Limitações.**
- O corte tira do Rice partidos ideologicamente marcados em algumas votações: PSOL na maioridade, NOVO, REDE e Cidadania em várias. Eles continuam nas outras análises.
- O Rice mede **coesão, não direção**: dois partidos com Rice 100 podem ter votado em lados opostos. A direção é coberta pelo D6 e pelo D11.

### D11. Alinhamento partidário

**Contexto.** A pergunta central fala em "alinhamento partidário", mas a primeira versão só calculava coesão (Rice), que não diz se o deputado seguiu o partido. A API tem as orientações das lideranças (`/votacoes/{id}/orientacoes`), com dados para as 8 votações, mas:
- as orientações vêm muitas vezes **por bloco ou federação**, com nomes concatenados (`PmdbPpPtbPscPhsPen`, `Fdr PSOL-REDE`);
- há orientações "Liberado" ou em branco;
- nem toda votação tem orientação do Governo.

**Decisão.**
1. **Fidelidade:** `fiel(d, v) = 1` se o `voto_valido` do deputado for igual à orientação do seu partido; `0` caso contrário.
2. **Taxa de fidelidade** = votos fiéis / votos válidos com orientação definida. É calculada por deputado, partido, espectro e legislatura.
3. **Alinhamento ao governo:** mesma fórmula, usando a orientação "Governo". Votações sem orientação do Governo ficam fora dessa medida.
4. **Bloco ou federação:** os partidos do bloco herdam a orientação dele. Se o partido tiver orientação própria na mesma votação, **a própria prevalece**.
5. "Liberado" ou em branco tiram o deputado do cálculo naquela votação. "Obstrução" equivale a "Não" (D5).
6. As orientações de Maioria, Minoria e Oposição não são usadas.

**Justificativa.** A fidelidade à orientação é a forma mais direta de medir alinhamento partidário, e o alinhamento ao governo permite separar ideologia de pertencer à base ou à oposição.

**Limitações.** A tradução de bloco em partidos exige uma tabela montada por parsing dos nomes e conferida à mão.

---

## 5. Produtividade e gasto

### D12. Meses de exercício

**Contexto.** A primeira versão usava "meses com gasto na CEAP" como medida de tempo de mandato. Isso subestima quem passou meses sem gastar e não distingue licenças e afastamentos.

**Decisão.**
1. Os períodos de exercício vêm de `/deputados/{id}/historico`. Um período começa num registro com `situacao = "Exercício"` e termina no registro seguinte da mesma legislatura.
2. Registros com `situacao` vazia são descartados. A API tem registros espúrios com data de 01/02/2023 ("Nome no início da legislatura"), inclusive para legislaturas antigas.
3. **Meses de exercício** = dias em exercício na legislatura ÷ 30,44. Licenças e afastamentos não contam; suplentes contam só enquanto estão em exercício.
4. Na 57ª legislatura, a contagem vai até a data de corte (D1).
5. A mesma fonte dá o partido com mais dias (D7).

**Justificativa.** O histórico é a fonte oficial do vínculo do deputado com o mandato, e a contagem em dias é precisa para mandatos parciais.

**Limitações.** A qualidade da medida depende da consistência do histórico da API, que tem registros espúrios conhecidos.

### D13. Produtividade bruta

**Contexto.** A primeira versão contava, com o mesmo peso:
- proposições normativas (PL, PLP, PEC, PDL);
- requerimentos e indicações (REQ, RIC, INC), que são produzidos em massa.

Havia deputados com mais de 5 mil proposições em uma única legislatura, e a mediana subia de 33 (53ª) para 106 (57ª), em parte pela facilidade do protocolo eletrônico de requerimentos. Uma indicação valia o mesmo que uma PEC. Além disso, o crédito de coautoria precisava de regra.

**Decisão.**
1. Contam as proposições **normativas** (PL, PLP, PEC, PDL) apresentadas na legislatura em que o deputado é o **primeiro autor**: `ordemAssinatura = 1` e `proponente = 1`.
2. **Produtividade bruta mensal** = contagem ÷ meses de exercício (D12).
3. Proposições de autoria de comissões, do Executivo ou do Senado não são atribuídas a nenhum deputado.
4. REQ, RIC e INC ficam fora da métrica principal.

**Justificativa.** As proposições normativas correspondem à "produção legislativa" do pré-projeto, e o critério do primeiro autor dá uma atribuição única por proposição. A normalização por mês corrige o efeito do tempo de exercício (D3).

**Limitações.** Proposições coletivas costumam ser encabeçadas pelo líder da bancada (por exemplo, PDLs de sustação de decretos assinados por toda a oposição). Com o critério do primeiro autor, **o líder recebe todo o crédito e os demais coautores nenhum**, o que tende a inflar a produtividade de líderes.

### D14. Produtividade qualificada

**Contexto.** A primeira versão definia "avançou" como "não está arquivada". A média da métrica crescia de forma monotônica com o tempo:

| Leg. | 51ª | 52ª | 53ª | 54ª | 55ª | 56ª | 57ª |
|---|---|---|---|---|---|---|---|
| Média | 0,03 | 0,11 | 0,19 | 0,27 | 0,36 | 0,55 | 0,72 |

Ela media quanto tempo as proposições tiveram para ser arquivadas, não quanto elas avançaram:
- proposições recentes ainda estão "Aguardando Designação de Relator", e a regra contava isso como avanço;
- pelo art. 105 do Regimento Interno, proposições são arquivadas automaticamente no fim da legislatura, então "Arquivada" não significa "não avançou".

O arquivo de proposições de 2019 (6.456 normativas, de todos os autores) mostra a distribuição das situações:

| Situação | Proporção |
|---|---|
| Tramitando em Conjunto (apensada) | 41% |
| Aguardando relator, parecer ou pauta | ~25% |
| Arquivada, retirada ou devolvida | ~16% |
| Transformado em Norma Jurídica | 5,8% |
| Aguardando Apreciação pelo Senado | 3,8% |
| Sem situação registrada | 5,5% |

**Decisão.**
1. **Conjunto:** as mesmas proposições do D13.
2. **Marco:** a proposição **atingiu o marco** se a situação atual indica que foi **aprovada pela Câmara**:
   - Aguardando Apreciação pelo Senado Federal ou Aguardando Envio ao Senado;
   - Aguardando Autógrafos, Aguardando Sanção, Aguardando Apreciação do Veto ou Aguardando Promulgação;
   - Transformado em Norma Jurídica.

   A lista final é fechada depois de ver todas as situações dos arquivos de 2015 a 2026.
3. **Produtividade qualificada** = proposições que atingiram o marco / proposições com situação registrada.
4. A métrica só é comparada **dentro da mesma legislatura e faixa** (D3).
5. **Robustez:** a mesma conta usando só "Transformado em Norma Jurídica".
6. Proposições apensadas ("Tramitando em Conjunto") contam como **não atingiu** (critério conservador).

**Justificativa.**
- "Transformada em norma" é rara demais: a maioria dos deputados teria taxa zero.
- "Aprovada em comissão" exigiria baixar o histórico de tramitação de dezenas de milhares de proposições e interpretar textos livres.
- "Aprovada na Câmara" sai da situação já disponível no arquivo, varia mais entre deputados e captura os projetos aprovados de forma conclusiva pelas comissões, que é como a maioria dos PLs sai da Câmara.

**Limitações.**
1. **Apensação:** a apensada fica com a situação "Tramitando em Conjunto" mesmo que o mérito tenha sido incorporado à principal. O critério conservador **subestima** a produtividade de quem tem muitos projetos apensados.
2. **Foto da coleta:** a situação é a do dia da coleta, não a do fim da legislatura. Na 57ª, proposições de 2026 tiveram pouco tempo para avançar.
3. **Reversão:** uma aprovação na Câmara pode ser desfeita depois (rejeição e arquivamento no Senado).

### D15. Gasto relativo da CEAP

**Contexto.** O teto mensal da cota parlamentar varia por UF, por causa do custo das passagens. Na primeira versão, a mediana do gasto mensal ia de R$ 21 mil (DF) a R$ 39,7 mil (AC), e a proporção de deputados no quadrante "gasto alto / produtividade baixa" ia de **0% no DF a 57% em RR**. O quadrante virava um mapa geográfico, e a "composição partidária do quadrante" refletia a força regional dos partidos. Também havia despesas lançadas depois do fim do mandato (328 registros residuais, de cerca de R$ 800 em média).

**Decisão.**

```
gasto_relativo = Σ vlrLiquido / Σ (cota mensal da UF vigente no mês × fração de dias em exercício no mês)
```

1. As somas percorrem os **meses de competência** (`numAno`/`numMes`) em que o deputado esteve em exercício na legislatura (D12).
2. Os tetos por UF, com as datas de vigência dos reajustes, vêm de **fonte oficial da Câmara** (ato da Mesa e atualizações), citada no relatório.
3. Usa-se o **teto vigente em cada mês**, não uma média do período.
4. O valor somado é o `vlrLiquido`, o efetivamente reembolsado, já descontadas glosas e compensações.
5. Só entram despesas com mês de competência **dentro dos períodos de exercício**.
6. Despesas sem deputado identificado (lideranças) ficam fora.
7. Na implementação, é preciso conferir no ato da Mesa se a cota é proporcional em meses de exercício parcial. Se o ato definir outra regra, segue-se o ato.

**Justificativa.**
- A razão sobre o teto neutraliza a diferença entre UFs e tem leitura direta ("usou 85% da cota").
- O teto mês a mês evita distorcer deputados de faixas curtas que exerceram antes ou depois de um reajuste.
- Numerador e denominador ficam em reais da mesma época, sem precisar corrigir inflação.
- O saldo não usado da cota acumula dentro do ano. Usar o total da legislatura, e não meses isolados, mantém a razão perto de 1 no máximo.

**Tabela de tetos (preenchida em 14/11/2026, `data/referencia/tetos_ceap.csv`).** Seis vigências cobrem a janela. Todas as mudanças são uniformes entre as 27 UFs, o que confirma a extração:

| Vigência | Ato | Mudança | DF | RR |
|---|---|---|---|---|
| 01/01/2014 – 31/03/2015 | Ato da Mesa 121/2013 | — | 27.977,66 | 41.612,80 |
| 01/04/2015 – 03/02/2016 | Ato da Mesa 4/2015 | +8,72% (IPCA) | 30.416,80 | 45.240,67 |
| 04/02/2016 – 29/02/2016 | Ato da Mesa 75/2016 | +R$ 73,86 (material de expediente) | 30.490,66 | 45.314,53 |
| 01/03/2016 – 31/01/2023 | Ato da Mesa 76/2016 | +R$ 298,00 (periódicos) | 30.788,66 | 45.612,53 |
| 01/02/2023 – 19/02/2026 | Ato da Mesa 270/2023 | +R$ 5.793,80 | 36.582,46 | 51.406,33 |
| 20/02/2026 – | Ato da Mesa 244/2026 | +13,75% (IPCA fev/2023–dez/2025) | 41.612,55 | 58.474,70 |

O Ato 244/2026 não publica tabela, só manda aplicar o IPCA. Os valores vêm da página oficial da Câmara (guia para jornalistas, "Cota Parlamentar") e coincidem, com diferença de até R$ 0,12, com o cálculo pelo número-índice do IPCA (IBGE/SIDRA, tabela 1737).

**Limitações.**
1. **Adicionais por cargo:** líderes, vice-líderes, presidentes e vice-presidentes de comissão e outros cargos recebem um adicional sobre a cota (R$ 1.353,04, R$ 902,02 ou R$ 5.075,62). O denominador usa só o teto da UF, então esses deputados podem parecer gastar "acima do teto". O adicional representa cerca de 2% a 4% da cota.
2. **Passagens fora da cota desde fev/2023:** o Ato 270/2023 deu direito a até 4 trechos aéreos de ida e volta por mês **além** da cota. Na implementação, é preciso verificar se essas passagens aparecem no arquivo da CEAP. Se aparecerem, precisam ser excluídas do numerador, senão o gasto relativo da 57ª fica inflado.
3. **Mudança de teto no meio do mês:** em fevereiro de 2016 e fevereiro de 2026, o teto mudou no meio do mês. Proposta: ponderar o teto pelos dias de cada vigência no mês, o mesmo critério dos meses parciais de exercício.

---

## 6. Análise

### D16. Quadrantes

**Contexto.** O pré-projeto define os quadrantes pela mediana de gasto e produtividade. Na primeira versão, os quadrantes estavam contaminados pelo tempo de mandato (D3) e pela UF (D15).

**Decisão.**
1. **Variáveis:** gasto relativo (D15) × produtividade bruta mensal (D13).
2. **Corte:** a mediana de cada variável, calculada **dentro de legislatura × faixa** (D3), só com deputados de ≥ 12 meses de exercício.
3. **Classificação:** "alto" = acima da mediana; "baixo" = igual ou abaixo. Com métricas contínuas, empates são raros; se a mediana da produtividade for 0, os deputados sem proposições ficam em "baixo".
4. **Quadrante de interesse:** gasto alto + produtividade baixa. Os casos extremos do D3 ficam sempre dentro dele.
5. **Teste quadrante × voto:** por votação, juntando todos os deputados num único teste, já com a classificação feita em cada faixa. Votantes fora da população do D3 saem do teste, e o relatório informa quantos são.

**Justificativa.** A mediana segue o pré-projeto (corte que vem da distribuição real, não de um valor arbitrário). Calculada dentro do estrato, ela compara pares. Como a classificação por faixa já corrige o tempo de exercício, um teste estratificado (Cochran-Mantel-Haenszel) não é necessário.

### D17. Bancada

**Contexto.** O pré-projeto cita "partidos ou bancadas específicas" no objetivo (d) e "tabulação cruzada entre partido, bancada e voto" na Seção 9, mas não define "bancada". As bancadas temáticas ("ruralista", "evangélica", "da bala") não têm composição oficial nem critério consolidado na literatura. As frentes parlamentares são formais, mas qualquer deputado entra só assinando. A bancada estadual (UF) é formal, mas não faz parte da pergunta de pesquisa.

**Decisão.**
1. O termo "bancada" sai do escopo.
2. A concentração do padrão gasto × produtividade é analisada **por partido e por espectro ideológico** (D9).
3. A UF permanece nos dados como **variável de controle** (especialmente no D15) e como recorte **descritivo** nas visualizações (mapa), não como unidade de análise inferencial.
4. Objetivo (d) reescrito para o relatório:

   > Testar a associação entre o padrão gasto-produtividade e o voto em pautas sociais, verificando se essa associação se concentra em partidos específicos ou está dispersa entre diferentes espectros políticos.

**Justificativa.** Uma classificação de bancadas temáticas dependeria da opinião de quem classifica, o que contraria o objetivo de análise imparcial e replicável.

### D18. Critérios estatísticos

**Contexto.**
- A primeira versão rodava 10 correlações e 3 qui-quadrados sem correção para testes múltiplos, e com 8 votações o número de testes aumenta.
- Na tabela partido × voto, a frequência esperada mínima ficou entre 0,1 e 2,6, faixa em que a aproximação do qui-quadrado não vale.
- Não havia medida de tamanho de efeito.

**Decisão.**
1. **Significância:** α = 0,05.
2. **Correção de Holm dentro de cada família de testes:**

   | Família | Pergunta | Teste | Nº de testes |
   |---|---|---|---|
   | F1 | Central: partido × voto | Qui-quadrado por votação | 8 |
   | F2 | Central: espectro × voto | Qui-quadrado por votação | 8 |
   | F3 | Secundária 2: gasto × produtividade | Spearman por legislatura × faixa, com produtividade bruta e qualificada | 18 |
   | F4 | Secundária 1: produtividade × voto | Mann-Whitney (pró × contra) por votação | 8 |
   | F5 | Secundária 3: quadrante × voto | Qui-quadrado 2×2 por votação | 8 |

3. **Tabelas 2×2** com frequência esperada < 5: teste exato de Fisher.
4. **Tabelas maiores** com frequência esperada < 5: p-valor por **permutação de Monte Carlo** (10.000 permutações, semente fixa).
5. A F1 usa o mesmo filtro do D10 (partidos com ≥ 5 votos válidos, sem deputados sem partido).
6. **Tamanho de efeito, sempre reportado:**

   | Teste | Medida de efeito |
   |---|---|
   | Qui-quadrado r×c (F1, F2) | V de Cramér |
   | 2×2 (F5) | Razão de chances (odds ratio), com IC 95% |
   | Spearman (F3) | ρ, com IC 95% (transformação de Fisher ou bootstrap) |
   | Mann-Whitney (F4) | Correlação rank-bisserial |

   A magnitude é interpretada pela convenção de Cohen, declarada no relatório.
7. **Intervalos de confiança de proporções:** método de Wilson.
8. **Semente aleatória fixa** em `config.py`, para que permutações e bootstrap sejam reproduzíveis.
9. Todos os resultados são lidos como **associação, nunca como causalidade**, coerente com o escopo descritivo e correlacional combinado com o professor.

**Justificativa.** A correção por família controla falsos positivos sem penalizar perguntas independentes entre si. A permutação resolve o caso em que o qui-quadrado não vale. Os tamanhos de efeito evitam ler significância como relevância.

---

## 7. Visualizações

**Contexto.** O pré-projeto promete quatro gráficos: heatmap de coesão, barras por legislatura, barras por partido no quadrante e dispersão interativa. O grupo quer figuras com padrão técnico e científico para o relatório, e também visualizações acessíveis a leitores leigos.

**Decisão: duas camadas.**

**Camada técnica (relatório).**
- **Estilo:** SciencePlots com `['science', 'ieee']`, com fallback automático para `no-latex` se o LaTeX não estiver instalado.
- **Exportação:** PDF vetorial para o relatório e PNG em 600 dpi para os slides.
- **Cores:** colormaps perceptualmente uniformes e seguros para daltônicos (*cividis*/*viridis*), e uma escala divergente neutra para o % pró-pauta, sem o par vermelho/azul, que soa partidário.

| Prioridade | Figuras |
|---|---|
| Essenciais | V1 heatmap % pró-pauta (partido ordenado por espectro × votação) · V2 heatmap de Rice · V4 evolução por legislatura · V7 Spearman com IC por legislatura × faixa · V8 % do partido no quadrante de interesse · V10 % contra a pauta dentro e fora do quadrante |
| Recomendadas | V3 espectro × votação (barras 100%) · V5 Previdência × Precatórios por partido (governo × ideologia) · V9 produtividade por voto |

**Camada de divulgação (interativa, plotly).**
- **Mapa do Brasil:**
  - **malha:** a oficial do IBGE, em duas versões, geográfica e em grade, para corrigir o viés de área;
  - **seletor de métrica:** gasto relativo, % no quadrante de interesse, índice pró-pauta e % pró-pauta por votação;
  - **interação:** hover com o resumo da UF (incluindo o *n*), e clique abre a lista de deputados da UF.
- **Mapa duplo "gasto bruto × gasto relativo":** mostra por que o D15 era necessário.
- **Dispersão gasto relativo × produtividade mensal:** com seletor de legislatura e faixa, medianas, quadrante de interesse e casos extremos destacados.
- **Hemiciclo por votação:** um ponto por deputado, ordenado por espectro e colorido pelo voto.
- **Publicação:** as interativas são publicadas no GitHub Pages do repositório.

---

## 8. Divergências em relação ao pré-projeto

| Pré-projeto | Decisão | Motivo |
|---|---|---|
| Recorte 2000–2026 (51ª–57ª) | 2015–2026 (55ª–57ª) | CEAP só a partir de 2009; poucas votações nominais nas legislaturas antigas (D1) |
| Estatuto do Desarmamento e Maria da Penha | Fora do estudo | Votações simbólicas, sem voto individual (2.1) |
| 4 votações citadas, "a ampliar" | 8 votações definidas | Cobertura das três legislaturas e votações que dividem o Plenário (2.1) |
| Endpoint `/deputados/{id}/proposicoes` | Arquivos em lote de proposições e autores | O endpoint não existe (retorna 405) |
| Endpoint `/deputados/{id}/despesas` | Arquivos anuais da CEAP | Exigiria dezenas de milhares de chamadas |
| TSE para filiação partidária | Histórico de deputados da Câmara | Dá as filiações com data, sem fonte externa (D7) |
| Rice com Sim e Não | Obstrução incorporada ao Não; corte de ≥ 5 votos válidos | D5 e D10 |
| "Alinhamento partidário" sem definição | Fidelidade à orientação do partido e do Governo | D11 |
| Produtividade = proposições, PECs e requerimentos | Só normativas, primeiro autor, por mês | D13 |
| Produtividade qualificada = "avançou além do arquivamento" | Proporção aprovada na Câmara | D14 |
| Gasto da CEAP em valor absoluto | Relativo ao teto da UF | D15 |
| "Partidos ou bancadas" | Partidos e espectro ideológico | D17 |
| Pipeline de "três etapas" (Seção 6) | Quatro etapas (como nas Seções 7 e 10) | Inconsistência interna do pré-projeto |

---

## 9. Pendências

| Item | Responsável | Observação |
|---|---|---|
| D4: critério de pauta de cunho social | Grupo | Redação para o relatório, a partir do rascunho em 2.1 |
| ~~Tabela de tetos da CEAP por UF e reajustes~~ | Feito (14/11/2026) | 6 vigências de 2014 a 2026; ver D15. Falta verificar as passagens fora da cota e decidir o teto no meio do mês |
| ~~Tabela de Bolognesi, Ribeiro e Codato (2023)~~ | Feito (14/11/2026) | 34 partidos conferidos contra o PDF (`docs/orientacao_partidaria.pdf`) |
| Classificação manual do MISSÃO | Grupo | Classificado como **direita** (14/11/2026). Falta citar a fonte documental (estatuto, programa ou manifesto) |
| Lista final de situações do D14 | Implementação | Depois de ver todos os arquivos de 2015 a 2026 |
| Tabela bloco → partidos das orientações (D11) | Quase feito (14/11/2026) | 12 de 13 blocos confirmados. O bloco de 2023 (`Bl UniPpFdrPsdbCid...`) foi confirmado pela [Agência Câmara, 12/04/2023](https://www.camara.leg.br/noticias/952375-novo-bloco-parlamentar-reune-nove-partidos-e-173-deputados-na-camara/): UNIÃO, PP, PSDB, CIDADANIA, PDT, PSB, AVANTE, SOLIDARIEDADE e PATRIOTA. Atenção: não é o bloco da eleição da Mesa de 01/02/2023. Falta confirmar o bloco de 2026 (`Bl UniPpPsd...`) |
| ~~Datas de mudanças de nome e fusões (D8)~~ | Feito (14/11/2026) | 18 eventos com data, processo e fonte do TSE |

---

## Referências

- BOLOGNESI, B.; RIBEIRO, E.; CODATO, A. Uma nova classificação ideológica dos partidos políticos brasileiros. *Dados*, v. 66, n. 2, 2023.
- CÂMARA DOS DEPUTADOS. Dados Abertos da Câmara dos Deputados. Disponível em: <https://dadosabertos.camara.leg.br>.
- CÂMARA DOS DEPUTADOS. Regimento Interno da Câmara dos Deputados, art. 105.
- DESPOSATO, S. W. Correcting for small group inflation of roll-call cohesion scores. *British Journal of Political Science*, v. 35, n. 4, 2005.
- HOLM, S. A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, v. 6, n. 2, 1979.
- RICE, S. A. The behavior of legislative groups: a method of measurement. *Political Science Quarterly*, v. 40, n. 1, 1925.
