# ADR-0017 — Consolidação por campo, não escolha de planilha

**Status:** aceito · **Data:** 2026-07-31 · **Implementado:** 2026-08-11/12

> **Retificação de 2026-08-12.** Esta ADR ficou marcada "proposto, implementação
> não começou" por mais de uma semana depois de `src/parser/consolidacao.py`
> já existir com 35 testes — inconsistência confirmada pela auditoria de
> 02/08 e só corrigida agora. O mecanismo está implementado (`consolidar()` +
> `materializar()`) e, desde 2026-08-11/12, ligado à produção do Cenário B via
> `parser.planejador._decidir_entre_deterministicos` (rota `"consolidado"`).
>
> **Limitação conhecida, não fechada:** a votação recebe todos os itens de
> todas as rotas, inclusive os que só uma rota produziu — um item exclusivo
> vira `Desfecho.VOTO_UNICO` com confiança 0,9, sem checar se a rota de
> origem tem histórico de fabricar linha (o problema que P-1.1 nomeia, ver
> `PLANO.md`). Não corrigido de propósito; ver a seção "Cenário B — Produto
> DSS" em `PLANO.md` para o detalhe e o estado exato.

## Contexto

Cada estratégia produz uma planilha do mesmo documento. A pergunta prática é: qual
delas entregar ao consumidor?

A resposta óbvia — escolher a de maior acurácia — desperdiça informação. Medição
contra o conjunto de reserva (10 itens, 9 páginas, seções variadas):

| Rota | Acurácia | Mesma régua? |
|---|---|---|
| posicional | **100%** | sim — no `resumo.json` |
| pdfplumber | **100%** | sim |
| camelot | **100%** | sim |
| ocr | 78% | sim |
| texto (`qwen3:4b`) | 100% em `energia_kcal`, 1 página | **não** |

**Três empatam em 100%**, e nenhuma foi medida em todas as 23 páginas. Escolher uma
delas é decisão arbitrária que joga fora a concordância das outras.

> **A rota de texto ainda não é comparável, e a linha acima não deve sugerir que
> seja.** Ela rodou **uma vez**, por script avulso, fora do fluxo do experimento:
> uma página, um campo conferido, sem entrar no `resumo.json` e sem acurácia
> calculada pela mesma régua das demais.
>
> Consequência para esta decisão: hoje a consolidação só tem **as seis
> determinísticas** como votantes reais. Isso basta para construir e validar o
> **mecanismo**, e não basta para a comparação final — que depende da bateria da
> seção 1 do plano.

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
