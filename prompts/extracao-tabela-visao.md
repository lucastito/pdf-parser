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

**Resposta vazia: a causa é corte por limite de tokens.** Três hipóteses foram
levantadas; duas caíram na medição.

*Não é o esquema restringido* — o texto livre, sem restrição alguma, também vinha
vazio.

*Não é só o raciocínio* — desligá-lo não mudou os números.

*É o limite de saída.* O motivo do encerramento denuncia: `stop` quando o modelo
termina, `length` quando é cortado. Pedidos de descrição terminam em ~689 tokens e
respondem; pedidos de leitura da tabela batem o teto perto de 1900 e voltam vazios,
cortados antes de fechar.

| prompt | `done_reason` | tokens | resposta |
|---|---|---|---|
| descreva a imagem | `stop` | 689 | 794 chars |
| leia a tabela | `length` | 1927 | vazia |
| leia com estes guardrails | `length` | 1887 | vazia |

Elevando o teto para 8192, a lista de alimentos saiu correta — e **ainda cortada**.
É aí que as duas hipóteses se encontram: o raciocínio não é a causa, é o que
consome o orçamento que o limite restringe.

**O que fazer ao adaptar este prompt.** Se a resposta vier vazia, verifique o
`done_reason` antes de mexer nas regras. Se for `length`, o problema não está no
texto: eleve `tokens_maximos` no perfil, ou peça menos itens por chamada. Mexer nos
guardrails não vai resolver, e você vai perder tempo como se perdeu aqui.

**Custo medido:** de 569 s a 1057 s por página, em processador. Confirma a rota por
modelo como processamento em lote, nunca interativo.

## Histórico

- **v1** (2026-07-29) — versão inicial. Extraída de constantes em código
  (`extratores/vlm.py`), acrescentando os guardrails de coluna e de interpolação,
  que não existiam.
