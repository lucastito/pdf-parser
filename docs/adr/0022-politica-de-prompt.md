# ADR-0022 — Política de prompt: base comum, e onde a otimização entra

**Status:** proposto · **Data:** 2026-08-01

## Contexto

A comparação entre modelos exige decidir uma coisa que parece detalhe e não é:
**cada modelo recebe o mesmo prompt, ou o prompt que funciona melhor com ele?**

A pergunta surgiu de uma observação correta: prompt afinado para uma família
frequentemente não transfere para outra. Famílias diferentes têm convenções de
instrução, comportamento de raciocínio e sensibilidade a formato distintos. Um
prompt bom num modelo pode ir mal noutro, e o inverso.

Nenhuma das duas escolhas é neutra:

| Escolha | Mede | Contamina |
|---|---|---|
| **Mesmo prompt para todos** | o modelo | favorece quem se aproxima da convenção do prompt-base |
| **Prompt otimizado por modelo** | modelo **+ esforço de otimização** | "esforço" não é igual entre eles, e não é verificável |

A segunda parece mais justa e é pior: torna o resultado **não reproduzível**.
Quem repetir o experimento não tem como saber quanto esforço foi gasto em cada
modelo, e a comparação vira "quem otimizou melhor".

## Decisão

**Prompt-base comum, com adaptação mínima e documentada por família.**

O que a adaptação pode mudar:

- marcadores de sistema e de turno exigidos pela família;
- a forma de pedir saída estruturada, quando a família tem convenção própria.

O que a adaptação **não** pode mudar:

- a instrução;
- os guardrails;
- os campos pedidos, a ordem, ou a definição de cada um.

A fronteira é: **formato é infraestrutura, instrução é otimização.** Adaptar
formato mantém a comparação; reescrever instrução a destrói.

### O prompt é fixado antes da triagem

O prompt **não** é uma das hipóteses da triagem (ADR-0020). Se variasse junto com
as outras oito, nenhum efeito seria atribuível — ele mudaria ao mesmo tempo que o
degrau, o contexto e a resolução, e a triagem mediria a soma.

A validação do prompt acontece **antes**, na máquina de referência, em escopo
pequeno, e o resultado é congelado antes de qualquer máquina rodar a bateria.

### Nenhuma máquina otimiza localmente

As máquinas do experimento rodam **o mesmo prompt**, sem exceção. Se cada uma
afinasse o seu, os resultados deixariam de ser comparáveis — e a comparação entre
máquinas é o propósito do experimento.

## Otimização automática de prompt: por que fica de fora **agora**

Ferramentas de otimização (DSPy) e de avaliação de variantes (promptfoo) foram
consideradas. Ficam fora desta fase, por três razões em ordem de peso:

**1. O orçamento de chamadas não comporta.** Otimização automática funciona
rodando dezenas a centenas de gerações. Na máquina de referência uma página custa
**45 a 77 minutos**, e mesmo em escopo reduzido são ~18 min por chamada. Uma
otimização levaria semanas por modelo.

**2. Enfraqueceria o argumento em vez de fortalecê-lo.** Otimizar por modelo é
exatamente o que torna a comparação questionável — ver a tabela acima.

**3. Não é o gargalo.** O defeito medido na rota de texto não foi prompt subótimo:
foi o esquema não declarar uma coluna que o documento tem, e o modelo alinhar por
posição em vez de por nome. Isso se corrige lendo a saída, não otimizando.

Sobre o segundo caso: o que `promptfoo` oferece — rodar variantes e comparar
contra asserções — **este projeto já faz melhor**, porque tem gabarito conferido à
mão e a métrica de erro contra omissão, que nenhum arnês genérico traz.

## Onde elas passam a fazer sentido

Duas condições, e ambas são futuras:

### Condição 1 — o ciclo ficar barato

Se em alguma máquina com aceleração o ciclo cair para **1 a 2 minutos** por
chamada, otimização automática passa a caber no orçamento. Aí vale reavaliar, e
com uma exigência: **mesmo procedimento e mesmo orçamento de tentativas para cada
família**, de forma que "esforço de otimização" vire constante em vez de variável
escondida.

### Condição 2 — desempate entre finalistas

O critério de corte é por zona de empate (ADR-0020): modelos que não se
distinguem estatisticamente avançam todos. Isso é correto para não decidir por
ruído — mas deixa em aberto o caso em que **é preciso escolher um**, e a
diferença observada é pequena demais para sustentar a escolha.

Nesse caso, otimizar o prompt de cada finalista **com orçamento idêntico** é um
critério de desempate defensável: mede qual responde melhor a esforço de
engenharia, que é informação real para quem vai operar o sistema.

**Duas ressalvas que ficam declaradas junto:**

> O resultado passa a responder *"qual modelo tem mais teto"*, e não *"qual modelo
> é melhor"*. São perguntas diferentes, e a segunda continua sem resposta.

> Otimizar contra o mesmo conjunto que mediu o empate **infla os dois** e escolhe
> o que sobreajusta melhor. O desempate exige dados separados dos que produziram o
> empate — a mesma regra de páginas disjuntas do ADR-0020.

## Consequências

**A favor:** a comparação entre modelos permanece reproduzível; qualquer pessoa
pode repetir o experimento com o prompt versionado e obter o mesmo resultado; e a
adaptação por família fica documentada, então o leitor vê exatamente o que mudou.

**Contra:** o prompt-base favorece modelos cuja convenção se aproxima dele, e
nenhum modelo aparece no seu máximo. **É limitação declarada, não corrigida** — e
a alternativa custaria a reprodutibilidade.

**Aberto:** quanto a escolha do prompt-base afeta o ranking. Só uma rodada com
prompt-base alternativo responderia, e ela não cabe no orçamento atual. Fica
registrado como o experimento que falta.
