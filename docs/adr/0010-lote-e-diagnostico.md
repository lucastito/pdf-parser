# ADR-0010 — Lote como unidade de execução, e diagnóstico como conhecimento explícito

**Status:** aceito · **Data:** 2026-07-30

## Contexto

Até aqui o sistema processava **um documento por vez**, com o operador escolhendo o
arquivo, conferindo o resultado e repetindo. Isso descreve o experimento, não o
produto: o caso de uso real é alguém entregar um diretório com dezenas de documentos
heterogêneos e esperar a saída consolidada, com o mínimo de intervenção manual.

Duas dificuldades surgem juntas ao mudar de um para muitos, e por isso são decididas
juntas:

**A pasta não é homogênea.** Documentos de origens diferentes têm layouts diferentes.
Um parâmetro global por execução — o que bastava para um arquivo — passa a errar em
todos menos um.

**A falha deixa de ser excepcional.** Com um arquivo, falhar e parar é aceitável: o
operador vê, corrige, repete. Com cem, parar no terceiro desperdiça o processamento
dos outros noventa e sete, e o operador não fica olhando.

Há ainda um achado anterior que pesa na decisão. A rotação de página derrubava
**quatro ferramentas a zero de acurácia** — não a um valor ruim, a zero. O tratamento
vivia duplicado em dois extratores, com implementações diferentes, e um terceiro nem
tratava. O conhecimento existia, mas estava enterrado dentro de cada extrator: quem
escrevesse o próximo cairia na mesma armadilha.

## Opções consideradas

| Opção | Vantagem | Desvantagem |
|---|---|---|
| Laço externo (script chamando o parser por arquivo) | Nada a construir | Sem consolidação, sem log unificado; a falha de um vira falha do script |
| Lote com parâmetro global | Simples | Erra em pasta heterogênea, que é o caso real |
| **Lote com decisão por arquivo** | Acomoda pasta heterogênea | Mais caro por documento; exige critério de confiança |
| Diagnóstico dentro de cada extrator | Localidade | Foi o estado anterior: duplicado, divergente e incompleto |
| **Diagnóstico como módulo próprio** | Escrito uma vez, aplicável a qualquer rota | Mais uma camada a manter |

## Decisão

**Um arquivo é lote de tamanho 1.** Não há caminho especial para o caso único. Sem
isso, o comportamento diverge entre um e cem documentos, e o caso testado deixa de
ser o caso executado.

**A decisão de layout é por arquivo, não por lote.** A ordem é: layout descoberto
por calibração, se a confiança bastar → layout do perfil informado → falha registrada
com diagnóstico. O limiar de confiança é explícito
(`CONFIANCA_MINIMA_DE_CALIBRACAO = 0.75`): abaixo dele o layout descoberto é
descartado em favor do perfil, porque um layout inventado produz extração que roda
sem erro e grava lixo.

**Uma falha não interrompe o lote.** Cada arquivo problemático vira um registro de
falha com motivo e **ação recomendada**, e o processamento segue. Falha é dado de
saída, não interrupção.

**O diagnóstico é módulo próprio, e o lote o consulta.** Quando um arquivo falha, a
classificação da falha chama o diagnóstico para transformar `Exception: ...` em algo
acionável. Essa dependência é deliberada: uma falha sem ação recomendada é só
reclamação.

O diagnóstico tem duas famílias, com propósitos distintos:

| Família | Quando roda | O que pega |
|---|---|---|
| Diagnóstico de documento | antes da extração | rotação, ausência de camada de texto, texto vertical, fontes problemáticas |
| Validação de saída | depois da extração | resultado plausível mas errado — cobertura baixa, valores fora de faixa |

A segunda existe porque o modo de falha mais caro não é o erro ruidoso: é o resultado
que passa na validação de tipo, parece dado e chega ao consumidor. **Cobertura alta
com valores errados é pior que cobertura baixa.**

## Consequências

- O produto passa a atender o caso de uso real: uma pasta entra, uma saída
  consolidada sai, com log, erros e pendências ao lado.
- O que falta vira **lista curta de pendências**, não planilha inteira para
  reconferir. É o que dirige a atenção humana ao que precisa dela.
- Custo: calibrar por arquivo é mais caro que decidir uma vez por lote. Aceito
  porque a alternativa erra em pasta heterogênea, e a rota determinística tem folga
  de sobra contra o alvo de referência (ADR-0003).
- O código de saída distingue "tudo certo" de "saiu resultado, com perdas" — quem
  automatiza precisa dessa diferença, e ela não cabe num booleano.
- O conhecimento sobre o que sabota a extração fica **escrito uma vez**, aplicável a
  qualquer rota nova, em vez de redescoberto por quem escrever o próximo extrator.
- Risco assumido: o diagnóstico é heurístico e pode errar. Mitigado por severidade
  explícita (`bloqueia` | `alerta` | `nota`) — só a mais alta impede o uso do
  resultado, e nenhuma verificação depende de conhecer o domínio do documento.
