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
| [0015](0015-limite-de-saida-do-modelo.md) | Teto de saída declarável, sem padrão embutido | `done_reason` `length` em 1887–1927 tokens: a resposta era **cortada**, não ausente |

## Em aberto

- **Estratégia de saída estruturada por modelo** — chamada de função × decodificação
  guiada × validação com retentativa. Decidir ao implementar a rota por modelo.
- **Motor de inferência** — depende da infraestrutura disponível.
- ~~**Composição final do conjunto de validação**~~ — **resolvido**. O conjunto de
  reserva cobre 10 itens em 9 páginas de seções distintas do documento, transcritos
  às cegas. Foi ele que revelou os defeitos de alinhamento do ADR-0012 e passou a
  demonstrar generalização: três rotas a 100% em layout não usado no ajuste.
- **Triagem de página por modelo** — a triagem atual é heurística determinística
  (densidade numérica e volume de texto). Classificar por conteúdo é decisão
  semântica e pode se beneficiar de um modelo. Hipótese a medir contra a baseline.
