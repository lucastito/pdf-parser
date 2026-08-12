# Auditoria de 2026-08-02 — o que foi verificado, e o que caiu

Cinco frentes independentes revisaram pipeline, arquitetura, documentação, testes e
as entregas do dia. Este documento registra **o que foi confirmado abrindo o
código**, separado do que é hipótese, e o que cada achado obriga a mudar.

Ele existe porque uma sessão longa produziu afirmações de "pronto" que não
resistiram à verificação. O registro fica para que a mesma busca não se repita.

> **Documento irmão:** [`AUDITORIA_TECNICA_CIENTIFICA.md`](../AUDITORIA_TECNICA_CIENTIFICA.md),
> na raiz, é uma auditoria independente feita por outro modelo, com escopo mais
> amplo — segurança, cadeia de suprimentos, desenho estatístico, corpus e
> reprodutibilidade. Ela **antecipou** o achado da métrica descrito abaixo, e
> levanta pontos que as cinco frentes daqui não cobriram. Os dois se somam; onde
> divergirem, vale o que estiver verificado no código.
>
> **Este documento é histórico — não é atualizado.** Congelado no estado em que
> foi escrito, do mesmo jeito que um ADR preserva hipótese refutada. **O estado
> atual de cada achado (aberto, fechado, parcial), verificado no código, vive em
> [`PLANO.md`](../PLANO.md)**, seção "P-1" e "Mapa completo dos P0 da auditoria
> externa" — checado por último em 2026-08-12.

## O achado que precede todos os outros: a acurácia não penaliza invenção

**CONFIRMADO** em `src/parser/concordancia.py:198`:

```python
comuns = set.intersection(*(set(indices[n]) for n in estrategias))
```

Só entram na conta os itens que **todas** as rotas encontraram. Disso decorre:

- uma rota que **fabrica** linhas não é penalizada — as inventadas caem fora da
  interseção;
- uma rota que encontra **2 itens, ambos certos**, marca 100%;
- acurácia alta e cobertura baixa são indistinguíveis no número publicado.

**Não é hipótese.** Está nos resultados gravados
(`experimentos/resultados/titoslaptop/resumo.json`), na página de referência, que
tem ~31 itens:

| Rota | Registros | Cobertura publicada |
|---|---|---|
| `pdfplumber` | 31 | 1.0 |
| `posicional` | 32 | 0,97 |
| **`camelot`** | **62** | **1.0** |

Camelot produz o **dobro** dos itens que existem na página, e aparece com cobertura
plena e ~99% de acurácia. O excedente nunca foi contado contra ele.

**Consequência:** todo número de acurácia gravado até aqui mede *concordância entre
os itens que sobreviveram à interseção*, não fidelidade ao documento. Nenhum deles
sustenta a comparação entre rotas sem que erro por fabricação seja medido à parte.

Isto invalida a leitura dos resultados, **não os dados brutos** — as extrações
continuam em disco e podem ser reavaliadas com a métrica corrigida.

## Erros de modelagem

### A página de triagem foi modelada como escalar, e a correção já estava escrita

`src/parser/configuracao.py:204` — `pagina_de_triagem_declarada: int | None`.

O `ADR-0016` já continha, **datada de 2026-08-01**, a retificação de que a triagem
roda *"uma página de cada característica da taxonomia (ADR-0021), não uma página
só"*. O campo escalar foi implementado no dia seguinte.

Propagação verificada — o conserto toca todos estes pontos:

| Onde | O que fixa |
|---|---|
| `src/parser/configuracao.py:204,239-262` | campo e propriedade, tipados `int` |
| `perfis/nutricional.json:9` | `"pagina_de_triagem": 29` |
| `tests/test_configuracao.py:256-303` | **três testes que travam o erro** |
| `experimentos/scripts/medir_modelos_pagina29.py:53-59` | lê o escalar |
| `experimentos/scripts/ensaio_previo.py` | lê o escalar |
| `docs/GLOSSARIO.md:105-115` | descreve crescimento por característica que o campo não comporta |

O primeiro desses testes chama-se `test_a_pagina_de_triagem_e_uma_so_e_declarada` —
"é uma só" no próprio nome. **O teste codificou o defeito como comportamento
esperado**, que é o pior desfecho possível: a suíte agora defende o erro.

### A taxonomia não existe em código

`src/parser/triagem.py:36-44` — `Classe` é um `StrEnum` de três valores
**mutuamente exclusivos**. Uma página precisa poder ser `DADOS` **e** rotacionada
**e** com grade ao mesmo tempo (ADR-0021). Não há estrutura que associe uma página
a um *conjunto* de características.

`REQUISITOS.md:19` (RF-3) ainda descreve triagem **binária** — nativo × imagem —,
que é exatamente a formulação que o ADR-0021 registra como o erro da primeira
versão. O requisito nunca foi atualizado.

## Peças certas, fora do caminho

Três módulos fazem o trabalho pretendido e **não são chamados por quem decide**:

| Peça | Estado | Quem chama |
|---|---|---|
| `diagnostico.diagnosticar` | detecta rotação, camada de texto, fontes | a CLI (imprime e sai) e `lote.py` **só depois de a extração falhar**, para enfeitar a mensagem de erro |
| `calibracao.descobrir_nomes_de_coluna` | descobre colunas por geometria, sem conhecimento prévio | **nenhum módulo de produção** — só teste |
| `degraus._diagnostico_de_corte` | mensagem rica distinguindo corte de vazio | **ninguém**; `RespostaCortada` nunca é levantada |

Enquanto isso, `fabrica.py:111,129` monta a ordem das colunas **sempre** do JSON
escrito à mão.

É o mesmo padrão do `aferir`, que foi escrito e passou um dia inteiro sem uma única
chamada. A lição foi registrada no ADR-0018 e **não foi aplicada retroativamente**
ao resto do código.

Além disso, `diagnostico.diagnosticar` opera no **documento inteiro**, não por
página — embora internamente já liste páginas individuais. Sem achado por página
não há como classificar página por característica.

## A suíte não é determinística

Duas auditorias independentes, sem tocar o servidor de modelos, obtiveram
resultados **diferentes** em execuções repetidas da suíte completa:

- falhas variando entre `test_configuracao.py`, `test_degraus.py`,
  `test_consolidacao.py` e `test_extratores_alternativos.py`;
- **todos passam quando o arquivo roda isolado**;
- não há `pytest-randomly` — a ordem de coleta é determinística;
- pista registrada: um `_desrot_*.pdf` deixado para trás por um teste.

**Consequência:** o número "630 passando" é uma amostra de tamanho 1 de um processo
instável. Suíte que dá resultado diferente na mesma árvore não serve de guarda —
nem aqui, nem, sobretudo, na máquina de outra pessoa.

## Testes que não protegem o que parecem proteger

**CONFIRMADO por mutação** (mutação injetada, teste continuou verde):

- `tests/test_extratores_alternativos.py:24-29,46-52` — `assert isinstance(registros,
  list)`. `ExtratorPdfplumber.extrair` foi mutado para `return []` incondicional e
  os testes passaram. O `pdf_exemplo` tem tabela real: havia material para verificar
  conteúdo, e não se verificou.
- `src/parser/calibracao.py:204-209` — o guard `if len(unidades) < 3: raise` foi
  **removido inteiro** e nada falhou. A garantia mais citada do módulo — *"quando não
  encontrar estrutura, falha; devolver layout plausível e errado grava lixo"* — só é
  exercida sob `PARSER_DOCUMENTO_CASO`, que não está definida por padrão: **8 de 13
  testes do arquivo ficam saltados** numa rodada normal.
- `tests/test_lote.py:132-140` — `assert all(...)` sobre lista possivelmente vazia é
  vacuamente verdadeiro.

Fora isso, 14 mutações em comportamentos críticos **foram pegas** — consolidação,
alinhamento por identificador, dimensionamento de contexto, degraus, trava de
processo morto, base-0. Essa parte da suíte protege de fato.

## Uma discordância entre auditorias, resolvida abrindo o código

A auditoria de testes concluiu que os cinco defeitos fecharam **por classe**. A
auditoria das entregas concluiu que dois fecharam **parcialmente**. Verificado:

```
testar_degrau_esquema.py:168   "num_ctx": rota.extras["contexto"]   ← valor fixo da rota
reconhecer_estrutura.py:109    "num_ctx": 6000                      ← cravado
```

A segunda está certa. **4 de 7 scripts aferem o contexto; 3 não.**

O erro da primeira é instrutivo e vale como norma: ela mutou
`test_rotas_por_modelo_declaram_contexto`, que verifica se o **perfil declara**
contexto. Mas o defeito não é o perfil não declarar — é o **script usar valor fixo
em vez de aferir**. A guarda testava a coisa vizinha, e a mutação a confirmou.

> **Norma:** ao dar um defeito por fechado, mutar o **caminho real de produção**, não
> uma guarda adjacente que menciona o mesmo assunto.

O mesmo vale para a página: `PAGINA = 29` permanece em `validar_prompt.py:51`,
`remedir_vlm_pagina_inteira.py:41`, `testar_degrau_esquema.py:37` e
`reconhecer_estrutura.py:89`. O commit que adicionou `aferir` a dois desses arquivos
**não trocou a constante de página neles** — a correção "por classe" foi por caso,
dentro do próprio commit que a anunciava.

## Documentação: afirmações falsas

| Onde | Diz | É |
|---|---|---|
| `PLANO.md:124` | 8 de 8 rotas no `resumo.json` | **7** (a linha 484 do mesmo arquivo diz 6) |
| `docs/adr/0017-*.md:3-5` | "proposto — a implementação não começou" | `consolidacao.py` tem 523 linhas e 35 testes |
| `PLANO.md:753` | 22 testes de consolidação | 35 |
| `docs/adr/0007-*.md` | OCR a 84,5% | ADR-0006 mede 99,5% na mesma rota; o índice já usa 99,5% |
| `PLANO.md:69-101` | itens 7,8 em P1 e **de novo** 7,8 em P3; cita "item 9" | não existe item 9, nem itens 1-4 |

`REQUISITOS.md` e `SPEC.md` **não citam** os ADRs 0017, 0021, 0022, 0023 nem 0024.
Quem lesse só a especificação não saberia que este desenho existe.

## Da auditoria independente: dois achados verificados aqui

O documento irmão levanta muito mais que isto. Registro os dois que reproduzi
abrindo o código, porque mudam o que precisa ser feito antes de distribuir.

### `--sem-modelos` não desliga todos os modelos

**CONFIRMADO** — `src/parser/fabrica.py:183` exclui apenas os nomes exatos `"llm"`
e `"vlm"`:

```python
if not incluir_modelos and nome in ("llm", "vlm"):
```

Executado contra o perfil real:

```
rotas com --sem-modelos: camelot, linear, ocr, pdfplumber, posicional, pymupdf, vlm-menor
```

`vlm-menor` **passa pelo filtro** e dispara carga de modelo numa execução que pediu
explicitamente para não usar modelo. Aqui custa uma surpresa; na máquina de outra
pessoa, custa horas de espera sem explicação — e contamina qualquer tempo medido em
paralelo.

A correção não é acrescentar `"vlm-menor"` à lista: seria de novo por caso. Cada
rota precisa **declarar** se usa modelo, e o filtro operar sobre a propriedade.

### A métrica: o mesmo achado, por outro caminho

O documento irmão chegou ao problema da acurácia antes desta auditoria, e com uma
evidência adicional: no conjunto de reserva há rotas com **278-309 itens extraídos
para 10 itens de referência**, ainda assim com acurácia de 100%.

Ele nomeia o que a métrica atual realmente é: **recall condicional dos campos do
gabarito** — não acurácia. E indica o conserto: alinhamento por emparelhamento
explícito, contagem de verdadeiros positivos, falsos positivos e falsos negativos,
duplicatas e itens sem chave; publicar precisão, recall e F1; falhar diante de
chave duplicada em vez de sobrescrever; **renomear a métrica histórica** para que
os números antigos não sejam lidos como se fossem os novos.

### O que não reproduzi

O `F841` que ele reporta em `medicao.py:81` **não existe mais** — `flake8` passa
limpo. Foi corrigido no caminho, entre a auditoria dele e esta.

Os achados de segurança (isolamento de processo, limites de recurso, injeção de
instrução via PDF, fórmula em CSV começando por `=`) **não foram verificados
aqui** e continuam em aberto. Não são hipóteses descartadas; são trabalho não
feito.

## O que passou íntegro

- os 51 itens abertos batem exatamente com a contagem por seção, e a seção 4 tem os
  21 itens;
- os 24 ADRs estão indexados sem lacuna;
- a guarda de confidencialidade tem 9 verificações e nenhum vocabulário restrito
  vazou em nenhum arquivo auditado;
- a trava de processo morto trata corretamente o caso do Windows (`OSError`
  winerror 87), com teste contra processo real;
- a guarda de paridade da escada de modelos funciona;
- a isenção de `/api/tags` na guarda de teto de tempo **não** enfraqueceu a guarda —
  são consultas de estado, não geração, e a mutação confirmou que geração com teto
  continua sendo pega.

## O que isto obriga, em ordem de dependência

A ordem não é de esforço, é de dependência: cada item torna o seguinte possível.

1. **Métrica que separa acerto, omissão e fabricação.** Sem isso, nenhuma medição
   nova vale mais que as antigas. Erro por invenção precisa de número próprio.
2. **Suíte determinística.** Guarda que dá resultado diferente na mesma árvore não
   guarda nada — e é o que iria para a máquina dos outros.
2b. **Rota declarando se usa modelo**, com `--sem-modelos` filtrando por essa
   propriedade. Pequeno, e bloqueia distribuição: hoje quem pedir para não usar
   modelo carrega um mesmo assim.
3. **Diagnóstico por página**, reaproveitando o que já lista páginas internamente.
4. **Característica como conjunto por página** — o segundo eixo do ADR-0021.
5. **Perfil com N páginas de triagem por categoria**, substituindo o escalar, e os
   três testes que o defendem reescritos para verificar o **mecanismo de
   descoberta**.
6. **Seleção por cobertura mínima** — mínimo de páginas, mínimo de documentos,
   cobertura total das características.
7. **Reconhecimento/calibração → prompt** (ADR-0023), com o prompt do perfil
   rebaixado a alternativa declarada.
8. **`Pipeline` roteando por característica** — hoje usa um extrator único para o
   documento inteiro (`pipeline.py:97`); documento misto exige rotas diferentes na
   mesma execução.
9. **Só então congelar o prompt e medir.** Congelar antes fixaria a configuração
   manual, que é o que se quer justamente evitar medir.

## Sobre as medições já feitas

Viram **linha de base**: registram o que se sabia antes, e não são apagadas.

Se a análise **descobrir** que a página de referência é de fato a melhor do
documento-caso para a característica dela, as medições feitas nela se reaproveitam —
terão sido feitas na página certa, ainda que por caminho manual. Se apontar outra
página, elas não servem como ponto extremo da curva, e a máquina de referência
precisa ser remedida na página descoberta.

Essa decisão é da evidência, não de quem escreve.
