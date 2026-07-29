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
| [0006](0006-ferramentas-convencionais-de-tabela.md) | Ferramentas convencionais avaliadas e descartadas | 133 e 104 registros extraídos, **0% de acurácia** — volume sem conteúdo |
| [0007](0007-ocr-e-resolucao.md) | Rota por OCR a 350 dpi | 84,5% de acurácia; curva de resolução não monotônica (400 dpi colapsa para 29%) |

## Em aberto

- **Estratégia de saída estruturada por modelo** — chamada de função × decodificação
  guiada × validação com retentativa. Decidir ao implementar a rota por modelo.
- **Motor de inferência** — depende da infraestrutura disponível.
- **Composição final do conjunto de validação** — definir o subconjunto não visto
  reservado para o julgamento final, separado do usado para iterar.
- **Triagem de página por modelo** — a triagem atual é heurística determinística
  (densidade numérica e volume de texto). Classificar por conteúdo é decisão
  semântica e pode se beneficiar de um modelo. Hipótese a medir contra a baseline.
