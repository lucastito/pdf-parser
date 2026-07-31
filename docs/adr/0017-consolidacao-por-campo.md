# ADR-0017 — Consolidação por campo, não escolha de planilha

**Status:** proposto · **Data:** 2026-07-31

> **Proposto, não aceito.** A decisão está tomada; a implementação não começou.
> Registrado agora porque o desenho já influencia o que a fase de preenchimento
> precisa produzir (ADR-0016).

## Contexto

Cada estratégia produz uma planilha do mesmo documento. A pergunta prática é: qual
delas entregar ao consumidor?

A resposta óbvia — escolher a de maior acurácia — desperdiça informação. Medição
contra o conjunto de reserva (10 itens, 9 páginas, seções variadas):

| Rota | Acurácia |
|---|---|
| posicional | **100%** |
| pdfplumber | **100%** |
| camelot | **100%** |
| ocr | 78% |
| texto (`qwen3:4b`) | 100% na página medida |

**Três empatam em 100%**, e nenhuma foi medida em todas as 23 páginas. Escolher uma
delas é decisão arbitrária que joga fora a concordância das outras.

## Decisão

**Consolidar por célula, com votação entre as estratégias.**

Para cada par (item, campo), as estratégias votam:

| Situação | Ação | Confiança |
|---|---|---|
| todas concordam | preenche | alta |
| maioria concorda | preenche, **registra a divergência** | média |
| empate | **pendência humana** | — |
| nenhuma leu | **pendência humana** | — |

### Rota ausente é ausência, não voto contrário

Máquinas com mais capacidade rodam modelos que a de referência não roda — e são
elas que se parecem com o servidor de destino. Uma estratégia que não rodou numa
máquina **não pode** contar como discordância; ela simplesmente não votou.

Sem essa distinção, a consolidação puniria a máquina mais modesta por não ter
rodado modelos grandes.

### A proveniência acompanha o valor

Cada célula consolidada registra **quantas estratégias concordaram** e **quais**.
Isso permite afirmar, para um valor específico: *"confirmado por seis leituras
independentes"* — o que nenhuma estratégia sozinha sustenta.

## Por que isso resolve duas coisas de uma vez

**Para o consumidor pessoal:** produz a planilha única, com o máximo de células
preenchidas com alta confiança.

**Para o caso de uso corporativo:** *é* o ciclo pedido — preenche o que dá, e o que
não dá vira pendência explícita para revisão humana. A diferença em relação a um
modelo adivinhando é que aqui a confiança vem de **concordância medida** entre
leituras independentes, não de autoavaliação do modelo.

## Limite que precisa ficar declarado

**Votação não é infalível.** Se as estratégias compartilharem a mesma fonte de
erro — a camada de texto do documento, por exemplo — elas erram juntas e a votação
**confirma o erro com confiança alta**.

Isso não é hipotético: cinco das oito rotas consomem a mesma camada de texto. As
genuinamente independentes são o reconhecimento óptico (lê a imagem) e a rota de
visão (idem).

Consequência de desenho: **a concordância entre rotas que compartilham fonte vale
menos que a concordância entre rotas independentes.** A implementação deve
registrar isso, e a métrica de confiança não pode tratar as duas como equivalentes.

## Alternativas descartadas

**Escolher a planilha de maior acurácia** — descarta a informação das demais, e há
empate triplo em 100%.

**Média dos valores numéricos** — inaplicável a campo textual, e mascara erro
grosseiro: a média entre 358 e 135 é 246, valor que não existe no documento.

**Preferir sempre a rota determinística** — é a mais rápida e acurada hoje, mas
falha em documentos que só a rota por modelo alcança. Fixar preferência elimina o
ganho de ter várias.

## Consequências

- Uma planilha só, com confiança por célula e pendências explícitas.
- A comparação entre estratégias deixa de ser competição por um vencedor: passa a
  ser insumo de um resultado combinado. **O primeiro lugar aceita empate.**
- Custo: a fase de preenchimento precisa rodar **todos** os sobreviventes, não só o
  melhor (ADR-0016).
- **Pendente:** a métrica erro × omissão. Omitir vira pendência (barato); errar
  entra na planilha (caro). Hoje as duas contam igual na acurácia, o que subestima
  o risco de uma estratégia confiante e errada.
