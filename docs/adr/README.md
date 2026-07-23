# ADRs — pdf-parser

Registro de decisões de arquitetura. Um arquivo por decisão (`NNNN-titulo.md`), criado **quando a decisão for tomada**, ao escolher entre as opções de [../../REQUISITOS.md](../../REQUISITOS.md).

Formato: contexto → opções consideradas (com trade-offs) → decisão → consequências. Justificar por critério técnico (qualidade/custo/VRAM/licença/velocidade), com medições quando houver.

## Decisões em aberto (a registrar ao decidir)

- **ADR-1 (proposto)** — Ferramenta da Etapa 1 (determinística): Docling × Marker/Surya × MinerU × PyMuPDF+pdfplumber+Camelot. Trade-off: qualidade em tabela × velocidade × idiomas × custo.
- **ADR-2 (proposto)** — Estratégia de triagem de página (digital × escaneado) e roteamento Etapa 1 vs Etapa 2.
- **ADR-3 (proposto)** — Modelo da Etapa 2 (VLM/LLM): Qwen2.5-VL × olmOCR 2 × DeepSeek-VL2 × GLM-4.5V × LLM-texto. **Restrição: o que a máquina suporta** (VRAM). Trade-off: qualidade × VRAM × velocidade × licença.
- **ADR-4 (proposto)** — Structured output: function calling × guided decoding (vLLM+Outlines/xgrammar, llama.cpp+GBNF) × Instructor. Trade-off: garantia sintática × simplicidade de setup.
- **ADR-5 (proposto)** — Motor de inferência: vLLM × Ollama/llama.cpp. Trade-off: recursos (guided_json) × simplicidade.
- **ADR-6 (proposto)** — Ferramenta de otimização de prompt: Promptfoo (começo) × DSPy (depois, se escalar). Decidir gatilho de migração.
- **ADR-7 (proposto)** — Eval: composição do golden set, métricas por tipo de campo, ferramenta (extract-eval), definição de holdout final.

Nenhuma decisão tomada ainda; estas entradas marcam o que precisará de ADR.
