# ADR-0020 — Pré-registro do protocolo experimental

**Status:** proposto · **Data:** 2026-07-31

> **Pré-registro.** Este documento fixa hipóteses, métricas e critério de corte
> **antes** de executar a bateria. O propósito é tornar verificável que as
> hipóteses não foram ajustadas depois de ver os resultados.
>
> Alterações posteriores são legítimas, mas entram como **emenda datada** ao
> final, nunca como reescrita silenciosa. O histórico do versionamento é a prova.

## Contexto

O experimento vai comparar estratégias de extração em várias máquinas, com
modelos de tamanhos e famílias diferentes. O desenho tem três decisões que
determinam a validade do resultado, e todas são criticáveis se tomadas depois
dos dados:

1. **quais hipóteses** cada rota testa;
2. **qual métrica** decide o que é melhor;
3. **qual critério** elimina um candidato.

Registrar depois é indistinguível de escolher o que favorece a conclusão. Por
isso o registro vem antes.

## Pergunta de pesquisa

> **Dado um documento com determinadas características estruturais, qual
> estratégia de extração o processa melhor, e a que custo computacional?**

Três subperguntas, cada uma respondida por um eixo do desenho:

| # | Pergunta | Eixo |
|---|---|---|
| Q1 | Existe característica em que a rota determinística perde para modelo? | taxonomia × rota |
| Q2 | Mais capacidade de hardware melhora o resultado, ou satura? | escada de máquinas |
| Q3 | A concordância entre rotas independentes prediz acerto? | consolidação por campo |

Q1 é a contribuição principal. Q2 é o eixo que o hardware heterogêneo torna
possível. Q3 sustenta a decisão de produto — preencher ou abrir pendência.

## Comparabilidade: dois níveis, e a razão de separá-los

Uma hipótese que só existe para uma rota **não pode** entrar na comparação entre
rotas: variar resolução de imagem não significa nada para a rota determinística,
e compará-las sob configurações diferentes mediria a configuração, não a
estratégia.

| Nível | O que varia | Aplica a |
|---|---|---|
| **Entre famílias** | nada — mesma página, mesmos campos, mesma métrica, mesmo gabarito | determinística ‖ texto ‖ visão |
| **Interno à rota** | as hipóteses abaixo | cada rota, isoladamente |

**A rota determinística entra com a sua melhor configuração conhecida**, não com
varredura. É o tratamento padrão de *baseline*: ela já foi calibrada (ADR-0002,
ADR-0007) e revarrer parâmetros nela responderia uma pergunta que não é a deste
experimento.

## As hipóteses

Cada hipótese isola **uma** variável. A coluna "por que discrimina" é o que a
justifica: hipótese que não tem razão declarada para mudar o resultado não entra.

### Rotas por modelo (texto e visão)

| # | Hipótese | Variável isolada | Por que discrimina |
|---|---|---|---|
| H1 | `Degrau.ESQUEMA_COMPLETO` | restrição máxima da saída | gramática pode tornar o caminho válido inalcançável em modelo pequeno (ADR-0015) |
| H2 | `Degrau.JSON_LIVRE` | restrição intermediária | garante JSON sem impor estrutura |
| H3 | `Degrau.TEXTO_COM_EXTRACAO` | sem restrição | mede se a restrição era o problema |
| H4 | raciocínio ligado | canal de raciocínio | medido: consome orçamento de tokens; **não desligável** neste servidor (ADR-0015) |
| H5 | contexto justo vs. folgado | orçamento de tokens | foi a causa medida das respostas vazias (ADR-0018) |
| H6 | página inteira vs. fatiada | tamanho da tarefa | fatiar foi a única forma que produziu saída válida na visão |
| H7 | prompt com vs. sem guardrails | instrução | guardrails custam tokens de entrada; medir se pagam |
| H8 | resolução da imagem (só visão) | entrada visual | dpi mais alto lê melhor e custa mais entrada (ADR-0003, ADR-0007) |

**H8 é assimétrica de propósito**, e isso fica declarado: a rota de texto não tem
imagem. Ela não invalida a comparação **entre** rotas porque a comparação entre
rotas usa a melhor configuração de cada uma — H8 só decide qual é a melhor
configuração *dentro* da rota de visão.

### Rota determinística (baseline)

Uma configuração, a melhor conhecida por calibração anterior. **Nenhuma
varredura.**

## Variáveis

**Independentes:** característica estrutural da página (ADR-0021) · rota ·
modelo (família, tamanho, quantização) · máquina (2/6/12/16 GB) · hipótese.

**Dependentes:** acurácia por campo · **erro vs. omissão** · tempo · tokens de
entrada e saída · tokens por segundo · pico de memória · degrau alcançado.

## Métricas

### Erro e omissão contam separado

A métrica central, e a que difere da prática comum de reportar só acurácia:

| Desfecho | Consequência no produto | Gravidade |
|---|---|---|
| valor correto | planilha preenchida | — |
| **omissão** | vira pendência para revisão humana | **aceitável** |
| **erro** | entra na planilha errado, e ninguém revisa | **grave** |

Colapsar os dois numa taxa de acerto trata como equivalentes duas falhas de
gravidade oposta. Um extrator que omite 20% e nunca erra é **melhor** para este
caso de uso que um que erra 10%, e a acurácia simples diria o contrário.

### Custo

Tempo por página, tokens por segundo, pico de memória, e a razão
**acurácia por unidade de custo** — que é o que responde se vale pagar mais.

### Fora, e por quê

| Métrica | Razão da exclusão |
|---|---|
| Energia (joules, watts) | exige instrumentação de hardware indisponível; estimativa por software em três fabricantes distintos seria número inventado |
| BLEU | mede semelhança de texto corrido; inadequado a campo estruturado, onde o valor está certo ou errado |

## Critério de corte entre triagem e preenchimento

### Separação de dados

**A página que elege o vencedor não pode ser a que mede o vencedor.** Triagem e
avaliação final usam páginas **disjuntas**. Sem isso, o desempenho reportado
inclui a sorte que fez aquele candidato vencer — o viés do vencedor.

### Zona de empate, não ranking

Avançam **todos** os candidatos que não se distinguem estatisticamente do melhor.

- **Teste:** McNemar pareado, adequado porque todas as rotas leem exatamente os
  mesmos campos da mesma página — as observações são pareadas, não independentes.
- **Incerteza:** intervalo de confiança por *bootstrap* sobre os campos.
- **Comparações múltiplas:** correção de Holm-Bonferroni sobre as comparações
  contra o melhor.

**Justificativa de não cortar por ranking:** a amostra de uma página são ~155
valores (31 itens × 5 campos). Isso distingue um candidato claramente ruim de um
bom, mas **não** distingue 96% de 98%. Cortar dentro da margem de erro seria
decidir por ruído — e a consolidação por campo (ADR-0017) aproveita diversidade,
então eliminar um candidato equivalente tem custo real.

### Os eliminados são reportados

A tabela completa da triagem entra no resultado, não só os sobreviventes. Omitir
os eliminados impede verificar se o corte foi honesto.

## Ameaças à validade, declaradas

| Ameaça | Mitigação | Resíduo |
|---|---|---|
| Amostra pequena na triagem | zona de empate; corte só do que se distingue | permanece: limitação declarada |
| Viés do vencedor | páginas disjuntas entre fases | reduzido, não eliminado |
| Erros correlacionados entre rotas | matriz de correlação antes de calibrar pesos (ADR-0017) | rotas que leem a mesma camada de texto podem errar juntas |
| Contaminação por concorrência | uma medição por vez; detecção de processo intruso (ADR-0019) | máquina de terceiro não é controlável |
| Variação entre versões de servidor | versão registrada por máquina | comparação entre versões diferentes fica marcada |
| Um único documento-caso | coleta por característica (ADR-0021) | **a ameaça mais séria hoje** |

## Reprodutibilidade

Registrado por execução: impressão digital do documento e do prompt · versão do
servidor, do modelo (digest) e do interpretador · parâmetros completos · máquina
· tokens de entrada e saída · contexto pedido e efetivo.

## Escopo publicável

Parte do contexto que motiva este projeto está sob acordo de confidencialidade.
**Nada de domínio de aplicação específico entra no material publicável** — nem
nomes, nem vocabulário setorial, que identifica por dedução.

O que é publicável: o método, as medições, a taxonomia estrutural e o domínio
nutricional de referência, cuja fonte permite reprodução com citação.

## Consequências

**A favor:** o desenho fica auditável; a crítica de ajuste posterior fica
respondida pelo histórico datado; e escrever o protocolo antes revelou uma
lacuna real — as hipóteses eram citadas como "8" desde o ADR-0016 sem nunca
terem sido enumeradas.

**Contra:** pré-registro custa liberdade. Descobertas durante a execução que
sugiram outra hipótese exigem emenda datada, o que é mais trabalhoso que mudar
de ideia em silêncio — e é exatamente o ponto.

**Aberto:** os valores concretos de "contexto justo vs. folgado" (H5) e de
resolução (H8) dependem da entrada medida de cada modelo, que só existe após a
primeira execução em cada máquina. O procedimento é fixado aqui; os números
saem de `parser.contexto.dimensionar`, não de escolha.
