# ADR-0015 — Limite de saída do modelo: nenhum padrão embutido

**Status:** aceito, **com retificação de 2026-07-31** · **Data:** 2026-07-31

> ## ⚠ Retificação — leia antes do resto
>
> **O parâmetro identificado neste ADR estava errado.** A decisão continua
> válida; o diagnóstico não.
>
> O servidor tem **dois** limites, e este ADR só conhecia um:
>
> | Parâmetro | O que limita | Padrão |
> |---|---|---|
> | teto de **saída** | quantos tokens o modelo gera | sem padrão baixo |
> | **contexto** | entrada **mais** saída, somadas | **4096** |
>
> Elevar o teto de saída para 16384 **não removeu o corte**: as respostas
> continuaram parando em ~1900 tokens. A prova é aritmética — somando entrada e
> saída, quatro casos com prompts de tamanhos diferentes pararam na **mesma soma
> exata de 4096**. A imagem consome ~2200 de entrada; sobrava o resto.
>
> **Consequência 1 — a conclusão "a rota de visão não preenche planilha nesta
> classe de hardware" mede um artefato de configuração, não o modelo.** Ela
> aparece mais abaixo neste documento e está errada.
>
> **Consequência 2 — a conclusão sobre o raciocínio perde peso.** Ele continua
> consumindo orçamento (isso foi medido de forma independente), mas chamá-lo de
> "o gargalo" atribuía a ele um efeito que era do contexto não declarado.
>
> **O que se sabe com o contexto correto:** a chamada **não termina em uma hora**
> em processador — o cliente desiste por tempo, o modelo não é cortado. A
> limitação desta máquina é de **tempo**, não de capacidade.
>
> Detalhe completo e o que fazer: seção 0 de `experimentos/PLANO.md`.

## Contexto

A rota por modelo devolvia **resposta vazia** sem erro algum: servidor responde
`200`, corpo vazio, extrator recebe zero item. Numa execução em lote isso vira
"processado, 0 registros" e passa — a falha muda que este projeto mais evita.

Três hipóteses foram levantadas. Duas caíram na medição, e o registro das três
fica porque hipótese invalidada é resultado: sem ele, a próxima pessoa refaz a
mesma busca, que aqui custou uma sessão inteira.

## Medição

Cinco instruções sobre a mesma página, uma medição por vez:

| Instrução | `done_reason` | Tokens | Resposta |
|---|---|---|---|
| descreva a imagem | `stop` | 689 | 794 caracteres |
| leia a tabela | `length` | 1927 | **vazia** |
| leia com campos | `length` | 1923 | **vazia** |
| leia em JSON | `length` | 1912 | **vazia** |
| leia com guardrails | `length` | 1887 | **vazia** |

O sinal está no motivo do encerramento: `stop` é o modelo terminando; `length` é a
geração sendo **cortada**. Descrever uma página cabe em 689 tokens; enumerar
dezenas de itens não cabe em ~1900, e o corte vem antes de a resposta fechar — por
isso volta vazia, e não parcial.

Elevando o teto para 16384, a mesma chamada devolveu os 31 alimentos da página,
corretos e na ordem, encerrando com `stop`.

### Hipóteses refutadas

**O esquema restringido** — a suspeita era que a gramática de decodificação
tornasse o caminho válido inalcançável. O texto livre, **sem restrição alguma**,
também vinha vazio.

**O canal de raciocínio, como causa isolada** — desligá-lo não mudou os números
(152 contra 152 tokens; 1817 contra 1844). Mas ele **é fator**: com teto de 8192, a
resposta saiu correta e ainda cortada, porque a maior parte do orçamento foi gasta
raciocinando. O raciocínio não causa o vazio; consome o orçamento que o limite
restringe.

**Adendo de 2026-07-31 — não há como desligá-lo.** As duas formas documentadas
foram medidas na mesma página:

| Forma | Raciocínio gerado | Resposta |
|---|---|---|
| `think: false` | 4043 caracteres | 185 caracteres |
| `/no_think` no prompt | **6254 caracteres** | **vazia** |

A segunda forma **piorou**. O raciocínio é inevitável nesta combinação de servidor
e modelo.

> **Retificado:** o parágrafo abaixo dizia que a rota de visão *"não preenche
> planilha nesta classe de hardware"*. **Está errado** — as duas configurações
> rodaram sob contexto padrão de 4096, e a resposta vazia era o corte descrito na
> retificação do topo. Com contexto suficiente, a mesma chamada não é cortada;
> ela simplesmente não termina em uma hora **em processador**.
>
> O que permanece verdadeiro: o raciocínio consome orçamento, e a rota de
> **texto**, no mesmo pedido, gasta zero raciocinando e produz 16767 caracteres
> com 100% de acurácia. A comparação entre as duas rotas continua favorecendo a
> de texto **nesta máquina** — mas por tempo, não por incapacidade.

## Decisão

**Os limites de saída *e de contexto* são declaráveis, e nenhum tem padrão
embutido no código.**

Um valor fixo no código seria número mágico sem procedência, contra o ADR-0008. E
o valor certo depende de coisas que variam: quantos itens a página tem, quanto o
modelo gasta raciocinando, qual modelo é, e — no caso do contexto — **quanto a
entrada consome**, que numa imagem é a maior parte.

**Declarar só o teto de saída não basta**, e foi o erro deste ADR: o contexto
tinha padrão do servidor, invisível, e era ele que cortava.

**Resposta cortada é diagnosticada como tal, não como vazia.** São exceções e
tipos de falha distintos — `resposta-cortada` × `resposta-vazia` × `sem-estrutura`.
A distinção decide onde procurar. Confundi-los custou duas hipóteses erradas.

**`done_reason` é sempre registrado com o resultado.** Foi ele que revelou que
havia corte.

**Os tokens de entrada e de saída são sempre registrados, e a soma verificada
contra o contexto.** Foi a **soma** que revelou *qual* limite cortava — e ela
vinha em toda resposta, descartada. Sem isso, o diagnóstico parou no parâmetro
errado por uma sessão inteira.

## Consequência de desenho

**Pedir uma página inteira de uma vez a um modelo pequeno tem custo alto e
frágil.** Ou se eleva muito o teto — e a resposta leva ~1000 s por página — ou se
pede menos itens por chamada, multiplicando o número de chamadas.

Isso reforça a decisão do ADR-0003: a rota determinística é o caminho padrão. A
mesma página é extraída em **0,2 s** com 100% de acurácia contra o conjunto de
reserva, contra ~1000 s da rota por modelo.

A rota por modelo continua valendo por outra razão: documentos que a rota
determinística não alcança. O que a medição fecha é a expectativa de que ela seja
alternativa geral **em processador** — o custo por página a torna inviável para
volume, e essa parte não muda com configuração.

> **Ressalva de escopo:** "nesta classe de hardware" significa **processador de
> baixo consumo**. Máquinas com placa de vídeo funcional não foram medidas, e é
> justamente para isso que existe o experimento multimáquina (ADR-0013).

## Consequências

- O valor do teto vai no perfil, medido por documento e modelo, com registro.
- Resposta vazia deixa de ser mistério: o tipo da falha aponta onde procurar.
- Fica registrado que **modelo pequeno lê a página corretamente** — a limitação é
  de orçamento de saída, não de compreensão. Distinção que muda a conclusão sobre
  a viabilidade da rota.
- Custo: mais um parâmetro por rota no perfil. Aceito — a alternativa é um número
  mágico que ninguém consegue questionar.
