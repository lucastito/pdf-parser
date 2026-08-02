# ADR-0024 — Reconhecimento antes da extração, em três níveis de custo

**Status:** proposto · **Data:** 2026-08-02

## Contexto

O parser hoje precisa que alguém **configure** a estrutura de cada documento:
quais colunas, em que ordem, com que rotação. Funciona no documento-caso — a rota
de texto chega a 100% assim — e não escala.

A objeção que motivou este registro é definitiva:

> *Não importa quantos PDF eu ache. Nunca vai ser suficiente quando a solução
> estiver rodando com documentos dos clientes.*

Está correta, e não se resolve com coleta. Qualquer conjunto de exemplos é uma
amostra do passado; o cliente manda o que não está nela. Ampliar a calibração
para "mais um layout" repete o problema num nível acima.

E há evidência de que o alcance atual é estreito: a descoberta de colunas por
geometria (ADR-0023) acerta **11 de 11** no documento-caso e **falha limpa** numa
tabela horizontal comum — testado com PDF sintético, devolveu lista vazia.

## Decisão

**O parser reconhece a página antes de extrair, e o reconhecimento tem três
níveis, acionados em ordem de custo.** Cada nível só roda se o anterior não
bastou.

### Nível 1 — o que o PDF já entrega (custo zero)

Medido no documento-caso, e discrimina mais do que se supunha:

| Sinal | TACO p29 | capa | tabela horizontal |
|---|---|---|---|
| rotação | **90** | 0 | 0 |
| densidade numérica | 65% | 0% | 72% |
| blocos de texto | 8 | 2 | 13 |
| linhas de grade | 3 verticais | 0 | 0 |
| camada de texto | sim | sim | sim |

Vem junto o **gerador do arquivo** (`PDFCreator 1.2.0`, `Ghostscript 9.0` no
documento-caso). É sinal forte e subutilizado: saída de scanner, de processador de
texto e de composição tipográfica têm assinaturas distintas.

### Nível 2 — inspeção determinística (barata)

Densidade numérica por faixa, contagem de linhas horizontais e verticais,
agrupamento de rótulos por geometria. Parte já existe em `diagnostico.py`,
`triagem.py` e `calibracao.py`.

É onde a descoberta de nomes de coluna (ADR-0023) opera. **Alcance conhecido:**
tabela com unidades empilhadas; falha em tabela horizontal.

### Nível 3 — o modelo descreve a estrutura (cara, e só quando preciso)

**Descrever não é extrair**, e a diferença de custo é o que torna o nível viável.
Medido no documento-caso com um modelo de 1,9 GB:

| Tarefa | Tempo | Tokens de saída |
|---|---|---|
| **descrever a estrutura** | **2,7 min** | **142** |
| extrair a página | 30 min | 2607 |

**~9% do custo.** E o resultado foi correto: identificou tabela, listou 12
colunas com os nomes certos, informou que há grade.

## O achado que justifica o desenho: as fontes se complementam

Comparando o que cada nível descobriu na mesma página:

| | Geometria (nível 2) | Modelo (nível 3) |
|---|---|---|
| Colunas encontradas | 11 | 12 |
| `Número do Alimento`, `Descrição` | **não vê** | **acha** |
| `Energia (kJ)` | **acha** | funde com `(kcal)` |

**As diferenças não são erros — são informação distinta.** A geometria não vê as
colunas de identificação porque elas ficam fora da faixa de rótulos; o modelo
funde as duas energias porque a distinção está nas unidades empilhadas, que é
geometria pura.

Juntas descrevem a página inteira. Isoladas, cada uma tem um ponto cego — e o
ponto cego de uma é a força da outra.

Isso ecoa a decisão de consolidação por campo (ADR-0017): **fontes independentes
que concordam sustentam confiança que nenhuma sozinha sustenta.** Aqui vale para
estrutura, não para valor.

## Consequências

**A favor:** documento novo deixa de exigir configuração manual; o prompt passa a
ser montado do que foi reconhecido, o que o torna comparável entre documentos
(ADR-0023); e o custo fica proporcional à dificuldade — documento bem-comportado
não paga o nível 3.

**Contra:** três caminhos significam três coisas que podem falhar, e a lógica de
quando escalar de nível é decisão nova. Errar para mais custa tempo; errar para
menos produz prompt mal informado.

**O que fica declarado como não medido:**

- o comportamento em **documento digitalizado sem camada de texto**, onde os
  níveis 1 e 2 entregam quase nada e tudo depende do nível 3;
- se a descrição do modelo permanece confiável em layout que ele não reconhece —
  aqui ele acertou num documento de tabela clara, que é o caso fácil;
- o critério de escalada entre níveis, que hoje é hipótese e precisa de
  documentos variados para virar regra.

> **Limite honesto:** este ADR registra uma arquitetura sustentada por **uma**
> medição num **um** documento. O que está medido é o custo relativo (9%) e a
> complementaridade das fontes. O resto é desenho, e a coleta de documentos é o
> que vai confirmá-lo ou refutá-lo.
