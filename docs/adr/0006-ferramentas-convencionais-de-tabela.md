# ADR-0006 — Ferramentas convencionais de extração de tabela

**Status:** aceito · **Data:** 2026-07-29

## Contexto

Antes de defender uma reconstrução própria, é preciso medir as ferramentas que uma
equipe usaria por padrão. Argumento perde para evidência quando alguém pergunta
"mas vocês tentaram?".

Foram avaliadas as três ferramentas de extração de tabela mais citadas para este
tipo de trabalho, cada uma na configuração adequada ao documento — vencer contra
uma versão mal configurada não provaria nada.

## Medição

Duas páginas do documento-caso, mesmo documento canônico, mesma normalização,
acurácia contra gabarito conferido à mão (40 itens × 5 campos):

| Estratégia | Acurácia | Registros | Tempo | Configuração |
|---|---|---|---|---|
| **Reconstrução posicional** | **100%** | 64 | 0,1 s | layout declarado |
| pdfplumber | **0%** | **133** | 0,9 s | estratégia `text` (sem grade) |
| Camelot | **0%** | **104** | 1,0 s | modo `stream` (sem grade) |
| Detector de borda | 0% | 4 | 0,4 s | padrão |
| OCR + reconstrução | 0% | 2 | 4,9 s | 200 dpi |
| Leitura linear | 0% | 0 | 0,0 s | — |

## O achado que importa

**pdfplumber e Camelot produziram mais registros que a estratégia vencedora — 133 e
104 contra 64 — e acertaram nenhum.**

Inspeção do que produziram:

```
campos:  ['Carbo-', 'Fibra']
valores: {'Carbo-': 'idrato', 'Fibra': 'Alimentar'}
```

Ambas interpretaram o **cabeçalho partido em duas linhas** como se fosse dados:
tomaram `"Carbo-"` por nome de coluna e `"idrato"` — a continuação da mesma palavra —
por valor. Dos 237 registros somados, **zero** contêm um item identificável.

Isso confirma, com número, o princípio declarado na especificação: *um extrator que
roda sem erro e grava lixo é pior do que um que falha alto*. Se a avaliação olhasse
apenas cobertura ou volume, estas ferramentas pareceriam as melhores.

## Verificação de que o resultado não é artefato

Zero de acurácia pode ter duas causas: a ferramenta lê errado, ou lê certo e o
mapeamento de campo não reconhece. A segunda acusaria injustamente.

Descartada por inspeção direta: nenhum dos 237 registros tem o campo identificador,
e nenhum contém o padrão "número + nome" que todo item do documento exibe. Não há
o que mapear — a estrutura extraída não corresponde à do documento.

## Decisão

Manter a reconstrução posicional como estratégia principal, e **manter as demais no
código** como régua permanente. Não são código morto: sem elas, a escolha da
principal volta a ser opinião.

## Consequências

- A defesa da reconstrução própria deixa de ser argumento e passa a ser medição.
- Fica documentado **por que** a rota convencional falha aqui: cabeçalho rotacionado
  e partido, mais ausência de linhas de grade. Não é limitação das bibliotecas em
  geral — é incompatibilidade com esta classe de documento.
- OCR entra com resultado próprio: reconhece os caracteres (verificado: encontra
  valores e rótulos numa página renderizada) mas a reconstrução a partir de
  coordenadas de imagem produziu apenas 2 registros. Merece investigação separada
  antes de qualquer conclusão sobre a rota por imagem.
- Um conjunto de reserva transcrito às cegas, fora dos 40 itens do gabarito, está
  pendente. Até que exista, a acurácia de 100% da estratégia posicional é
  **tautológica** — ela gerou o material que foi conferido.
