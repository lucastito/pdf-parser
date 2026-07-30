# ADR-0009 — Avaliação por gabarito como ferramenta de produto

**Status:** aceito · **Data:** 2026-07-29

## Contexto

Ao separar produto de material de validação, os módulos de avaliação exigiram uma
decisão que não era óbvia: eles servem a quem valida escolhas de projeto, ou a quem
opera o parser?

A resposta muda onde eles vivem, e por consequência o que a equipe que herdar o
projeto encontra ao abrir o código.

## Distinção adotada

**O mecanismo de avaliação é produto. Os dados de uma validação específica não são.**

Quem recebe o parser e o aponta para documentos próprios precisa responder às mesmas
perguntas que surgiram aqui: *isto está lendo certo? em que campo erra? posso confiar
antes de mandar para o sistema de destino?* Negar-lhe o instrumento obrigaria a
reimplementá-lo — e provavelmente pior, porque as armadilhas já foram encontradas.

| Fica no produto | Vai para o material de validação |
|---|---|
| Carregar gabarito de arquivo | O gabarito de um documento específico |
| Medir acurácia por campo | Os resultados de uma rodada |
| Conjunto de reserva como conceito | O conjunto de reserva transcrito |
| Comparar estratégias entre si | A comparação entre máquinas |
| Registrar procedência da execução | A procedência de uma máquina |

## O que a avaliação preserva do que foi aprendido

Cinco comportamentos, cada um resposta a um erro real cometido durante o
desenvolvimento:

1. **Correção do revisor vira valor de referência.** Uma marcação diferente de "ok" é
   lida como o valor correto. Sem isso, a acurácia seria medida contra o próprio erro
   do extrator.
2. **Alinhamento por identificador, com recuo para o número do item.** Algumas
   ferramentas fragmentam texto no meio da palavra; casar por nome descartava itens
   cujos valores estavam corretos.
3. **Métrica por campo, não só agregada.** Um índice global alto esconde um campo
   sistematicamente errado, que é o modo de falha mais caro a jusante.
4. **Tolerância relativa em comparação numérica.** `"42"` e `42.0` são o mesmo valor;
   acusá-los produziria relatório que grita sem motivo.
5. **Valor inventado é penalizado.** Um campo que o documento não afirma e o extrator
   preenche conta como erro, não como cobertura.

## Ordem de uso, do ponto de vista de quem opera

```
1. diagnosticar    o documento tem algo que sabota a leitura?
2. calibrar        qual o layout deste documento?
3. ingerir         processa o lote, consolida, lista pendências
4. avaliar         (opcional) confere contra um gabarito próprio
```

Os três primeiros bastam para operar. O quarto é para quem quer número antes de
confiar — e é o que permite dizer "este parser acerta 98% nos meus documentos" em vez
de "parece estar funcionando".

## Como construir um gabarito próprio

O procedimento é o mesmo que se mostrou válido aqui, e a ordem importa:

1. **Extrair uma amostra** de 30 a 50 itens e gravar num arquivo de conferência.
2. **Conferir à mão** contra o documento original, corrigindo o que estiver errado no
   próprio arquivo.
3. **Medir** as estratégias contra esse gabarito.
4. **Reservar um conjunto não visto** — itens de páginas que não participaram de
   nenhuma decisão, transcritos sem consultar a saída do extrator.

O passo 4 não é formalidade. Um gabarito **gerado** pelo extrator e apenas confirmado
mede aquela estratégia contra si mesma: ela acerta por construção. Só o conjunto de
reserva transforma "acurácia de 100%" em afirmação defensável.

Vale também pelo que revela do outro lado: o conjunto de reserva usado neste projeto
encontrou dois erros humanos de transcrição e um defeito no próprio código de
comparação. Conferência humana não é infalível, e medir os dois lados é o que expõe
isso.

## Consequências

- A equipe que herdar o projeto encontra o instrumento de avaliação, não apenas o
  resultado de uma avaliação alheia.
- O comando de avaliação exige que o gabarito seja informado — não há caminho padrão,
  e portanto nenhum dado de validação específica embutido no produto.
- Os arquivos de validação deste projeto ficam em diretório próprio, fora do pacote
  de produção, e não são necessários para executar o parser.
