# ADR-0015 — Limite de saída do modelo: nenhum padrão embutido

**Status:** aceito · **Data:** 2026-07-31

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

## Decisão

**O teto de saída é declarável e não tem padrão embutido no código.**

Um valor fixo no código seria número mágico sem procedência, contra o ADR-0008. E
o valor certo depende de três coisas que variam: quantos itens a página tem,
quanto o modelo gasta raciocinando, e qual modelo é.

**Resposta cortada é diagnosticada como tal, não como vazia.** São exceções e
tipos de falha distintos — `resposta-cortada` × `resposta-vazia` × `sem-estrutura`.
A distinção decide onde procurar: vazio manda investigar modelo ou prompt; corte
manda aumentar o limite. Confundi-los custou duas hipóteses erradas.

**`done_reason` é sempre registrado com o resultado.** Foi ele, e só ele, que
revelou a causa.

## Consequência de desenho

**Pedir uma página inteira de uma vez a um modelo pequeno tem custo alto e
frágil.** Ou se eleva muito o teto — e a resposta leva ~1000 s por página — ou se
pede menos itens por chamada, multiplicando o número de chamadas.

Isso reforça a decisão do ADR-0003: a rota determinística é o caminho padrão. A
mesma página é extraída em **0,2 s** com 100% de acurácia contra o conjunto de
reserva, contra ~1000 s da rota por modelo.

A rota por modelo continua valendo por outra razão: documentos que a rota
determinística não alcança. O que a medição fecha é a expectativa de que ela seja
alternativa geral — não é, nesta classe de hardware.

## Consequências

- O valor do teto vai no perfil, medido por documento e modelo, com registro.
- Resposta vazia deixa de ser mistério: o tipo da falha aponta onde procurar.
- Fica registrado que **modelo pequeno lê a página corretamente** — a limitação é
  de orçamento de saída, não de compreensão. Distinção que muda a conclusão sobre
  a viabilidade da rota.
- Custo: mais um parâmetro por rota no perfil. Aceito — a alternativa é um número
  mágico que ninguém consegue questionar.
