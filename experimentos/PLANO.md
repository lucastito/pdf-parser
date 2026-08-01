# Plano do experimento — o que falta, em ordem

> Atualizado em **2026-07-31**. Este arquivo é o ponto de retomada: diz o que
> falta, em que ordem, e **por quê** cada item vem antes do seguinte.
>
> O que já foi feito não aparece aqui — está nos ADRs e no histórico do git.

## Duas entregas, e a ordem entre elas

| # | Entrega | Prazo |
|---|---|---|
| 1 | **Produto** — preencher planilha sozinho, pendência para revisão humana | prioridade declarada |
| 2 | **Artigo** — submissão a periódico de análise de documentos | **15/11/2026**, rede em 31/01/2027 |

A ordem é essa e não se inverte. A boa notícia é a sobreposição: **a taxonomia, a
consolidação por campo e a métrica erro × omissão servem às duas** — são
requisito do produto e contribuição do artigo ao mesmo tempo.

## Estado

| | |
|---|---|
| Testes | **539 passando**, 6 saltados |
| Estilo | `flake8` e `black` limpos |
| Guarda de confidencialidade | 9/9 |
| ADRs | **21** |
| Ciclos de importação | **nenhum** (39 módulos) |
| Rotas com resultado gravado | 8 de 8 |
| Documentos-caso | **1** — é o gargalo, ver eixo B |

## Os três eixos

O trabalho não é uma fila. São três eixos com custos e dependências diferentes, e
tratá-los como fila foi o que travou o planejamento anterior.

```
        taxonomia (ADR-0021)
               │
        documentos por característica
               │
     ┌─────────┴─────────┐
     │                   │
DETERMINÍSTICAS      MODELOS
segundos/página      dezenas de min/página
todas × tudo         triagem por característica
     │                   │
     │            corte por zona de empate
     │            (reporta eliminados)
     │                   │
     │            preenchimento, páginas disjuntas
     └─────────┬─────────┘
               ▼
     matriz de correlação de erros
               ▼
     CONSOLIDAÇÃO POR CAMPO
```

**Por que a consolidação não espera a triagem.** Ela vota entre as rotas que
existirem — o ADR-0017 já trata rota ausente como ausência, não voto contrário.
O **mecanismo** pode ser construído com as determinísticas e entregar o pedido do
produto agora. O que **não** pode ser fixado antes das medições é o **peso** de
cada voto: rotas que leem a mesma camada de texto erram juntas, e calibrar sem a
matriz de correlação seria retrabalho garantido.

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

**Rotas por modelo — medido em 2026-07-31**, uma medição por vez, na página 29:

| Rota | Tarefa | Tempo | Resultado |
|---|---|---|---|
| texto (`qwen3:4b`) | página inteira, **com valores** | 2904 s | **31 itens, 100%** em `energia_kcal` (31/31) |
| visão (`qwen3-vl:4b`) | 5 itens, só nomes+energia | 1078 s | 4 de 5 — leu `135` onde o documento diz `358` |
| visão (`qwen3-vl:4b`) | página, **com valores** | 1026 s | **resposta vazia** — não atende o caso de uso |
| determinística | página inteira | **0,2 s** | 100% |

> ### ⚠ A linha "resposta vazia" acima está RETIFICADA — leia a seção 0
>
> A conclusão registrada era *"a rota de visão não preenche planilha nesta classe
> de hardware"*. **Ela mede um artefato de configuração, não o modelo.**
>
> A causa é o **limite de contexto**, que o projeto não declarava: o padrão do
> servidor limita entrada e saída **juntas**, e a imagem consome quase todo o
> espaço. Provado por aritmética — quatro casos, com prompts de tamanhos
> diferentes, parando na **mesma soma exata**. Ver a seção 0.
>
> A conclusão sobre o **raciocínio** continua de pé: foi medida de forma
> independente. Mas o peso dela cai — se o contexto for suficiente, o raciocínio
> deixa de ser fatal e passa a ser apenas custo.

**Não há como desligar o raciocínio** neste servidor com este modelo. As duas
formas foram medidas: `think: false` gerou 4043 caracteres de raciocínio,
`/no_think` gerou **6254** — piorou. A questão fica fechada.

**A rota de texto funciona de ponta a ponta**, e isso nunca tinha sido medido. Ela
recebe o texto já extraído, então não comete o erro de leitura de dígito que a
rota de visão cometeu.

O custo por página inteira é ~14.500× o da rota determinística. Isso não a
descarta — ela resolve documentos que a determinística não alcança — mas define
onde cada uma serve.

Um dado que explica muito: na rota de visão, **4043 caracteres foram gastos
raciocinando para produzir 185 de resposta**. Na de texto, zero raciocínio e 16767
de resposta. O raciocínio consome o orçamento que o limite de tokens restringe
(ADR-0015).

Detalhe completo em `resultados/titoslaptop/rotas-por-modelo.json`.

---

## 0. Retificação do limite de contexto — ✅ CONCLUÍDA

> **Fechada em 2026-07-31.** Mantida aqui como resultado, não como tarefa: é a
> evidência que sustenta ADR-0018 e a regra de nunca herdar padrão de servidor.

### O desfecho, medido sem limite de cliente

A pergunta que ficara aberta — *quanto a chamada leva quando nada a interrompe* —
tem resposta:

| | Valor |
|---|---|
| Tempo | **77,4 min** (4641 s) |
| `done_reason` | **`stop`** — terminou sozinha, sem corte |
| Tokens | entrada 2376 + saída 5684 = **8060** de 12271 disponíveis |
| Resposta | **vazia** |

**Duas leituras, e a segunda importa mais.**

A correção do contexto **funcionou**: sobrou espaço (8060 de 12271) e não houve
corte. Mas a resposta veio vazia mesmo assim, com 5684 tokens gerados — ou seja,
**o contexto não era a única causa**.

A explicação verificada: o servidor devolve o campo de raciocínio preenchido
**mesmo com o raciocínio declarado como desligado**, e o script de medição
descartava esse campo. Os tokens foram para lá. É lacuna de instrumentação, não
incapacidade do modelo — e é por isso que a instrumentação (eixo A) vem antes de
remedir.

Dado bruto em `resultados/titoslaptop/vlm-pagina-inteira-sem-limite.json`.

### O que foi provado

O teto declarado era `num_predict=16384`, mas as respostas cortavam em ~1870
tokens com `done_reason=length`. Somando **entrada + saída** de cada medição:

| Caso | entrada + saída | soma | motivo |
|---|---|---|---|
| fatiado, 5 itens | 2184 + 1581 | 3765 | `stop` |
| rota de texto | 1819 + 5948 | 7767 | `stop` |
| `/no_think` | 2175 + 1921 | **4096** | `length` |
| com valores | 2227 + 1869 | **4096** | `length` |
| valores + `/no_think` | 2233 + 1863 | **4096** | `length` |
| controle | 2189 + 1907 | **4096** | `length` |

**Quatro casos, prompts de tamanhos diferentes, mesma soma exata.** O padrão de
`num_ctx` no Ollama é 4096 e limita entrada e saída **juntas**; a imagem consome
~2200 de entrada. O `num_predict` nunca foi o limite atuante — o caso que
funcionou funcionou porque **coube**.

Verificação independente: com `num_ctx` explícito, o servidor passou a reportar
contexto de 16384 e o modelo cresceu de 3,6 GB para 5,5 GB.

**Consequência: a conclusão "a rota de visão não preenche planilha nesta classe
de hardware" mede um artefato de configuração, não o modelo.**

### O que aconteceu ao corrigir o contexto — medido, três casos

Dado bruto em `resultados/titoslaptop/contexto-limite.json`.

| Caso | Contexto | Desfecho | Quem parou |
|---|---|---|---|
| A | 4096 (padrão) | cortado em **exatamente 4096**, 21 min | o servidor |
| B | 16384 | **>1 h sem terminar** | o cliente, por tempo |
| C | 32768 | **>1 h sem terminar** | o cliente, por tempo |

**A causa está confirmada.** O caso A bateu a parede; B e C não bateram parede
nenhuma. Se o contexto não fosse o limite atuante, os três teriam cortado igual.

**E a conclusão prática mudou de forma, não de veredito.** Corrigir o parâmetro
**não tornou a rota viável nesta máquina** — trocou uma falha por outra:

| | Antes | Depois |
|---|---|---|
| Falha | resposta vazia por corte | não termina em tempo útil |
| Velocidade | rápida (21 min) | lenta (>1 h) |
| Diagnóstico | **enganoso** — parecia incapacidade | claro — é a máquina |

Formulação correta: *em processador de baixo consumo, uma página inteira pela
rota de visão não termina em tempo utilizável*. Isso não é limitação do modelo
nem de configuração — ele **lê a página corretamente**, como o caso de 5 itens
mostrou. É capacidade computacional.

**Não medido, e vale medir:** quanto a chamada realmente levaria sem limite de
cliente, e o comportamento em máquina com placa de vídeo funcional — que é
justamente o que o experimento multimáquina existe para responder (ADR-0013).

- [x] Código (TDD): `degraus.py` envia `num_ctx`; propagar por `fabrica.py`,
      `ollama.py`, `extratores/vlm.py`
- [x] **Declarar no perfil** — feito em 2026-07-31. Estava aberto enquanto o
      resto já funcionava, que é a pior combinação: a correção existia no código
      e ficava **desligada** no arquivo que as medições usam, então a próxima
      rodada herdaria o defeito em silêncio. `vlm` recebeu 12271 e `llm` 11650,
      valores devolvidos por `parser.contexto.dimensionar` a partir da entrada
      medida — não escolhidos à mão. Procedência em `DEFAULTS`, guarda em
      `TestPerfisDoProjeto.test_rotas_por_modelo_declaram_contexto`
- [x] Corrigir as mensagens de erro — hoje mandam aumentar `tokens_maximos`, que
      a medição refuta
- [x] **Registrar sempre** `prompt_eval_count`, `eval_count` e a soma: foi a soma
      que revelou a causa, e ela era descartada. `Uso` grava os três, em falha
      **e** em sucesso, e sobrevive à serialização — coberto por
      `TestUsoNoResultado`, que faltava: o dado ia para o JSON sem teste algum
      garantindo que continuasse indo
- [x] Retificar ADR-0015, `SPEC.md` e a memória do projeto
- [x] ADR novo: dimensionamento de contexto, com a regra — **nunca confiar em
      padrão de servidor para parâmetro que decide resultado** (ADR-0018)
- [x] Remedir o caso que falhou sob `num_ctx` correto — feito: 77,4 min, sem
      corte. Ver o desfecho no topo desta seção
- [ ] **Refazer com o canal de raciocínio gravado** — a única parte que resta, e
      depende da instrumentação (A1). Mesmos 77 min de máquina; o que muda é o
      dado ficar completo

### Fórmula de dimensionamento de memória

O limite **nativo** do modelo quase nunca é o que aperta: um modelo de 4B suporta
256k de contexto, mas 256k pediria ~45 GB. **Quem manda é a memória.**

Medido, com um modelo de visão de 4B:

| Contexto | Memória medida | Previsto pela reta de 2 pontos | Erro |
|---|---|---|---|
| 4096 | 3,6 GB | — | — |
| 16384 | 5,5 GB | — | — |
| 32768 | **8,0 GB** | 8,03 GB | **0,4%** |

Ou seja ~0,16 MB por token de contexto neste modelo.

**A linearidade foi testada, não assumida.** A reta foi ajustada com os dois
primeiros pontos e **previu o terceiro** com 0,4% de erro — que é a diferença
entre curva ajustada e curva com poder preditivo.

Projeção que isso sustenta: **64k de contexto pediria ~13 GB e não cabe em uma
placa de 12 GB**, mesmo com um modelo pequeno. Com modelos maiores, o teto cai.

> **Limite que continua declarado:** o número compara o crescimento do **processo
> inteiro** (cache + buffers + codificador visual), não o cache de atenção
> isolado que a literatura calcula. E vale para **um** modelo — a inclinação
> depende da arquitetura, e é isso que a instrumentação abaixo vai levantar.

Forma proposta, com uma entrada **medida** e não suposta:

```
necessário = entrada_medida + saída_esperada + margem
viável     = (memória_livre − peso_do_modelo) / custo_por_token
usar       = min(nativo_do_modelo, viável, necessário × folga)
```

Foi exatamente `entrada_medida` que faltou: supôs-se que o teto bastava sem
medir quanto a imagem consumia.

- [ ] Instrumentar o experimento para gravar, a cada execução: contexto pedido,
      memória do processo, tokens de entrada e de saída, modelo, máquina.
      **Custo zero de tempo** — os números já passam pela chamada e são
      descartados. Com 10 modelos × várias máquinas, a fórmula deixa de ser
      heurística de um ponto e vira ajuste sobre dezenas
- [ ] Medir o custo por token do modelo de **texto** da mesma família e tamanho:
      isola o custo do codificador visual, e é a comparação mais informativa
      disponível

## Onde cada seção entra nos três eixos

As seções abaixo mantêm a numeração original — o que muda é **quando** cada uma
roda, e o eixo a que pertence.

| Eixo | Seções | Depende de | Bloqueia |
|---|---|---|---|
| **A — código e instrumentação** | 1 (parcial), 2, 5 | nada; roda aqui | tudo o mais |
| **B — coleta de documentos** | 5 | taxonomia (ADR-0021) | a triagem por característica |
| **C — execução distribuída** | 1, 2b, 3, 4 | A e B prontos, e as outras máquinas | o artigo |

**A é o único eixo que não depende de terceiros.** É por onde se começa, e é o
que entrega ao produto. B depende de curadoria manual. C depende de pessoas.

### Cronograma até 15/11

| Quando | O quê | Risco |
|---|---|---|
| ago | Eixo A: instrumentação, consolidação, taxonomia no código | baixo — só depende daqui |
| ago–set | Eixo B: coleta por característica, com cuidado de dado pessoal | **médio** — curadoria manual, e é trabalho humano |
| set | Preparar e distribuir o pacote das outras máquinas | **alto** — precisa das pessoas disponíveis |
| set–out | Eixo C: execução, triagem, corte, preenchimento | **alto** — máquina de terceiro, e refazer custa dias |
| out–nov | Análise, consolidação final, escrita | apertado se algo acima escorregar |

**Os dois riscos que podem estourar o prazo não são técnicos:** a coleta (depende
do Lucas) e a disponibilidade de quem vai rodar (depende de terceiros). Ambos
precisam começar cedo — em especial avisar as pessoas, porque baixar os modelos é
transferência grande e leva dias.

**Rede de segurança declarada:** se o resultado não amadurecer até novembro, a
mesma conferência tem uma segunda janela em janeiro. Nada do trabalho se perde;
o que muda é a trilha.

---

## 1. Fechar a medição das rotas por modelo

**Por que:** sem isso, a comparação tem um buraco — **6 de 8 rotas** estão no
`resumo.json`. As duas por modelo foram medidas por script avulso, fora do fluxo
do experimento, e por isso não têm acurácia calculada da mesma forma.

- [ ] Bateria da rota de texto — 8 casos pareados com os da visão
- [ ] Consolidar os parâmetros num só lugar: contexto, teto de saída, `dpi` e
      degrau
- [ ] **Integrar as rotas de modelo ao `resumo.json`** — hoje vivem em
      `rotas-por-modelo.json`, à parte, e a comparação entre as oito não fecha
- [ ] Varredura de degraus contra o servidor real, gravada no experimento

### O registro de ambiente

Resolvido nesta sessão:

- [x] **versão do servidor de inferência** — versões diferentes entre máquinas
      tornam os resultados incomparáveis, e antes isso passaria despercebido.
      Agora vai no `ambiente.json` e no comando `ambiente`
- [x] **memória de vídeo por caminho neutro de fabricante** — lida do registro do
      sistema (64 bits), não da interface que satura em 4 GB. Placa dedicada tem
      prioridade sobre gráfico integrado, que não declara o campo (ADR-0019)

Falta:

- [ ] **versão do driver de vídeo** — afeta desempenho e alocação de memória
- [ ] **contexto efetivamente usado** e **tokens de entrada/saída** por chamada —
      o tipo `Uso` já os carrega; falta gravá-los no resultado

> **Armadilha de ambiente, encontrada na máquina de referência.** O pacote
> instalado apontava para um **clone antigo**, e `python -m parser.cli` executava
> código desatualizado enquanto os testes rodavam o fonte correto. Uma medição
> feita assim mediria a versão errada sem nada denunciar.
>
> Verificar antes de medir: `python -c "import parser; print(parser.__file__)"`
> tem de apontar para o repositório em uso. O script das outras máquinas precisa
> conferir isso e falhar alto se divergir.

## 2. Consolidação por campo

> Decisão registrada em [ADR-0017](../docs/adr/0017-consolidacao-por-campo.md),
> incluindo o limite: rotas que compartilham fonte de erro podem errar juntas,
> e a votação confirmaria o erro com confiança alta.

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

### O que se constrói agora, e o que espera medição

A distinção evita o retrabalho que a pressa produziria:

| Parte | Quando | Por quê |
|---|---|---|
| **Mecanismo** — votar, decidir, abrir pendência | **agora** (eixo A) | não muda quando chegam votantes novos; ADR-0017 já trata rota ausente |
| **Pesos** — quanto vale cada voto | **depois** das medições | rotas que leem a mesma camada de texto **erram juntas**; calibrar sem a matriz de correlação seria decidir por suposição |

Por isso os pesos entram **parametrizados**, não embutidos: o mecanismo entrega o
comportamento que o produto pede hoje, e a calibração é trocada depois sem tocar
na lógica.

**Fundação que já existe:** `src/parser/concordancia.py` **mede** divergência
entre estratégias (`comparar_estrategias`). Falta a camada que **decide**. A
`Pendencia` de `lote.py` é o encaixe da saída.

- [x] Implementar a consolidação com proveniência (quantas rotas concordaram) —
      `src/parser/consolidacao.py`, 22 testes
- [x] **Pesos parametrizados**, com o padrão uniforme declarado como provisório

### O que a primeira execução sobre dados reais revelou

A primeira rodada devolveu **56,2% de células com voto único**. A suspeita
natural — "as rotas leem pouco" — estava errada. Era **alinhamento faltando**, em
dois níveis, e nenhum deles é defeito da votação.

**Identificador.** Só **81 de ~283 itens** apareciam nas quatro rotas. A causa não
é acento: o extrator de tabela insere **espaço no meio da palavra** ao atravessar
a quebra de coluna num cabeçalho rotacionado.

| Rota | Identificador lido |
|---|---|
| posicional | `1 Arroz, integral, cozido` |
| pdfplumber | `1 Arroz, integra l, cozido` |

Dois itens, um voto cada. **200 alimentos fora da votação por um espaço.**

**Campo.** O perfil mapeava **5** campos e o documento tem **11**. Cada variante
virava coluna própria — por acento perdido no OCR (`Proteina`) ou ordem trocada
pela rotação (`Alimentar Fibra`).

#### Efeito acumulado, medido

| Etapa | Concordância | Voto único |
|---|---|---|
| inicial | 39,3% | 56,2% |
| + mapeamento parcial (5 campos) | 40,7% | 54,6% |
| + alinhamento de identificador | 60,4% | 33,3% |
| **+ mapeamento completo (11 campos)** | **79,4%** | **13,5%** |

- [x] **Ampliar o `mapeamento` do perfil** para todos os campos do documento
- [x] **Alinhar identificadores entre rotas** — normalização de acento, espaço e
      caixa antes de indexar

> **Exclusão deliberada:** `Energia (kd)` **não** entra no mapeamento. É leitura
> corrompida do OCR, não variante legítima, e acolhê-la faria o erro votar como
> se fosse boa leitura — a votação confirmaria o valor errado com confiança alta,
> que é o modo de falha que a consolidação existe para evitar. Há teste guardando.

- [ ] Rodar a consolidação sobre as **23 páginas**, não só as 9 atuais
- [ ] Investigar os **6,8% de pendência** restantes: divergência real, ou ainda
      alinhamento?
- [ ] **A votação precisa lidar com conjuntos diferentes de rotas.** Máquinas com
      mais capacidade rodam modelos que a de referência não roda, e são elas que se
      parecem com o servidor de destino. Uma rota ausente numa máquina não pode
      invalidar a consolidação, nem contar como discordância — é ausência, não voto
      contrário
- [ ] Métrica **erro × omissão**: omitir vira pendência (bom); errar entra na
      planilha errado (péssimo). Hoje contam igual na acurácia
- [ ] **Matriz de correlação de erros** entre rotas — pré-requisito da calibração,
      e resultado publicável por si: mostra quais estratégias são de fato
      independentes
- [x] ADR da decisão — [ADR-0017](../docs/adr/0017-consolidacao-por-campo.md)

## 2b. Escopo: triagem e preenchimento são fases distintas

> Decisão registrada em [ADR-0016](../docs/adr/0016-triagem-e-preenchimento.md),
> com a conta completa e a verificação estrutural das páginas.

**O problema, com números.** Se cada modelo rodar todas as hipóteses em todas as
páginas, a conta explode:

| | Cálculo | Resultado |
|---|---|---|
| Modelos × hipóteses | (4 visão + 5 texto) × 8 | 72 execuções por página |
| × páginas de dados | 72 × 23 | **1.656 execuções** |
| × tempo medido (~2900 s) | | **~56 dias de máquina** |

Inviável. A saída não é cortar hipóteses no escuro — é separar o que cada fase
responde.

### Fase 1 — triagem: **1 página, muitas hipóteses**

**Pergunta:** qual a melhor configuração de cada modelo?

**Página 29, e a mesma em todas as máquinas.** Foi a usada nas medições desta
sessão — texto e imagem verificados por impressão digital. Se cada máquina triasse
numa página diferente, as configurações vencedoras não seriam comparáveis.

**Uma página basta, e isso foi verificado, não suposto.** As páginas de dados são
estruturalmente idênticas:

| Página | Rotação | Palavras | Imagens | Colunas |
|---|---|---|---|---|
| 29 | 90° | 546 | 0 | 11 |
| 33 | 90° | 495 | 0 | 11 |
| 41 | 90° | 524 | 0 | 11 |
| 45 | 90° | 463 | 0 | 11 |
| 47 | 90° | 546 | 0 | 11 |

Mesma rotação, mesma sequência de unidades no cabeçalho, sem imagens. Só o conteúdo
muda. **Acrescentar páginas do mesmo formato custaria 3× o tempo sem acrescentar
informação** — o que a ferramenta faz numa, faz nas outras.

**Quando ampliar:** se aparecer página com formato diferente — tabela vertical,
outro número de colunas, imagem embutida, orientação distinta. Aí a página nova
testa algo que a 29 não testa, e entra. É critério de conteúdo, não de quantidade.

Custo: ~29 h com 4 hipóteses (as que discriminaram nesta sessão).

### Fase 2 — preenchimento: **23 páginas, 1 configuração**

**Pergunta:** qual planilha cada estratégia produz, para consolidar?

Só os sobreviventes da triagem, cada um com a configuração que venceu. Nenhuma
hipótese varia aqui — variar tornaria as planilhas incomparáveis.

Custo: ~56 h para 3 modelos sobreviventes. As 6 rotas determinísticas fazem as 23
páginas em segundos.

**O corte tem zona de empate.** Modelos que não se distinguem estatisticamente
entre si avançam **todos** — a consolidação por campo aproveita a diversidade, e
cortar por ranking dentro da margem de erro seria decisão sem base.

O limiar exato **não é fixado agora**: depende de como os resultados se
distribuírem. A amostra de uma página são ~155 valores (31 itens × 5 campos), o
que sustenta distinguir um modelo claramente ruim de um bom, mas **não** distinguir
96% de 98%. O corte será desenhado para o que a amostra sustenta, com o número
registrado junto da justificativa.

### Por que a separação é metodologicamente correta

Não é só economia. **As duas fases medem coisas diferentes:**

- A triagem mede **configuração** — variar é o objetivo.
- O preenchimento mede **estratégia** — variar seria confundir a comparação.

Rodar tudo em tudo produziria 1.656 planilhas incomparáveis entre si, porque cada
uma teria configuração diferente. A consolidação por campo exige o oposto: todas as
planilhas da mesma página, produzidas sob a mesma condição.

### Onde o escopo fica baixo, e onde abre

| Momento | Escopo | Por quê |
|---|---|---|
| Triagem | 1 página, 5 campos | descobrir configuração não exige o documento inteiro |
| Preenchimento | 23 páginas, todos os campos | é a planilha que vai para o consumidor |
| Consolidação | todas as planilhas da fase 2 | votação por campo exige o conjunto completo |

**O vencedor final aceita empate.** Três rotas determinísticas já empatam em 100%
contra o conjunto de reserva — e é justamente por isso que a consolidação por campo
é melhor que escolher uma: onde empatam, a concordância vira confiança.

## 3. TACO completo

**Escopo real, medido:** 23 páginas de dados, ~15 campos por alimento, pelo menos 3
tabelas distintas (centesimal+minerais, vitaminas, ácidos graxos). O perfil hoje
declara 9 páginas e 5 campos.

- [ ] Ampliar o perfil para as 23 páginas e todos os campos
- [ ] Gerar a planilha consolidada — serve de entrada ao consumidor pessoal **e**
      mede completude

## 4. Preparar as outras máquinas

**Por que depois:** os parâmetros descobertos nos itens 0 e 1 vão fixados no
script. Rodar antes significaria mandar configuração mal ajustada, e a comparação
mediria o ajuste em vez da máquina.

**Premissa que mudou:** as máquinas têm placas de fabricantes **diferentes**
(NVIDIA, AMD e Intel). Nada pode depender de ferramenta de um fabricante só.

### 4.1 Detecção de ambiente — verificada, não suposta

**A memória de vídeo reportada por WMI é errada acima de 4 GB.** O campo
`AdapterRAM` é inteiro de 32 bits: uma placa de 12 GB reporta 4 GB. Um script que
decidisse o modelo por esse número mandaria a máquina grande rodar como pequena.

Fonte correta, **neutra de fabricante**: o registro do Windows, em
`HardwareInformation.qwMemorySize` (64 bits). Verificado nesta máquina; as
ferramentas de fabricante servem só para confirmar.

- [ ] Ler do registro; cruzar com as demais fontes e **alertar em discordância**
- [ ] **Gráfico integrado não tem esse campo** — usa memória do sistema
      dinamicamente. É caso distinto, não erro
- [ ] **Máquina com duas placas** (integrada + dedicada) é comum em portátil:
      escolher a correta e reportar, **nunca somar**

### 4.2 Contenção — o experimento divide a máquina com o dono dela

Um jogo aberto durante a medição contamina o tempo, e **nada no número denuncia**.
É a mesma classe de erro das duas medições concorrentes, que já custou uma
refação.

**Exclusividade de placa de vídeo não é possível**, e é limitação do sistema
operacional: o agendador é multiplexado por projeto, não há como reservá-la, e
quando a memória enche o driver despeja por prioridade — o processo em primeiro
plano ganha do nosso. Impedir outro programa de abrir exigiria privilégio
administrativo e interceptação de processos, que é comportamento de software
malicioso.

O que funciona: os **contadores de desempenho do sistema** expõem nome e
identificador do processo sem depender de fabricante. Verificado.

- [ ] Detectar o intruso e **nomeá-lo** no aviso — "feche o programa X"
- [ ] **Pausar entre chamadas, nunca durante**: matar uma geração de 20 minutos
      pela metade não recupera nada
- [ ] **Chamada interrompida não retoma — refaz.** O servidor não expõe ponto de
      retomada, e o tempo daquela medição já estaria contaminado de qualquer forma
- [ ] **Blocos pequenos** (um modelo × uma configuração × uma página) limitam a
      perda a uma chamada
- [ ] Retomar **sozinho** quando o intruso fechar, **e** aceitar tecla — mas a
      tecla **só vale com a placa livre**; senão recusa e repete o alerta

### 4.3 Contaminação silenciosa — a que produz número plausível e errado

- [ ] **Modelo que não cabe na memória cai para o processador** e fica ordens de
      grandeza mais lento. Sairia como "esta máquina é lenta"
- [ ] **Redução por temperatura**: as primeiras medições saem mais rápidas que as
      últimas, e a diferença viraria "resultado"
- [ ] Modo de economia de energia; modelo residual de rodada anterior na memória

### 4.4 Robustez e integridade

- [ ] Download falho, disco cheio, suspensão automática, reinicialização por
      atualização, antivírus
- [ ] **Servidor pré-instalado em versão diferente invalida a comparação** entre
      máquinas: detectar e registrar, não só assumir
- [ ] Impressão digital do documento: garantir que todas leem o **mesmo** arquivo
- [ ] Registrar versão de tudo — servidor, driver, interpretador, modelo
- [ ] Verificar o isolamento em clone limpo: nenhuma máquina vê o resultado da
      outra

### 4.5 Experiência de quem executa

- [ ] **Execução em blocos sequenciais**, com log em arquivo e retomada do último
      bloco concluído
- [ ] **Estimativa de tempo calibrada na própria máquina** pelo primeiro bloco —
      uma estimativa da máquina de referência erraria por fator grande
- [ ] **Saída acessível a leitor de tela** — requisito real, não hipotético.
      Barra desenhada com caracteres e sobrescrita no terminal não expõe objeto de
      acessibilidade; a primitiva nativa do interpretador expõe. Usar a nativa
- [ ] **Guia para leigos**: um comando, mensagem clara a cada passo, e o que
      enviar de volta se falhar
- [ ] **Escada de modelos** — ver `MODELOS.md` e ADR-0014. Um modelo por vez, do
      menor ao maior, até falhar

## 5. Taxonomia de características, e a coleta que ela destrava

> Taxonomia registrada em
> [ADR-0021](../docs/adr/0021-taxonomia-de-caracteristicas.md), com a tabela
> completa marcada por custo de detecção.

**O entregável final do projeto** é diferente do que existe hoje. Hoje temos
*"esta rota acertou X% neste documento"*. O que serve ao consumidor é: **dado um
documento com estas características, use esta estratégia com esta configuração.**

**O vocabulário vem antes dos documentos**, e a ordem importa: sem saber o que
procurar, a coleta traz dez documentos que exercitam a mesma característica. O
vocabulário torna a coleta eficiente — poucos documentos, muitas características.

### Característica é um segundo eixo da página

A correção que o ADR-0021 registra: `triagem.Classe` responde *"o que tem nesta
página?"*; a característica responde *"como ela está codificada?"*. Uma página é
`DADOS` **e** `DIGITALIZADA` ao mesmo tempo.

E a unidade é a **página**, não o arquivo — senão o documento misto, que é o caso
difícil, se perderia num rótulo único por PDF.

### O que o diagnóstico já detecta

`src/parser/diagnostico.py` cobre **cinco** características estruturais, cada uma
com severidade e ação recomendada:

| Detectado | Severidade |
|---|---|
| página rotacionada | bloqueia |
| sem camada de texto | bloqueia |
| camada de texto parcial | alerta |
| texto vertical | alerta |
| mapa de caracteres incompleto | alerta |

Os outros seis achados do módulo descrevem **qualidade do resultado**, não
estrutura da entrada — são diagnóstico de extração, não taxonomia.

Hoje ele **descreve**. O roteiro exige que **recomende**.

- [x] Taxonomia completa, marcando **detectável hoje** × **exige código** ×
      **exige inspeção manual** — ADR-0021
- [ ] Implementar a característica como segundo eixo em `triagem.py`, reusando o
      diagnóstico como fonte
- [ ] **Coletar documentos por característica** (eixo B) — com cuidado de dado
      pessoal: nada que identifique alguém entra no conjunto
- [ ] Evoluir o diagnóstico de descritivo para **prescritivo**
- [ ] Benchmark de patologias, depois que os documentos existirem

> **Limite que fica declarado:** o roteiro só pode afirmar sobre característica
> **medida em documento real**. Hoje há **um** documento — tabela rotacionada,
> texto nativo, 11 colunas, sem imagem. Toda a medição descreve esse caso. Regra
> de decisão sem documento que a exercite é hipótese, não resultado.

## 5b. Ampliar o alcance

- [ ] Adapters de outros formatos: XLSX, DOCX, TXT, XML (hoje só PDF)

## 6. Relatórios e artigo

**Do produto:**

- [ ] Relatório técnico (matriz completa, acurácia por campo, limitações)
- [ ] Relatório executivo (uma página: o que ganhou, por quanto, o que custou)
- [ ] Mapa de aderência à especificação de referência — vai em `docs/_private/`

**Do artigo** — protocolo em
[ADR-0020](../docs/adr/0020-pre-registro-do-protocolo.md):

- [ ] Rascunho vivo, atualizado à medida que as medições saem — escrever no fim
      obrigaria a reconstruir raciocínio já esquecido
- [ ] Tabela completa da triagem, **com os eliminados** — omiti-los impede
      verificar se o corte foi honesto
- [ ] Seção de ameaças à validade, com as mitigações e o resíduo de cada uma
- [ ] Pacote de reprodutibilidade: prompts, perfis, versões, sementes, código de
      avaliação

> **O que não entra, e é decisão, não esquecimento:** nada de domínio de
> aplicação sob confidencialidade — nem nomes, nem vocabulário setorial, que
> identifica por dedução. O material publicável é o método, as medições, a
> taxonomia e o domínio de referência de fonte aberta.

---

## Acoplamento — medido, não afirmado

Verificado em 2026-07-31 sobre os 39 módulos do pacote:

| Indicador | Resultado |
|---|---|
| **Ciclos de importação** | **nenhum** |
| Fan-in mais alto | `modelo` (20) e `portas` (15) — as abstrações |
| Fan-out mais alto | `cli` (17) e `fabrica` (11) — os pontos de composição |
| Módulos folha | 9, entre eles `contexto` e `degraus` |

A leitura: ausência de ciclos em 39 módulos indica camadas de verdade. Fan-in
concentrado nas abstrações é o padrão de ports & adapters — todos dependem do
contrato, ninguém de implementação. Fan-out alto **só** onde é trabalho conhecer
as peças; se `fabrica` tivesse fan-out baixo, a fiação estaria espalhada.

Observação sem ação por ora: `lote` importa `extratores.posicional` dentro de
funções, para calibrar layout. É import local, não dependência estrutural — mas
é o único ponto onde um módulo de orquestração cita implementação pelo nome.

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
