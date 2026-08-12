# ADR-0017 — Consolidação por campo, não escolha de planilha

**Status:** aceito · **Data:** 2026-07-31 · **Implementado:** 2026-08-11/12

> **Retificação de 2026-08-12.** Esta ADR ficou marcada "proposto, implementação
> não começou" por mais de uma semana depois de `src/parser/consolidacao.py`
> já existir com 35 testes — inconsistência confirmada pela auditoria de
> 02/08 e só corrigida agora. O mecanismo está implementado (`consolidar()` +
> `materializar()`) e, desde 2026-08-11/12, ligado à produção do Cenário B via
> `parser.planejador._decidir_entre_deterministicos` (rota `"consolidado"`).
>
> **Limitação encontrada na mesma sessão, e fechada mais tarde no mesmo dia
> (P-1.1/P0.1, achado das auditorias de 02/08).** A votação recebia todos os
> itens de todas as rotas, inclusive os que só uma rota produziu. No corpus,
> `camelot` chegou a devolver 62 registros para uma página de ~31 — um item
> assim virava `Desfecho.VOTO_UNICO` com confiança 0,9, quase tão alta quanto
> concordância plena, sem checar se a rota de origem tem histórico de
> fabricar linha.
>
> **Solução:** `Desfecho.ITEM_EXCLUSIVO`. Quando um item aparece em só 1 das
> N (N ≥ 2) rotas ativas de uma consolidação, todas as células daquele item
> viram pendência de revisão humana — não voto automático. Cobertura parcial
> genuína (2 ou mais de N rotas concordando) continua com confiança normal;
> só o caso extremo, uma leitura solitária entre várias consultadas, é
> tratado como suspeito. Com uma única rota ativa no total — o caso do
> Cenário A, `pipeline.Pipeline`, um extrator por documento — o comportamento
> de voto único de sempre é preservado, porque aí "exclusivo" não distingue
> nada: não há segunda rota para desconfiar.
>
> **Por que pendência, e não penalizar a confiança do voto único comum:**
> sem gabarito, a votação não decide sozinha se a leitura solitária é
> fabricação ou cobertura legítima que só aquela rota alcançou — as duas
> produzem o mesmo padrão de dados (um item, uma rota). Errar para o lado da
> pendência custa trabalho humano; errar para o lado do voto automático
> publica um valor inventado com aparência de confiança alta, que é o modo
> de falha mais caro deste módulo (ver "Limite que precisa ficar declarado"
> abaixo). O valor não confirmado continua visível no relatório e no JSON
> (`ResultadoConsolidacao.valores_divergentes`) — pendência é "não publicar
> sem revisão", não "esconder o que a rota leu".
>
> Testado em `tests/test_consolidacao.py::TestItemExclusivo` (6 casos,
> unitário) e, na fronteira real onde a lacuna vivia,
> `tests/test_planejador.py::TestDecisaoEntreRotasDeterministicas::test_item_lido_por_uma_so_rota_nao_vaza_como_dado_confirmado`
> (integração).

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
| item lido por 1 de N≥2 rotas consultadas | **pendência humana** — suspeita de fabricação, não cobertura confirmada | — |

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
