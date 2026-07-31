# ADR-0021 — Taxonomia de características estruturais

**Status:** proposto · **Data:** 2026-07-31

## Contexto

O entregável final do projeto não é *"esta rota acertou X% neste documento"*. É:

> **dado um documento com estas características, use esta estratégia com esta
> configuração.**

Uma regra assim exige nomear as características. Sem vocabulário, três coisas
quebram ao mesmo tempo: a coleta traz dez documentos que exercitam a mesma
propriedade; a comparação entre máquinas não sabe se mediu casos equivalentes; e
o resultado não generaliza para nenhum documento novo.

**A ordem importa e é contra-intuitiva:** o vocabulário vem **antes** dos
documentos. É ele que torna a coleta eficiente — poucos documentos, muitas
características.

## O erro que este registro corrige

A primeira formulação tratava a taxonomia como classificação **de documento**, em
módulo separado, e escolhia um nome que não colidisse com `triagem.Classe`.

Estava errado por dois motivos.

**Primeiro: são eixos ortogonais, não conceitos rivais.** `triagem.Classe`
responde *"o que tem nesta página?"* — dados, contexto, descartável. A taxonomia
responde *"como esta página está codificada?"* — nativa, digitalizada, com grade,
rotacionada. Uma página é `DADOS` **e** `DIGITALIZADA_INCLINADA` ao mesmo tempo.
As duas classificam a mesma unidade, por perguntas diferentes.

**Segundo, e mais grave: a unidade é a página, não o documento.** Um documento
misto tem páginas nativas e páginas digitalizadas. Um rótulo por arquivo apagaria
a distinção justamente no caso que a literatura considera mais difícil — e
"documento misto" é uma das classes que se quer medir.

## Decisão

**A taxonomia é um segundo eixo de classificação da página**, ao lado de
`triagem.Classe`, e não um módulo novo.

Consequências práticas: menos código, e a fonte já existe. `diagnostico.py`
detecta hoje **cinco** características estruturais, cada uma com severidade e
ação recomendada — a estrutura `Achado(codigo, severidade, detalhe, acao)` já é o
encaixe da taxonomia.

## O que já é detectável, medido no código

| Característica | Código do achado | Severidade |
|---|---|---|
| página rotacionada | `pagina-rotacionada` | bloqueia |
| sem camada de texto | `sem-camada-de-texto` | bloqueia |
| camada de texto parcial | `camada-de-texto-parcial` | alerta |
| texto vertical | `texto-vertical` | alerta |
| mapa de caracteres incompleto | `mapa-de-caracteres-incompleto` | alerta |

Os demais achados do módulo (`cobertura-baixa`, `valor-constante`,
`fora-da-faixa`, `nenhum-registro`, `sem-identificador`,
`identificador-sem-numero`) descrevem **qualidade do resultado**, não estrutura da
entrada. São diagnóstico de extração, não taxonomia — e a distinção precisa ficar
explícita para que a classificação não misture causa com efeito.

## A taxonomia completa

Marcada por custo de detecção, que é o que decide o que entra primeiro.

### Codificação da página

| Característica | Detecção |
|---|---|
| texto nativo | **pronta** |
| digitalizada (sem camada de texto) | **pronta** |
| mista — nativa e digitalizada no mesmo arquivo | **pronta** (por página) |
| camada de texto parcial | **pronta** |
| mapa de caracteres incompleto | **pronta** |
| identificação do programa gerador | exige código (metadados) |

### Geometria

| Característica | Detecção |
|---|---|
| página rotacionada | **pronta** |
| texto vertical | **pronta** |
| inclinação de digitalização | exige código |
| múltiplas colunas de texto | exige código |

### Estrutura de tabela

| Característica | Detecção |
|---|---|
| tabela com grade | exige código |
| **tabela sem bordas** (alinhamento por espaço) | exige código |
| células mescladas / cabeçalho hierárquico | exige código |
| registro em várias linhas | exige código |
| tabela que cruza páginas | exige código |
| número de colunas | **pronta** (via reconstrução posicional) |

### Conteúdo não textual

| Característica | Detecção |
|---|---|
| imagem embutida | **pronta** |
| gráfico / diagrama | exige inspeção manual |
| manuscrito | exige inspeção manual |
| ruído de digitalização | exige código |

## Como a taxonomia é usada

**Na coleta:** é a lista de compras. Cada documento novo entra por qual
característica exercita, não por parecer variado. Documento que só repete
característica já coberta não acrescenta informação e custa tempo de execução.

**Na triagem (ADR-0016):** uma página por característica, a mesma em todas as
máquinas. É o que torna "melhor configuração" uma afirmação por classe, e não uma
média sobre um conjunto arbitrário.

**No diagnóstico:** hoje ele **descreve**; o roteiro exige que **recomende**. A
evolução para prescritivo depende de haver medição por característica — e é por
isso que a taxonomia vem antes.

## Limite declarado

> O roteiro só pode afirmar sobre característica **medida em documento real**.
>
> Hoje há **um** documento: tabela rotacionada, texto nativo, 11 colunas, sem
> imagem. Toda a medição do projeto descreve esse caso. Regra de decisão sobre
> característica que nenhum documento exercita é hipótese, não resultado — e a
> tabela acima é, nessa medida, um plano de coleta antes de ser um resultado.

## Consequências

**A favor:** a coleta ganha critério; a comparação entre máquinas passa a ser por
classe; e a taxonomia serve às duas entregas — é pré-requisito do produto (saber
que estratégia aplicar) e a contribuição científica (o mapa característica →
estratégia).

**Contra:** classificar por página multiplica o volume de rótulos, e as
características que exigem inspeção manual não escalam. A mitigação é priorizar o
que já é detectável e declarar o resto como coberto por amostragem.

**Aberto:** a granularidade de "tabela sem bordas" versus "grade parcial" só se
decide com documentos na mão. Fixá-la agora seria inventar distinção que talvez
nenhum documento exercite.
