# CLAUDE.md — pdf-parser

Instruções para agentes trabalhando neste repositório.

## O que é

Parser de documentos **agnóstico de domínio**, em duas etapas (determinística + VLM/LLM),
que extrai conteúdo estruturado e entrega **saída validada contra schema**.
Entrada e saída são **parametrizáveis**: o núcleo não conhece formato de arquivo nem destino.

Ver [README.md](README.md) e [REQUISITOS.md](REQUISITOS.md).

**Ao retomar o trabalho:** o plano do que falta, em ordem e com justificativa, está
em [PLANO.md](PLANO.md). As decisões e as medições que as sustentam estão em
[docs/adr/](docs/adr/) — inclusive hipóteses que a medição refutou, registradas de
propósito para que a busca não se repita.

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

## Dois cenários de uso, um núcleo só

Este repositório serve dois propósitos diferentes, no mesmo código:

- **Cenário A — pesquisa** (branch `main`, deste repositório): comparar
  modelos, famílias, configurações e hipóteses. Documento-caso é o TACO;
  perfil de exemplo é `perfis/nutricional.json` — **não é template a
  replicar**, é só o exemplo de um domínio. Usa os subcomandos `ambiente`,
  `diagnosticar`, `calibrar`, `avaliar`, `comparar`, `experimento` e a classe
  `parser.pipeline.Pipeline`.
- **Cenário B — uso corporativo** (mantido fora deste repositório, num
  branch e remoto privados): processar documentos reais de um cenário de
  produção, agnóstico ao domínio deles — não há estrutura fixa a assumir.
  Usa só `ingerir`, que roteia por página (`parser.planejador`) sem layout
  nem ordem de coluna declarados à mão.

**Não há parâmetro de "modo" no código — o parâmetro é qual comando você
roda.** `ingerir` é o único caminho de produção; os demais são ferramenta de
pesquisa e não precisam ser tocados para operar em B.

O que é compartilhado entre os dois, e por quê:

| Módulo | Por quê é dos dois |
|---|---|
| `calibracao`, `triagem`, `diagnostico`, `planejador`, `fabrica` | descoberta de estrutura é agnóstica de domínio por definição |
| `vocabulario` | ler "campo esperado" de uma planilha de schema é agnóstico — não sabe se o schema é nutricional, financeiro ou técnico, só sabe procurar o que foi declarado |
| `degraus` | qualquer chamada a LLM/VLM, em A ou B, precisa da mesma escada de restrição de saída |
| `contexto` | dimensionar `num_ctx` pela entrada medida importa tanto num experimento quanto em produção real |
| `concordancia`, `consolidacao` | comparar rotas entre si é tanto sinal de confiança em tempo de execução (B) quanto métrica de comparação (A) |

O que é só de A, e por quê:

| Módulo | Por quê não entra em B |
|---|---|
| `escada`, `procedencia`, `medicao` | alocação de modelo por máquina emprestada, trava de execução concorrente — B roda num servidor só |
| `extratores/linear.py` | piso de comparação, deliberadamente ruim; não serve a produção |
| `parser.pipeline.Pipeline` | um extrator só por documento — o modelo que `planejador` existe para superar |

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
