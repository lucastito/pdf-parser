# Golden set

Gabarito de avaliação: os valores que o extrator **deveria** produzir.

## Por que conferido à mão

Um gabarito gerado pelo próprio extrator mediria o extrator contra ele mesmo — o
resultado seria 100% por construção e não diria nada. A conferência humana contra
o documento original é o que dá sentido a todas as métricas.

## Arquivos

| Arquivo | Estado |
|---|---|
| `taco-para-conferir.csv` | **proposta**, ainda não conferida |
| `taco.csv` | gabarito conferido (criar após a revisão) |

## Como conferir

`taco-para-conferir.csv` traz 40 alimentos × 5 macronutrientes (200 valores), com
a coluna `pagina_pdf` indicando onde cada linha foi lida. Ao lado de cada valor há
uma coluna `*_ok` para marcação:

- `ok` — confere com o documento
- o **valor correto** — se estiver errado
- `?` — se estiver ambíguo ou ilegível

Ao terminar, renomeie para `taco.csv`. É contra esse arquivo que a matriz de
avaliação passa a comparar todos os extratores.

**Não conferir "por amostragem otimista".** Os erros que interessam são os
sistemáticos — uma coluna inteira deslocada produz valores plausíveis e é
justamente o que a conferência precisa pegar.

## Fonte e licença

Dados extraídos da **Tabela Brasileira de Composição de Alimentos (TACO)**,
NEPA/UNICAMP, 4ª edição ampliada e revisada, Campinas, 2011.

A obra permite reprodução total ou parcial desde que citada a fonte — daí a
inclusão destes dados aqui. Fontes cuja licença proíba redistribuição não entram
neste diretório, mesmo quando disponíveis localmente.
