# Alocação de modelos por máquina — **RASCUNHO**

> ## ⚠ Este documento é rascunho, e assim permanece até que as máquinas relatem
>
> **A tabela abaixo não está fechada.** Ela depende de números que ainda não
> existem: a memória real de cada máquina, e a fração que cada uma de fato acelera.
> Hoje eles são estimativa minha, não medição.
>
> **A regra:** a alocação vira definitiva **quando as seis máquinas tiverem enviado
> seu diagnóstico** — VRAM, RAM livre, e a divisão real medida por `/api/ps`. Só
> então o martelo é batido, e este aviso sai.
>
> Enquanto isso, `MODELOS.md` e o `PLANO.md` **referenciam este documento** em vez
> de repetir a alocação. Uma tabela em três lugares diverge em três — foi o que
> aconteceu com a escada, e está registrado adiante.

## O que mudou de entendimento, e por quê

**Memória de vídeo não é limite de execução — é a fração que vai acelerada.**

O servidor divide o modelo sozinho: carrega na placa o que couber e deixa o resto
na memória do sistema, com o processador cuidando dessas camadas. Não é
configuração; é o comportamento padrão.

**Medido na máquina de referência em 2026-08-02**, com `/api/ps`:

| Modelo | Total | Na placa | Na memória do sistema |
|---|---:|---:|---:|
| `qwen3:4b` | 3,28 GB | **0,54 GB (16%)** | 2,75 GB |

O modelo é **maior que a placa inteira** (2 GB) e roda mesmo assim.

Isso invalida o critério anterior — *"modelo entra se couber na placa"* —, que teria
excluído da máquina de referência tudo acima de 2 GB, inclusive o modelo com o qual
ela produziu 100% na página de referência.

**E a placa de 2 GB é usável.** Medido antes: forçando o descarregamento total, o
modelo vai a 100% na placa e roda a **17,1 tokens/s contra 17,5** em processador. A
afirmação correta não é *"a placa não é usada"* — é **"a placa é usável e não
compensa"**, porque a capacidade de computação dela (6.1, de 2017) não supera o
processador. Isso é resultado sobre a placa, não sobre o software.

## Os dois critérios, e o que cada um mede

Nenhum dos dois sozinho serve. Usados juntos, a distinção **é** o que o experimento
mede:

| Critério | Responde |
|---|---|
| cabe na **placa** | quanto vai acelerado — **velocidade** |
| cabe em **placa + memória** | se roda — **viabilidade** |

Daí os dois conjuntos por máquina:

- **obrigatório** — cabe com folga na placa, roda acelerado. É o que sustenta a
  comparação **entre** máquinas;
- **estendido** — só cabe somando a memória do sistema, roda com repartição. Mede
  **o custo de exceder a placa**, que nenhuma outra configuração mede.

## A tabela (rascunho)

Todas as máquinas rodam **as 6 rotas determinísticas** — `posicional`,
`pdfplumber`, `camelot`, `ocr`, `linear`, `pymupdf`. Custam segundos, não dependem
de placa, e são a linha de base contra a qual os modelos são comparados.

| Máquina | Placa | Obrigatório (acelerado) | Estendido (repartido) | Fabricantes |
|---|---|---|---|---:|
| referência | 2 GB | os 8 do piso, em processador | `minicpm-v4.5:8b`, `qwen3:8b`, `gemma4:12b` | **5** |
| B | 6 GB | os 8 + `qwen3:8b` | `deepseek-ocr:3b`, `gemma4:12b` | **5** |
| C | 8 GB † | os 8 + `qwen3:8b`, `qwen3-vl:8b` | `gemma4:12b`, `qwen3:14b` | **5** |
| D | 8 GB | igual a C | igual a C | **5** |
| E | 12 GB | + `gemma4:12b`, `qwen3:14b` | `qwen3:30b` | **5** |
| F | 16 GB | tudo até 14b | `qwen3:30b`, `qwen3-vl:30b` | **5** |

**As seis alcançam as cinco famílias** — Alibaba, OpenBMB, Zhipu, DeepSeek e
Google. Era o que faltava no desenho anterior: pelo critério da placa, Google só
entrava a partir de 12 GB, e os envelopes baixos ficavam sem o controle de
independência. A repartição resolve.

† **A máquina C tem placa AMD RDNA 1 (gfx1010)**, arquitetura que o servidor
provavelmente rejeita — ver `PLANO.md`, seção 4.1. Se cair para processador, ela
não se perde: vira **um segundo ponto sem placa útil, com processador muito
superior** ao da máquina de referência (65 W e 6 núcleos, contra 15 W e 4). Isso
isola o efeito do processador, que nenhuma outra máquina isola. **Falha aqui é
dado.**

## Cada máquina baixa um a mais, que deve falhar

Escada que só sobe enquanto funciona não revela o teto — e o teto é o que orienta
decisão de infraestrutura.

O modelo de falha é **relativo à máquina**: o degrau seguinte ao que ela comporta,
não um valor absoluto. Assim a máquina de referência tenta um de 8B e a maior tenta
um de 30B, e nenhuma baixa 20 GB à toa.

## Tamanhos verificados no catálogo — 2026-08-02

Conferidos contra a origem, **não estimados**. Três números do `MODELOS.md`
estavam errados:

| Modelo | Documentado | **Real** | Consequência |
|---|---|---|---|
| `gemma4:12b` | ~8 GB | **7,6 GB** | cabia em 8 GB e estava alocado só a partir de 12 |
| `minicpm-v4.5:8b` | ~5,5 GB | **6,1 GB** | — |
| `gemma4:e2b` | ausente | **7,2 GB** | menor porte da família Google, nunca considerado |

E a família Google tem portes que o levantamento ignorou: `e2b` (7,2 GB), `e4b`
(9,6 GB), `26b` (18 GB), `31b` (20 GB). **Nenhum cabe em 6 GB de placa** — o menor
já passa —, e é por isso que a repartição com memória do sistema é o que dá Google
aos envelopes baixos.

## Três incoerências a resolver antes de fechar

Levantadas em 02/08, cruzando `MODELOS.md`, a tabela por envelope e o instalador:

1. **`qwen3-vl:4b` não está na escada de visão documentada** — que salta de `2b`
   para `8b` —, mas está no instalador, na tabela por envelope, e é **o modelo mais
   medido do projeto** (100% na página de referência). A revisão de 01/08 trocou um
   pelo outro e não propagou.
2. **O instalador tem 8 modelos; a escada documentada tem 13.** Faltam `qwen3:8b`,
   `qwen3:14b`, `qwen3:30b`, `gemma4:12b`, `qwen3-vl:8b` e `qwen3-vl:30b`.
3. **O teste de paridade não pega isso** — ele compara o instalador com
   `parser.cli`, e ambos têm os mesmos 8. A fonte única precisa ser a escada, com
   envelope declarado por modelo.

**Decisão registrada:** ficam os três portes da família de referência — `2b`, `4b`
e `8b`. São três pontos da **mesma** família com tudo o mais constante, que é a
curva de tamanho mais limpa que o experimento pode ter, e aproveita o que já foi
medido.

## O que falta para bater o martelo

- [ ] As seis máquinas enviam diagnóstico: placa, memória total e livre, e a
      **divisão real medida** por `/api/ps` — não inferida do nome da placa
- [ ] Confirmar se a máquina C usa a placa AMD ou cai para processador
- [ ] Recalcular a tabela **a partir dos números medidos**, substituindo as
      estimativas
- [ ] Remover o aviso de rascunho e propagar para `MODELOS.md`
