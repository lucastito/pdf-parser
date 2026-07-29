# ADR-0002 — Reconstrução posicional de tabela

**Status:** aceito · **Data:** 2026-07-29 · **Revisado:** 2026-07-29

> **Atenção.** Os números de comparação abaixo mediam **cobertura**, não acurácia, e
> foram obtidos antes da camada de adaptação (desrotação + alinhamento posicional).
> Com essa camada, pdfplumber e Camelot alcançam 100% e 99% de acurácia — ver
> [ADR-0006](0006-ferramentas-convencionais-de-tabela.md). A decisão desta ADR
> continua válida, mas **a justificativa mudou**: não é acurácia superior, é
> velocidade (0,1 s contra 0,4–0,8 s), independência do arquivo original e evidência
> por coordenada de campo.

## Contexto

O documento-caso apresenta uma tabela com duas propriedades que quebram as
abordagens convencionais:

1. **Sem linhas de grade.** As colunas são definidas só por alinhamento visual.
2. **Rotacionada 90°.** Os cabeçalhos são verticais e cada faixa horizontal contém
   *um atributo de todos os itens*, não *todos os atributos de um item*. O que
   parece linha é, na verdade, coluna.

Escrever reconstrução própria é assumir complexidade. Isso precisa ser justificado
contra a alternativa de usar um detector pronto — que é o que uma equipe faria por
padrão, e com razão.

## Medição

Três extratores sobre as mesmas 4 páginas, a partir do mesmo documento canônico:

| Extrator | Registros | Campos | Cobertura | Tempo |
|---|---|---|---|---|
| **Posicional** | **127** | **1524** | **91%** | 0,03 s |
| Detector pronto (`find_tables`) | 4 | 4 | 0% | 0,53 s |
| Leitura linear (piso) | 0 | 0 | 0% | 0,00 s |

O detector pronto retorna **zero tabelas** nas páginas de dados: sem linhas de grade,
não há o que detectar. Os 4 campos vieram de fragmentos irrelevantes. Além de
inaproveitável, foi **17× mais lento**.

A leitura linear não produziu nada: o padrão `rótulo → valor` não sobrevive à ordem
em que o PDF emite o texto, justamente por causa da rotação.

## Opções

| Opção | Vantagem | Desvantagem |
|---|---|---|
| Detector pronto | Sem código próprio; manutenção terceirizada | **Não funciona neste documento** (medido) |
| Leitura linear | Trivial | **Não funciona em tabela rotacionada** (medido) |
| **Reconstrução posicional** | Funciona; independe de grade; produz evidência com coordenada | Exige descrever o layout; sensível a mudança de diagramação |
| Modelo de visão | Enxerga o layout como humano | Fora do envelope do ambiente-alvo (ADR-0003); a comparar quando houver infraestrutura |

## Decisão

**Reconstrução posicional**, com o layout declarado como dado (`LayoutTabela`), não
embutido no algoritmo.

A estratégia: agrupar rótulos por faixa de Y, agrupar valores por coluna de X, cruzar
os dois eixos. Cada valor extraído carrega página, *bounding box*, texto bruto e
vizinhança.

Uma sutileza que a implementação revelou: a **unidade**, não o nome do atributo, é o
que ancora verticalmente a faixa. Um atributo publicado em duas unidades tem o nome
escrito uma vez só, a meio caminho entre as duas linhas de valores — ancorar pelo
nome erra ambas. Ancorar pela unidade separa corretamente as duas faixas.

## Consequências

- Adaptar a outro documento com a mesma patologia é trocar números de layout, não
  reescrever código.
- **Sensível a mudança de diagramação:** uma nova edição do documento com layout
  diferente exige recalibrar o layout. O golden set é o que detecta isso.
- O extrator implementa a mesma porta que os demais, então **entra na matriz de
  comparação sem tratamento especial** — inclusive contra um extrator baseado em
  modelo, quando houver.
- Os dois extratores de controle permanecem no código. Não são código morto: são a
  régua que sustenta a decisão, e precisam rerodar a cada mudança relevante.

## Ressalva

Os números acima medem **cobertura e volume, não acurácia**. Um extrator que
preenchesse todos os campos com valores errados exibiria a mesma cobertura. A
acurácia só pode ser afirmada contra o gabarito conferido manualmente — pendente.
Até lá, a conclusão defensável é limitada: *o detector pronto não serve para este
documento*, o que já é suficiente para justificar esta decisão.
