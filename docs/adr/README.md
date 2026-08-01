# ADRs — pdf-parser

Registro de decisões de arquitetura. Um arquivo por decisão (`NNNN-titulo.md`), criado
**quando a decisão é tomada**.

Formato: contexto → medição (quando houver) → opções com trade-offs → decisão →
consequências. A justificativa é técnica e, sempre que possível, **medida** — número
vale mais que argumento.

## Decisões registradas

| ADR | Decisão | Evidência que a sustenta |
|---|---|---|
| [0001](0001-biblioteca-de-extracao-de-pdf.md) | PyMuPDF como leitor de PDF | Extração ingênua produziu 89 palavras reais em 534k caracteres |
| [0002](0002-reconstrucao-posicional-de-tabela.md) | Reconstrução posicional própria | 1524 campos contra 4 do detector pronto, e 17× mais rápido |
| [0003](0003-rota-deterministica-como-padrao.md) | Rota determinística como padrão | 164 páginas em 1,55 s — ~190× dentro do alvo de referência |
| [0004](0004-proveniencia-por-campo.md) | Proveniência por campo desde o início | Retrofitar exigiria reescrever todo consumidor |
| [0005](0005-comparabilidade-como-requisito.md) | Comparabilidade como requisito | Sem régua comum, a diferença medida é artefato do pipeline |
| [0006](0006-ferramentas-convencionais-de-tabela.md) | Ferramentas convencionais **funcionam** com camada de adaptação | pdfplumber 100%, Camelot 99% após desrotação e alinhamento posicional |
| [0007](0007-ocr-e-resolucao.md) | Rota por OCR a 350 dpi | 99,5% de acurácia; curva de resolução não monotônica (400 dpi colapsa) |
| [0008](0008-configuracao-declarativa.md) | Perfis e prompts fora do código | Sete parâmetros ajustáveis em sete arquivos, cinco deles em Python |
| [0009](0009-avaliacao-como-ferramenta-de-produto.md) | O mecanismo de avaliação é produto; os dados de uma validação não | Quem aponta o parser para documentos próprios faz as mesmas perguntas |
| [0010](0010-lote-e-diagnostico.md) | Lote como unidade de execução, com decisão de layout por arquivo | Rotação derrubava quatro ferramentas a **zero** de acurácia |
| [0011](0011-unidade-e-esquema-declarados.md) | Unidade e esquema de saída declarados no perfil | `Origem.DERIVADO` definido e validado, produzido por nada |
| [0012](0012-alinhamento-do-gabarito.md) | Alinhamento por descrição antes de número | Conjunto de reserva media **0%** em rotas que acertam 100% |
| [0013](0013-desenho-do-experimento-multimaquina.md) | Três eixos de comparação entre máquinas | Confrontar máquinas diferentes mede hardware, não estratégia |
| [0014](0014-selecao-de-modelos-para-comparacao.md) | Critérios de seleção de modelos, com trade-offs | Nove candidatos da mesma família enviesariam a conclusão |
| [0015](0015-limite-de-saida-do-modelo.md) | Teto de saída declarável, sem padrão embutido — **com retificação**: o parâmetro culpado estava errado | `done_reason` `length`: a resposta era **cortada**, não ausente. Ver ADR-0018 |
| [0016](0016-triagem-e-preenchimento.md) | Triagem e preenchimento como fases distintas | O desenho ingênuo dava **1.656 execuções, ~56 dias** de máquina |
| [0017](0017-consolidacao-por-campo.md) | Consolidar por célula, não escolher planilha *(proposto)* | Três rotas empatam em **100%**; escolher uma descarta a concordância |
| [0018](0018-dimensionamento-de-contexto.md) | Contexto calculado por medição, nunca herdado do padrão do servidor | Quatro casos, prompts de tamanhos diferentes, parando na **mesma soma exata** de entrada+saída |
| [0019](0019-ambiente-de-execucao-em-maquina-de-terceiro.md) | O que não se controla em máquina alheia: detectar e declarar, não impedir | Leitura padrão de memória de vídeo **trunca em 4 GB**; exclusividade de placa é impossível |
| [0020](0020-pre-registro-do-protocolo.md) | Hipóteses, métricas e critério de corte fixados **antes** da bateria *(proposto)* | Registrar depois é indistinguível de escolher o que favorece a conclusão; as "8 hipóteses" eram citadas desde o ADR-0016 **sem nunca terem sido enumeradas** |
| [0021](0021-taxonomia-de-caracteristicas.md) | Característica estrutural é **2º eixo da página**, ao lado da classe de conteúdo *(proposto)* | Uma página é `DADOS` **e** `DIGITALIZADA` ao mesmo tempo; rótulo por documento apagaria o **documento misto**, que é o caso difícil |
| [0022](0022-politica-de-prompt.md) | Prompt-base comum, adaptação só de formato; otimização automática fica para depois *(proposto)* | Prompt por modelo torna o resultado **não reproduzível** — a comparação vira "quem otimizou melhor" |

## Em aberto

- ~~**Estratégia de saída estruturada por modelo**~~ — **resolvido**: degraus de
  saída (esquema completo → JSON livre → texto livre), com o degrau usado
  registrado junto do resultado. Ver SPEC §4.4 e `src/parser/degraus.py`.
- **Motor de inferência** — depende da infraestrutura disponível.
- **Custo de contexto por arquitetura** — a curva medida (ADR-0018) prevê bem,
  mas vale para **um** modelo. A inclinação depende da arquitetura, e o
  experimento em várias máquinas vai levantar os demais pontos.
- ~~**Composição final do conjunto de validação**~~ — **resolvido**. O conjunto de
  reserva cobre 10 itens em 9 páginas de seções distintas do documento, transcritos
  às cegas. Foi ele que revelou os defeitos de alinhamento do ADR-0012 e passou a
  demonstrar generalização: três rotas a 100% em layout não usado no ajuste.
- **Triagem de página por modelo** — a triagem atual é heurística determinística
  (densidade numérica e volume de texto). Classificar por conteúdo é decisão
  semântica e pode se beneficiar de um modelo. Hipótese a medir contra a baseline.
