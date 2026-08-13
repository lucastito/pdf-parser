# ADR-0021 — Taxonomia de características estruturais

**Status:** aceito · **Data:** 2026-07-31 · **Implementado:** 2026-08-12

> A peça que faltava fisicamente — a característica "imagem embutida", já
> catalogada abaixo como "pronta" quando na verdade não existia em código —
> foi implementada em `diagnostico.py` em 2026-08-12, junto com o piso de
> área que a torna utilizável em produção (evita disparar em todo logotipo
> de cabeçalho). Ver `PLANO.md`, seção "5. Taxonomia".
>
> **Retificação de escopo, 2026-08-12 (−1.4, PLANO.md).** Esta ADR já
> decidia que a taxonomia é "um segundo eixo... ao lado de `triagem.Classe`,
> e não um módulo novo" (ver "Decisão" abaixo) — `Classe` não precisava (nem
> devia) virar conjunto, e a característica como conjunto de códigos de
> achado já roda em produção desde `planejador.py:132`. O que faltava era só
> a forma consultável do documento inteiro (`diagnostico.caracterizar_documento`
> + `diagnostico.paginas_por_caracteristica` + `diagnostico.caracteristicas_do_documento`
> + `diagnostico.contagem_por_caracteristica`, novos) e o `Perfil` comportar N
> páginas de referência por característica
> (`paginas_de_referencia_por_caracteristica` — nome escolhido para não
> colidir com `triagem.py`; substitui o escalar `pagina_de_triagem_declarada`).
> Ver o detalhe completo — inclusive o que continua fora de escopo — em
> `PLANO.md`, seção "−1.4, o que foi fechado e o que continua aberto".
>
> **Segunda retificação, mesma sessão: descoberta é aberta, não verificação
> de catálogo fechado.** Ver a seção "Descoberta de característica: aberta
> no desenvolvimento, fechada em produção" abaixo — formaliza
> `diagnostico.MetodoDeDeteccao` (3 métodos, do mais barato ao mais caro) e
> corrige uma armadilha de enquadramento: a pergunta certa não é "esta
> página tem característica N?" pra cada N do catálogo — é "que
> característica(s) esta página tem?", com a resposta vindo da sonda, não
> de uma lista fixa sendo conferida item a item.
>
> **Terceira retificação, 2026-08-13 (resto do −1.4, PLANO.md): descoberta
> de característica exercitada de verdade, contra os dois documentos reais
> de um cenário corporativo separado (fora deste repositório).** Em vez de
> escrever sonda no escuro para as ~13
> características que faltavam, a investigação de desenvolvimento que a
> seção seguinte já formalizava foi executada de fato — inspeção página a
> página dos dois documentos reais (blocos de texto, retângulos vetoriais,
> renderização visual). Três características tinham evidência real e
> viraram sonda, com validação (e uma correção real de falso positivo — ver
> "O que já é detectável" abaixo): `pagina-em-paisagem`,
> `multiplas-colunas-de-texto`, `tabela-com-fundo-colorido`. Duas ficaram
> **observadas em documento real, mas não implementadas** — célula
> mesclada/cabeçalho hierárquico (exige reconstrução de tabela que o
> projeto não tem ainda) e gráfico/diagrama (exige inspeção visual ou LLM
> para distinguir de foto ou tabela) — upgrade de status honesto em relação
> a "hipotético, nunca visto", sem inventar código sem base. As demais
> (manuscrito, idioma diferente, digitalização torta/ruim, PDF antigo)
> seguem hipotéticas — nenhum dos dois documentos tem página digitalizada.
> O algoritmo de "quantas páginas por característica" também fechou nesta
> sessão: `diagnostico.escolher_paginas_de_referencia` — 1 página
> representante por **combinação exata** de características, não por
> característica isolada, operacionalizando o princípio que a seção "A
> combinação é o que se mede" já declarava. Ver `PLANO.md`, "−1.4, o que
> foi fechado e o que continua aberto" pro detalhe completo.

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

> **Limite declarado sobre `triagem.Classe`, não sobre a taxonomia em si
> (2026-08-12).** Ortogonal não quer dizer preciso. `Classe` decide por dois
> limiares grosseiros — contagem de palavra e densidade numérica — e os dois
> têm caso real de erro: uma página com **um parágrafo curto** (a conclusão
> que "vazou" da página anterior por quebra de formatação, por exemplo) pode
> cair abaixo de `PALAVRAS_MINIMAS` e virar `DESCARTAVEL`. Isso é mais grave
> que um erro comum de classe: `DESCARTAVEL` vira `rota="nenhuma"` no
> roteador — a página é pulada, **zero tentativa de extração**, sem a rede
> de segurança que protege `DADOS`/`CONTEXTO` errados (a tentativa
> determinística seguinte falha limpo e escala pro modelo). Conteúdo real
> pode desaparecer em silêncio. Corrigir isso exige medição — mais sinal que
> só contagem de palavra, ou escalar o caso ambíguo para uma classificação
> mais cara (método 3, ver abaixo) em vez de descartar direto — não um
> número ajustado no escuro. Ver `PLANO.md`, item aberto correspondente.

## Decisão

**A taxonomia é um segundo eixo de classificação da página**, ao lado de
`triagem.Classe`, e não um módulo novo.

Consequências práticas: menos código, e a fonte já existe. `diagnostico.py`
detecta hoje **cinco** características estruturais, cada uma com severidade e
ação recomendada — a estrutura `Achado(codigo, severidade, detalhe, acao)` já é o
encaixe da taxonomia.

## Descoberta de característica: aberta no desenvolvimento, fechada em produção

**A pergunta certa não é "esta página tem tabela? tem rotação?"** — verificar
item a item um catálogo fixo. É **"que característica(s) esta página tem?"**,
com a resposta vindo de quem descobre, não da pergunta. `caracterizar_pagina`
(`diagnostico.py`) reflete isso desde 2026-08-12: não é uma função com um
`if` por característica catalogada, é um **registro de sondas**
(`_SONDAS`/`@_sonda`) — cada sonda roda, e reporta um achado ou nada.
Adicionar característica nova ao código é registrar uma sonda nova; a função
central nunca muda.

**Três métodos de descoberta, do mais barato ao mais caro** — cada achado
declara qual usou (`Achado.metodo`, `diagnostico.MetodoDeDeteccao`):

| Método | O que é | Exemplo hoje |
|---|---|---|
| `METADADO_NATIVO` | Propriedade que o PDF já expõe, lida direto da estrutura — sem calcular nada | `pagina-rotacionada` (atributo de rotação), `mapa-de-caracteres-incompleto` (contagem de marcadores no arquivo bruto) |
| `FERRAMENTA_DETERMINISTICA` | Heurística ou cálculo sobre o conteúdo — determinístico, sem rede nem modelo | `sem-camada-de-texto`, `texto-vertical`, `imagem-embutida` |
| `LLM_SIMPLES` | Classificação por modelo pequeno/rápido, pro que geometria não alcança | **nenhum achado usa ainda** — é o que falta pro eixo C (domínio) |

**O catálogo de características conhecidas cresce por decisão de quem
desenvolve, não em tempo de execução.** Rodar um LLM livre (ou uma
ferramenta determinística nova) sobre um documento real pode revelar uma
característica que não está nas 19 de hoje — isso é trabalho de
**desenvolvimento**: a pessoa nota, decide se entra no catálogo, e só então
alguém escreve a sonda (com o método adequado) que a detecta daí em diante.
**A aplicação instalada no servidor do cliente não faz esse trabalho** — ela
aplica os métodos já desenvolvidos para as características já catalogadas,
sejam 19 ou quantas estiverem no código naquele momento. Um ponto de
extensão pra isso acontecer também em produção é desejável no futuro, mas
não é frequente o bastante hoje para justificar construir agora.

## O que já é detectável, medido no código

| Característica | Código do achado | Severidade |
|---|---|---|
| página rotacionada | `pagina-rotacionada` | bloqueia |
| sem camada de texto | `sem-camada-de-texto` | bloqueia |
| camada de texto parcial | `camada-de-texto-parcial` | alerta |
| texto vertical | `texto-vertical` | alerta |
| mapa de caracteres incompleto | `mapa-de-caracteres-incompleto` | alerta |
| imagem embutida | `imagem-embutida` | nota |
| página em paisagem | `pagina-em-paisagem` | nota |
| múltiplas colunas de texto | `multiplas-colunas-de-texto` | alerta |
| tabela com fundo colorido/listras | `tabela-com-fundo-colorido` | nota |

As últimas três, fechadas em 2026-08-13, vieram de investigação contra
documento real de um cenário corporativo separado (fora deste
repositório), não de heurística no escuro:

- **`pagina-em-paisagem`** — trivial (`mediabox.width > mediabox.height`),
  sem calibração. Usa `mediabox`, não `rect`: `rect` troca largura por
  altura sob rotação de 90/270°, o que faria uma página retrato rotacionada
  contar como paisagem — achado real de teste, corrigido antes de
  validar contra os documentos reais.
- **`multiplas-colunas-de-texto`** — agrupa blocos de texto por faixa de X
  que não se sobrepõe, descartando grupos abaixo de um piso de palavras
  (`PALAVRAS_MINIMAS_POR_COLUNA = 15`, ponto de partida declarado sobre os
  dois documentos, mesmo espírito de `AREA_MINIMA_DE_IMAGEM_RELEVANTE`).
  Generaliza corretamente entre dois layouts bem diferentes, confirmado
  contra os dois documentos reais: prosa em coluna dupla (um deles é
  formatado em slides) e coluna de comentário de revisão reservada à parte
  do corpo do texto (o outro, num documento de texto corrido) — ambos são
  geometricamente a mesma característica.
- **`tabela-com-fundo-colorido`** — agrupa retângulos preenchidos por linha
  (mesmo Y), exige 2+ células por linha somando ≥35% da largura da página,
  3+ linhas e 2+ cores distintas entre elas. **Achado real de validação:**
  a primeira versão não excluía preenchimento quase-preto, e uma tabela com
  borda desenhada como retângulo fino preenchido de preto (não traço)
  produzia dezenas de "linhas", todas pretas; somada a **uma única** célula
  de destaque colorida não relacionada em outro ponto da mesma página, isso
  passava no piso de "2+ cores" por acidente — corrigido excluindo
  preenchimento com os três canais abaixo de 0,15 (`LIMIAR_QUASE_PRETO`) do
  agrupamento, tratado como linha de grade (`tabela com grade`,
  característica ainda não implementada), não como cor de tabela.

**Observado em documento real, mas não implementado — motivo declarado,
não esquecimento:**

| Característica | Por que não virou sonda ainda |
|---|---|
| célula mesclada / cabeçalho hierárquico | Exige reconstrução de estrutura de tabela (detectar que uma célula cobre várias subcolunas) que o projeto não tem como primitiva geral — diferente de geometria simples de linha/retângulo. |
| gráfico / diagrama | Distinguir diagrama esquemático de gráfico de dados ou de foto exige inspeção visual (método 3, `LLM_SIMPLES`) — geometria não alcança essa distinção. |

As demais características do catálogo (`CARACTERISTICAS.md`) — manuscrito,
número em formato estrangeiro, idioma diferente, digitalização torta/ruim,
PDF gerado por digitalizador antigo, tabela sem grade por só espaçamento —
continuam **hipotéticas**, sem mudança de status: nenhum dos dois
documentos reais investigados tem página digitalizada nem exercita essas
características.

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
| página em paisagem | **pronta** |
| múltiplas colunas de texto | **pronta** |
| inclinação de digitalização | exige código |

### Estrutura de tabela

| Característica | Detecção |
|---|---|
| tabela com fundo colorido/listras | **pronta** |
| tabela com grade | exige código |
| **tabela sem bordas** (alinhamento por espaço) | exige código |
| células mescladas / cabeçalho hierárquico | observada em documento real, exige código (reconstrução de tabela) |
| registro em várias linhas | exige código |
| tabela que cruza páginas | exige código |
| número de colunas | **pronta** (via reconstrução posicional) |

### Conteúdo não textual

| Característica | Detecção |
|---|---|
| imagem embutida | **pronta** |
| gráfico / diagrama | observada em documento real, exige inspeção visual/LLM |
| manuscrito | exige inspeção manual |
| ruído de digitalização | exige código |

## Como a taxonomia é usada

**Na coleta:** é a lista de compras. Cada documento novo entra por qual
característica exercita, não por parecer variado. Documento que só repete
característica já coberta não acrescenta informação e custa tempo de execução.

**Na página de referência (ADR-0016; nome escolhido para não colidir com
`triagem.Classe` — ver `GLOSSARIO.md`):** uma página por característica, a
mesma em todas as máquinas. É o que torna "melhor configuração" uma
afirmação por classe, e não uma média sobre um conjunto arbitrário.

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
