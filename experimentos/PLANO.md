# Plano do experimento — o que falta, em ordem

> Atualizado em **2026-07-31**. Este arquivo é o ponto de retomada: diz o que
> falta, em que ordem, e **por quê** cada item vem antes do seguinte.
>
> O que já foi feito não aparece aqui — está nos ADRs e no histórico do git.

## Estado

| | |
|---|---|
| Testes | 507 passando, 6 saltados |
| Cobertura | 81% |
| Estilo | `flake8` e `black` limpos |
| Guarda de confidencialidade | 9/9 |
| ADRs | 15 |
| Rotas com resultado gravado | **6 de 8** — faltam as duas de modelo |

## O que já está medido

Contra o conjunto de reserva (10 itens, 9 páginas, seções variadas, transcrito às
cegas):

| Rota | Gabarito principal | **Conjunto de reserva** |
|---|---|---|
| posicional | 100% (tautológico) | **100%** |
| pdfplumber | 100% | **100%** |
| camelot | 99% | **100%** |
| ocr | 99,5% | 78% |
| linear (piso) | 0% | 0% |
| pymupdf (detector pronto) | 0% | 0% |

A coluna da direita é a que vale: mede **generalização** para layout que não foi
usado no ajuste. Três rotas a 100% é evidência forte.

**Rota por modelo:** o modelo lê a página corretamente, mas custa ~1061 s contra
0,2 s da rota determinística (ADR-0015). Nenhum resultado dela está gravado no
experimento ainda.

---

## 1. Fechar a medição das rotas por modelo

**Por que primeiro:** sem isso, a comparação tem um buraco — 6 de 8 rotas medidas.
E os parâmetros descobertos aqui vão fixados no script das outras máquinas.

- [ ] Bateria da rota de texto — 8 casos pareados com os da visão
- [ ] Consolidar os parâmetros num só lugar: teto de saída, `dpi`, degrau, e
      **como desligar o raciocínio** (em aberto: `think: false` não é respeitado;
      falta medir `/no_think`)
- [ ] Rodar `parser experimento` com as rotas de modelo e gravar em
      `experimentos/resultados/`
- [ ] Varredura de degraus contra o servidor real, gravada no experimento

## 2. Consolidação por campo

**Por que aqui:** é o item de maior valor do projeto inteiro, e ainda não existe.
Ele resolve **duas coisas de uma vez**.

Hoje cada extrator produz uma planilha. Escolher "a melhor" desperdiça informação:
três rotas empatam em 100%, e nenhuma acerta tudo em todas as páginas.

**A saída é votar por célula, não escolher por arquivo:**

| Situação | Ação | Confiança |
|---|---|---|
| todas as rotas concordam | preenche | alta |
| maioria concorda | preenche, **registra a divergência** | média |
| empate ou ninguém leu | **pendência humana** | — |

Isto **é** o ciclo que o consumidor corporativo pediu — "preenche o que dá, e o que
não sabe vira pendência" — e ao mesmo tempo produz a planilha única que o consumidor
pessoal precisa como entrada.

- [ ] Implementar a consolidação com proveniência (quantas rotas concordaram)
- [ ] Métrica **erro × omissão**: omitir vira pendência (bom); errar entra na
      planilha errado (péssimo). Hoje contam igual na acurácia
- [ ] ADR da decisão

## 3. TACO completo

**Escopo real, medido:** 23 páginas de dados, ~15 campos por alimento, pelo menos 3
tabelas distintas (centesimal+minerais, vitaminas, ácidos graxos). O perfil hoje
declara 9 páginas e 5 campos.

- [ ] Ampliar o perfil para as 23 páginas e todos os campos
- [ ] Gerar a planilha consolidada — serve de entrada ao consumidor pessoal **e**
      mede completude

## 4. Preparar as outras máquinas

**Por que depois:** os parâmetros descobertos no item 1 vão fixados no script. Rodar
antes significaria mandar configuração mal ajustada, e a comparação mediria o ajuste
em vez da máquina.

- [ ] **Revisar os dois scripts**: sintaxe validada, ensaio antes de rodar, guarda
      contra medições concorrentes, dependências e modelos baixados, log legível,
      branch e PR automáticos
- [ ] **Guia para leigos**: um comando, mensagem clara a cada passo, e o que enviar
      ao Lucas se falhar
- [ ] **Escada de modelos** — ver `MODELOS.md` e ADR-0014. Um modelo por vez, do
      menor ao maior, até falhar
- [ ] Verificar o isolamento em clone limpo: nenhuma máquina vê o resultado da outra

## 5. Ampliar o alcance

- [ ] Adapters de outros formatos: XLSX, DOCX, TXT, XML (hoje só PDF)
- [ ] Benchmark de patologias: PDF escaneado, tabela horizontal, duas colunas.
      **Precisa de documentos** — não temos nenhum com essas características

## 6. Depois dos pull requests

- [ ] Relatório técnico (matriz completa, acurácia por campo, limitações)
- [ ] Relatório executivo (uma página: o que ganhou, por quanto, o que custou)
- [ ] Mapa de aderência à especificação de referência — vai em `docs/_private/`

---

## Regras que valem para tudo acima

Nascidas de defeitos reais desta sessão. Estão em
`docs/adr/` e na memória do projeto.

**Uma medição por vez.** Duas em paralelo inflam o tempo das duas, e nada no
resultado denuncia. Aconteceu, e os números tiveram de ser refeitos.

**Ensaiar script longo antes de rodar.** Um ensaio de 15 segundos pegou um erro de
sintaxe que teria custado uma noite de medição.

**Zero absoluto em todas as estratégias é suspeita da régua, não da extração.** Uma
rota que acerta 100% num gabarito não erra 100% em outro do mesmo documento.

**Reputação escolhe o que testar; medição decide o que usar.** Dois modelos
promovidos como especializados em documento foram desqualificados em benchmark
independente.

**Escada de comparação precisa de pelo menos três origens distintas.** Concentração
alta é sinal de pesquisa rasa, não de convergência do mercado.
