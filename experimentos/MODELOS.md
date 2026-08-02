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

> **Revisão de 2026-08-01.** O levantamento anterior era de julho e a área anda
> rápido: apareceram **modelos especializados em documento** que não existiam na
> lista, e a escada não tinha piso — começava em 3,3 GB. Critério do projeto
> confirmado nesta revisão: **apenas peso aberto**, licença indiferente; nenhum
> serviço pago por chamada.

| # | Modelo | Origem | Tam. | Pergunta que só ele responde |
|---|---|---|---|---|
| 0 | `minicpm-v4.6:1b` | OpenBMB | **1,6 GB** | **o menor da escada** — piso do envelope mínimo |
| 1 | `qwen3-vl:2b` | Alibaba | 1,9 GB | **denominador comum**, e o menor da família de referência |
| 2 | `glm-ocr` | Zhipu | 1,6–2,2 GB | **especializado em documento**, e minúsculo |
| 3 | `deepseek-ocr:3b` | DeepSeek | 6,7 GB | **compressão óptica de contexto** — abordagem distinta das demais |
| 4 | `minicpm-v4.5:8b` | OpenBMB | ~5,5 GB | codificador visual diferente **sobre outra base de linguagem** |
| 5 | `qwen3-vl:8b` | Alibaba | 6,1 GB | **efeito do tamanho** na família de referência, resto constante |
| 6 | `gemma4:12b` | Google | ~8 GB | **família independente**, e multimodal nas duas rotas |
| 7 | `qwen3-vl:30b` | Alibaba | 20 GB | **teto de capacidade**: existe para falhar e marcar o limite |

### O que mudou, e por quê

**Entrou o degrau 0.** A escada anterior começava em 3,3 GB e não tinha piso: o
menor modelo já era grande demais para uma comparação que quer descobrir onde a
qualidade quebra.

> A expectativa era que ele passasse a usar a placa de 2 GB. **A medição refutou**
> — a causa é a arquitetura da placa, não o tamanho do modelo. Ver a retificação
> na alocação por envelope, adiante.

**Entraram dois especializados em documento.** A escada anterior tinha só modelos
generalistas, e essa era a lacuna mais criticável: comparar generalistas entre si
não responde se um especializado resolveria melhor. `glm-ocr` e `deepseek-ocr`
existem para essa pergunta.

**`deepseek-ocr` deixa de ser descarte e vira degrau.** Ele havia sido excluído
por benchmark de terceiro — que relatava arquivos vazios com sucesso reportado. O
projeto **sabe diagnosticar exatamente essa patologia** (é a do ADR-0018), e
descartar por fonte externa o que se sabe medir é fraqueza metodológica, não
economia. Se ele falhar aqui, será por medição própria.

**A abordagem dele é distinta das demais**, e isso vale mais que a reputação:
comprime o contexto visual em ordens de grandeza menos tokens. Como o gargalo
medido neste projeto é justamente orçamento de tokens, é a hipótese mais
diferente que a escada tem.

### Por que cada um está aqui

**Degrau 0 — o piso que faltava.** A escada anterior começava em 3,3 GB e não
tinha piso. Ele é o menor modelo de visão viável, e serve para responder até onde
a qualidade se sustenta quando o orçamento é mínimo — em qualquer máquina, não só
na de referência.

**Degrau 1 — o denominador comum, agora em par.** `qwen3-vl:2b` e `qwen3-vl:4b`
rodam nas cinco máquinas. Além de amarrar a comparação entre elas, o par mede **o
efeito do tamanho dentro da mesma família** — mesma origem, geração e quantização,
só o tamanho muda. É o experimento mais limpo da escada, e sai de graça.

**Degrau 2 — especializado em documento, e minúsculo.** Primeiro colocado no
OmniDocBench V1.5, com foco declarado em tabela complexa e fórmula. Responde a
pergunta que nenhum generalista responde: *um modelo feito para documento resolve
melhor que um modelo grande genérico?* E cabe em 1,6 GB, o que torna a pergunta
ainda mais interessante.

**Degrau 3 — abordagem estruturalmente diferente.** Comprime o contexto visual em
7 a 20× menos tokens. Como o gargalo medido neste projeto é **orçamento de
tokens** (ADR-0015, ADR-0018), é a hipótese mais distinta que a escada tem — não
"mais um modelo", e sim outra ideia de como resolver.

**Degrau 4 — codificador visual sobre outra base.** Isola a variável *codificador
visual* mantendo o resto comparável, que é leitura mais limpa que trocar tudo de
uma vez.

**Degrau 5 — o efeito do tamanho, continuado.** Fecha a curva da família de
referência: 2B → 4B → 8B, com todo o resto constante.

**Degrau 6 — a única família verdadeiramente independente.** Os demais degraus
compartilham origem ou base; este não. E por ser multimodal, permite comparar **a
mesma família lendo texto e lendo imagem**, isolando a diferença entre as duas
rotas sem trocar de fabricante junto. Entra como **controle de independência**,
não como candidato a vencedor.

**Degrau 7 — existe para falhar.** Escada que só sobe enquanto funciona não revela
o teto, e o teto é o que orienta a decisão de infraestrutura.

### Cinco origens, e por que isso importa

Alibaba · OpenBMB · Zhipu · DeepSeek · Google. A escada anterior tinha três, e a
primeira versão de todas tinha **uma** — nove modelos da mesma família, erro
registrado adiante.

Concentração de origem é risco concreto: se a família dominante fosse ruim neste
documento, a conclusão registrada seria *"modelos abertos não servem para tabela"*
quando o correto seria *"aquela família não serve"*.

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
| 1 | `qwen3:1.7b` | Alibaba | 1,4 GB | **piso** da rota de texto |
| 2 | `qwen3:4b` | Alibaba | 2,5 GB | **denominador comum** com a máquina de referência |
| 3 | `qwen3:8b` | Alibaba | 5,2 GB | **efeito do tamanho**, com todo o resto constante |
| 4 | `gemma4:12b` | Google | ~8 GB | **família independente**, e a mesma das duas rotas |
| 5 | `qwen3:14b` | Alibaba | 9,3 GB | limite prático do envelope de 12 GB |
| 6 | `qwen3:30b` | Alibaba | 19 GB | **teto**: existe para falhar |

### Por que cada um está aqui

**Degrau 1 — o piso.** Já instalado na máquina de referência, e o menor da rota
de texto.

**Degrau 2** — o denominador comum, comparável entre as cinco máquinas.

**Degraus 1 → 2 → 3: o experimento mais limpo da escada.** Mesma família, mesma
geração, mesmo treinamento; só o tamanho muda, em três pontos. Qualquer diferença
é atribuível ao tamanho e a mais nada — é o que responde *"modelo maior lê
melhor?"*, a pergunta que sustenta o dimensionamento.

**Degrau 4 — controle de independência.** Os demais são a mesma família. Sem uma
origem externa, resultado ruim seria indistinguível de "esta família é ruim". E
por ser multimodal, permite comparar **a mesma família lendo texto e lendo
imagem** — isolando a diferença entre as rotas sem trocar de fabricante junto.

**Degraus 5 e 6** — a escada de capacidade, até falhar.

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

**A revisão de 2026-08-01 levou a cinco** — Alibaba, OpenBMB, Zhipu, DeepSeek e
Google — e acrescentou um segundo eixo de diversidade que a regra não previa:
**abordagem**, não só origem. Generalista, especializado em documento e compressão
de contexto são três respostas diferentes ao mesmo problema, e comparar só
generalistas entre si deixaria a pergunta *"um especializado resolveria melhor?"*
sem resposta.

Vale para o dimensionamento também: recomendar servidor com base em uma família só
amarra a decisão a um fornecedor.

## Descartados, e por quê

**`granite3.2-vision` (2B)** — posicionado para documento, mas um benchmark
independente o desqualificou: saídas malformadas ou com tabelas erradas.

**`llava:7b`** — OCRBench 536 contra 852 e ~888 dos incluídos. Ver acima.

**Modelos de 32B+** — não cabem no maior envelope disponível com contexto
utilizável.

> **Descarte por fonte externa é provisório, não definitivo.** Nenhum destes foi
> medido aqui. Servem para escolher o que testar primeiro, não para concluir — e
> se sobrar tempo, medir o `granite3.2-vision` tem valor justamente por ser
> barato e por sabermos diagnosticar a falha que lhe atribuem.

### Reintegrado: `deepseek-ocr` (3B)

**Estava nesta lista e saiu dela em 2026-08-01.** O motivo do descarte era gerar
arquivos vazios reportando sucesso — que é **exatamente a patologia do ADR-0018**,
a que custou uma sessão inteira de investigação neste projeto.

E aí está a inversão: descartar por fonte externa aquilo que este projeto **sabe
diagnosticar** é fraqueza metodológica, não economia. A instrumentação do canal de
raciocínio, acrescentada nesta sessão, detecta precisamente esse modo de falha —
e já provou o valor ao recuperar uma extração perfeita que vinha sendo descartada
como resposta vazia.

Ele entra como degrau 3 da escada de visão, com uma justificativa que nenhum outro
tem: **comprime o contexto visual em 7 a 20× menos tokens**. Como o gargalo medido
aqui é orçamento de tokens, é a abordagem mais distinta do conjunto.

Se falhar, será por medição própria — e o resultado terá valor, porque confirmaria
ou refutaria um benchmark de terceiro com instrumentação que aquele benchmark não
tinha.

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

> ### ➜ A alocação vive em [`ALOCACAO-POR-MAQUINA.md`](ALOCACAO-POR-MAQUINA.md)
>
> **Este documento define a escada; aquele define quem roda o quê.** A tabela que
> ficava aqui foi movida, e não duplicada: ela existia em três lugares — aqui, no
> instalador e em `parser.cli` — e os três divergiram. `gemma4:12b` estava alocado
> a partir de 12 GB por um tamanho errado (~8 GB documentado, **7,6 GB** real), e o
> instalador ficou com 8 dos 13 modelos.
>
> **Aquele documento é rascunho** até as seis máquinas relatarem placa, memória e a
> divisão real medida. Enquanto isso, nenhuma alocação está fechada.

O princípio permanece: cada modelo roda na **menor máquina que o comporta**; quando
couber em mais de uma, roda também na maior — comparar o mesmo modelo em envelopes
distintos é o que responde *"mais capacidade ajuda?"*.

> ### ⚠ RETIFICAÇÃO (2026-08-02) — a placa é usável, e o modelo não precisa caber nela
>
> Duas afirmações desta seção estavam erradas, e as duas foram corrigidas por
> medição.
>
> **"A placa fica com 0 MiB em uso" — falso.** Forçando o descarregamento total, o
> modelo vai a **100% na placa** e roda a **17,1 tokens/s contra 17,5** em
> processador. A placa **é usável**; o que ela não é, é mais rápida. A causa
> continua sendo a capacidade de computação (6.1, de 2017), não o tamanho do
> modelo — mas a conclusão correta é *"usá-la não compensa"*, que é afirmação sobre
> a placa, não sobre o software.
>
> **"Modelo precisa caber na placa" — falso.** O servidor **reparte sozinho**:
> carrega na placa o que couber e deixa o resto na memória do sistema. Medido em
> 02/08 com `/api/ps`: `qwen3:4b` ocupa 3,28 GB, dos quais **0,54 GB (16%) na placa**
> e 2,75 GB na memória do sistema. **O modelo é maior que a placa inteira e roda.**
>
> Isso muda o critério de alocação: memória de vídeo determina **a fração
> acelerada**, não se o modelo executa. Por isso a alocação passou a ter dois
> conjuntos — o que cabe na placa e o que cabe somando a memória do sistema.
>
> A causa é a **capacidade de computação da placa (6.1, de 2017)**, abaixo do que
> o servidor exige para descarregar — não o tamanho do modelo.
>
> Este envelope é, portanto, **execução em processador**, e assim deve ser
> declarado. Continua sendo o piso da curva, com uma descontinuidade honesta em
> relação aos demais em vez de gradação fingida. Ver ADR-0014.

**O denominador comum é um par**, não um modelo: `qwen3-vl:2b` **e**
`qwen3-vl:4b`. Além de amarrar a comparação entre as cinco máquinas, o par mede o
efeito do tamanho dentro da mesma família — mesma origem, geração e quantização,
só o tamanho muda. Custa o dobro de tempo no denominador e entrega um experimento
limpo de graça.

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
