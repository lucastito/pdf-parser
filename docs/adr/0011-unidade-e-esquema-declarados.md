# ADR-0011 — Unidade e esquema de saída como declaração do perfil

**Status:** aceito · **Data:** 2026-07-30

## Contexto

RF-7 exige saída validada contra schema, com **tipo e unidade quando aplicável**.
Duas partes disso estavam por fazer, e o sintoma de cada uma era visível no código:

**Unidade.** A unidade existia apenas como texto inerte dentro do rótulo —
`"Energia (kcal)"` — usado para desambiguar o mapeamento e nunca para converter. O
modelo de dados já definia `Origem.DERIVADO`, com "conversão de unidade" no próprio
docstring, validado desde o início (ADR-0004) e **produzido por nada**. Um consumidor
que espere kJ e receba kcal erra por fator ~4, sem aviso algum.

**Esquema de saída.** A validação por campo já existia (Pydantic, na construção do
`Registro`), mas não cobre invariantes do **conjunto**: coluna ausente, tipo
divergente entre registros, lote heterogêneo. O destino CSV monta o cabeçalho a partir
do primeiro registro — um lote em que o segundo registro traga um campo a mais perde
a coluna **sem erro algum**. O pipeline completa, o arquivo parece bom, e o dado não
está lá. É a mesma classe de falha muda que orienta o desenho do projeto inteiro.

Havia ainda um fato administrativo: as duas bibliotecas necessárias estavam
**instaladas e sem uso**, e sequer declaradas em `pyproject.toml`. Dependência não
declarada e não usada é dívida disfarçada de trabalho pronto.

## A tensão a resolver

Converter unidade parece exigir que o núcleo conheça unidades. Se conhecer, deixa de
ser agnóstico — e o núcleo agnóstico é princípio estruturante, não preferência: o
mesmo parser serve documentos de domínios sem relação entre si.

A saída para essa tensão define a decisão.

## Opções consideradas

| Opção | Vantagem | Desvantagem |
|---|---|---|
| Não converter; deixar ao consumidor | Nada a construir | Empurra o problema para quem tem menos contexto; RF-7 fica descoberto |
| Converter por detecção automática da unidade no rótulo | Automático | O núcleo passa a conhecer unidades de domínio; muda em silêncio a saída de documentos já medidos |
| **Converter sempre, com a tabela vinda do perfil** | Núcleo agnóstico e RF-7 atendido | Exige declaração explícita por documento |
| Tabela de fatores escrita à mão | Sem dependência nova | Aceita `g → kcal` e devolve número plausível |
| **Biblioteca que conhece dimensão** | Recusa conversão impossível | Dependência a mais, e custo de carga |

## Decisão

**A etapa de conversão é permanente no pipeline; a tabela de conversão vem do
perfil.** Essa separação é o que preserva o agnosticismo: o núcleo sabe *converter*, e
nunca sabe que "kcal" ou "g" existem. Sem regra declarada, a etapa executa e devolve o
registro intacto — não por estar desligada, mas por não haver o que converter. É o
mesmo contrato de `Mapeamento`, sempre aplicado com regras vindas de fora.

A conversão roda **depois do mapeamento**, nunca antes: as regras são declaradas sobre
os nomes canônicos, que só existem a partir dali.

**A aritmética é delegada a uma biblioteca que conhece dimensão**, em vez de escrita à
mão. A razão é específica: uma tabela de fatores caseira aceita `g → kcal` e devolve um
número plausível. Conhecendo dimensão, a conversão impossível é **recusada** — e
recusada na *carga do perfil*, não no meio de um lote de 164 páginas.

**A validação de esquema tabular é uma segunda porta, aplicada ao conjunto antes da
gravação.** Antes, não depois: dado inválido que chegou ao destino já contaminou o
consumidor, e nenhum erro posterior desfaz isso.

Regras que a conversão obedece, todas verificadas em teste:

- Campo convertido sai como `DERIVADO`, **preservando a evidência do valor original** —
  a auditoria continua chegando ao texto bruto no documento.
- A confiança é **propagada, nunca elevada**: converter não acrescenta conhecimento.
- **Sentinela não se converte.** `Tr` em grama continua `Tr`; não há número a
  multiplicar (ADR-0004).
- Sem unidade-alvo declarada, o campo passa intacto, com `EXTRAIDO` preservada.

## Consequências

- RF-7 passa a ser atendido de fato, e `Origem.DERIVADO` deixa de ser um valor órfão
  do modelo.
- **Nenhuma medição anterior muda de valor.** Sem declaração no perfil, as duas etapas
  são inertes — condição necessária para que os resultados já registrados continuem
  comparáveis (ADR-0005).
- Um perfil inconsistente falha na **carga**, com o nome do arquivo na mensagem, em
  vez de no meio de uma execução longa.
- O lote heterogêneo deixa de perder coluna em silêncio: passa a falhar alto, nomeando
  a coluna, o motivo e o índice do registro.
- Custo: duas dependências a mais, e a carga do registro de unidades custa centenas de
  milissegundos. Mitigado carregando-o uma vez por processo e resolvendo cada fator na
  construção, fora do laço por registro — do contrário o custo apareceria como custo do
  extrator na matriz de comparação, que é artefato de instrumentação, não medição.
- O esquema descreve os **campos** do registro. Colunas de proveniência que o destino
  acrescenta na gravação ficam fora de propósito: não são dado extraído, e exigi-las no
  perfil obrigaria cada usuário a declarar detalhe de destino.
