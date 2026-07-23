# pdf-parser

Parser de PDF **agnóstico de domínio**, em **duas etapas** — uma determinística e uma com **VLM/LLM** — que extrai conteúdo estruturado (texto, tabelas, campos) de documentos, incluindo PDFs digitais, escaneados e de baixa qualidade, e entrega **saída validada contra um schema** (JSON) definido por quem usa. O schema é parâmetro: o parser não presume o tipo de documento nem os campos.

> **Estado:** esqueleto. Nada implementado ainda. Requisitos detalhados em [REQUISITOS.md](REQUISITOS.md); decisões de ferramenta/modelo em aberto em [docs/adr/](docs/adr/) (a criar ao decidir). Futuro aparece como **proposto**.

## Por que duas etapas

PDFs "reais" são hostis: colunas, tabelas sem bordas, páginas escaneadas (imagem sem texto), layout torto. A tese: **combinar** camada determinística (barata, exata, para PDF digital limpo) com camada de modelo (VLM/LLM, para o visual e o semântico), escolhendo a rota pela natureza da página.

1. **Etapa 1 — Determinística.** Para PDF digital (texto real), extrair texto e tabelas com ferramentas rápidas e baratas. Fallback para OCR clássico em escaneados ruins.
2. **Etapa 2 — VLM/LLM.** Para páginas-imagem/layout complexo, um modelo lê a página e extrai direto para o schema; ou, se a Etapa 1 já extraiu o texto, um LLM de texto estrutura o resultado.

Sobre tudo isso, **saída estruturada garantida** (não confiar que o modelo "formatou certo") e **avaliação medida** antes de qualquer produção com dado real.

## Caso de uso guia

PDF chega (novo ou em lote) → pipeline extrai os campos definidos no schema → **JSON validado contra schema** (um campo por vez, com tipo/unidade quando aplicável) → destino a critério de quem usa (CSV, banco, API…). **Zero parsing manual de texto solto** e **zero prompt digitado à mão** (system prompt fixo, versionado, chamado por script/job). O schema e o destino são configuráveis; o núcleo é agnóstico.

## Restrição de hardware

O modelo VLM/LLM escolhido **deve ser o que a máquina do usuário suporta**. Dimensionamento e candidatos por faixa de VRAM estão em [REQUISITOS.md](REQUISITOS.md) — a escolha é on-premise/open-weight (sem depender de API proprietária), decidida por trade-off medido.

## Estrutura

```
pdf-parser/
├── src/            # pipeline: etapa1 (deterministica), etapa2 (VLM/LLM), structured output
├── tests/          # testes + golden set de avaliação
├── samples/        # PDFs de exemplo p/ dev (não versionar PDFs reais/sensíveis)
├── docs/
│   └── adr/        # decisões (parser, modelo, structured output, eval) — criar ao decidir
├── REQUISITOS.md   # requisitos funcionais + ferramentas candidatas + plano de eval
└── README.md
```

## Roadmap (alto nível)

- [ ] Esqueleto (feito)
- [ ] **proposto** — Etapa 1 determinística (texto + tabelas + fallback OCR)
- [ ] **proposto** — Etapa 2 VLM/LLM (página-imagem → schema)
- [ ] **proposto** — Structured output validado (schema/grammar/Pydantic)
- [ ] **proposto** — Golden set + eval por campo (critério objetivo de produção)

Requisitos completos, modelos por VRAM, structured output e plano de avaliação: **[REQUISITOS.md](REQUISITOS.md)**.
