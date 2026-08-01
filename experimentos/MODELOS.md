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

Cada degrau precisa responder a uma pergunta que os outros não respondem. Modelo
que não isola variável nova não entra, por melhor que seja sua reputação.

| # | Modelo | Origem | Tam. | OCRBench | DocVQA | Pergunta que só ele responde |
|---|---|---|---|---|---|---|
| 1 | `qwen3-vl:4b` | Alibaba | 3,3 GB | — | — | **denominador comum**: é o que roda na máquina de referência |
| 2 | `minicpm-v:8b` | OpenBMB | 5,5 GB | **852** | — | codificador visual diferente **sobre a mesma base de linguagem** |
| 3 | `qwen2.5vl:7b` | Alibaba | ~6 GB | ~888 | **96,4** | o melhor medido da classe: define o **teto de qualidade** alcançável |
| 4 | `gemma3:12b` | Google | 8,1 GB | — | 82,3 | **família independente**, e multimodal: mesma família nas duas rotas |
| 5 | `qwen3-vl:30b` | Alibaba | 20 GB | — | — | **teto de capacidade**: existe para falhar e marcar o limite da máquina |

### Por que cada um está aqui

**Degrau 1 — o único comparável com a máquina de referência.** Sem ele, nenhuma
comparação entre as máquinas seria legítima (ADR-0013).

**Degrau 2 — o mais interessante tecnicamente, e não por reputação.** Duas razões
medidas:

1. Ele é construído sobre a **mesma base de linguagem** da família do degrau 1
   (Qwen2-7B), com codificador visual diferente (SigLip-400M). Isso isola a
   variável *codificador visual* mantendo a base constante — comparação mais
   limpa que trocar tudo de uma vez.
2. Produz **~640 tokens** para uma imagem grande, contra os ~2164 que a página
   custa hoje. Como a causa medida das respostas vazias foi **corte por limite de
   tokens**, gerar menos tokens ataca a raiz do problema, não o sintoma.

**Degrau 3 — o teto de qualidade.** 96,4 em DocVQA é quase o desempenho humano
(98,1). Serve de referência superior: se nem ele resolver este documento, a
conclusão sobre a rota por modelo é forte, não circunstancial.

**Degrau 4 — a única família verdadeiramente independente.** Os degraus 1 a 3
compartilham base de linguagem; este não. E por ser multimodal, permite comparar
**a mesma família lendo texto e lendo imagem**, isolando a diferença entre as duas
rotas sem trocar de fabricante junto.

Seu DocVQA (82,3) é claramente inferior ao do degrau 3 — e é por isso que ele
entra como **controle de independência**, não como candidato a vencedor.

**Degrau 5 — existe para falhar.** Escada que só sobe enquanto funciona não revela
o teto, e o teto é o que orienta a decisão de infraestrutura.

### Descartado depois de verificar: `llava:7b`

Estava na versão anterior desta escada como "referência histórica" — justificativa
fraca, e os números a derrubam: **OCRBench 536** contra 852 e ~888 dos demais, com
apenas 82 pontos em compreensão de documento, que é exatamente a nossa tarefa.

Custaria 4,7 GB de download e horas de execução em cada máquina para produzir um
resultado previsivelmente ruim. "Referência histórica" não é pergunta científica;
é curiosidade — e curiosidade não justifica ocupar um degrau.

## Escada de texto (o modelo recebe o texto já extraído)

| # | Modelo | Origem | Tam. | Pergunta que só ele responde |
|---|---|---|---|---|
| 1 | `qwen3:4b` | Alibaba | 2,5 GB | **denominador comum** com a máquina de referência |
| 2 | `qwen3:8b` | Alibaba | 5,2 GB | **efeito do tamanho**, com todo o resto constante |
| 3 | `gemma3:12b` | Google | 8,1 GB | **família independente**, e a mesma das duas rotas |
| 4 | `qwen3:14b` | Alibaba | 9,3 GB | limite prático dos 12 GB |
| 5 | `qwen3:30b` | Alibaba | 19 GB | **teto**: existe para falhar |

### Por que cada um está aqui

**Degrau 1** — único comparável com a máquina de referência.

**Degrau 2 — o experimento mais limpo da escada.** Mesma família, mesma geração,
mesmo treinamento; só o tamanho muda. Qualquer diferença de resultado é atribuível
ao tamanho, e não a mais nada. É o degrau que responde diretamente *"modelo maior
lê melhor?"* — a pergunta que sustenta o dimensionamento.

**Degrau 3 — controle de independência.** Os degraus 1, 2, 4 e 5 são a mesma
família. Sem uma origem externa, um resultado ruim seria indistinguível de "esta
família é ruim". Ele também é multimodal, o que permite comparar **a mesma família
lendo texto e lendo imagem** — isolando a diferença entre as rotas sem trocar de
fabricante junto.

**Degraus 4 e 5** — a escada de capacidade, até falhar.

### Uma alternativa considerada e não incluída: `llama3.1:8b`

Foi cogitada como "a família mais usada em produção". **A justificativa não
resistiu à verificação:** não encontrei benchmark de extração estruturada que a
coloque à frente das alternativas nesta tarefa. O que os comparativos mostram é
vantagem da família do degrau 1 em raciocínio e uso de ferramentas.

Popularidade não é evidência para *esta* tarefa. Se o degrau 3 mostrar que a
escolha de família importa muito, aí sim vale acrescentar uma quarta origem — mas
com hipótese, não por prestígio.

### Por que a rota de texto importa

Recebe ~649 tokens de entrada contra ~2164 da imagem, na mesma página. Se produzir
resultado comparável, é a rota preferível por custo — e essa comparação nunca foi
feita neste projeto. É a lacuna que a bateria atual está fechando.

## Viés de fabricante: um erro corrigido, e a regra que fica

A primeira versão desta escada tinha **nove degraus da mesma família**. Não foi
decisão — foi consequência de pesquisar mal: os benchmarks citam muito uma família,
e eu segui a citação em vez de procurar as alternativas.

O risco é concreto e vale enunciar: se aquela família tivesse desempenho ruim neste
documento, a conclusão registrada seria *"modelos abertos não servem para tabela"*.
A conclusão correta seria *"aquela família não serve"* — e a diferença entre as duas
muda a decisão de infraestrutura.

**Regra que fica: escada de comparação precisa de pelo menos três origens
distintas.** Uma família pode ter viés de treinamento, licença restritiva, ou
simplesmente ir mal num tipo de documento. Três origens tornam o resultado
atribuível à abordagem, não ao fabricante.

Vale para o dimensionamento também: recomendar servidor com base em uma família só
amarra a decisão a um fornecedor.

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
| **contexto** (`num_ctx`) | **declarar sempre** | o padrão do servidor é **4096** e limita entrada **mais** saída; uma imagem consome ~2200 só de entrada. Foi a causa real das respostas vazias — ver a nota abaixo |
| `num_predict` (teto de saída) | **16384** | necessário, mas **não suficiente**: sozinho não impede o corte, porque o limite que corta é o contexto |
| `dpi` da imagem | **150** | ADR-0003 — compromisso entre legibilidade e custo |
| degrau de saída | **fixado, não livre** | ADR-0013 — descer livremente faz cada máquina medir uma restrição diferente |
| medições simultâneas | **nunca** | duas concorrentes inflam o tempo das duas, e aqui o tempo é o resultado |
| `done_reason` | **sempre registrado** | `stop` = terminou; `length` = cortado. Foi ele que revelou a causa do vazio |

> ### ⚠ O contexto é o parâmetro que faltava — não repita este erro
>
> Durante uma sessão inteira, o projeto acreditou que o teto de **saída** era o
> limite atuante. Não era. Elevá-lo para 16384 não removeu o corte: as respostas
> continuaram parando em ~1900 tokens.
>
> A prova é aritmética. Somando **entrada + saída**, quatro casos com prompts de
> tamanhos diferentes pararam na mesma soma exata:
>
> | Caso | entrada + saída | soma | motivo |
> |---|---|---|---|
> | coube | 2184 + 1581 | 3765 | `stop` |
> | cortado | 2175 + 1921 | **4096** | `length` |
> | cortado | 2227 + 1869 | **4096** | `length` |
> | cortado | 2233 + 1863 | **4096** | `length` |
>
> **Regra que fica: nunca confiar em padrão de servidor para parâmetro que decide
> resultado.** Um padrão não declarado é número mágico com dono externo.
>
> **Sempre registrar tokens de entrada e de saída, e verificar a soma.** Eles
> vinham em toda resposta e eram descartados; foi a soma que revelou a causa.

> **Sobre o raciocínio: não há como desligá-lo** nesta combinação de servidor e
> modelo. As duas formas foram medidas — `think: false` gerou 4043 caracteres,
> `/no_think` gerou **6254** e piorou.
>
> Ele **consome** orçamento, mas chamá-lo de "o gargalo" atribuía a ele um efeito
> que era do contexto não declarado. Com contexto suficiente, ele passa a ser
> custo, não impedimento.

## O que cada máquina roda

Quatro envelopes, de fabricantes diferentes. Cada modelo roda na **menor máquina
que o comporta**; quando couber em mais de uma, roda também na maior — comparar o
mesmo modelo em envelopes distintos é o que responde "mais capacidade ajuda?".

| Envelope | Escada de visão | Escada de texto |
|---|---|---|
| **2 GB** (processador) | `qwen3-vl:4b` | `qwen3:4b` |
| **6 GB** | + `minicpm-v:8b`, `qwen2.5vl:7b` | + `qwen3:8b` |
| **8 GB** | os mesmos do degrau de 6 GB | os mesmos do degrau de 6 GB |
| **12 GB** | + `gemma3:12b` | + `gemma3:12b`, `qwen3:14b` |
| **16 GB** | + `qwen3-vl:30b` (teto) | + `qwen3:30b` (teto) |

**A faixa de 6-8 GB é a mais informativa**, e quase ficou de fora do
levantamento: ocupa o vão entre "não roda quase nada" e "roda quase tudo", que é
onde a curva custo × qualidade deve dobrar. Uma escada 2 → 12 → 16 mediria os
extremos e perderia o joelho.

Os dois envelopes vizinhos rodam **o mesmo conjunto de modelos**, de propósito:
assim a diferença medida é atribuível à máquina, e não ao que cada uma rodou. E
se uma das duas não estiver disponível a tempo, o degrau continua na curva.

**O piso de 2 GB executa só o denominador comum** — o modelo que as quatro
compartilham. Ali uma página pela rota de visão leva **77 minutos** (medido, sem
limite de cliente), então a bateria inteira custaria semanas. Mas o ponto é
necessário: sem ele a curva perde o extremo onde a coisa quebra, e "que qualidade
se consegue sem placa de vídeo" fica sem resposta.

**Um modelo por vez, do menor ao maior, até falhar.** Dois modelos disputando
memória falham por contenção, não por incapacidade — e isso produziria um teto
falso.

## Fontes

Levantamento de julho de 2026:

- [Qwen2.5-VL Technical Report](https://arxiv.org/pdf/2502.13923)
- [Qwen3-VL Technical Report](https://arxiv.org/pdf/2511.21631)
- [OCRBench v2](https://arxiv.org/html/2501.00321v2)
- [Local Vision-Language OCR Benchmark](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- [Best Open-Weight OCR and Document AI Models 2026](https://presenc.ai/research/best-open-weight-ocr-document-ai-models-2026)
- [Ollama — biblioteca de modelos](https://ollama.com/library/qwen3-vl)
- [Comparação de VLMs auto-hospedados](https://gigagpu.com/self-hosted-vision-language-model-comparison/)
- [Multimodal AI: open-source VLMs 2026](https://www.bentoml.com/blog/multimodal-ai-a-guide-to-open-source-vision-language-models)
- [MiniCPM-V no Ollama](https://ollama.com/library/minicpm-v)
- [Gemma 3 no Ollama](https://ollama.com/library/gemma3)
