# ADR-0013 — Desenho do experimento em várias máquinas

**Status:** aceito · **Data:** 2026-07-30

## Contexto

O ambiente-alvo declarado é modesto (~2 GB de VRAM). Isso levanta uma pergunta que
nenhuma medição numa única máquina responde: **mais memória de vídeo melhora o
resultado, ou é indiferente?**

A resposta orienta uma decisão concreta de infraestrutura — dimensionar a máquina
que executará o produto. Errar para cima desperdiça; errar para baixo entrega um
sistema que não roda.

## O que **não** se compara

Confrontar diretamente resultados de máquinas com capacidades diferentes mede
**hardware**, não estratégia. Uma máquina com folga de memória rodando um modelo
maior e vencendo não prova nada além do óbvio.

Pior: se cada máquina escolher livremente o que roda — qual modelo, qual grau de
restrição de saída, qual resolução — a comparação passa a medir a escolha.

## Decisão

**Três eixos de comparação, cada um com escopo próprio.**

### 1. Entre máquinas, só o que todas conseguem rodar

Os degraus de saída (SPEC §4.4) e os modelos pequenos rodam em qualquer máquina do
conjunto, inclusive a mais modesta. Esse é o **denominador comum**, e é onde a
comparação entre máquinas é legítima: mesma entrada, mesma restrição, mesmo
modelo — a única variável que resta é a máquina.

**Todas as máquinas rodam todos os degraus, em ordem, mesmo depois de um
funcionar.** Parar no primeiro sucesso é o certo em produção e destrói a
comparação: se a máquina A responde no degrau 1 e para, não há como saber se
responderia no 3, e o confronto com uma máquina B que só responde no 3 fica sem
base.

Cada tentativa registra degrau, sucesso, **tipo** da falha e tempo. `resposta
vazia` e `sem estrutura` são achados diferentes — o primeiro sugere problema de
modelo, o segundo de formato — e colapsá-los em "falhou" perde a distinção
justamente na comparação em que ela importa.

### 2. Dentro de uma máquina com folga, a escada de capacidade

Numa máquina que comporta modelos maiores, roda-se uma **escada crescente** de
tamanho, do menor ao maior, até que a máquina não aguente. A falha é resultado,
não acidente: ela marca o teto real daquele hardware.

Isso responde a pergunta original — se o ganho de qualidade acompanha o aumento de
capacidade, ou se satura. Um platô é tão informativo quanto uma curva: significa
que capacidade adicional não se converte em resultado.

**Um modelo por vez, sempre.** Dois modelos disputando a mesma memória de vídeo
inflam o tempo de ambos e podem falhar por contenção, não por incapacidade — o que
produziria um teto falso. A trava de medição (`parser.medicao`) impede rodadas
concorrentes na mesma máquina.

### 3. Dentro de cada máquina, estratégias entre si

Cada rodada é **autocontida**: as estratégias são comparadas no mesmo ambiente,
com o mesmo documento. É a comparação que sempre vale, e não depende das outras
máquinas.

## O que toda rodada registra

Sem isto, nenhum resultado é confrontável depois:

- **máquina**: processador, núcleos, memória, GPU e memória de vídeo;
- **entrada**: documento e sua impressão digital — máquinas diferentes lendo
  arquivos diferentes produziriam divergência que pareceria de hardware;
- **parâmetros**: modelo, resolução, degrau, restrição de saída;
- **condição**: memória livre e carga no início da rodada;
- **dados brutos**, antes de qualquer conclusão: a acurácia é recalculada depois,
  sobre os mesmos dados, sem reexecutar.

## Consequências

- A pergunta "mais capacidade ajuda?" passa a ter resposta **medida**, não opinião
  — e serve de evidência para dimensionar infraestrutura.
- Um resultado de máquina potente não contamina a comparação: ele vive no eixo 2,
  declaradamente exploratório, e não no eixo 1.
- Custo: a máquina modesta roda uma bateria que não a favorece, e a potente roda
  duas (o denominador comum e a escada). É o preço de manter os eixos separados.
- O teto de cada máquina fica documentado, incluindo **como** falhou.
- Risco assumido: o conjunto de máquinas é pequeno e não é amostra estatística.
  Os resultados descrevem aquelas máquinas, e a extrapolação é hipótese — não
  conclusão.
