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

**Resposta vazia — a causa não é o esquema.** A hipótese inicial era que o esquema
restringido tornava o caminho válido inalcançável. **A medição refutou.** Os três
degraus de saída foram medidos com a mesma imagem e a mesma instrução:

| Degrau | Segundos | `done_reason` | Tokens gerados | Resposta |
|---|---|---|---|---|
| esquema completo | 306,2 | `stop` | 153 | vazia |
| `format: "json"` | 81,9 | `stop` | 152 | vazia |
| texto livre, sem restrição | 1055,4 | `length` | 1844 | vazia |

O texto livre, sem restrição alguma, também devolve vazio — logo a restrição não é a
causa. Em todos os casos o modelo **gera tokens** e nada chega ao campo de resposta;
no último, o orçamento inteiro é consumido.

**Causa 1, confirmada: o canal de raciocínio.** O modelo declara `thinking` entre as
capacidades e gasta a geração inteira ali. Com o raciocínio desligado, o mesmo modelo
responde corretamente em 237 s (521 tokens) — lê a tabela, identifica os nutrientes,
as colunas e a sentinela `Tr`. Por isso a rota desliga o raciocínio por padrão.

**Causa 2, em aberto: algo no prompt de extração.** Mesmo com o raciocínio desligado,
este prompt continua devolvendo vazio, enquanto um prompt de descrição simples
responde. O `eval_count` fica em 152 em toda rodada vazia, com ou sem raciocínio.

Se você está adaptando este prompt e obtém resposta vazia, comece por um prompt
curto que funcione e vá acrescentando as regras uma a uma — é assim que se descobre
qual delas trava a geração.

Os degraus de saída continuam justificados — impedem que resposta vazia vire "página
sem dados" em silêncio —, mas **não** resolvem este problema.

**Custo medido:** de 82 s a 1055 s por página, em processador. Confirma a rota por
modelo como processamento em lote, nunca interativo.

## Histórico

- **v1** (2026-07-29) — versão inicial. Extraída de constantes em código
  (`extratores/vlm.py`), acrescentando os guardrails de coluna e de interpolação,
  que não existiam.
