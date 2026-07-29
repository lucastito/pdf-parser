# Extração de tabela — rota de texto

Para modelos de linguagem que recebem o **texto** já extraído da página.

## Instrução

Extraia os itens da tabela. Para cada item, informe os campos pedidos.

## Guardrails

- Use exatamente os valores impressos no documento. Não calcule, não converta, não
  arredonde.
- Se um valor não aparecer no texto, **omita o campo**. Não estime, não repita o
  valor de outro item, não use zero como substituto.
- Reproduza marcadores especiais como estão: `Tr`, `NA`, `*`. Eles não são zero.
- Preserve a vírgula decimal como está no documento; a conversão acontece depois.
- Não acrescente campos que não foram pedidos.
- Responda apenas com JSON válido, sem texto antes ou depois.

## Justificativa de cada regra

**"Não calcule nem converta"** — o modelo tem tendência a "corrigir" valores que
parecem inconsistentes, por exemplo recalculando energia a partir dos macronutrientes.
Isso produz um número plausível que não está no documento, e a extração deixa de ser
extração.

**"Omita o campo em vez de estimar"** — um campo ausente é registrado como ausente e
aparece nas métricas de cobertura. Um campo estimado entra como se fosse lido, e
contamina a acurácia sem deixar rastro. O modelo preenchendo lacunas é a falha mais
cara desta rota, porque é invisível.

**"Marcadores não são zero"** — no documento-caso, `Tr` significa "presente em
quantidade desprezível" e `NA` significa "não analisado". São afirmações diferentes
entre si e diferentes de zero. Somar `Tr` como zero falseia qualquer total, sem
levantar erro.

**"Preserve a vírgula"** — a normalização é a mesma para todas as estratégias
(ADR-0005). Se o modelo converter por conta própria, a comparação passa a medir a
conversão dele em vez da extração.

**"Não acrescente campos"** — o esquema de saída já descarta campo extra, mas pedir
explicitamente reduz tokens gastos em conteúdo que será jogado fora.

**"Apenas JSON"** — mesmo com a decodificação restringida por esquema, a instrução no
texto importa: sem ela a amostragem degrada e modelos pequenos passam a devolver
prosa.

## Histórico

- **v1** (2026-07-29) — versão inicial. Extraída de constantes que estavam em código
  (`ollama.py`), sem justificativa registrada.
