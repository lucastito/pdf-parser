# Extração de tabela — rota de visão

Para modelos que recebem a **página renderizada como imagem**.

## Instrução

A imagem mostra uma página com uma tabela. Leia a tabela e extraia os itens.

Atenção ao alinhamento das colunas: o cabeçalho pode estar rotacionado e a tabela
pode não ter linhas de grade separando as células.

## Guardrails

- Use exatamente os valores impressos na imagem. Não calcule, não converta, não
  arredonde.
- Se um valor não estiver legível, **omita o campo**. Não adivinhe pelo contexto,
  não interpole entre vizinhos.
- Reproduza marcadores especiais como estão: `Tr`, `NA`, `*`. Eles não são zero.
- Preserve a vírgula decimal como aparece na imagem.
- Confira a qual coluna cada valor pertence antes de atribuí-lo. Em tabela sem
  grade, valores de colunas vizinhas parecem pertencer à mesma.
- Não acrescente campos que não foram pedidos.
- Responda apenas com JSON válido.

## Justificativa de cada regra

**"Confira a coluna"** — é o risco específico desta rota. Sem linhas de grade, o
alinhamento é dado só por proximidade visual, e um deslocamento de uma coluna produz
valores todos plausíveis e todos errados. É pior que não extrair, porque passa por
validação de tipo e faixa.

**"Não adivinhe pelo contexto"** — um modelo de visão que não consegue ler um dígito
tende a inferir do padrão dos vizinhos. O resultado é um valor coerente com a
vizinhança e inexistente no documento.

**"Não interpole"** — variação da anterior, e mais tentadora em tabela numérica onde
os valores parecem seguir progressão.

As demais regras têm a mesma justificativa da rota de texto — ver
[extracao-tabela-texto.md](extracao-tabela-texto.md).

## Notas de operação

**A resolução é variável do experimento.** Duas execuções com resoluções diferentes
não são comparáveis entre si, e o valor é registrado com cada resultado. Ver
ADR-0007 para a curva medida na rota de reconhecimento óptico — que não é monotônica,
e o mesmo pode valer aqui.

**Resposta vazia: a causa é corte pelo limite de CONTEXTO.** Quatro hipóteses
foram levantadas; três caíram na medição.

*Não é o esquema restringido* — o texto livre, sem restrição alguma, também vinha
vazio.

*Não é só o raciocínio* — desligá-lo não mudou os números.

*Não é o teto de saída* — elevá-lo a 16384 **não** removeu o corte. As respostas
continuaram parando perto de 1900 tokens, o que contradiz o teto declarado.

*É o **contexto**, que limita entrada e saída somadas.* Uma página renderizada
consome ~2200 tokens só de entrada. Com o padrão de 4096, sobram ~1900 para a
resposta — e é exatamente aí que ela é cortada.

A prova é aritmética. Somando entrada + saída:

| caso | entrada + saída | soma | `done_reason` |
|---|---|---|---|
| descreva a imagem | cabe | 3765 | `stop` |
| leia a tabela | 2175 + 1921 | **4096** | `length` |
| leia com guardrails | 2227 + 1869 | **4096** | `length` |
| teto elevado a 16384 | 2189 + 1907 | **4096** | `length` |

Prompts de tamanhos diferentes parando na **mesma soma exata** é assinatura de
teto atingido. Ver [ADR-0018](../docs/adr/0018-dimensionamento-de-contexto.md).

**O que fazer ao adaptar este prompt.** Se a resposta vier vazia, **some
`prompt_eval_count` e `eval_count`** antes de mexer nas regras. Se a soma bater
no contexto configurado, o problema não é o texto — é o contexto, e mexer nos
guardrails só perde tempo.

Declare o contexto (`num_ctx`) com folga sobre o que a **entrada** consome. Só
elevar o teto de saída não resolve: foi o que se tentou aqui, e não resolveu.

**Custo medido:** de 569 s a 1057 s por página, em processador — e esses tempos
são de chamadas que foram **cortadas**. Com contexto suficiente a chamada não
terminou em uma hora, o que reforça a rota por modelo como processamento em
lote, nunca interativo, **nesta classe de máquina**.

Máquinas com placa de vídeo funcional não foram medidas. É o que o experimento
em várias máquinas existe para responder
([ADR-0013](../docs/adr/0013-desenho-do-experimento-multimaquina.md)).

## Histórico

- **v2** (2026-07-31) — corrigido o diagnóstico de resposta vazia. A versão
  anterior culpava o teto de saída e mandava elevá-lo; a medição mostrou que o
  limite atuante é o **contexto**, e que elevar o teto sozinho não resolve.
- **v1** (2026-07-29) — versão inicial. Extraída de constantes em código
  (`extratores/vlm.py`), acrescentando os guardrails de coluna e de interpolação,
  que não existiam.
