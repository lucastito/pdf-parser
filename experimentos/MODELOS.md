# Modelos candidatos: levantamento e escada de capacidade

> **Levantamento de julho de 2026**, a partir de repositórios públicos, benchmarks
> independentes e relatórios técnicos. **Nada aqui foi medido neste projeto** —
> é a lista de candidatos que o experimento vai testar, não conclusão sobre eles.
>
> Distinguir as duas coisas é o ponto: reputação orienta a escolha do que testar;
> só a medição decide o que usar.

## Por que este documento existe

A máquina de referência (~2 GB de memória de vídeo) só comporta modelos pequenos.
Máquinas com mais capacidade abrem uma classe inteira que aqui não roda — e a
pergunta que sustenta o dimensionamento de infraestrutura é: **mais capacidade
melhora o resultado, ou satura?**

Responder exige rodar uma escada crescente até a máquina não aguentar. E exige que
quem executa não precise descobrir os parâmetros sozinho: eles vão resolvidos.

## Escada de visão (o modelo lê a página como imagem)

| Degrau | Modelo | Tamanho | Cabe em 12 GB | Papel no experimento |
|---|---|---|---|---|
| 1 | `qwen3-vl:4b` | 3,3 GB | sim | **denominador comum** — é o que roda na máquina de referência |
| 2 | `qwen2.5vl:7b` | ~6 GB | sim | o mais recomendado para documento e tabela em benchmarks independentes |
| 3 | `qwen3-vl:8b` | 6,1 GB | sim | mesma família do degrau 1, maior — isola o efeito do tamanho |
| 4 | `qwen3-vl:30b` | 20 GB | **não** | **teto esperado** — a falha marca o limite real da máquina |

O degrau 1 é o único comparável com a máquina de referência. Os demais vivem no
eixo exploratório (ADR-0013): comparam-se **entre as máquinas maiores**, não com a
pequena.

O degrau 4 existe para falhar. Uma escada que só sobe enquanto funciona não revela
o teto, e o teto é justamente o que orienta a compra.

## Escada de texto (o modelo recebe o texto já extraído)

| Degrau | Modelo | Tamanho | Cabe em 12 GB | Papel |
|---|---|---|---|---|
| 1 | `qwen3:1.7b` | 1,4 GB | sim | piso — cabe em quase qualquer máquina |
| 2 | `qwen3:4b` | 2,5 GB | sim | **denominador comum** com a máquina de referência |
| 3 | `qwen3:8b` | 5,2 GB | sim | isola o efeito do tamanho |
| 4 | `qwen3:14b` | 9,3 GB | apertado | limite prático dos 12 GB |
| 5 | `qwen3:30b` | 19 GB | **não** | teto esperado |

A rota de texto é intrinsecamente mais barata: recebe ~649 tokens de entrada
contra ~2164 da imagem, na mesma página. Se produzir resultado comparável, é a
rota preferível — e essa comparação nunca foi feita.

## Descartados, e por quê

**`granite3.2-vision` (2B)** — posicionado para documento, mas um benchmark
independente o desqualificou: saídas malformadas ou com tabelas erradas.

**`deepseek-ocr` (3B)** — desqualificado no mesmo benchmark por gerar arquivos
efetivamente vazios, apesar de reportar sucesso e tempo baixo. **É exatamente a
patologia que enfrentamos aqui** (resposta vazia com `done_reason` de sucesso), e
foi o que custou uma sessão de investigação. Não repetir.

**Modelos de 32B+** — não cabem em 12 GB nem quantizados.

Ambos os descartes vêm de fonte externa, não de medição própria. Se houver tempo,
vale medir o `deepseek-ocr` justamente por ser barato e por já sabermos diagnosticar
a falha dele — mas ele não entra na escada principal.

## Parâmetros já resolvidos

Estes **não** são para descobrir de novo. Custaram uma sessão inteira de medição
na máquina de referência, e vão fixados no script.

| Parâmetro | Valor | Por quê |
|---|---|---|
| `num_predict` (teto de saída) | **16384** | com ~2048 a geração é cortada no meio e a resposta volta **vazia**; 16384 deixou a página inteira caber |
| `dpi` da imagem | **150** | ADR-0003 — compromisso entre legibilidade e custo |
| degrau de saída | **fixado, não livre** | ADR-0013 — descer livremente faz cada máquina medir uma restrição diferente |
| medições simultâneas | **nunca** | duas concorrentes inflam o tempo das duas, e aqui o tempo é o resultado |
| `done_reason` | **sempre registrado** | `stop` = terminou; `length` = cortado. Foi ele que revelou a causa do vazio |

> **Em aberto:** como desligar o canal de raciocínio. O parâmetro `think: false` é
> enviado e **não é respeitado** por esta combinação de servidor e modelo — a
> contagem de tokens não muda. A forma alternativa (`/no_think` no prompt) está em
> medição. O valor final entra aqui quando fechar.

## O que cada máquina roda

**Máquina de referência (~2 GB):** só o degrau 1 de cada escada. É o denominador
comum, e é onde a comparação entre todas as máquinas é legítima.

**Máquinas com folga:** a escada inteira, **um modelo por vez**, do menor ao maior,
até falhar. Dois modelos disputando memória de vídeo falham por contenção, não por
incapacidade — e isso produziria um teto falso.

**Entre as máquinas maiores:** se tiverem a mesma capacidade e placas diferentes, a
comparação isola arquitetura de memória. Se tiverem capacidades diferentes, isola o
efeito da memória. As duas perguntas são úteis e independentes.

## Fontes

Levantamento de julho de 2026:

- [Qwen2.5-VL Technical Report](https://arxiv.org/pdf/2502.13923)
- [Qwen3-VL Technical Report](https://arxiv.org/pdf/2511.21631)
- [OCRBench v2](https://arxiv.org/html/2501.00321v2)
- [Local Vision-Language OCR Benchmark](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- [Best Open-Weight OCR and Document AI Models 2026](https://presenc.ai/research/best-open-weight-ocr-document-ai-models-2026)
- [Ollama — biblioteca de modelos](https://ollama.com/library/qwen3-vl)
