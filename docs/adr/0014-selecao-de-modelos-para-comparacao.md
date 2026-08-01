# ADR-0014 — Seleção de modelos: critérios e trade-offs

**Status:** aceito, **com revisão de 2026-07-31 (envelopes reais)** · **Data:** 2026-07-31

> **Revisão.** A versão original supunha dois envelopes: ~2 GB e "12 GB". As
> máquinas disponíveis são **quatro**, com capacidades distintas — e uma delas,
> de 6 GB, não estava prevista. A alocação das escadas foi refeita abaixo.

## Contexto

A comparação entre estratégias exige decidir **quais** modelos entram. A decisão
tem custo real: cada modelo consome espaço em disco, tempo de execução em máquina
de terceiro e, sobretudo, ocupa uma vaga que outro modelo poderia usar melhor.

O ambiente-alvo é modesto (~2 GB de memória de vídeo). Máquinas com mais
capacidade abrem uma classe que ali não roda, e a pergunta que orienta a decisão
de infraestrutura é direta: **mais capacidade melhora o resultado, ou satura?**

Errar essa resposta custa dinheiro nas duas direções — servidor grande demais
desperdiça, pequeno demais entrega um sistema que não roda.

## Os quatro envelopes

| Envelope | Papel na escada | O que roda |
|---|---|---|
| **2 GB** (processador) | **piso da curva** | denominador comum, e as rotas determinísticas |
| **6 GB** | degrau baixo | modelos de 4B e 7-8B |
| **8 GB** | degrau baixo, **redundante de propósito** | idem, com folga maior |
| **12 GB** | degrau médio | até 12-14B |
| **16 GB** | teto | 14B com folga; 24-30B quantizado, apertado |

**A faixa de 6-8 GB é a mais informativa da escada, e quase ficou de fora.** Ela
ocupa o vão entre "não roda nada" e "roda quase tudo" — que é onde a curva
custo × qualidade deve dobrar. Uma escada 2 → 12 → 16 mediria os extremos e
perderia o joelho.

**Por que dois envelopes vizinhos, e não um.** Duas razões, e a segunda vale mais
que a primeira:

1. **Redundância de disponibilidade.** São máquinas de terceiros; se uma não
   rodar a tempo, o degrau não desaparece da curva.
2. **Resolução onde a curva dobra.** 6 e 8 GB são a região de transição. Dois
   pontos ali distinguem uma subida suave de um degrau abrupto — distinção que um
   ponto só não sustenta.

> **Limitação declarada:** máquinas vizinhas em memória podem ter placas de
> **gerações diferentes**, e aí a diferença entre elas não é só de memória.
> Registrar geração e versão de driver junto do resultado; sem isso, a
> comparação entre 6 e 8 GB confundiria duas variáveis.

### O piso não é descartável

A máquina de 2 GB roda em processador, e uma página pela rota de visão leva
**77 minutos** ali (medido, sem limite de cliente). É lento demais para a bateria
completa — mas isso a torna o **ponto extremo da curva**, não um estorvo.

A pergunta Q2 do protocolo (ADR-0020) é *"mais capacidade melhora ou satura?"*.
Uma curva 6 → 12 → 16 sem o ponto de 2 GB perde justamente o extremo onde a coisa
quebra. E "que qualidade se consegue sem placa de vídeo" é pergunta legítima para
quem decide infraestrutura, raramente respondida porque a literatura mede em
hardware de centro de dados.

**O que o piso executa:** o **denominador comum** — o modelo que as quatro
máquinas compartilham, sob as mesmas hipóteses. Não a bateria inteira, que ali
custaria semanas.

## O erro que motivou este registro

A primeira lista tinha **nove modelos da mesma família**. Não foi decisão: foi
consequência de seguir a citação mais frequente nos benchmarks em vez de procurar
alternativas.

O risco é concreto. Se aquela família tivesse desempenho ruim no documento-caso, a
conclusão registrada seria *"modelos abertos não servem para tabela"*, quando o
correto seria *"aquela família não serve"*. A diferença muda a recomendação de
infraestrutura e amarra a decisão a um fornecedor.

## Critérios de inclusão

Um modelo entra se, e só se, responde a uma pergunta que os outros não respondem.
Quatro critérios, aplicados nesta ordem:

**1. Cabe no envelope.** Quatro envelopes: 2, 6, 12 e 16 GB. Cada modelo roda na
**menor máquina que o comporta** — e, quando couber em mais de uma, também numa
maior, porque comparar o *mesmo* modelo em envelopes diferentes é o que responde
Q2. Modelo que não cabe em nenhuma só entra como **teto declarado** — para falhar
e marcar o limite.

**2. Isola uma variável.** Tamanho, codificador visual, família de origem ou
geração. Modelo que varia tudo ao mesmo tempo não permite atribuir causa.

**3. Tem evidência pública na tarefa certa.** Desempenho em compreensão de
documento e reconhecimento de texto — não em capacidade geral. Um modelo forte em
raciocínio e fraco em documento não serve aqui.

**4. Diversidade de origem.** Ao menos uma família independente por escada. Sem
isso, resultado ruim é indistinguível de "esta família é ruim".

## Escada de visão

| # | Modelo | Origem | Tam. | OCRBench | DocVQA | Variável que isola |
|---|---|---|---|---|---|---|
| 1 | `qwen3-vl:4b` | Alibaba | 3,3 GB | — | — | denominador comum entre máquinas |
| 2 | `minicpm-v:8b` | OpenBMB | 5,5 GB | **852** | — | codificador visual, base de linguagem constante |
| 3 | `qwen2.5vl:7b` | Alibaba | ~6 GB | ~888 | **96,4** | teto de qualidade da classe |
| 4 | `gemma3:12b` | Google | 8,1 GB | — | 82,3 | família independente + multimodal |
| 5 | `qwen3-vl:30b` | Alibaba | 20 GB | — | — | teto de capacidade (falha esperada) |

**O degrau 2 merece destaque, e não por reputação.** Ele usa a *mesma base de
linguagem* da família do degrau 1, com codificador visual diferente. Isso isola a
variável "codificador visual" mantendo o resto constante — comparação mais limpa
que trocar tudo. E produz **~640 tokens** para uma imagem grande, contra ~2164 que
a página custa hoje: como a causa medida das respostas vazias foi **corte por
limite de tokens** (ADR-0015), gerar menos tokens ataca a raiz, não o sintoma.

**O degrau 3 é o teto de qualidade.** 96,4 em DocVQA é quase o humano (98,1). Se
nem ele resolver este documento, a conclusão sobre a rota por modelo passa a ser
forte em vez de circunstancial.

## Escada de texto

| # | Modelo | Origem | Tam. | Variável que isola |
|---|---|---|---|---|
| 1 | `qwen3:4b` | Alibaba | 2,5 GB | denominador comum |
| 2 | `qwen3:8b` | Alibaba | 5,2 GB | **tamanho, com todo o resto constante** |
| 3 | `gemma3:12b` | Google | 8,1 GB | família independente; mesma família nas duas rotas |
| 4 | `qwen3:14b` | Alibaba | 9,3 GB | limite prático do envelope de 12 GB |
| 5 | `qwen3:30b` | Alibaba | 19 GB | teto (falha esperada) |

O degrau 2 é o experimento mais limpo das duas escadas: mesma família, mesma
geração, só o tamanho muda. Responde diretamente *"modelo maior lê melhor?"*.

O degrau 3 aparece nas duas escadas de propósito — sendo multimodal, permite
comparar **a mesma família lendo texto e lendo imagem**, isolando a diferença entre
as rotas sem trocar de fabricante junto.

## Descartados, com o motivo

| Modelo | Motivo |
|---|---|
| `llava:7b` | **OCRBench 536** contra 852 e ~888 dos incluídos; 82 pontos em compreensão de documento. Estava na lista como "referência histórica" — curiosidade não é hipótese |
| `llama3.1:8b` | Cogitado por popularidade. Não há benchmark de extração estruturada que o coloque à frente nesta tarefa; os comparativos mostram vantagem da família 1 em raciocínio e ferramentas. **Popularidade não é evidência para esta tarefa** |
| `granite3.2-vision` | Desqualificado em benchmark independente: saídas malformadas |
| `deepseek-ocr` | Desqualificado por gerar arquivos vazios **reportando sucesso e tempo baixo** — exatamente a patologia que custou uma sessão de investigação aqui |
| 32B+ | Não cabem nem no envelope de 16 GB com contexto utilizável |

## Alocação por envelope

Cada modelo na menor máquina que o comporta. Os que couberem em mais de uma
rodam também na maior — é a comparação do mesmo modelo em hardware diferente que
responde Q2 (ADR-0020), e ela não custa vaga nova.

| Envelope | Escada de visão | Escada de texto |
|---|---|---|
| 2 GB (processador) | `qwen3-vl:4b` (denominador) | `qwen3:4b` (denominador) |
| 6 GB | + `minicpm-v:8b`, `qwen2.5vl:7b` | + `qwen3:8b` |
| 8 GB | os mesmos do degrau de 6 GB | os mesmos do degrau de 6 GB |
| 12 GB | + `gemma3:12b` | + `gemma3:12b`, `qwen3:14b` |
| 16 GB | + `qwen3-vl:30b` (teto, falha esperada) | + `qwen3:30b` (teto, falha esperada) |

O degrau de 8 GB roda **o mesmo conjunto** do de 6 GB, e isso é deliberado: com
modelos idênticos, a diferença medida é atribuível à máquina. Rodar modelos
diferentes ali responderia outra pergunta e perderia esta.

**O denominador comum é o que amarra a escada.** Sem um modelo que rode nas
quatro, as máquinas produziriam resultados sem ponto de contato, e a diferença
entre elas seria indistinguível da diferença entre os modelos que cada uma roda.

Os dois últimos descartes vêm de fonte externa, não de medição própria — e isso
fica declarado. Se houver tempo sobrando, medir o `deepseek-ocr` tem valor
justamente por já sabermos diagnosticar a falha dele.

## Consequências

- A pergunta "mais capacidade ajuda?" passa a ter resposta **medida**, com o teto
  de cada máquina documentado — incluindo **como** falhou.
- Cada degrau isola uma variável, então o resultado é atribuível a uma causa e não
  a um conjunto de mudanças simultâneas.
- Nenhuma conclusão fica amarrada a um fabricante: há origem independente nas duas
  escadas.
- **Custo assumido:** ~45 GB de download nas máquinas maiores, e horas de execução.
  É o preço de uma comparação que se sustenta.
- **Limite declarado:** os números públicos citados aqui **não foram verificados
  neste projeto**. Servem para escolher o que testar, não para concluir. A medição
  local é que decide — e pode contradizê-los.
- O conjunto de máquinas é pequeno e não é amostra estatística. Os resultados
  descrevem aquelas máquinas; extrapolar é hipótese, não conclusão.
- **As placas são de fabricantes diferentes.** Nada no procedimento pode depender
  de ferramenta de um fabricante só — vale para detecção de memória, de contenção
  e de versão de driver (ADR-0019).
- **Envelope não é o mesmo que desempenho.** Caber na memória diz que o modelo
  roda, não quanto tempo leva. A máquina de 2 GB executa em processador e é
  ordens de grandeza mais lenta — por isso recebe só o denominador comum.

## Fontes

- [Qwen2.5-VL Technical Report](https://arxiv.org/pdf/2502.13923) — DocVQA 96,4
- [Gemma 3 Technical Report](https://arxiv.org/html/2503.19786v1) — DocVQA por tamanho
- [MiniCPM-V: A GPT-4V Level MLLM on Your Phone](https://arxiv.org/pdf/2408.01800) — OCRBench 852
- [OCRBench v2](https://arxiv.org/html/2501.00321v2) — metodologia e limites do benchmark
- [Local Vision-Language OCR Benchmark](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/) — desqualificações
