# ADR-0019 — Executar em máquina de terceiro: o que não se controla

**Status:** aceito · **Data:** 2026-07-31

## Contexto

O ADR-0013 desenhou a comparação entre máquinas e listou o que toda rodada
registra — incluindo "GPU e memória de vídeo". O desenho está certo; **falta o
como**, e o como reserva armadilhas que invalidam a medição em silêncio.

As máquinas do conjunto não são de laboratório. São computadores pessoais de
outras pessoas, com placas de **fabricantes diferentes**, usados para outras
coisas, operados por quem não acompanha o experimento.

Tudo aqui foi **verificado na máquina de referência**, não deduzido de
documentação.

## Decisão 1 — a leitura de memória de vídeo tem de ser a correta

**A interface padrão do sistema reporta memória de vídeo em campo de 32 bits.**
Uma placa de 12 GB reporta 4 GB. O valor não é aproximado: é truncado no teto.

Consequência direta para este experimento: um script que dimensionasse o modelo
por esse número mandaria a máquina grande rodar como pequena — e mediríamos a
decisão errada do script, não a máquina.

**Fonte adotada: o registro do sistema**, campo de 64 bits, **neutro de
fabricante**. As ferramentas de fabricante servem apenas para confirmar.

Dois casos que a verificação revelou e que não são erro:

- **Gráfico integrado não declara o campo** — usa memória do sistema
  dinamicamente. "Quanta memória de vídeo tem" não é pergunta bem posta ali, e
  precisa de tratamento próprio.
- **Máquina com duas placas** (integrada e dedicada) é comum em portátil.
  Escolher a correta e reportar; **nunca somar**.

Fontes divergentes viram **alerta**, não escolha silenciosa.

## Decisão 2 — contenção se detecta e se declara; não se impede

Um programa pesado aberto durante a medição disputa a placa de vídeo, e **nada no
número denuncia**. É a mesma classe de falha das medições concorrentes que o
ADR-0013 já trata com trava — mas ali o concorrente é nosso, e aqui é do dono da
máquina.

**Exclusividade de placa de vídeo não é possível**, e a limitação é do sistema
operacional:

- o agendador é multiplexado por projeto; não há reserva exclusiva para processo
  de usuário;
- quando a memória enche, o driver despeja por prioridade — e o programa em
  primeiro plano ganha do nosso, em segundo. O modelo é que seria empurrado para
  a memória principal;
- impedir outro programa de abrir exigiria privilégio administrativo e
  interceptação de processos: **comportamento de software malicioso**, inaceitável
  na máquina de quem está fazendo um favor.

**O que funciona, e foi verificado:** os contadores de desempenho do sistema
expõem **nome e identificador** de cada processo que usa a placa, sem depender de
fabricante. Dá para nomear o intruso no aviso — "feche o programa X" — em vez de
pedir algo genérico.

### A chamada interrompida refaz; não retoma

Duas razões, e a segunda basta sozinha:

1. O servidor não expõe ponto de retomada. Uma chamada é atômica para o cliente.
2. **Se houve disputa, aquela medição já está contaminada** — o tempo dela inclui
   a contenção. Retomar preservaria um número que não vale nada.

Daí duas consequências de desenho:

- **Pausar entre chamadas, nunca durante.** Matar uma geração de vinte minutos
  pela metade não recupera nada.
- **Blocos pequenos** — um modelo × uma configuração × uma página — limitam a
  perda a uma chamada. O custo é recarregar o modelo com mais frequência.

### Retomada: automática **e** manual, com guarda

O experimento vigia a placa e retoma sozinho quando o intruso fecha — quem está
jogando não volta ao terminal para autorizar. Mas também aceita comando manual,
**com uma guarda**: se a placa ainda estiver ocupada, o comando é **recusado** e o
alerta repetido.

Sem a guarda, bastaria confirmar cedo demais para o bloco recomeçar contaminado.

## Decisão 3 — a contaminação silenciosa é a que mais preocupa

Falhas ruidosas são baratas: aparecem e são investigadas. Estas produzem **número
plausível e errado**, que é o modo de falha que este projeto mais evita:

| Situação | O que o número diria | O que é |
|---|---|---|
| modelo não cabe na memória e cai para o processador | "esta máquina é lenta" | configuração |
| redução por temperatura em portátil | "as últimas medições pioraram" | térmica |
| modo de economia de energia | diferença entre máquinas | ajuste do sistema |
| modelo residual da rodada anterior | menos memória disponível | limpeza |
| servidor pré-instalado em versão diferente | divergência entre máquinas | **invalida a comparação** |

Todas precisam ser **detectadas e registradas**, não presumidas ausentes.

## Decisão 4 — a saída é acessível por padrão

**Requisito real, não hipotético:** quem opera o experimento usa leitor de tela.

Painel redesenhado no lugar do terminal — barra desenhada com caracteres,
animação, reposicionamento de cursor — **não expõe objeto de acessibilidade**: é
texto sobrescrito, que ou vira ruído contínuo ou fica mudo.

A primitiva de progresso do interpretador **expõe** esse objeto, como qualquer
janela de instalação do sistema. Usá-la resolve os dois públicos com um caminho
só.

Onde não houver primitiva, o modo acessível emite **uma linha nova por evento**,
com a informação em frase — "bloco 4 de 12 concluído em 19 minutos" — em vez de
desenho.

A escolha do modo é **automática**: o sistema informa se há leitor ativo
(verificado). Um parâmetro força qualquer um dos modos, porque detecção
automática pode errar.

## Consequências

- O que o ADR-0013 pede fica **executável**: "registrar memória de vídeo" tem
  agora um caminho que não mente acima de 4 GB.
- O experimento convive com o dono da máquina em vez de disputar com ele. Nenhuma
  medição contaminada entra no resultado, e ninguém precisa deixar de usar o
  próprio computador.
- **Perda máxima por interrupção: uma chamada.** O preço é recarregar o modelo
  com mais frequência.
- Custo declarado: o script fica bem maior do que "instalar, baixar, rodar". Cada
  verificação existe porque a alternativa é um número que parece resultado e não
  é.
- Risco que permanece: a lista de contaminações silenciosas não é exaustiva. Se
  aparecer resultado inexplicável, **suspeitar do ambiente antes da estratégia** —
  já aconteceu nesta sessão, com um parâmetro herdado que ninguém tinha declarado
  (ADR-0018).
