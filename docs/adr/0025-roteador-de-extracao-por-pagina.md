# ADR-0025 — Roteador de extração por página, sem estrutura declarada

**Status:** aceito · **Data:** 2026-08-11 · **Implementado e em produção (Cenário B):** 2026-08-11/12

> Validado de ponta a ponta contra documentos reais de um cenário corporativo
> separado (fora deste repositório) — ver "Cenário B" em `PLANO.md` pro
> estado exato e o que ainda falta (inclusive uma lacuna conhecida na
> consolidação, ADR-0017). O Cenário A não usa este roteador ainda.

## Contexto

Até aqui, `parser ingerir` — o comando de produção — processava qualquer
documento pelo mesmo caminho único: descobria (ou recebia do perfil) **um**
layout de tabela e rodava `ExtratorPosicional` sobre o intervalo de páginas
configurado. `triagem.Classe` (o que a página contém: dados, contexto ou
descartável) só filtrava páginas dentro/fora; nunca decidia *qual* extrator
usar. `diagnostico.py` já calculava, internamente, sinais por página
(rotação, ausência de camada de texto, texto vertical) mas descartava essa
granularidade ao agregar tudo num `Achado` por documento.

Isso bastava enquanto o único documento validado era o TACO — tabela
nutricional nativa, unidades entre parênteses. Não serve ao objetivo real: o
sistema precisa aceitar **qualquer PDF**, com ou sem tabela, nativo ou
escaneado, de qualquer domínio — e decidir sozinho, por página, qual
ferramenta ou modelo local usar. Sem isso, adotar um documento novo continua
exigindo que alguém declare `layout` ou `campos_na_ordem` no perfil antes de
rodar — o que o próprio ADR-0023 já nomeou como "configuração manual
disfarçada de automação". Pior ainda seria a alternativa que motivou este
registro: uma IA generalista (Claude, GPT) inspecionando o documento em tempo
de desenvolvimento para calibrar parâmetros manualmente. Isso serve para
experimento e depuração — nunca para produção, porque reintroduz exatamente
o humano-no-laço que o parser existe para eliminar.

A peça que faltava já estava desenhada em três ADRs, nenhum implementado:

- **ADR-0021** — característica estrutural é um eixo por página, ortogonal a
  `triagem.Classe`.
- **ADR-0023** — o prompt do modelo é montado do que foi detectado, não
  declarado por humano.
- **ADR-0024** — reconhecimento em três níveis de custo: sinal grátis →
  inspeção determinística → modelo descreve a estrutura.

Este ADR registra a integração que faltava entre essas três decisões e o
caminho de produção (`lote.py`), generalizando para além do formato do TACO.

## Decisão

**O parser decide a rota de cada página em tempo de execução**, num módulo
novo, `src/parser/planejador.py`, chamado por `lote.py` no lugar do único
`ExtratorPosicional` fixo que havia antes. Nenhuma chamada de rede ou de
modelo acontece dentro do planejador — ele só decide; quem executa é
`parser.fabrica` (função nova, `montar_extrator_para_decisao`) a partir da
decisão.

**Princípio-chave:** a agnosticidade não vem de uma geometria "inteligente o
bastante para qualquer tabela" — isso é pesquisa sem fim, e a calibração
geométrica (`parser.calibracao`) segue ajustada só ao que já foi medido. Vem
do **roteamento**: tentar o caminho barato primeiro e escalar honestamente
para o modelo local quando o determinístico não reconhece a estrutura, nunca
fingir sucesso.

Ordem de decisão por página, em custo crescente:

1. **Sem camada de texto** (`diagnostico.caracterizar_pagina`, sinal grátis) →
   rota OCR. Verificado **antes** de consultar `triagem.Classe`: zero
   palavras faria a triagem classificar a página como `DESCARTAVEL` por
   volume, o que descartaria uma página escaneada em vez de roteá-la para
   reconhecimento óptico — a densidade numérica que a triagem mede não
   significa nada sobre zero palavras.
2. **`Classe.DESCARTAVEL`** → nenhuma extração.
3. **`Classe.CONTEXTO`** → nenhuma extração nesta fatia (ver "fora do
   escopo" abaixo).
4. **`Classe.DADOS`, com texto** → tenta calibração geométrica
   (`calibracao.calibrar`) restrita àquela página. Confiança acima do limiar
   (0,75, o mesmo já usado antes desta mudança) → rota posicional, com o
   layout descoberto.
5. **Confiança insuficiente ou calibração sem estrutura reconhecível** → rota
   de texto por modelo (nível 3). `calibracao.descobrir_nomes_de_coluna` é
   chamado **só aqui** — nunca incondicionalmente — porque só faz sentido
   depois que a página já foi classificada como tabela. Quando há estrutura
   parcial (algumas colunas reconhecidas mesmo sem confiança suficiente para
   a rota posicional), a ordem descoberta monta o prompt (ADR-0023); quando
   não há nenhuma, o prompt cai para a forma genérica declarada, e o
   resultado carrega essa proveniência.

`fabrica.montar_extrator_para_decisao` monta o extrator a partir da decisão —
nunca do perfil, para layout e ordem de colunas. O perfil só entra para as
rotas de modelo, e só pelo que é configuração legítima de negócio (qual
modelo chamar, com que prompt-base) — nunca por como o documento está
estruturado. Quando a rota decidida exige configuração ausente (nível 3 sem
`llm`/`vlm` declarado; OCR sem layout disponível — ver limite abaixo), a
página vira **pendência explícita** (`RotaNaoConfigurada`), e as demais
páginas do arquivo continuam sendo processadas — o mesmo princípio de
`lote.py` de que uma falha não custa o resto do trabalho.

## Consequências

**A favor:** `parser ingerir` aceita documento sem perfil de estrutura
declarado; a mesma engenharia que antes decidia layout por confiança agora
decide **rota**; `descobrir_nomes_de_coluna` deixa de ser peça órfã ("só
teste", como a auditoria de 2026-08-02 registrou) e entra no caminho real de
produção; o princípio "falha alto, nunca lixo" se preserva — página sem
estrutura reconhecível vira pendência nomeada, nunca registro inventado.

**Contra:** o comportamento de uma pasta deixa de ser "um layout, um
resultado" e passa a ser por página, o que torna o log mais longo (mitigado
por um resumo agregado por rota, não por página individual). A escolha de
quando escalar de nível 2 para nível 3 usa um único limiar de confiança
(0,75) medido num documento só — o mesmo limite que a calibração já tinha.

## Limite declarado (fora desta fatia)

- **Nível 3 tem, por desenho, duas variantes — texto (`llm`) e visão
  (`vlm`)** (ADR-0024). Esta fatia implementa só a de texto. Não há ainda
  critério medido de quando uma página deveria escalar direto para VLM em
  vez de tentar a rota de texto primeiro; fica para quando houver documentos
  variados o bastante para medir a diferença.
- **OCR ainda depende de layout declarado no perfil como alternativa.** A
  calibração geométrica opera sobre a camada de texto nativa
  (`FontePDF`/`Palavra`); uma página sem essa camada não tem o que calibrar
  pela mesma rota. Descobrir layout a partir das caixas delimitadoras que o
  próprio OCR devolve é generalização plausível, mas não implementada nem
  medida — hoje, sem perfil declarando `rotas.posicional.layout`, uma página
  sem texto nativo vira pendência.
- **Decisão por página inteira, não por região.** Um documento com mais de
  uma tabela na mesma página, ou tabela e texto corrido misturados, recebe
  uma rota só. Roteamento por região fica para quando houver caso medido que
  o exija.
- **`Classe.CONTEXTO` não entra na extração** nesta fatia — mesmo
  comportamento de antes da mudança. Extrair informação de páginas de
  contexto (metodologia, glossário) é trabalho futuro, não regressão desta
  fatia.
- **Os achados dos itens P-1 do `PLANO.md`** (métrica que não penaliza
  fabricação, `--sem-modelos` incompleto, taxonomia `Classe` como enum
  exclusivo, suíte não-determinística) seguem abertos — pertencem ao núcleo
  compartilhado entre os dois contextos de uso do projeto, e são a próxima
  fatia, não esta.

## Não medido

Este ADR registra uma decisão de integração, não um resultado de
generalização. O que está medido é o que já sustentava ADR-0021/0023/0024
individualmente — um documento, uma família de layout. Continua em aberto
saber com que taxa a rota de texto (nível 3) produz saída aproveitável em
documentos de estrutura genuinamente diferente da tabela nutricional, e é
isso que a coleta de documentos por característica (`experimentos/pdf/`) e o
uso real no Cenário B vão responder.
