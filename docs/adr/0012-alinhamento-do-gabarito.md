# ADR-0012 — Alinhamento do gabarito: descrição antes de número

**Status:** aceito · **Data:** 2026-07-30

## Contexto

Medir acurácia exige parear cada item extraído com o item correspondente do
gabarito. A chave usada era `"<número> <descrição>"`, com recuo para o número
sozinho — decisão que tinha justificativa: algumas ferramentas fragmentam o texto
no meio da palavra (`"Arroz, integra l, cozido"`), e casar por nome descartaria
itens cujos **valores** estão corretos.

Essa decisão produziu um resultado impossível: o conjunto de reserva media **0% em
todas as estratégias**, inclusive na que acerta 100% no gabarito principal.

## O que a medição mostrou

O conjunto de reserva foi transcrito às cegas, com numeração **local** (1 a 10) —
a ordem em que os itens foram escolhidos, não a do documento. O mesmo item aparece
como `1 Pão, milho, forma` no gabarito e `51 Pão, milho, forma` na extração, com o
mesmo valor de energia.

Pior que não casar: o documento **tem** um item de número 1 — outro alimento, com
outro valor. O alinhamento por número pareava os dois e reportava **erro de
extração**, quando o erro era de pareamento. Um zero que não media nada, e que
sugeria que as ferramentas não funcionavam.

Ao ampliar o conjunto de reserva para as 9 páginas que ele cobre, dois outros
defeitos de medição apareceram na mesma classe:

| Defeito | Sintoma | Causa |
|---|---|---|
| Numeração local | 0% em todas as rotas | número casa com item errado |
| Sentinela por grafia | erro concentrado em fibra e lipídeos | gabarito diz `Tr`, extrator diz `traco` |
| Descrição fragmentada | uma rota a 40% | `"Abobora, p esco ço"` não bate exato, cai no número |

Os três **pareciam** erro de extração. Nenhum era.

## Decisão

**A ordem de alinhamento é: identificador completo → descrição → descrição sem
espaços → número.**

O que muda em relação ao anterior é a posição do número: ele deixa de ser o
primeiro recuo e passa a ser o último. A razão é assimétrica:

- Quando a descrição bate, ela **identifica** o item — é o nome do que foi medido.
- Quando o número bate, ele apenas **posiciona** — e a posição pode ser local ao
  gabarito, como foi aqui.

Um pareamento errado por número não falha ruidosamente: ele reporta valores
divergentes, que se leem como erro de extração. É a pior forma de falhar.

**A chave sem espaços** cobre a fragmentação que motivava o número: `"Abobora, p
esco ço, crua"` e `"Abóbora, pescoço, crua"` colapsam na mesma chave, sem afrouxar
— dois alimentos diferentes continuam diferentes sem espaços.

**Sentinelas se comparam pelo que afirmam, não pela grafia.** `Tr` (documento) e
`traco` (modelo) são o mesmo valor. Mas uma sentinela nunca equivale a outra —
`Tr` afirma "quantidade desprezível", `NA` afirma "não sabemos" (ADR-0004) — nem
equivale a zero.

## Consequências

- A medição contra o conjunto de reserva passa a ser **legítima**. Antes de
  corrigir, a única acurácia independente do projeto era inutilizável.
- O resultado corrigido, em 9 páginas e seções variadas: três rotas a **100%**,
  reconhecimento óptico a 78%. As duas rotas de controle continuam em 0%, como
  esperado.
- **A generalização passa a estar demonstrada.** Antes, o conjunto de reserva
  cobria 2 itens numa página, e a suspeita de ajuste ao gabarito não podia ser
  descartada.
- Custo: quatro chaves de alinhamento em vez de duas. Aceito — cada uma cobre uma
  falha específica e medida das outras.
- Risco assumido: descrição idêntica em itens diferentes pararia no primeiro. Não
  ocorre neste documento, e o identificador completo tem precedência.

## Regra que fica

**Zero absoluto em todas as estratégias é suspeita de defeito na régua, não de
extração ruim.** Uma estratégia que acerta 100% num gabarito não erra 100% em
outro do mesmo documento. Quando os números são impossíveis, o instrumento está
errado.
