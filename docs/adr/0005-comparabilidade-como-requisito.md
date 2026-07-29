# ADR-0005 — Comparabilidade como requisito de arquitetura

**Status:** aceito · **Data:** 2026-07-29

## Contexto

O projeto precisa sustentar afirmações do tipo *"esta abordagem é melhor que aquela
para este documento"*. Sem instrumento de medida, essa frase é preferência pessoal.
Com instrumento, é evidência — e evidência sobrevive a discordância.

O risco a evitar é sutil: se cada abordagem tiver seu próprio pipeline de limpeza e
seu próprio formato de saída, a diferença medida entre elas será artefato do
encanamento, não da abordagem. A comparação pareceria rigorosa e não mediria nada.

## Decisão

**Comparabilidade é requisito de arquitetura, não etapa final de avaliação.**

Três consequências estruturais:

### 1. Uma porta única para extração

Toda estratégia — determinística, por biblioteca, por modelo — implementa o mesmo
contrato: documento canônico entra, registros validados saem. Trocar de estratégia é
trocar de objeto, sem alteração no núcleo.

### 2. Normalização fora da estratégia

```
estratégia A ──┐
estratégia B ──┼──► normalização ──► schema ──► registro validado
estratégia C ──┘   (a MESMA para todas)
```

A normalização vive no núcleo, **depois** da extração e idêntica para todos os braços.
É variável controlada, não objeto da comparação. Se cada estratégia normalizasse à sua
maneira, a diferença medida seria do encanamento.

### 3. Métrica por campo, não só agregada

Um índice global alto esconde um campo sistematicamente errado — que é justamente o
modo de falha mais caro a jusante. A avaliação reporta cada campo isoladamente e
expõe os piores.

Comparação numérica usa tolerância relativa: `"42"` e `42.0` são o mesmo valor.
Marcadores e texto usam igualdade exata, porque ali qualquer diferença é real.

## Estratégias mantidas para comparação

| Estratégia | Papel | Pergunta que responde |
|---|---|---|
| Leitura linear | piso | Quanto a reconstrução realmente ganha? |
| Detector pronto | alternativa convencional | A ferramenta padrão dá conta? |
| Reconstrução posicional | proposta | Vence as duas — e por quanto? |

As duas primeiras **não são código morto**: são a régua. Removê-las tornaria a
terceira uma escolha sem justificativa mensurável.

## Compromisso de honestidade

O relatório reporta o que for medido, não o que confirmaria a hipótese inicial.

Isso tem consequência concreta: se o detector pronto passar a funcionar bem — nova
versão, outro documento — a conclusão correta passa a ser adotá-lo, e o extrator
próprio vira complexidade injustificada. **Um resultado negativo é resultado.**

Vale também para a rota por modelo: se ela não superar a determinística, esse é o
achado, e ele é publicável.

## Consequências

- Custo real: manter estratégias que sabidamente perdem, e escrever testes para o
  próprio instrumento de medida.
- O instrumento é validado por mutação — sabotagens deliberadas (tolerância inflada,
  valor inventado não penalizado) precisam quebrar os testes. Um comparador que
  arredonda a favor produziria relatório convincente e conclusão falsa.
- A avaliação precisa ser reexecutada a cada troca de versão de componente: mudar uma
  peça no meio da comparação invalida os números anteriores.
- O conjunto usado para iterar **não é conjunto de validação final**. Ajustar decisões
  observando o mesmo conjunto enviesa; um subconjunto não visto deve ser reservado
  para o julgamento final.
