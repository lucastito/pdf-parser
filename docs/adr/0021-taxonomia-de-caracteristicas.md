# ADR-0021 — Taxonomia de características estruturais

**Status:** aceito · **Data:** 2026-07-31 · **Implementado:** 2026-08-12

> A peça que faltava fisicamente — a característica "imagem embutida", já
> catalogada abaixo como "pronta" quando na verdade não existia em código —
> foi implementada em `diagnostico.py` em 2026-08-12, junto com o piso de
> área que a torna utilizável em produção (evita disparar em todo logotipo
> de cabeçalho). Ver `PLANO.md`, seção "5. Taxonomia".

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

## Três eixos, e por que não bastava um

A primeira versão desta taxonomia tinha **um** eixo: degradação e patologia
(rotação, ruído, camada de texto ausente). É o eixo que a experiência deste
projeto produziu, e ele sozinho tem um problema de aceitação: os conjuntos de
referência da área classificam por outro critério, e uma taxonomia própria que
ignora o vocabulário estabelecido parece desconhecimento, não contribuição.

Os conjuntos de referência anotam **elementos de layout**: cinco categorias em
PubLayNet (texto, título, lista, tabela, figura), onze em DocLayNet (acrescenta
nota de rodapé, fórmula, cabeçalho e rodapé de página, título de seção, imagem),
treze em DocBank. DocLayNet acrescenta ainda um eixo de **domínio** — relatório
financeiro, manual, artigo científico, lei, patente, edital.

Nenhum dos três anota degradação. É aí que este trabalho acrescenta.

| Eixo | Pergunta | Origem |
|---|---|---|
| **A — layout** | que elementos a página contém? | adotado dos conjuntos de referência |
| **B — degradação** | o que dificulta a leitura? | **contribuição deste trabalho** |
| **C — domínio** | de que tipo é o documento? | adotado, e garante que a coleta não enviese |

Adotar A e C em vez de inventar nomes novos é o que permite dizer *"acrescento um
eixo que aqueles conjuntos não cobrem"* — o acréscimo vira contribuição em vez de
omissão.

**O eixo C existe por uma razão prática, não decorativa:** dez PDFs que são todos
relatórios financeiros exercitam poucas características. O domínio é o controle
contra coleta enviesada.

### Eixo A — elementos de layout

Adotados de DocLayNet, que é o mais completo dos três e o único anotado por
humanos:

texto corrido · título · título de seção · lista · **tabela** · figura ·
imagem · fórmula · nota de rodapé · cabeçalho de página · rodapé de página

Neste projeto a **tabela** é o elemento de interesse; os demais entram como
contexto que pode confundir a extração — uma nota de rodapé numérica logo abaixo
de uma tabela é candidata clássica a virar linha fantasma.

### Eixo C — domínio do documento

Adotados de DocLayNet: relatório financeiro · manual · artigo científico · lei e
regulamento · patente · edital.

Acrescentado, porque é o caso de uso deste projeto e não aparece naquele
conjunto: **relatório técnico com tabela de dados** — laudo, boletim, tabela de
composição, ficha técnica.

## Eixo B — degradação e estrutura

Marcado por custo de detecção, que é o que decide o que entra primeiro.

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

## A combinação é o que se mede, não o eixo isolado

Uma página não é "digitalizada" **ou** "tabela sem grade" — ela é as duas coisas,
num domínio. A unidade de análise do experimento é a **combinação**:

> tabela sem grade (A) + digitalizada com inclinação (B) + relatório técnico (C)

É por isso que a triagem roda **uma página por combinação relevante**, e não uma
por eixo. E é a combinação que a regra final vai citar: *"para tabela sem grade em
página digitalizada, use esta estratégia"*.

**Não se persegue o produto cartesiano dos três eixos** — seriam centenas de
combinações, a maioria sem documento que a exercite. Entram as combinações que a
coleta encontrar, e o que não for coletado fica declarado como não medido.

## Fontes

- [DocLayNet: A Large Human-Annotated Dataset for Document-Layout
  Analysis](https://dl.acm.org/doi/pdf/10.1145/3534678.3539043) — 11 elementos de
  layout, 6 domínios, anotação humana
- [PubLayNet: Largest Dataset Ever for Document Layout
  Analysis](https://www.semanticscholar.org/paper/PubLayNet:-Largest-Dataset-Ever-for-Document-Layout-Zhong-Tang/b5799d10df17de3232540e990da69553800d6376)
  — 5 categorias, anotação automática
- [A Comparative Study of PDF Parsing Tools Across Diverse Document
  Categories](https://arxiv.org/pdf/2410.09871) — comparação de ferramentas por
  categoria de documento

> **Limite das fontes:** os conjuntos citados anotam layout, não degradação, e
> nenhum foi usado para calibrar nada aqui. Servem para ancorar o vocabulário —
> a medição deste projeto é independente deles.
