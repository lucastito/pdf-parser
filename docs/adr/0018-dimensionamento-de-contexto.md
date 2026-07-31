# ADR-0018 — Dimensionamento de contexto: calcular, nunca herdar o padrão

**Status:** aceito · **Data:** 2026-07-31

## Contexto

Uma sessão inteira de medição concluiu que a rota por modelo de visão *"não
preenche planilha nesta classe de hardware"*. **A conclusão estava errada**, e o
erro custou caro: virou ADR, foi publicada, e teria ido para os scripts das
outras máquinas.

A causa não foi falta de medição — foram cinco medições, uma por vez, com o
motivo de encerramento registrado. Foi **medir bem o parâmetro errado**.

Este ADR registra o achado, o método que falhou, e a regra que impede a
repetição.

## Dois limites, e o projeto declarava um

O servidor expõe dois parâmetros que soam intercambiáveis e não são:

| Parâmetro | Limita | Padrão |
|---|---|---|
| teto de **saída** | quantos tokens o modelo gera | alto |
| **contexto** | entrada **mais** saída, somadas | **4096** |

O projeto declarava só o primeiro. O segundo herdava o padrão do servidor —
invisível na configuração, invisível no resultado, e decisivo.

Numa página renderizada como imagem, a **entrada** consome ~2200 tokens. Com
contexto de 4096, sobram ~1900 para a resposta, e a geração é cortada ali por
mais alto que esteja o teto de saída.

## A medição que provou

Somando entrada e saída de cada chamada — dois números que vinham em **toda**
resposta e eram descartados:

| Caso | entrada + saída | soma | encerramento |
|---|---|---|---|
| 5 itens (coube) | 2184 + 1581 | 3765 | `stop` |
| rota de texto (coube) | 1819 + 5948 | 7767 | `stop` |
| página, com valores | 2227 + 1869 | **4096** | `length` |
| idem, sem raciocínio | 2233 + 1863 | **4096** | `length` |
| idem, outra instrução | 2175 + 1921 | **4096** | `length` |
| controle, teto a 16384 | 2189 + 1907 | **4096** | `length` |

**Quatro casos, com prompts de tamanhos diferentes, parando na mesma soma
exata.** Isso não é comportamento de modelo — é teto sendo atingido.

O caso que funcionou funcionou porque **coube**, não por ser qualitativamente
diferente. E a rota de texto ultrapassou 4096 porque, sem imagem, o servidor
dimensiona o contexto pelo pedido.

Verificação independente: declarando o contexto, o servidor passou a reportar o
valor pedido e o processo cresceu de 3,6 GB para 5,5 GB. O parâmetro é
respeitado; só nunca havia sido enviado.

## Decisão

**O contexto é calculado a cada chamada, a partir de medição, e nunca herdado do
padrão do servidor.**

```
necessário = entrada_medida + saída_esperada + margem
viável     = (memória_livre − peso_do_modelo) / custo_por_token
usar       = min(nativo_do_modelo, viável, necessário)
```

Três decisões embutidas, cada uma com razão:

**`entrada_medida`, não estimada.** É o termo que faltou. O custo de uma imagem
em tokens depende da resolução e do codificador visual — não se adivinha. Uma
chamada barata mede.

**`viável` limita por memória, não por capacidade do modelo.** O limite nativo
quase nunca é o que aperta: um modelo de 4B suporta 256k de contexto, mas 256k
pediria ~45 GB.

**`min` dos três.** Pedir mais contexto do que se precisa custa memória sem
retorno.

### Errar para cima não é seguro — e o erro é assimétrico ao contrário do óbvio

A intuição natural é que errar para cima é inofensivo: no pior caso sobra
espaço. **Não é o caso**, e o modo de falha é o pior dos dois:

| Erro | Consequência | Diagnóstico |
|---|---|---|
| para baixo | corte, resposta vazia | enganoso, mas **detectável** pela soma |
| para cima demais | não cabe → despejo para o processador | **silencioso** |

Um modelo que não cabe na memória não falha: fica ordens de grandeza mais lento,
e o número sai como *"esta máquina é lenta"*. É a contaminação silenciosa do
ADR-0019 — resultado plausível e errado, o modo de falha que este projeto mais
evita.

Daí a regra: **errar para cima até o limite de memória, nunca além dele.** E
quando nem o peso do modelo couber, **falhar alto** em vez de rodar — porque o
tempo medido descreveria a configuração, não a máquina.

### Implementado em `src/parser/contexto.py`

O cálculo é código, não recomendação em documento — 14 testes, escritos antes.
Inclui como regressão o caso que produziu a conclusão errada: entrada de 2227
com o padrão de 4096 não deixa espaço para a resposta, e o cálculo tem de pedir
mais que isso.

### Corolário: a soma é verificada e registrada

Entrada, saída e a soma vão no resultado de toda chamada, e a soma é conferida
contra o contexto declarado. **Soma igual ao contexto é assinatura de corte**, e
o diagnóstico deve dizê-lo — não deixar quem lê descobrir sozinho.

## A curva de memória tem poder preditivo

Medindo o processo em três contextos, com um modelo de visão de 4B:

| Contexto | Memória medida | Previsto pela reta de 2 pontos | Erro |
|---|---|---|---|
| 4096 | 3,6 GB | — | ajuste |
| 16384 | 5,5 GB | — | ajuste |
| 32768 | **8,0 GB** | 8,03 GB | **0,4%** |

A reta foi ajustada com os dois primeiros pontos e **previu o terceiro** — que é
a diferença entre curva ajustada e curva com poder preditivo. Só a segunda
sustenta dimensionar máquina que ainda não se tem.

Projeção que isso autoriza: **contexto de 64k pede ~13 GB e não cabe numa placa
de 12 GB**, mesmo com modelo pequeno.

> **Limites declarados:** a medida é do **processo inteiro** (cache de atenção,
> buffers e codificador visual), não do cache isolado que a literatura calcula. E
> vale para **um** modelo — a inclinação depende da arquitetura. Generalizar
> exige medir outros, e é o que a instrumentação do experimento vai levantar.

## O erro de método, e por que ele fica registrado

Três falhas encadeadas, todas evitáveis:

**1. Aceitar que o sintoma sumiu sem conferir o número.** Elevar o teto de saída
"resolveu" um caso e a investigação seguiu. As respostas continuaram cortando em
~1900 tokens com teto declarado de 16384 — contradição visível no dado, não
conferida.

**2. Descartar o que a resposta já entregava.** Entrada e saída vinham em cada
chamada. Foi a **soma** delas que revelou a causa. O dado estava ali o tempo
todo.

**3. Confiar em padrão de servidor.** Um padrão não declarado é número mágico com
dono externo — contraria o ADR-0008 tanto quanto um número no código, e é pior,
porque nem aparece.

**A contradição foi apontada de fora**, por quem não estava medindo: *"o teto era
16384, por que cortou em 1870?"* Vale registrar que a pergunta certa veio de
alguém sem compromisso com a hipótese em curso.

## Consequências

- **Duas afirmações publicadas foram retificadas**, não apagadas: a de que a rota
  de visão não preenche planilha, e a de que o raciocínio é o gargalo. Quem leu a
  versão anterior precisa encontrar a correção.
- **A conclusão correta sobre esta máquina é outra.** Medido em três contextos, a
  falha muda de natureza:

  | Contexto | Desfecho | Quem parou |
  |---|---|---|
  | 4096 (padrão) | cortado em **exatamente 4096**, 21 min | o servidor |
  | 16384 | **>1 h sem terminar** | o cliente, por tempo |
  | 32768 | **>1 h sem terminar** | o cliente, por tempo |

  Declarar o contexto **não tornou a rota viável nesta máquina** — trocou falha
  rápida e de diagnóstico enganoso por falha lenta e de diagnóstico claro. A
  limitação passa a ser **tempo em processador**, não capacidade: o modelo lê a
  página corretamente, como o caso de 5 itens mostrou.

  Que os dois contextos maiores **não tenham cortado** é a confirmação: se o
  contexto não fosse o limite atuante, os três teriam parado igual.

  Dado bruto em `experimentos/resultados/titoslaptop/contexto-limite.json`.
- As medições da rota de visão precisam ser **refeitas** sob contexto declarado.
  Elas mediram o artefato.
- Os scripts das outras máquinas não configuravam nenhum dos dois parâmetros.
  Teriam medido a mesma parede, com modelos maiores — que consomem **mais**
  contexto por imagem — e produzido conclusão de infraestrutura errada.
- Custo: mais um parâmetro por rota, e uma chamada de medição antes da primeira
  extração. Aceito — a alternativa é herdar em silêncio um limite que decide o
  resultado.
