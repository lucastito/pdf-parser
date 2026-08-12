# Requisitos — pdf-parser

Requisitos funcionais + ferramentas/modelos candidatos + plano de avaliação. Requisitos numerados (RF-N). Onde há **várias opções**, estão listadas como candidatas — a escolha sai de trade-off medido e vira um ADR em [docs/adr/](docs/adr/).

> **atendido** = implementado **e** medido · **parcial** = implementado, com
> limite declarado · **proposto** = ainda não implementado.
>
> Estado revisado em 2026-07-31 contra o código e as medições. A acurácia citada
> é contra o **conjunto de reserva** — layout não usado no ajuste —, que é o
> número que vale.

---

## Requisitos funcionais

### Etapa 1 — Extração determinística
- **RF-1 — PDF digital (texto real).** Extrair texto e tabelas de PDFs com texto nativo, de forma rápida e barata (sem VLM). ***(atendido)*** — quatro rotas independentes; três a **100%**: posicional, pdfplumber e camelot. Uma página em **0,2 s**. Ver ADR-0002, ADR-0006.
- **RF-2 — Fallback OCR.** Em PDFs escaneados de baixa qualidade, cair para OCR clássico. ***(parcial)*** — rota implementada e medida (**78%** no conjunto de reserva, 99,5% no gabarito principal), mas **nunca exercitada em documento realmente digitalizado**: não temos nenhum. Ver ADR-0007.
- **RF-3 — Triagem de página.** Decidir por página se é texto nativo (rota determinística) ou imagem/layout complexo (rota Etapa 2). ***(atendido no Cenário B; parcial no Cenário A)*** — `triagem.py` classifica por densidade numérica e volume de texto; `diagnostico.caracterizar_pagina` cobre o segundo eixo (características, não exclusivas — ADR-0021); `parser.planejador` (ADR-0025) roteia de fato, por página, entre determinístico/palavra-chave/OCR/modelo, sem layout declarado à mão. Em uso no caminho de produção do Cenário B (`ingerir`). O Cenário A não usa este roteador — `pipeline.Pipeline` continua com um extrator só por documento inteiro.

### Etapa 2 — VLM/LLM
- **RF-4 — Página como imagem → schema.** Para páginas-imagem ou layout complexo, um VLM lê a página inteira como imagem e extrai direto para o schema (pula parser separado). ***(parcial)*** — implementado e medido: o modelo **lê a página corretamente**. O limite é de **tempo em processador**, não de capacidade — ver ADR-0018. Precisa ser remedido sob contexto declarado. No Cenário B, o roteador (ADR-0025) também decide VLM como **complemento** de outra rota quando a página tem imagem embutida relevante — não só como escalada final.
- **RF-5 — LLM de texto pós-Etapa 1.** Quando a Etapa 1 já extraiu o texto (PDF digital), usar um LLM de texto para estruturar — não precisa VLM. ***(atendido)*** — 31 itens em JSON válido, **100%** em `energia_kcal` contra o gabarito, sem raciocínio. Custo: ~14.500× a rota determinística. O prompt segue a política de ADR-0022 (base comum, sem otimização por modelo) e, para estrutura desconhecida, é montado do diagnóstico em vez de declarado à mão (ADR-0023, implementado no Cenário B).
- **RF-6 — On-premise/open-weight.** Sem depender de API proprietária; modelo roda localmente, limitado à memória da máquina. ***(atendido)*** — tudo local. A relação entre contexto e memória está medida e **prevê fora do intervalo de ajuste** (ADR-0018).

### Saída estruturada
- **RF-7 — JSON validado contra schema.** A saída é constrangida a JSON válido contra o schema, não texto livre pós-processado. O schema é definido por quem usa; o parser é agnóstico ao domínio. ***(atendido)*** — degraus de saída (esquema completo → JSON livre → texto livre), com o degrau usado registrado junto do resultado. Validação tabular por Pandera. Ver SPEC §4.4, ADR-0011.
- **RF-8 — Destino configurável.** JSON validado → grava no destino escolhido, sem parsing manual. O destino é parâmetro, não fixo. ***(parcial)*** — porta `Destino` com CSV e JSON implementados; o lote grava os dois sempre. Banco e API ainda não têm adaptador — no Cenário B, o destino real (uma chamada a outro sistema) ainda não existe como `Destino`, ver `PLANO.md`.
- **RF-11 — Consolidação por campo, quando mais de uma rota concorda.** Em vez de escolher "a melhor" planilha entre rotas determinísticas que rodaram sobre a mesma página, votar célula a célula — concordância plena preenche com confiança alta, maioria preenche e registra a divergência, empate ou ausência vira pendência humana. ***(parcial)*** — implementado e em produção no Cenário B (`consolidacao.py`, ADR-0017), mas com uma lacuna conhecida e não fechada: um item que só uma rota produziu entra como voto único de confiança 0,9 sem checar risco de fabricação (ver `PLANO.md`, P-1.1 e "Cenário B"). Peso de voto por rota continua uniforme e provisório, sem matriz de correlação de erro medida.

### Operação
- **RF-9 — Sem prompt manual.** Prompt fixo, versionado, chamado por script/job. ***(atendido)*** — prompts versionados em `prompts/`, fora do código (ADR-0008); execução em lote sobre pasta (ADR-0010).
- **RF-10 — Eval antes de produção.** Nenhuma ida a produção com dado real sem avaliação medida. *(obrigatório)* — mecanismo pronto e em uso: gabarito conferido à mão, conjunto de reserva transcrito às cegas, acurácia por campo (ADR-0009, ADR-0012).

---

## Ferramentas candidatas — Etapa 1 (determinística)

| Ferramenta | Força | Nota |
|---|---|---|
| **Docling** (IBM) | Tabelas complexas, saída estruturada pronta p/ pipeline LLM | self-hosted |
| **Marker + Surya OCR** (Datalab) | Rápido, multilíngue, exporta markdown/JSON/chunks; roda GPU/CPU/Mac | PDF/imagem/DOCX/XLSX |
| **MinerU** (OpenDataLab) | SOTA OmniDocBench v1.6 (95.69), só 1.2B params, OCR 84 idiomas, layout, markdown/JSON | ótimo custo-benefício |
| **PaddleOCR-VL** | Reporta 96.33 no mesmo benchmark | *número do fabricante, não validado por terceiro* |
| **PyMuPDF / pdfplumber** | Extração de texto de PDF digital limpo | determinístico puro |
| **Camelot** | Tabelas | determinístico puro |
| **Tesseract (pytesseract)** | OCR clássico | fallback p/ escaneado |

## Modelos candidatos — Etapa 2 (VLM/LLM open-weight, on-premise)

| Modelo | Tipo | Por quê | VRAM mínima |
|---|---|---|---|
| **Qwen2.5-VL** (7B/32B/72B) | Vision-Language | Lê página como imagem (tabela torta, escaneado, layout complexo). Líder OCRBench (~888), 95.7% DocVQA, multilíngue (29 idiomas), Apache 2.0 nas menores | 7B: 24GB · 72B: 2×80GB |
| **olmOCR 2** (7B, Allen Institute) | VLM especialista OCR | PDF→markdown limpo preservando ordem de leitura, tabelas, equações | 1×24GB |
| **DeepSeek-VL2** (MoE, 27B total/4.5B ativo) | VLM | Eficiência MoE: roda como modelo bem menor, ótimo custo/VRAM | 1×24–48GB |
| **GLM-4.5V** | VLM | SOTA open-source multimodal 2026, modo "thinking" p/ docs complexos | multi-GPU |
| **Llama 3.3 / Qwen3 / Mistral / Gemma 3** | LLM texto puro | Usar **depois** do Docling/Marker extrair o texto — não precisa VLM se PDF for digital | 7B–32B: 1 GPU |

**Dimensionamento:** 7B ≈ 24GB · 32B ≈ 24–32GB quantizado · 72B ≈ 2–4× 80GB. **O modelo escolhido deve ser o que a máquina suporta.**

> **Medido neste projeto, e refina os números acima:** o peso do modelo é só uma
> parte. O **contexto** cobra memória à parte, e a conta é linear e previsível —
> um modelo de 4B quantizado ocupa 3,6 GB com contexto de 4096 e **8,0 GB** com
> 32768. A curva ajustada com dois pontos previu o terceiro com **0,4% de erro**.
>
> Consequência prática: contexto de 64k pediria ~13 GB **só neste modelo
> pequeno** e não caberia numa placa de 12 GB. Dimensionar por peso do modelo
> subestima. Ver [ADR-0018](docs/adr/0018-dimensionamento-de-contexto.md).

**Recomendação prática (a validar):** PDF digital limpo → MinerU/Marker (mais barato/rápido que VLM 7B+ por página). PDF escaneado/foto ruim → VLM ou olmOCR direto na imagem.

## Structured output — como forçar a saída (candidatas)

- **Function/tool calling:** campos definidos como parâmetros de função com schema; modelo devolve chamada já validada.
- **Constrained/guided decoding:** motor de inferência (vLLM + Outlines/xgrammar, ou llama.cpp + gramática GBNF) só deixa passar tokens que mantêm JSON válido — geração sintaticamente garantida.
- **Instructor** (Python): Pydantic model espelhando os campos do schema; injeta no provider (Ollama/vLLM/outros locais), valida e faz retry se errar o schema.

**Fluxo alvo:** schema Pydantic/JSON (um campo por vez, tipo+unidade quando aplicável) → modelo via vLLM `guided_json` ou Instructor → JSON validado → destino configurável. Zero parsing manual.

## Como testar/comparar modelos e prompts (candidatas)

- **Promptfoo:** compara prompts/modelos, integra CI/CD; aponta regressão ao mudar prompt/modelo. *Começar por aqui p/ montar golden set e comparar modelo×modelo.*
- **DSPy:** programável — define Signature (entrada: texto/imagem do PDF; saída: schema) + métrica, otimiza prompt e few-shot contra dataset. *Aplicar depois, se nº de campos/variações crescer.*

## Plano de avaliação (obrigatório antes de produção)

- **Golden set:** 30–100 PDFs reais representativos (digital limpo, escaneado, baixa qualidade) com o resultado correto como gabarito.
- **Métrica por campo, não geral:** Exact Match p/ categóricos/enum/IDs; F1 ou similaridade de texto p/ campos livres; tolerância percentual p/ campos numéricos (comparação exata de string falha em "42"×"42.0" ou "NYC"×"New York").
- **Ferramenta candidata:** **extract-eval** (open-source: precision/recall/F1 por campo p/ extração JSON contra gabarito, inclusive campos aninhados).
- **Matriz comparativa:** rodar a avaliação para cada combinação (parser determinístico × modelo × prompt), montar tabela interna → critério objetivo de produção; **rerodar sempre que trocar modelo/versão** para detectar regressão.

> **Nota de rigor (herdada do jobfit):** golden set usado para iterar **não é holdout**. Se ajustar prompt/modelo olhando o mesmo conjunto, reserve um conjunto final não-visto para o gate de produção.
