# CLAUDE.md — pdf-parser

Instruções para agentes trabalhando neste repositório.

## O que é

Parser de documentos **agnóstico de domínio**, em duas etapas (determinística + VLM/LLM),
que extrai conteúdo estruturado e entrega **saída validada contra schema**.
Entrada e saída são **parametrizáveis**: o núcleo não conhece formato de arquivo nem destino.

Ver [README.md](README.md) e [REQUISITOS.md](REQUISITOS.md).

## Regra de confidencialidade — leia antes de escrever qualquer coisa

Parte do contexto deste projeto vem de material sob **NDA**.

A regra não é apenas "não citar nomes". É mais estrita:

> **Só entra em arquivo versionado o que é indiferente ao modelo de negócio
> e ao contexto de qualquer cliente.**

Isso proíbe, além de nomes de empresa e de produto, o **vocabulário técnico
setorial** — mesmo sem citar nome algum. Um domínio identifica tanto quanto um nome:
um repositório cheio de jargão de um setor específico revela o cliente por dedução.

Proibido em: código, comentários, documentação, ADRs, roadmap, backlog,
nomes de arquivo, nomes de branch e mensagens de commit.

**Referência do que é permitido:** o domínio nutricional (TACO) e tudo que for
genérico de processamento de documentos. Em caso de dúvida sobre um termo,
pergunte antes de escrever — não tente adivinhar.

Material sensível vive **apenas** em caminhos ignorados pelo git:

| Caminho | Conteúdo |
|---|---|
| `CLAUDE.local.md` | contexto de trabalho, nomes reais, mapeamento |
| `docs/_private/` | especificações de terceiros, planos mestre |
| `.githooks/denylist.txt` | os termos restritos em si |

Em texto versionado, prefira formulações neutras: "o consumidor A / B",
"o perfil corporativo", "um domínio de aplicação".

Dois hooks aplicam isso (`.githooks/pre-commit` e `.githooks/commit-msg`).
**Nunca** use `--no-verify` neste repositório. Se um hook bloquear, o termo sai —
não o hook. Ver [.githooks/README.md](.githooks/README.md).

Se você é um agente e precisa do contexto completo, leia `CLAUDE.local.md`.
Se esse arquivo não existir, trabalhe só com o que está versionado e **pergunte**.

## Setup

```sh
git config core.hooksPath .githooks   # uma vez por clone
.githooks/selftest.sh                 # verifica a guarda
```

## Restrição de hardware

O ambiente de desenvolvimento tem **2 GB de VRAM e 16 GB de RAM**.
Nenhum VLM open-weight de 7B+ roda localmente. Ao propor modelo ou pipeline,
verifique contra esse teto antes de sugerir — e prefira sempre a rota determinística.
LLM/VLM é camada **opcional e medida**, nunca o caminho padrão.

## Princípios

- **Determinístico primeiro.** Modelo só onde o determinístico não alcança, e sempre medido contra ele.
- **Saída validada, não confiada.** Schema (Pydantic/grammar), nunca parsing de texto solto.
- **Proveniência por campo.** Todo valor carrega se foi extraído, derivado ou inferido, com confiança.
- **Sem eval, sem produção.** Nenhum dado real em produção sem avaliação medida por campo.
- **Núcleo agnóstico.** Adicionar formato de entrada ou destino não altera o núcleo.
