# ADR-0003 — Rota determinística como caminho padrão

**Status:** aceito · **Data:** 2026-07-29

## Contexto

Há duas rotas possíveis para extrair conteúdo estruturado de documentos: regras
determinísticas sobre a camada de texto, ou um modelo de visão que lê a página
renderizada como imagem.

O ambiente-alvo de desenvolvimento impõe um teto: **~2 GB de memória de vídeo, 16 GB
de memória de sistema, processador de baixo consumo (15 W)**. Além disso, existe um
requisito não-funcional de referência: **documento de porte médio processado em menos
de 5 minutos**.

Essa restrição é um dado do projeto, não um acidente a contornar. Decidir sob ela é
parte do trabalho.

## Medição

Rota determinística, documento completo de 164 páginas, no ambiente-alvo:

| Etapa | Tempo |
|---|---|
| Leitura do arquivo | 0,59 s |
| Extração | 0,96 s |
| **Total** | **1,55 s** (9,4 ms por página) |

Contra o alvo de 300 s, a margem é de aproximadamente **190×**.

Quanto à rota por modelo: um modelo de visão de 7 bilhões de parâmetros, quantizado,
requer da ordem de **16 GB de memória de vídeo** para operar com imagem em resolução
alta — necessária para ler tabela densa. O ambiente-alvo dispõe de 2 GB. **A rota não
cabe**, e reduzir a resolução para caber destruiria justamente o detalhe que se quer
testar.

## Opções

| Opção | Vantagem | Desvantagem |
|---|---|---|
| **Determinística primeiro** | Cabe no ambiente; ~190× dentro do alvo; auditável; barata | Exige descrever o layout; frágil a mudança de diagramação |
| Modelo primeiro | Robusto a variação de layout; enxerga estrutura visual | Não cabe no ambiente-alvo; ordens de grandeza mais lenta; sem baseline não há como saber se ajuda |
| Só modelo, em serviço externo | Remove a restrição de hardware | Custo recorrente; dado sai do ambiente; ainda sem baseline de comparação |

## Decisão

**A rota determinística é o caminho padrão.** A rota por modelo é camada opcional,
adicionada quando houver infraestrutura, e sempre **medida contra** a determinística.

Duas razões independentes sustentam isso, e a segunda vale mesmo sem a primeira:

1. **Cabe no envelope e supera o alvo com folga.** Não há problema de desempenho a
   resolver.
2. **Sem baseline não há como afirmar que o modelo ajuda.** Introduzir o modelo antes
   de ter número de referência tornaria impossível justificar a escolha depois — o
   ganho seria alegado, não demonstrado.

## Consequências

- A porta `Extrator` mantém a rota por modelo plugável sem alteração do núcleo.
- Quando houver infraestrutura, a pergunta a responder está formulada e é mensurável:
  *o modelo supera a rota determinística neste documento, e a que custo?*
- **A resposta pode ser negativa**, e isso é um resultado publicável — não uma falha
  do experimento.
- Reduzir escopo por restrição de ambiente é decisão consciente, registrada aqui.
  Ambiente com mais memória de vídeo muda a análise, não a arquitetura.

## Dimensionamento, se a restrição for revista

| Uso | Memória de vídeo |
|---|---|
| Modelos de texto pequenos (até 4B) | 8 GB |
| **Modelo de visão 7B em resolução alta** | **16 GB** |
| Dois modelos simultâneos, para comparação | 24 GB |
