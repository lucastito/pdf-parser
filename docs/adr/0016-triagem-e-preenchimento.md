# ADR-0016 — Triagem e preenchimento como fases distintas

**Status:** aceito · **Data:** 2026-07-31

> **Limite aberto, confirmado no código em 2026-08-12** (achado originalmente
> pela auditoria de 02/08): esta ADR fala em "uma página de triagem", e
> `src/parser/configuracao.py` implementa isso como campo **escalar**
> (`pagina_de_triagem_declarada: int | None`), não uma página por
> característica da taxonomia (ADR-0021) como a seção 5 de `PLANO.md` já
> reconhece ser necessário. Ainda não corrigido — não é regressão desta
> sessão, é dívida que já existia e continua existindo.

## Contexto

O experimento compara oito estratégias de extração. Duas delas — as rotas por
modelo — têm parâmetros que variam: teto de tokens, canal de raciocínio, grau de
restrição da saída, resolução da imagem. Máquinas com mais capacidade rodam
modelos que a de referência não roda (ADR-0014).

A pergunta que motivou este registro veio de uma conta simples: **se cada modelo
rodar todas as variações em todas as páginas, quantas execuções são?**

## A conta, com tempos medidos

Medições desta sessão, na página 29 do documento-caso:

| Rota | Tarefa | Tempo |
|---|---|---|
| texto (`qwen3:4b`) | página inteira | 2904 s |
| visão (`qwen3-vl:4b`) | 5 itens | 1078 s |
| determinística | página inteira | **0,2 s** |

Projetando o desenho ingênuo:

```
(4 modelos de visão + 5 de texto) × 8 hipóteses  =    72 execuções por página
72 × 23 páginas de dados                          = 1.656 execuções
1.656 × ~2.900 s                                  =   ~56 dias de máquina
```

**Inviável.** E cortar hipóteses no escuro para caber no orçamento seria decidir por
conveniência, não por método.

## Decisão

**Duas fases, com perguntas diferentes.**

### Fase 1 — triagem: uma página, muitas hipóteses

**Pergunta:** qual a melhor configuração de cada modelo?

> ### ⚠ RETIFICAÇÃO (2026-08-01) — uma página basta **por característica**, não no total
>
> A afirmação abaixo é verdadeira **dentro de um documento**: as páginas de dados
> daquele arquivo são estruturalmente idênticas, e isso foi verificado. Ela deixa
> de valer assim que entram documentos de outras características.
>
> **O furo, apontado pelo Lucas:** eleger finalistas medindo **uma** característica
> e depois fazê-los competir em **seis** é viés de seleção. Um modelo fraco em
> tabela com grade pode ser o melhor em página digitalizada e inclinada — e teria
> sido eliminado antes de ser testado no que faz bem.
>
> É exatamente a objeção que um revisor levantaria, e ela procede.
>
> **A correção:** a triagem roda **uma página de cada característica** da taxonomia
> (ADR-0021), não uma página só. O custo não multiplica por seis, porque as
> hipóteses que se mostrarem dominantes na primeira característica ficam fixas nas
> seguintes — revarrer o que já discriminou não acrescenta informação.
>
> O corte por zona de empate passa a valer **por característica**: um modelo
> eliminado em tabela continua competindo em digitalizado. A eliminação é do par
> (modelo, característica), não do modelo.

**Uma página basta, e isso foi verificado — não suposto.** As páginas de dados são
estruturalmente idênticas:

| Página | Rotação | Palavras | Imagens | Colunas |
|---|---|---|---|---|
| 29 | 90° | 546 | 0 | 11 |
| 33 | 90° | 495 | 0 | 11 |
| 41 | 90° | 524 | 0 | 11 |
| 45 | 90° | 463 | 0 | 11 |
| 47 | 90° | 546 | 0 | 11 |

Mesma rotação, mesma sequência de unidades no cabeçalho, sem imagens. Só o conteúdo
muda. **O que a ferramenta faz numa, faz nas outras** — acrescentar páginas do mesmo
formato custaria 3× o tempo sem acrescentar informação.

**Critério para ampliar: conteúdo, não quantidade.** Entra amostra que teste algo
que a atual não testa — tabela vertical, outro número de colunas, imagem embutida,
orientação distinta. Verificar a estrutura antes de decidir; não presumir variedade.

**A mesma página em todas as máquinas.** Página 29, verificada por impressão
digital do texto e da imagem renderizada. Triar em páginas diferentes tornaria as
configurações vencedoras incomparáveis entre máquinas — o oposto do propósito.

### Fase 2 — preenchimento: 23 páginas, uma configuração

**Pergunta:** qual planilha cada estratégia produz?

Só os sobreviventes da triagem, cada um com a configuração que venceu. **Nenhuma
hipótese varia aqui**, e não por economia: variar tornaria as planilhas
incomparáveis entre si, que é exatamente o oposto do que a consolidação por campo
precisa.

Custo estimado: ~56 h para três modelos sobreviventes. As seis rotas
determinísticas fazem as 23 páginas em segundos.

### Corte entre as fases: zona de empate

**Modelos que não se distinguem estatisticamente avançam todos.** Cortar por
ranking dentro da margem de erro é decisão sem base — e na consolidação por campo a
diversidade tem valor próprio: um modelo mediano no agregado pode ser o único que
acerta um campo específico.

**O limiar não é fixado antes de ver a distribuição.** E precisa caber no que a
amostra sustenta: uma página são ~155 valores (31 itens × 5 campos), o que
distingue um modelo claramente ruim de um bom, mas **não** distingue 96% de 98%.

## Por que a separação é correta, não só barata

As duas fases medem coisas diferentes:

- A triagem mede **configuração**. Variar é o objetivo.
- O preenchimento mede **estratégia**. Variar seria confundir a comparação.

O desenho ingênuo produziria 1.656 planilhas mutuamente incomparáveis, porque cada
uma teria configuração distinta. A consolidação por campo (planejada) exige o
oposto: todas as planilhas da mesma página, sob a mesma condição.

A economia — de ~56 dias para ~3,5 — é consequência, não motivo.

## Consequências

- O experimento cabe num fim de semana em vez de dois meses.
- Cada fase produz artefato próprio: a triagem produz **configurações vencedoras**
  (descartáveis depois); o preenchimento produz **planilhas** (insumo da
  consolidação).
- O critério de ampliação fica objetivo e verificável: comparar estrutura de página
  antes de acrescentar amostra.
- **Risco assumido:** se um modelo for bom na página de triagem e ruim em outra
  seção, a configuração escolhida contamina a fase 2. Mitigado pela verificação
  estrutural acima — mas se surgir página de formato diferente, a triagem precisa
  ser refeita incluindo-a.
- **Limite declarado:** os tempos projetados vêm de duas medições na máquina de
  referência. Máquinas diferentes terão tempos diferentes, e a projeção pode errar
  por fator relevante. Serve para dimensionar, não para prometer prazo.
