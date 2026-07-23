# Requisitos — pdf-parser

Requisitos funcionais + ferramentas/modelos candidatos + plano de avaliação. Requisitos numerados (RF-N). Onde há **várias opções**, estão listadas como candidatas — a escolha sai de trade-off medido e vira um ADR em [docs/adr/](docs/adr/).

> **proposto** = ainda não implementado.

---

## Requisitos funcionais

### Etapa 1 — Extração determinística
- **RF-1 — PDF digital (texto real).** Extrair texto e tabelas de PDFs com texto nativo, de forma rápida e barata (sem VLM). *(proposto)*
- **RF-2 — Fallback OCR.** Em PDFs escaneados de baixa qualidade, cair para OCR clássico. *(proposto)*
- **RF-3 — Triagem de página.** Decidir por página se é texto nativo (rota determinística) ou imagem/layout complexo (rota Etapa 2). *(proposto)*

### Etapa 2 — VLM/LLM
- **RF-4 — Página como imagem → schema.** Para páginas-imagem ou layout complexo, um VLM lê a página inteira como imagem e extrai direto para o schema (pula parser separado). *(proposto)*
- **RF-5 — LLM de texto pós-Etapa 1.** Quando a Etapa 1 já extraiu o texto (PDF digital), usar um LLM de texto para estruturar — não precisa VLM. *(proposto)*
- **RF-6 — On-premise/open-weight.** Sem depender de API proprietária (OpenAI/Claude); modelo roda localmente, limitado à VRAM da máquina. *(proposto)*

### Saída estruturada
- **RF-7 — JSON validado contra schema.** A saída é constrangida a JSON válido contra o schema (um campo por vez, com tipo e unidade quando aplicável), não texto livre pós-processado. O schema é definido por quem usa; o parser é agnóstico ao domínio. *(proposto)*
- **RF-8 — Destino configurável.** JSON validado → grava no destino escolhido (CSV, banco, API…), sem parsing manual. O destino é parâmetro, não fixo. *(proposto)*

### Operação
- **RF-9 — Sem prompt manual.** System prompt fixo, versionado, chamado por script/job (disparo ao chegar PDF novo ou em batch agendado). *(proposto)*
- **RF-10 — Eval antes de produção.** Nenhuma ida a produção com dado real sem avaliação medida (ver plano de eval). *(obrigatório)*

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
