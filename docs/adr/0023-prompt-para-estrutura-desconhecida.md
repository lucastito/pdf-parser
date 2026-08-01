# ADR-0023 — Prompt para documento de estrutura desconhecida

**Status:** proposto · **Data:** 2026-08-01

## Contexto

Em 2026-08-01 a rota de texto passou de 0% para **100%** na página de referência.
A correção que produziu esse salto foi entregar ao modelo **a ordem exata das
colunas** do documento, numerada.

O ganho é real e está medido. Mas ele expõe um problema que a medição não revela:

> **O prompt que funciona 100% neste documento está errado por construção em
> qualquer outro.**

Quem entrega documento ao sistema não sabe as colunas de antemão. Pode ser um
relatório sem tabela nenhuma, um digitalizado sem camada de texto, um arquivo com
outro número de colunas, ou um documento com várias tabelas diferentes entre si.

Declarar a ordem no perfil resolve **um** documento por vez, com trabalho humano
para cada. Isso não é produto — é configuração manual disfarçada de automação.

## O que a medição diz sobre cada alternativa

Três formas de montar o prompt, e duas já têm número:

| Forma | Acurácia medida | Escala |
|---|---|---|
| Instrução genérica ("extraia a tabela") | **0%** — devolvia colunas trocadas | qualquer documento |
| Regra descrita ("alinhe por nome", "conte as colunas") | **60%** — três versões tentaram | qualquer documento |
| **Ordem das colunas entregue** | **100%** | **um documento por vez** |

A leitura é desconfortável e precisa ficar registrada: **o que funciona não
escala, e o que escala não funciona.** Nenhuma das três serve ao produto como
está.

## Decisão

**O prompt é montado a partir do que o pipeline detecta, não do que o humano
declara.**

A peça central já existe e não precisa ser criada: `parser.calibracao.calibrar`
**descobre as faixas de colunas sozinha**, a partir da geometria da página, sem
nenhuma declaração prévia. É o mesmo mecanismo que faz a rota posicional
funcionar em documento não configurado.

O fluxo passa a ser:

```
documento → diagnóstico (que características tem?)
          → calibração (quais colunas, em que ordem?)
          → prompt montado com essa ordem
          → extração
```

O humano deixa de declarar a estrutura; ele **confere** o que foi detectado.

### O que cada peça já entrega

| Peça | O que detecta hoje | Estado |
|---|---|---|
| `diagnostico.py` | rotação, camada de texto ausente/parcial, texto vertical, mapa de caracteres | **pronto** |
| `triagem.py` | página é dados, contexto ou descartável | **pronto** |
| `calibracao.py` | faixas de coluna, rótulos, unidades — **por geometria** | **pronto** |
| montagem do prompt | — | **falta** |

O trabalho novo é a última linha: transformar o que já é detectado numa instrução.

### Quando não houver estrutura detectável

Documento digitalizado sem camada de texto não permite calibração geométrica. Aí
o prompt cai para a forma genérica, **e o resultado é declarado como tal** — não
se finge que a extração teve a mesma base.

É o mesmo princípio da consolidação (ADR-0017): quando a confiança não se
sustenta, o sistema diz isso em vez de preencher.

## Consequências

**A favor:** o produto passa a aceitar documento novo sem configuração manual; a
mesma detecção que hoje escolhe a estratégia passa a informar o prompt; e a
qualidade do prompt vira **função do que se detectou**, o que é auditável.

**Contra:** o prompt deixa de ser constante e passa a variar por documento — o que
**colide com o ADR-0022**, que fixa prompt-base comum para tornar a comparação
reprodutível.

A colisão se resolve separando os dois usos, e a distinção precisa ficar explícita:

| Uso | Prompt | Por quê |
|---|---|---|
| **Experimento** | fixo, com a ordem do documento-caso declarada | comparar modelos exige constante |
| **Produto** | montado do diagnóstico | aceitar documento desconhecido exige variável |

São propósitos diferentes. O experimento mede modelos sob condição controlada; o
produto processa documento arbitrário. Usar o mesmo prompt nos dois seria
confundir medição com operação.

**Aberto, e é o que a coleta de documentos vai responder:** quanto a montagem
automática se aproxima da declaração manual. Hoje há **um** documento, e nele a
declaração dá 100%. Se a montagem automática der 90% em dez documentos variados,
é melhor produto que 100% em um só — mas isso é hipótese até haver os dez.

## Limite declarado

> Este ADR registra uma **decisão de desenho**, não um resultado. A montagem
> automática de prompt **não foi implementada nem medida**. O que está medido é o
> problema que ela resolve: 0% com prompt genérico, 60% com regra descrita, 100%
> com ordem declarada.
