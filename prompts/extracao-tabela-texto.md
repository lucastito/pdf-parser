# Extração de tabela — rota de texto

Para modelos de linguagem que recebem o **texto** já extraído da página.

## Instrução

Extraia os itens da tabela. Para cada item, informe os campos pedidos.

**Quando a ordem das colunas for informada, siga-a como referência.** Cada linha de
dados traz um valor para **cada** coluna declarada, na sequência — e o campo pedido
vem da posição indicada, não do nome que parece próximo.

A tabela costuma ter **mais colunas do que os campos pedidos**, e as não pedidas
aparecem no meio, não só nas pontas.

Marcadores como `NA` e `Tr` **ocupam uma coluna** como qualquer valor. Pular um
deles desalinha todos os campos seguintes.

O `identificador` é o número do item **seguido da descrição completa**, como
aparecem no documento. Exemplo de forma: `12 Farinha, de mandioca, torrada`.

**A resposta usa os nomes dos campos pedidos, não os do cabeçalho do documento.**
O cabeçalho serve para localizar a coluna certa; a chave de saída é sempre a que
foi pedida. E a resposta é **uma lista de todos os itens da página**, não um item
solto.

## Guardrails

- **Responda com a lista completa**, no formato pedido. Um objeto solto, ou um
  item por resposta, não atende.
- **Use as chaves pedidas.** Copiar o nome do cabeçalho do documento como chave
  produz saída que o destino não reconhece.
- **Sem ordem de colunas informada, alinhe por nome, nunca por posição.** Se uma
  coluna do documento não estiver entre os campos pedidos, pule-a — não empurre o
  valor dela para o campo seguinte, e **não a inclua na resposta**. **Com a ordem de
  colunas informada** (a lista numerada na instrução), vale o contrário: o campo
  pedido é o que está na posição indicada, não o que o nome mais parecido sugerir —
  é a mesma regra da instrução acima, repetida aqui porque esta seção costuma ser
  lida sozinha.
- O `identificador` leva número **e** descrição. Só o número não identifica o item.
- Use exatamente os valores impressos no documento. Não calcule, não converta, não
  arredonde.
- Se um valor não aparecer no texto, **omita o campo**. Não estime, não repita o
  valor de outro item, não use zero como substituto.
- Reproduza marcadores especiais como estão: `Tr`, `NA`, `*`. Eles não são zero.
- Preserve a vírgula decimal como está no documento; a conversão acontece depois.
- Não acrescente campos que não foram pedidos.
- Responda apenas com JSON válido, sem texto antes ou depois.

## Justificativa de cada regra

**"Alinhe por nome, nunca por posição" (sem ordem informada)** — regra nascida de
defeito medido, não de precaução, e anterior ao ADR-0023 (que ainda não existia
em 2026-08-01): quando não há ordem de colunas descoberta, nome é o único sinal
disponível. Com ordem descoberta, ADR-0023 mede o oposto — ver a nota acrescentada
ao guardrail em 2026-08-12, corrigindo uma contradição que a auditoria externa
apontou entre esta seção e a instrução do topo. Na bateria de 2026-08-01 o
modelo devolveu, para o primeiro item,
`energia_kcal = 124` (correto) e `proteina_g = 517`. O 517 é a **energia em
quilojoules** do mesmo item: o documento tem uma coluna de energia em kJ que não
estava entre os campos pedidos, e o modelo, em vez de pulá-la, empurrou todos os
valores uma posição — deixando o último campo vazio.

O defeito é silencioso: os números são todos reais e vêm da linha certa. Só a
conferência contra gabarito revela que estão na coluna errada.

**A segunda rodada corrigiu três campos e deixou dois**, e a causa remanescente é
mais específica que a primeira. A ordem real do documento-caso é:

```
Umidade | Energia(kcal) | Energia(kJ) | Proteína | Lipídeos | Colesterol | Carboidrato | Fibra | ...
70,1    | 124           | 517         | 2,6      | 1,0      | NA         | 25,8        | 2,7   | ...
```

O modelo devolveu `carboidrato = 70,1` — que é a **Umidade**, a primeira coluna.
Ao encontrar `NA` na coluna de colesterol, ele deixou de contá-la como coluna e
se reorientou a partir do início da linha.

Daí as duas regras acrescentadas: contar as colunas do cabeçalho antes de
extrair, e tratar marcador (`NA`, `Tr`) como ocupante de coluna. **Não é o mesmo
defeito da v2** — aquele era coluna não pedida nas pontas; este é marcador não
numérico no meio.

**"Identificador com número e descrição"** — o modelo devolvia apenas o número
(`1`), e as demais estratégias devolvem `1 Arroz, integral, cozido`. Nenhum item
casava na consolidação nem contra o gabarito, e a rota aparecia com zero acertos
apesar de ter lido a tabela.

**"Não calcule nem converta"** — o modelo tem tendência a "corrigir" valores que
parecem inconsistentes, por exemplo recalculando energia a partir dos macronutrientes.
Isso produz um número plausível que não está no documento, e a extração deixa de ser
extração.

**"Omita o campo em vez de estimar"** — um campo ausente é registrado como ausente e
aparece nas métricas de cobertura. Um campo estimado entra como se fosse lido, e
contamina a acurácia sem deixar rastro. O modelo preenchendo lacunas é a falha mais
cara desta rota, porque é invisível.

**"Marcadores não são zero"** — no documento-caso, `Tr` significa "presente em
quantidade desprezível" e `NA` significa "não analisado". São afirmações diferentes
entre si e diferentes de zero. Somar `Tr` como zero falseia qualquer total, sem
levantar erro.

**"Preserve a vírgula"** — a normalização é a mesma para todas as estratégias
(ADR-0005). Se o modelo converter por conta própria, a comparação passa a medir a
conversão dele em vez da extração.

**"Não acrescente campos"** — o esquema de saída já descarta campo extra, mas pedir
explicitamente reduz tokens gastos em conteúdo que será jogado fora.

**"Apenas JSON"** — mesmo com a decodificação restringida por esquema, a instrução no
texto importa: sem ela a amostragem degrada e modelos pequenos passam a devolver
prosa.

**"Use as chaves pedidas, e responda com a lista"** — regra nascida de uma
**regressão que a v3 causou**. Ao enfatizar "localize a coluna pelo nome no
cabeçalho", o prompt fez o modelo passar a devolver as colunas *do documento* como
chaves — `Umidade (%)`, `Energia (kJ)`, `Cinzas (g)` — e num objeto solto, sem a
lista. O extrator rejeitou tudo: **zero registros em 89 s**.

A lição é sobre prompt, não sobre o modelo: reforçar uma regra pode enfraquecer
outra que estava implícita. A instrução de alinhamento estava correta; faltava
dizer que o cabeçalho serve para **localizar**, e a chave de saída continua sendo
a pedida.

## Histórico

- **v4** (2026-08-01) — chaves de saída e formato de lista explicitados, após a
  regressão descrita acima.
- **v3** (2026-08-01) — contar colunas do cabeçalho e tratar marcador como
  ocupante de coluna, após o modelo devolver a umidade no campo de carboidrato.
- **v2** (2026-08-01) — alinhamento por nome de coluna e identificador completo.
  As duas regras vêm de defeito medido na bateria completa, não de precaução:
  colunas deslocadas por uma posição e identificador só com o número. Ver as
  justificativas acima.
- **v1** (2026-07-29) — versão inicial. Extraída de constantes que estavam em código
  (`ollama.py`), sem justificativa registrada.
