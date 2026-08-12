# Plano — pdf-parser (Cenário A e Cenário B)

> Atualizado em **2026-08-12**. Este arquivo cobre os dois cenários que
> compartilham o mesmo código (ver [CLAUDE.md](CLAUDE.md), "Dois cenários
> de uso"): **Cenário A** — o experimento científico, mantido neste
> repositório — e **Cenário B** — um cenário de uso corporativo, mantido em
> repositório privado separado, fora daqui.
>
> **Aviso sobre nomenclatura, pra não confundir:** a seção "Duas entregas",
> logo no início do bloco do Cenário A mais abaixo, foi escrita **antes de o
> Cenário B existir** e chama de "Produto" um entregável do **próprio
> Cenário A** — a ferramenta genérica de pesquisa como projeto pessoal, não
> o uso corporativo. É coincidência de nome entre dois conceitos diferentes.

## Índice por escopo

| Escopo | Onde |
|---|---|
| **Só Cenário B** (uso corporativo, fora deste repositório) | seção "Cenário B", logo abaixo — resumo mínimo; o detalhe vive no repositório privado |
| **Só Cenário A** (experimento científico) | o resto do arquivo, a partir de "Cenário A — Experimento científico" |
| **Os dois** (código compartilhado) | ver [CLAUDE.md](CLAUDE.md), tabela "O que é compartilhado" — o achado abaixo sobre `concordancia.py`/`consolidacao.py` é o **mesmo** P-1.1 descrito na seção do Cenário A, porque o código é o mesmo — não são dois problemas, é um problema citado nos dois lugares por necessidade de contexto |

---

## Cenário B

> Este repositório não é o ponto de retomada do Cenário B — só registra o
> que afeta código **compartilhado**, porque isso importa pra quem trabalha
> aqui também. Detalhe operacional do Cenário B vive no repositório privado.

O roteador de extração por página (ADR-0025), a consolidação por voto célula
a célula (ADR-0017) e o vocabulário de campo esperado (`vocabulario.py`) são
usados em produção nesse cenário desde 2026-08-11/12, validados contra
documentos reais.

### ✅ Pendência em código compartilhado — fechada em 2026-08-12

**Era o mesmo P-1.1** descrito em "P-1 — o que as auditorias de 02/08 puseram
na frente de tudo", mais abaixo — `concordancia.py`/`consolidacao.py` são
módulos **compartilhados**, o código é idêntico para os dois cenários.

- **`concordancia.py` ganhou `itens_exclusivos`** — os itens que uma rota
  produziu e não entraram na interseção aparecem no relatório, com aviso
  explícito. Isso é **visibilidade**, não **penalização**: a `taxa` de
  concordância continua calculada só sobre a interseção, e um item fabricado
  não reduz esse número. Isso não mudou.
- **A rota `"consolidado"` (`planejador.py`) tinha uma lacuna real:** ela
  chamava `consolidar(saidas)` com **todos** os itens de **todas** as
  rotas, inclusive os exclusivos. Um item que só uma rota "lia" (podendo ser
  fabricação — o caso medido no corpus é o Camelot devolvendo 62 registros
  pra uma página de ~31) virava um **voto único** no resultado final, com
  confiança **0,9** — quase tão alta quanto concordância plena, sem checar
  se aquele item veio de uma rota historicamente propensa a inventar linha.
  **Corrigido com `Desfecho.ITEM_EXCLUSIVO`** (ADR-0017): item presente em
  só 1 das N≥2 rotas ativas vira pendência de revisão humana, não voto
  automático; cobertura parcial genuína (2+ de N concordando) continua com
  confiança normal.

### Limites declarados em código compartilhado

- **Piso de imagem relevante (`AREA_MINIMA_DE_IMAGEM_RELEVANTE = 0.02`,
  `diagnostico.py`) é calibração sobre dois documentos, não medição.** Sem
  ele, todo logotipo de cabeçalho disparava VLM em toda página. Com ele, uma
  imagem pequena mas informativa fica de fora.
- **Peso da votação em `consolidacao.py` continua uniforme e provisório**
  (herdado do ADR-0017) — calibrar exige a matriz de correlação de erro
  entre rotas, que só existe depois de medição.
- **Enum/faixa do vocabulário (`vocabulario.py`) casam por número de linha,
  não por coluna** — um limite genérico do leitor de planilha de schema,
  independente de qual planilha for usada.

---

## Cenário A — Experimento científico

> Atualizado em **2026-07-31**. Este bloco é o ponto de retomada do Cenário
> A: diz o que falta, em que ordem, e **por quê** cada item vem antes do
> seguinte.
>
> O que já foi feito não aparece aqui — está nos ADRs e no histórico do git.

## Duas entregas, e a ordem entre elas

| # | Entrega | Prazo |
|---|---|---|
| 1 | **Produto** — preencher planilha sozinho, pendência para revisão humana | prioridade declarada |
| 2 | **Artigo** — submissão a periódico de análise de documentos | **15/11/2026**, rede em 31/01/2027 |

A ordem é essa e não se inverte. A boa notícia é a sobreposição: **a taxonomia, a
consolidação por campo e a métrica erro × omissão servem às duas** — são
requisito do produto e contribuição do artigo ao mesmo tempo.

## ⭐ Ordem de execução — 59 itens abertos

> **Isto é uma ordem, não uma lista.** São **59 itens abertos** neste documento,
> e o que está abaixo diz em que sequência atacá-los — nada é removido nem
> substituído. O detalhe e a justificativa de cada um vivem na seção
> correspondente adiante.
>
> A distinção não é formal: ao resumir a lista, a seção 4 — sozinha com **21
> itens** — desapareceu três vezes nesta sessão. Contagem por seção:

| Seção | Abertos |
|---|---|
| **4. Outras máquinas** | **29** — cresceu em 02/08: AMD, Linux, dependências de sistema |
| 1. Rotas por modelo | 8 |
| 6. Relatórios e artigo | 7 |
| 2. Consolidação por campo | 5 |
| 5. Taxonomia | 4 |
| 0. Contexto (refazer visão) | 3 |
| 3. TACO completo | 2 |
| 5b. Outros formatos | 1 |

> **A ordem tem uma razão:** distribuir é uma das **últimas** etapas — depois que
> os amigos rodarem, o que resta é consolidar e escrever. Cada rodada lá custa
> horas, e bug que chega lá custa uma refação que não se pode pedir. Daí a
> **tolerância zero**: tudo que é necessário para rodar na máquina deles precisa
> estar pronto e testado **antes**.

### ⚠ P-1 — o que as auditorias de 02/08 puseram na frente de tudo

**Duas auditorias independentes** revisaram o projeto no mesmo dia: uma por outro
modelo, com escopo amplo ([`AUDITORIA_TECNICA_CIENTIFICA.md`](AUDITORIA_TECNICA_CIENTIFICA.md)),
e uma em cinco frentes internas ([`AUDITORIA-2026-08-02.md`](experimentos/AUDITORIA-2026-08-02.md)).
Elas convergiram num achado que **precede todo o resto**, e a prioridade agora é
resolver o que elas apontaram.

| # | O que | Por que antes de tudo |
|---|---|---|
| −1.1 | **Métrica que penalize fabricação** | ✅ **Fechado em 2026-08-12.** `concordancia.py:198` usa `set.intersection` e continua medindo só a interseção — isso não mudou, é o papel de `concordancia.py` — mas a lacuna que publicava o item fabricado como dado (na consolidação, não na medição) foi fechada; ver "Cenário B" no topo deste arquivo e ADR-0017 |
| −1.2 | **Suíte determinística** | ⚠ **Investigado a fundo em 2026-08-12, não reproduzido — não é o mesmo que fechado.** Duas auditorias tiveram falhas **diferentes** na mesma árvore, isoladas todas passavam. Tentativas de reprodução hoje: 3 rodadas completas em ordem fixa, 4 rodadas com ordem **de verdade** embaralhada (`pytest-randomly`, sementes 111/222/333/42 — `PYTHONHASHSEED` não é fixo neste ambiente, então cada rodada já usava semente de hash diferente) e leitura de código dos 4 módulos citados (`configuracao.py`, `degraus.py`, `consolidacao.py`, `concordancia.py`) atrás de `set()` sem `sorted()`, mutação de `os.environ` fora de `monkeypatch`, `lru_cache` compartilhado, threading — nada encontrado; todo `set()` nos dois últimos módulos já passa por `sorted()` antes de virar saída. **Todas as sete rodadas passaram integralmente.** A única pista que este arquivo registrava (arquivo temporário deixado para trás) já tinha sido corrigida — nome único + limpeza — **antes** da auditoria de 02/08 encontrar a instabilidade, e não explicaria falha em `test_configuracao.py`/`test_degraus.py`, que não tocam PDF. **`pytest-randomly` adotado permanentemente** (`pyproject.toml`) como tripwire: se a instabilidade for real e só não apareceu hoje, uma rodada futura com ordem embaralhada tem mais chance de expor. **Gatilho automático de captura criado** (`tests/_gatilho_instabilidade.py`, testado em `tests/test_gatilho_instabilidade.py` contra um caso real e controlado de contaminação entre testes): quando um teste falha rodando a suíte completa, grava sozinho — sem precisar de ninguém notar na hora — a ordem exata dos testes que rodaram antes, a semente do `pytest-randomly`, e o resultado de rodar o mesmo teste sozinho num processo novo (confirma ou não o padrão "passa isolado, falha no conjunto"), tudo em `diagnostico-instabilidade/` (fora do git). Guarda instável não guarda nada — e é o que iria para a máquina dos outros; permanece aberto até haver uma falha real para investigar, não uma hipótese |
| −1.3 | **`--sem-modelos` filtrando por propriedade** | ✅ **Fechado.** `fabrica.py` filtra por identidade de função (`ROTAS.get(nome) in (_llm, _vlm)`), não por nome exato — cobre `vlm-menor`/`llm-menor`. Teste dedicado: `tests/test_fabrica.py::test_exclui_tambem_as_variantes_menores_de_modelo`. Esta linha estava desatualizada: o código já tinha corrigido antes de o texto ser revisado |
| −1.4 | **Diagnóstico por página → característica → páginas de triagem** | ✅ **Parcialmente fechado em 2026-08-12** — ver detalhe logo abaixo. Destrava os perfis; os perfis destravam a distribuição |

Fora desses, seguem **abertos e não verificados** os achados de segurança da
auditoria independente: isolamento de processo, limites de recurso, injeção de
instrução vinda do PDF, e célula de planilha começando por `=`. Não são hipóteses
descartadas — é trabalho não feito.

### −1.4, o que foi fechado e o que continua aberto — 2026-08-12

**Correção de escopo, feita ao planejar, antes de escrever código:** o
`ADR-0021` diz explicitamente que a taxonomia é *"um segundo eixo de
classificação da página, ao lado de `triagem.Classe` — e não um módulo
novo"*. `Classe` (DADOS/CONTEXTO/DESCARTÁVEL) não devia virar conjunto — é
uma classificação grosseira intencional, que continua exclusiva de
propósito. E a característica **já é** um conjunto em produção: `achados =
{a.codigo for a in caracterizar_pagina(...)}` já existe em
`planejador.py:132`, testado, sem enum exclusivo. Não havia necessidade
(nem justificativa no próprio ADR) de mexer em `planejador.py`/`Classe` —
seria risco em código de produção já validado, sem ganho.

Também **não faz parte deste item**, ainda que relacionado: fazer
`pipeline.Pipeline` (Cenário A) rotear por página durante a extração — isso
é a outra metade do **P0.5** ("fechado só para o Cenário B"), rastreada à
parte, não duplicada aqui.

**Fechado:**
- `diagnostico.caracterizar_documento(caminho)` — `caracterizar_pagina`
  para todas as páginas do documento, de forma estruturada
  (`{página: [Achado, ...]}`), em vez de só por-página isolada ou agregada
  em texto (`diagnosticar`, que cita número de página dentro da string
  `detalhe`, não como dado consultável).
- `diagnostico.paginas_por_caracteristica(...)` — a relação inversa,
  código de achado → páginas que o têm; a forma que escolher página de
  triagem por característica precisa.
- `Perfil.paginas_de_triagem_declaradas: dict[str, list[int]]` substitui o
  escalar `pagina_de_triagem_declarada: int | None` — N páginas **por
  característica**, não um valor só pro documento inteiro.
  `perfis/nutricional.json` migrado (`"pagina_de_triagem": 29` →
  `"paginas_de_triagem": {"pagina-rotacionada": [29]}`); os dois scripts
  que liam o campo antigo (`medir_modelos_pagina29.py`, `ensaio_previo.py`)
  atualizados.
- Validado contra documento real do corpus (36 páginas,
  `NARA_JFK_104-10095-10314_skew.pdf`), não só sintético — rodou limpo.

**Ainda aberto, de propósito, fora do escopo de hoje:**
- Os achados estruturais cobrem só 5 características (rotação, ausência de
  texto, texto vertical, mapa de caracteres, imagem embutida) — a taxonomia
  completa do `ADR-0021` (19 códigos em `CARACTERISTICAS.md`, eixos
  layout/degradação/domínio) continua maior do que o que há em código; o
  próprio ADR já declara isso "aberto".
- P0.5 (Cenário A, `pipeline.Pipeline` sem roteamento por página) — item
  separado, não tocado.
- O algoritmo de "quantas páginas por característica" continua sem regra
  fechada — o `ADR-0021` só fixa o princípio ("1 por combinação relevante,
  sem duplicar coleta"), não o "quantas". `Perfil` agora **comporta** N; o
  "como escolher N" ainda é decisão de quem monta o perfil, não automação.

### Mapa completo dos P0 da auditoria externa (`AUDITORIA_TECNICA_CIENTIFICA.md`)

> **Verificado item a item em 2026-08-12, lendo o código atual — não o resumo da
> auditoria.** A tabela P-1 acima só nomeava 4 pendências; a auditoria externa
> tem **sete** achados P0, e três delas (P0.2, P0.3, P0.4) nunca tinham entrado
> em lugar nenhum deste plano. Ficam aqui, por completo, pra isso não se repetir.

| # | O que a auditoria pede | Estado verificado em 2026-08-12 |
|---|---|---|
| P0.1 | Métrica que penalize itens fabricados/duplicados | ✅ **Fechado em 2026-08-12** — é o mesmo −1.1 acima. `itens_exclusivos` (`concordancia.py`) continua sendo visibilidade, não penalização — isso não mudou — mas a lacuna da consolidação (item que só uma rota leu virando voto único a 0,9 de confiança) foi fechada com `Desfecho.ITEM_EXCLUSIVO`; ver "Cenário B" no topo deste arquivo e ADR-0017 |
| P0.2 | Holdout deixou de ser independente (já revelou bug, código foi corrigido em resposta) — precisa de teste final **novo**, nunca tocado | **Aberto, nunca rastreado antes de hoje.** Nenhum arquivo do repositório reclassifica `holdout.csv` como "desenvolvimento" nem propõe um teste final intocado |
| P0.3 | Gabarito (`taco.csv`) sem dupla anotação, cegamento nem adjudicação | **Aberto, nunca rastreado antes de hoje.** `experimentos/golden/README.md` descreve conferência de **uma pessoa só** — ver a seção "Limite declarado" adicionada lá em 2026-08-12 |
| P0.4 | Protocolo dos degraus no experimento diverge do caminho de produção (contexto/seed/temperatura/raciocínio não propagados; prompt não é o mesmo) | **Aberto, nunca rastreado antes de hoje.** `src/parser/cli.py:526` monta `SaidaEmDegraus(_cliente(rota), campos)` sem propagar nenhum desses parâmetros da rota, e o prompt é montado ad hoc, não reaproveitado do caminho real |
| P0.5 | Pipeline principal não roteia por características da página (`lote.py` chamava `ExtratorPosicional` direto) | **Fechado — só para o Cenário B.** `ingerir()` roteia por página por padrão (`calibrar_por_arquivo=True` → `planejador`, ADR-0025). O Cenário A (`pipeline.Pipeline`) continua com um extrator só, sem essa ligação |
| P0.6 | Sem fronteira de segurança pra entrada não confiável (sandbox, limites de recurso/tempo/páginas/pixels) | **Aberto**, já citado no parágrafo acima desta tabela |
| P0.7 | Ambiente não travado (dependências sem teto de versão, sem lockfile, sem CI, tags de modelo mutáveis) | **Parcialmente fechado.** `pyproject.toml` agora declara `pdfplumber`/`camelot-py`/`pytesseract`/`Pillow`/`psutil` (faltavam antes) — mas continua sem teto de versão, sem lockfile (`uv.lock`/equivalente) e sem CI |

Achados adicionais da mesma auditoria, fora da lista de sete, também nunca
rastreados antes de hoje — **verificados no código, não supostos**:

| Achado | Onde | Estado verificado em 2026-08-12 |
|---|---|---|
| Proveniência mistura "como foi obtido" com "o quanto é confiável" | `ollama.py` marca saída de LLM/VLM como `Origem.EXTRAIDO` — mesma categoria de uma leitura por coordenada | **Aberto.** `modelo.py` só tem `EXTRAIDO`/`DERIVADO`/`INFERIDO`/`AUSENTE`; não existe eixo separado pra "método de obtenção" |
| Schema do degrau é fraco; corte (`done_reason=length`) só é detectado quando a resposta vem **vazia** | `degraus.py`, `_esquema()` e `_tentar()` | **Aberto.** Uma resposta não vazia mas cortada no meio de um JSON sintaticamente válido pode passar sem ser marcada como corte |
| Trava de `medicao.py` não é atômica (checar-depois-escrever, não `O_CREAT\|O_EXCL`) | `medicao.py`, função de trava | **Aberto** — risco de corrida real entre dois processos, não hipotético |
| Guarda de confidencialidade: uma exceção de allowlist libera a **linha inteira**, não só o trecho permitido | `.githooks/verificar.py`, `_coberta_por_excecao` | **Aberto.** Um termo proibido na mesma linha de um termo permitido passaria sem ser barrado |
| Contradição no prompt de texto: a instrução manda alinhar por posição quando a ordem é informada, e o guardrail dizia "nunca por posição" sem essa exceção | `prompts/extracao-tabela-texto.md` | **Corrigido em 2026-08-12** — guardrail reescrito pra citar a exceção explicitamente |
| `experimentos/golden/README.md` descrevia `taco.csv` como "a criar", apesar de o arquivo já existir e já ser usado por toda a matriz de avaliação | `experimentos/golden/README.md` | **Corrigido em 2026-08-12** |

### ⚠ Conflito de prioridade entre este plano e a auditoria externa — real, não hipotético

**Achado em 2026-08-12, ao responder se havia algo em `PLANO.md` que contrariasse
as auditorias.** Havia: a ordem P-1 → P0 (fechado) → **P1 (antes de distribuir)**
→ P2 → P3 (fecha o artigo) deste plano só bloqueia em **4** dos **7** P0 da
auditoria externa. Nada aqui impede, hoje, avançar pra P1/P2/P3 — inclusive
rodar o experimento nas máquinas de outras pessoas e escrever o artigo — com
P0.2 (holdout não independente), P0.3 (gabarito sem dupla anotação), P0.4
(protocolo dos degraus divergente) e P0.6 (sem fronteira de segurança) ainda
abertos.

Isso colide direto com a seção 14 da própria auditoria externa
("Critérios de aceite antes de submeter o artigo"), que lista golden
independente com dupla anotação, teste final nunca usado em desenvolvimento e
configuração íntegra por execução como **pré-requisitos**, não como itens
paralelos — e com a ordem de fases dela (Fase 0 → 1 → 2 → 3), que coloca
corpus/anotação/segurança **antes** de qualquer campanha confirmatória.

**Bloqueio explícito, a partir de agora:** P1, P2 e P3 abaixo **não devem
avançar para o ponto de gerar resultado citável no artigo (P3) nem para rodar
a bateria nas máquinas de terceiros (P1) enquanto P0.2, P0.3, P0.4 e P0.6
continuarem abertos.** Preparar o pacote de distribuição (o lado de
engenharia de P1 — detecção de ambiente, contenção, robustez) pode seguir em
paralelo, porque não depende deles; **rodar a campanha e publicar o número,
sim, depende**.

### 🔑 O corpus existe: 19 PDFs, 16 características cobertas

**Fechado em 02/08.** O gargalo declarado por meses — "só há um documento-caso" —
deixou de existir. O corpus está em [`experimentos/pdf/`](experimentos/pdf/), com
[`manifest.yaml`](experimentos/pdf/manifest.yaml) declarando, por documento: SHA-256, páginas,
proveniência, situação de redistribuição e **características confirmadas por
página, com a evidência de cada uma**.

| | |
|---|---|
| Documentos | **19** |
| Características com ao menos um caso | **19 de 19** |
| Reproduzíveis por link público | 16 de 19 |
| Critério de seleção | [`pdf/CARACTERISTICAS.md`](experimentos/pdf/CARACTERISTICAS.md) |
| Método da busca (743 PDFs varridos) | [`pdf/TRIAGEM.md`](experimentos/pdf/TRIAGEM.md) |

**Este é o insumo da etapa que destrava todo o resto.** A sequência, e a razão de
cada seta:

```
experimentos/pdf/  →  descobrir descrição de cada PDF      (metadados + determinismo + modelo)
                   →  descobrir características por página (taxonomia, ADR-0021)
                   →  escolher páginas de triagem          (1 por característica, incl. mista)
                   →  gerar os perfis                      (N páginas por categoria)
                   →  derivar o prompt de cada modelo      (ADR-0023)
                   →  DISTRIBUIR
```

**O endereço `experimentos/pdf/` é o que se passa à ferramenta de descoberta** — não
um documento por vez, não uma página escolhida à mão.

Sem essa etapa não há perfil; sem perfil não há página de triagem; sem página de
triagem a distribuição mede a configuração manual de quem escreveu o prompt, que é
exatamente o que o experimento existe para evitar.

O que **não** existe hoje para isso, confirmado pelas auditorias: `diagnosticar`
roda no documento inteiro e não por página; a taxonomia não tem estrutura em código
(`triagem.Classe` é enum de três valores exclusivos, quando uma página tem várias
características); e o perfil comporta **uma** página de triagem, não N.

### 📌 Regra: a alocação de modelos só fecha com as máquinas medidas

**Fonte única:** [`ALOCACAO-POR-MAQUINA.md`](experimentos/ALOCACAO-POR-MAQUINA.md) define quem
roda o quê. [`MODELOS.md`](experimentos/MODELOS.md) define a escada e **referencia** aquele
documento em vez de repetir a tabela — ela já existiu em três lugares e os três
divergiram.

**Em código, a fonte é `src/parser/escada.py`** — nome, rota, tamanho verificado no
catálogo, fabricante e a pergunta que cada degrau responde. O instalador e a linha
de comando **derivam** dela; nenhum dos dois escreve modelo à mão. Para acrescentar
um modelo à escada, é o único arquivo a tocar. `alocar()` devolve os três conjuntos
de uma máquina — obrigatório, estendido e o de falha proposital — a partir de placa,
memória livre e se a placa **de fato acelera**, que é medição, não nome de peça.

**Ela é rascunho, e permanece assim até que as seis máquinas relatem** placa,
memória total e livre, e a **divisão real medida** por `/api/ps` — não inferida do
nome da placa. Só então o martelo é batido e o aviso de rascunho sai.

Motivo: a tabela atual usa estimativa de memória para cinco das seis máquinas.
Fechar antes seria alocar por palpite, e cada erro custa horas de download na
máquina de outra pessoa.

### P0 — o que limitava qualquer execução futura — ✅ **fechado em 2026-08-02**

Sem isto, medir 4-6 h produzia dado que seria descartado — aconteceu duas vezes.

**Os cinco defeitos, cada um fechado por classe e com guarda que falha antes da
correção.** A distinção importa: corrigir o caso deixa a próxima ocorrência passar,
e na máquina de outra pessoa ela custa horas.

| Defeito | O que aconteceu | Guarda que fechou a classe |
|---|---|---|
| índice de página base-0 | rodada inteira leu a página seguinte | `paginas_do_documento()` + página de triagem **declarada**, e a CLI imprime as páginas antes de começar |
| trava órfã | o PID era gravado, **e nunca conferido** | `_processo_vive()`, incluindo o `OSError` 87 que o Windows levanta no lugar de `ProcessLookupError` |
| limite de tempo do cliente | matou duas medições no meio | teste que lê o código dos scripts e barra teto em chamada de geração |
| chaves inventadas pelo modelo | 3 de 6 modelos devolveram nomes próprios | teste que barra `format: "json"` sem justificativa adjacente |
| contexto fixo para seis modelos | cortou o `glm-ocr` no meio da geração | `aferir` **chamada** nos três scripts — medir a entrada antes de dimensionar |

Sobre o último: a função existia desde cedo e **passou o dia sem uma chamada**.
Guarda que ninguém invoca documenta a intenção e não impede nada.

### P1 — antes de distribuir (tolerância zero)

> **Nota de numeração (corrigida 2026-08-12):** os itens abaixo usavam os
> números soltos "7" e "8", que colidiam com outros "7"/"8" na seção P3 mais
> abaixo — dois itens completamente diferentes com o mesmo número, em duas
> tabelas separadas. Prefixados por seção (`P1-`, `P3-`) agora, pra que "item
> 8" nunca mais seja ambíguo. Achado pela auditoria de 02/08, não corrigido
> até esta data.

| # | Item | Por que primeiro |
|---|---|---|
| P1-1 | **Ensaio prévio em escopo mínimo** | erro aparece em minutos, não em horas |
| P1-2 | **A seção 4 inteira — os 21 itens** | detecção de ambiente, contenção, contaminação silenciosa, robustez, experiência de quem executa |

✅ **Script de preparação com a escada nova** — fechado em 02/08. Ele instalava
três modelos quando a escada do ADR-0014 já tinha oito. Agora traz os oito, **e um
teste amarra a lista dele à de `parser.cli`**: eram duas listas em linguagens
diferentes, sem nada impedindo que divergissem de novo. Quem executa baixaria
~26 GB do conjunto errado e descobriria horas depois.

**Não existe item "9" nesta lista** — a frase abaixo foi escrita como se
houvesse um, e não há. O que ela descreve é o próprio **P1-2**: os 21 itens da
seção 4 não são um recorte, são **todos** pré-requisito de rodar sem
supervisão na máquina de outra pessoa.

Fica de fora dos cinco, e continua aberto: **colunas deslocadas** — valores reais
no campo errado. A guarda é a ordem de colunas entregue ao modelo, e ela só fecha
quando vier do reconhecimento (P2), não de perfil escrito à mão.

### P2 — destrava o chefe (e o produto)

> **2026-08-12 — o item P2-1 mudou de estado, mas só para o Cenário B.** O
> "prompt intermediário para qualquer PDF" citado como "não implementado"
> abaixo **foi implementado** para o Cenário B: é o roteador de extração por
> página, ADR-0025 (`src/parser/planejador.py`), que monta a ordem de colunas
> a partir da geometria descoberta e escala pro modelo quando preciso — ver
> "Cenário B" no topo deste arquivo. **Para o Cenário A**
> (medir e comparar modelos sob o protocolo pré-registrado do experimento,
> ADR-0020) isso continua não fechado: o roteador ainda não foi ligado ao
> caminho do experimento (`pipeline.Pipeline`, que é só de A), e o item P2-2
> abaixo continua de pé.

| # | Item | Estado |
|---|---|---|
| P2-1 | **Prompt intermediário para qualquer PDF** | decidido (ADR-0023/0024) e **implementado para o Cenário B** (ADR-0025) — Cenário A ainda não usa o roteador |
| P2-2 | **Pipeline conectado** — reconhecimento → prompt → extração | peças prontas; ligadas em B via `planejador`+`fabrica`+`lote`, **fiação do experimento (A) ainda faltando** |

O que existia antes desta ressalva: nomes de coluna por geometria (11/11 no
documento-caso) e reconhecimento por modelo (9% do custo da extração). O que
faltava: montar o prompt com isso e ligar ao fluxo — feito para B, não para A.

### P3 — fecha o artigo

| # | Item | Custo |
|---|---|---|
| P3-1 | **Refazer os modelos sob as correções** | ~4-6 h de máquina parada |
| P3-2 | **Documentação e varredura final** | sem máquina |

**Só 2 dos 8 modelos estão medidos de forma comparável.** Os outros rodaram cada
um com uma configuração diferente, antes das correções — servem de indício, não
de resultado.

### Fora desta lista, e é sua ação

**Coletar os PDFs por característica.** Não bloqueia P1 nem P2 — o reconhecimento
é justamente o que dispensa configurar cada documento. Bloqueia a **triagem por
característica**, que é evidência central do artigo.

Lista do que procurar: [CARACTERISTICAS.md](experimentos/pdf/CARACTERISTICAS.md).

## Estado

| | |
|---|---|
| Testes | **795 passando**, 10 saltados (`pytest -m "not experimento_a"`) — atualizado em 2026-08-12 após fechar P-1.1/P0.1, −1.3 e (parcialmente) −1.4, cobrir `cli.py::_comparar`, branches de erro de `_avaliar`, e um teste de integração ponta a ponta contra um documento real do corpus. `pytest-randomly` ligado por padrão (ordem embaralhada a cada rodada) e gatilho automático de captura de instabilidade — ver −1.2 |
| Estilo | `flake8` e `black` limpos — drift de formatação (versão de `black` mais nova) corrigido em 2026-08-12 |
| Guarda de confidencialidade | 9/9 |
| ADRs | **24** |
| Ciclos de importação | **nenhum** (39 módulos) |
| Rotas com resultado gravado | 7 de 8 — a de visão vive à parte |
| Documentos-caso | **19**, cobrindo 19 características — ver [pdf/](experimentos/pdf/) |
| Vocabulário | [GLOSSARIO.md](docs/GLOSSARIO.md) — "degrau" tinha 3 sentidos |

### Medido na máquina de referência (página 29, ociosa)

| Rota | Acurácia | Tempo |
|---|---|---|
| posicional | 100% | 0,1 s |
| pdfplumber | 100% | 0,5 s |
| camelot | 98,7% | 0,8 s |
| ocr | 99,3% | 3,0 s |
| **texto** (`qwen3:4b`) | **100%** | **1340,8 s** |
| **visão** (`qwen3-vl:4b`) | **100%** em 5 itens | 4641 s (página inteira) |

**Esta máquina executa em processador**, e não por falta de memória: a placa de
2 GB tem arquitetura de 2017, abaixo do que o servidor exige. Forçar o uso dela
foi medido e é **marginalmente pior** (17,1 contra 17,5 tokens/s).

## Os três eixos

O trabalho não é uma fila. São três eixos com custos e dependências diferentes, e
tratá-los como fila foi o que travou o planejamento anterior.

```
        taxonomia (ADR-0021)
               │
        documentos por característica
               │
     ┌─────────┴─────────┐
     │                   │
DETERMINÍSTICAS      MODELOS
segundos/página      dezenas de min/página
todas × tudo         triagem por característica
     │                   │
     │            corte por zona de empate
     │            (reporta eliminados)
     │                   │
     │            preenchimento, páginas disjuntas
     └─────────┬─────────┘
               ▼
     matriz de correlação de erros
               ▼
     CONSOLIDAÇÃO POR CAMPO
```

**Por que a consolidação não espera a triagem.** Ela vota entre as rotas que
existirem — o ADR-0017 já trata rota ausente como ausência, não voto contrário.
O **mecanismo** pode ser construído com as determinísticas e entregar o pedido do
produto agora. O que **não** pode ser fixado antes das medições é o **peso** de
cada voto: rotas que leem a mesma camada de texto erram juntas, e calibrar sem a
matriz de correlação seria retrabalho garantido.

## A pergunta que as duas entregas compartilham

O chefe pergunta: *qual o **menor** modelo, na configuração **mínima**, que
resolve o **máximo** com alta certeza.* O artigo pergunta: *mais capacidade
melhora o resultado, ou satura?*

**São a mesma medição** — o joelho da curva custo × qualidade. O que muda é o
formato de saída: um quer uma recomendação ("use X em máquina Y"), o outro quer a
curva com a metodologia que a sustenta.

Isso define a ordem das três perguntas, e ela não é arbitrária:

| # | Pergunta | Por que nesta ordem |
|---|---|---|
| 1 | **configuração** | modelo mal configurado parece ruim; sem isso tudo mede o erro de configuração — foi o que aconteceu com o contexto herdado |
| 2 | **modelo** | com todos bem configurados, a comparação passa a ser justa |
| 3 | **infraestrutura** | sabendo o modelo, "que máquina ele exige" é a pergunta de compra |

## O fluxo, corrigido

```
0. VALIDAR O PROMPT — máquina de referência, escopo pequeno
   não é medição comparativa; é acerto de configuração
   prompt é CONGELADO ao fim desta etapa (ADR-0022)
        ↓
1. TRIAGEM — 8 hipóteses × modelos × 1 página POR CARACTERÍSTICA
   5 máquinas, cada uma o que comporta
   corte por zona de empate, POR CARACTERÍSTICA, eliminados reportados
        ↓
2. PREENCHIMENTO — sobreviventes × documentos completos × 1 configuração
   páginas disjuntas das de triagem
        ↓
3. CONSOLIDAÇÃO + avaliação (acurácia por campo, erro × omissão)
```

**Os documentos não bloqueiam a distribuição.** A triagem usa uma página por
característica; enquanto a coleta não termina, ela roda com as características já
disponíveis. Quem bloqueia é o **prompt validado**.

### O que os scripts das máquinas fazem — e o que não fazem

**Fazem:** rodar o mesmo prompt, a mesma página, a mesma escada do menor ao maior
até não caber; registrar versão de servidor, modelo, driver, memória, e **quanto
foi para a placa contra quanto foi para o processador**.

**Não fazem:** otimizar prompt localmente, escolher modelo, descartar resultado
ruim. Se cada máquina afinar o seu, os resultados deixam de ser comparáveis e o
experimento morre. **Coletar é local; decidir é central**, com os dados das cinco
juntos.

## O que já está medido

> ### ⚠ Toda esta seção é LINHA DE BASE, não resultado
>
> Duas razões, e as duas vieram das auditorias de 02/08:
>
> **A métrica não penaliza fabricação** (P-1.1) — os percentuais medem concordância
> entre os itens que sobreviveram à interseção, não fidelidade ao documento.
>
> **A página foi escolhida à mão** — a página 29 nunca foi *descoberta* como a
> melhor do documento para a característica dela. Se a análise do corpus a
> confirmar, estas medições se reaproveitam; se apontar outra, elas não valem como
> ponto extremo da curva e a máquina de referência precisa ser remedida.
>
> Os dados brutos continuam em disco e podem ser reavaliados com a métrica
> corrigida. O que cai é a leitura, não a coleta.

### Inventário: quem foi medido, e onde — levantado em 02/08

**Uma única máquina tem resultado gravado.** `experimentos/resultados/` contém
apenas `titoslaptop`.

| Modelo | Onde aparece | Comparável? |
|---|---|---|
| `qwen3-vl:4b` | 3 arquivos, inclusive página inteira sem limite | parcial |
| `qwen3-vl:2b` | 3 arquivos | parcial |
| `glm-ocr` | 2 arquivos | não — cortado por contexto herdado |
| `minicpm-v4.6:1b` | 2 arquivos | não |
| `deepseek-ocr:3b` | 2 arquivos | não |
| `minicpm-v4.5:8b` | 1 arquivo | não |
| `qwen3:4b` | validação de prompt | parcial |
| **`qwen3:1.7b`** | **nenhum** | **nunca rodou** |

**Nenhum dos oito tem medição comparável**: rodaram com configurações diferentes,
antes das correções de contexto e de degrau, e todos sob a métrica que não penaliza
fabricação. Servem de indício sobre o que roda nesta classe de hardware — não de
resultado.

As máquinas de 6, 8, 12 e 16 GB **não rodaram nada ainda**, e não devem rodar antes
dos itens P-1.

Contra o conjunto de reserva (10 itens, 9 páginas, seções variadas, transcrito às
cegas):

| Rota | Gabarito principal | **Conjunto de reserva** |
|---|---|---|
| posicional | 100% (tautológico) | **100%** |
| pdfplumber | 100% | **100%** |
| camelot | 99% | **100%** |
| ocr | 99,5% | 78% |
| linear (piso) | 0% | 0% |
| pymupdf (detector pronto) | 0% | 0% |

A coluna da direita é a que vale: mede **generalização** para layout que não foi
usado no ajuste. Três rotas a 100% é evidência forte.

**Rotas por modelo — medido em 2026-07-31**, uma medição por vez, na página 29:

| Rota | Tarefa | Tempo | Resultado |
|---|---|---|---|
| texto (`qwen3:4b`) | página inteira, **com valores** | 2904 s | **31 itens, 100%** em `energia_kcal` (31/31) |
| visão (`qwen3-vl:4b`) | 5 itens, só nomes+energia | 1078 s | 4 de 5 — leu `135` onde o documento diz `358` |
| visão (`qwen3-vl:4b`) | página, **com valores** | 1026 s | **resposta vazia** — não atende o caso de uso |
| determinística | página inteira | **0,2 s** | 100% |

> ### ⚠ A linha "resposta vazia" acima está RETIFICADA — leia a seção 0
>
> A conclusão registrada era *"a rota de visão não preenche planilha nesta classe
> de hardware"*. **Ela mede um artefato de configuração, não o modelo.**
>
> A causa é o **limite de contexto**, que o projeto não declarava: o padrão do
> servidor limita entrada e saída **juntas**, e a imagem consome quase todo o
> espaço. Provado por aritmética — quatro casos, com prompts de tamanhos
> diferentes, parando na **mesma soma exata**. Ver a seção 0.
>
> A conclusão sobre o **raciocínio** continua de pé: foi medida de forma
> independente. Mas o peso dela cai — se o contexto for suficiente, o raciocínio
> deixa de ser fatal e passa a ser apenas custo.

**Não há como desligar o raciocínio** neste servidor com este modelo. As duas
formas foram medidas: `think: false` gerou 4043 caracteres de raciocínio,
`/no_think` gerou **6254** — piorou. A questão fica fechada.

**A rota de texto funciona de ponta a ponta**, e isso nunca tinha sido medido. Ela
recebe o texto já extraído, então não comete o erro de leitura de dígito que a
rota de visão cometeu.

O custo por página inteira é ~14.500× o da rota determinística. Isso não a
descarta — ela resolve documentos que a determinística não alcança — mas define
onde cada uma serve.

Um dado que explica muito: na rota de visão, **4043 caracteres foram gastos
raciocinando para produzir 185 de resposta**. Na de texto, zero raciocínio e 16767
de resposta. O raciocínio consome o orçamento que o limite de tokens restringe
(ADR-0015).

Detalhe completo em `resultados/titoslaptop/rotas-por-modelo.json`.

---

## 0. Retificação do limite de contexto — ✅ CONCLUÍDA

> **Fechada em 2026-07-31.** Mantida aqui como resultado, não como tarefa: é a
> evidência que sustenta ADR-0018 e a regra de nunca herdar padrão de servidor.

### O desfecho, medido sem limite de cliente

A pergunta que ficara aberta — *quanto a chamada leva quando nada a interrompe* —
tem resposta:

| | Valor |
|---|---|
| Tempo | **77,4 min** (4641 s) |
| `done_reason` | **`stop`** — terminou sozinha, sem corte |
| Tokens | entrada 2376 + saída 5684 = **8060** de 12271 disponíveis |
| Resposta | **vazia** |

**Duas leituras, e a segunda importa mais.**

A correção do contexto **funcionou**: sobrou espaço (8060 de 12271) e não houve
corte. Mas a resposta veio vazia mesmo assim, com 5684 tokens gerados — ou seja,
**o contexto não era a única causa**.

A explicação verificada: o servidor devolve o campo de raciocínio preenchido
**mesmo com o raciocínio declarado como desligado**, e o script de medição
descartava esse campo. Os tokens foram para lá. É lacuna de instrumentação, não
incapacidade do modelo — e é por isso que a instrumentação (eixo A) vem antes de
remedir.

Dado bruto em `resultados/titoslaptop/vlm-pagina-inteira-sem-limite.json`.

### O que foi provado

O teto declarado era `num_predict=16384`, mas as respostas cortavam em ~1870
tokens com `done_reason=length`. Somando **entrada + saída** de cada medição:

| Caso | entrada + saída | soma | motivo |
|---|---|---|---|
| fatiado, 5 itens | 2184 + 1581 | 3765 | `stop` |
| rota de texto | 1819 + 5948 | 7767 | `stop` |
| `/no_think` | 2175 + 1921 | **4096** | `length` |
| com valores | 2227 + 1869 | **4096** | `length` |
| valores + `/no_think` | 2233 + 1863 | **4096** | `length` |
| controle | 2189 + 1907 | **4096** | `length` |

**Quatro casos, prompts de tamanhos diferentes, mesma soma exata.** O padrão de
`num_ctx` no Ollama é 4096 e limita entrada e saída **juntas**; a imagem consome
~2200 de entrada. O `num_predict` nunca foi o limite atuante — o caso que
funcionou funcionou porque **coube**.

Verificação independente: com `num_ctx` explícito, o servidor passou a reportar
contexto de 16384 e o modelo cresceu de 3,6 GB para 5,5 GB.

**Consequência: a conclusão "a rota de visão não preenche planilha nesta classe
de hardware" mede um artefato de configuração, não o modelo.**

### O que aconteceu ao corrigir o contexto — medido, três casos

Dado bruto em `resultados/titoslaptop/contexto-limite.json`.

| Caso | Contexto | Desfecho | Quem parou |
|---|---|---|---|
| A | 4096 (padrão) | cortado em **exatamente 4096**, 21 min | o servidor |
| B | 16384 | **>1 h sem terminar** | o cliente, por tempo |
| C | 32768 | **>1 h sem terminar** | o cliente, por tempo |

**A causa está confirmada.** O caso A bateu a parede; B e C não bateram parede
nenhuma. Se o contexto não fosse o limite atuante, os três teriam cortado igual.

**E a conclusão prática mudou de forma, não de veredito.** Corrigir o parâmetro
**não tornou a rota viável nesta máquina** — trocou uma falha por outra:

| | Antes | Depois |
|---|---|---|
| Falha | resposta vazia por corte | não termina em tempo útil |
| Velocidade | rápida (21 min) | lenta (>1 h) |
| Diagnóstico | **enganoso** — parecia incapacidade | claro — é a máquina |

Formulação correta: *em processador de baixo consumo, uma página inteira pela
rota de visão não termina em tempo utilizável*. Isso não é limitação do modelo
nem de configuração — ele **lê a página corretamente**, como o caso de 5 itens
mostrou. É capacidade computacional.

**Não medido, e vale medir:** quanto a chamada realmente levaria sem limite de
cliente, e o comportamento em máquina com placa de vídeo funcional — que é
justamente o que o experimento multimáquina existe para responder (ADR-0013).

- [x] Código (TDD): `degraus.py` envia `num_ctx`; propagar por `fabrica.py`,
      `ollama.py`, `extratores/vlm.py`
- [x] **Declarar no perfil** — feito em 2026-07-31. Estava aberto enquanto o
      resto já funcionava, que é a pior combinação: a correção existia no código
      e ficava **desligada** no arquivo que as medições usam, então a próxima
      rodada herdaria o defeito em silêncio. `vlm` recebeu 12271 e `llm` 11650,
      valores devolvidos por `parser.contexto.dimensionar` a partir da entrada
      medida — não escolhidos à mão. Procedência em `DEFAULTS`, guarda em
      `TestPerfisDoProjeto.test_rotas_por_modelo_declaram_contexto`
- [x] Corrigir as mensagens de erro — hoje mandam aumentar `tokens_maximos`, que
      a medição refuta
- [x] **Registrar sempre** `prompt_eval_count`, `eval_count` e a soma: foi a soma
      que revelou a causa, e ela era descartada. `Uso` grava os três, em falha
      **e** em sucesso, e sobrevive à serialização — coberto por
      `TestUsoNoResultado`, que faltava: o dado ia para o JSON sem teste algum
      garantindo que continuasse indo
- [x] Retificar ADR-0015, `SPEC.md` e a memória do projeto
- [x] ADR novo: dimensionamento de contexto, com a regra — **nunca confiar em
      padrão de servidor para parâmetro que decide resultado** (ADR-0018)
- [x] Remedir o caso que falhou sob `num_ctx` correto — feito: 77,4 min, sem
      corte. Ver o desfecho no topo desta seção
- [ ] **Refazer com o canal de raciocínio gravado** — a única parte que resta, e
      depende da instrumentação (A1). Mesmos 77 min de máquina; o que muda é o
      dado ficar completo

### Fórmula de dimensionamento de memória

O limite **nativo** do modelo quase nunca é o que aperta: um modelo de 4B suporta
256k de contexto, mas 256k pediria ~45 GB. **Quem manda é a memória.**

Medido, com um modelo de visão de 4B:

| Contexto | Memória medida | Previsto pela reta de 2 pontos | Erro |
|---|---|---|---|
| 4096 | 3,6 GB | — | — |
| 16384 | 5,5 GB | — | — |
| 32768 | **8,0 GB** | 8,03 GB | **0,4%** |

Ou seja ~0,16 MB por token de contexto neste modelo.

**A linearidade foi testada, não assumida.** A reta foi ajustada com os dois
primeiros pontos e **previu o terceiro** com 0,4% de erro — que é a diferença
entre curva ajustada e curva com poder preditivo.

Projeção que isso sustenta: **64k de contexto pediria ~13 GB e não cabe em uma
placa de 12 GB**, mesmo com um modelo pequeno. Com modelos maiores, o teto cai.

> **Limite que continua declarado:** o número compara o crescimento do **processo
> inteiro** (cache + buffers + codificador visual), não o cache de atenção
> isolado que a literatura calcula. E vale para **um** modelo — a inclinação
> depende da arquitetura, e é isso que a instrumentação abaixo vai levantar.

Forma proposta, com uma entrada **medida** e não suposta:

```
necessário = entrada_medida + saída_esperada + margem
viável     = (memória_livre − peso_do_modelo) / custo_por_token
usar       = min(nativo_do_modelo, viável, necessário × folga)
```

Foi exatamente `entrada_medida` que faltou: supôs-se que o teto bastava sem
medir quanto a imagem consumia.

- [ ] Instrumentar o experimento para gravar, a cada execução: contexto pedido,
      memória do processo, tokens de entrada e de saída, modelo, máquina.
      **Custo zero de tempo** — os números já passam pela chamada e são
      descartados. Com 10 modelos × várias máquinas, a fórmula deixa de ser
      heurística de um ponto e vira ajuste sobre dezenas
- [ ] Medir o custo por token do modelo de **texto** da mesma família e tamanho:
      isola o custo do codificador visual, e é a comparação mais informativa
      disponível

## Onde cada seção entra nos três eixos

As seções abaixo mantêm a numeração original — o que muda é **quando** cada uma
roda, e o eixo a que pertence.

| Eixo | Seções | Depende de | Bloqueia |
|---|---|---|---|
| **A — código e instrumentação** | 1 (parcial), 2, 5 | nada; roda aqui | tudo o mais |
| **B — coleta de documentos** | 5 | taxonomia (ADR-0021) | a triagem por característica |
| **C — execução distribuída** | 1, 2b, 3, 4 | A e B prontos, e as outras máquinas | o artigo |

**A é o único eixo que não depende de terceiros.** É por onde se começa, e é o
que entrega ao produto. B depende de curadoria manual. C depende de pessoas.

### Cronograma até 15/11

| Quando | O quê | Risco |
|---|---|---|
| ago | Eixo A: instrumentação, consolidação, taxonomia no código | baixo — só depende daqui |
| ago–set | Eixo B: coleta por característica, com cuidado de dado pessoal | **médio** — curadoria manual, e é trabalho humano |
| set | Preparar e distribuir o pacote das outras máquinas | **alto** — precisa das pessoas disponíveis |
| set–out | Eixo C: execução, triagem, corte, preenchimento | **alto** — máquina de terceiro, e refazer custa dias |
| out–nov | Análise, consolidação final, escrita | apertado se algo acima escorregar |

**Os dois riscos que podem estourar o prazo não são técnicos:** a coleta (depende
do Lucas) e a disponibilidade de quem vai rodar (depende de terceiros). Ambos
precisam começar cedo — em especial avisar as pessoas, porque baixar os modelos é
transferência grande e leva dias.

**Rede de segurança declarada:** se o resultado não amadurecer até novembro, a
mesma conferência tem uma segunda janela em janeiro. Nada do trabalho se perde;
o que muda é a trilha.

---

## 1. Fechar a medição das rotas por modelo

**Por que:** sem isso, a comparação tem um buraco — **6 de 8 rotas** estão no
`resumo.json`. As duas por modelo foram medidas por script avulso, fora do fluxo
do experimento, e por isso não têm acurácia calculada da mesma forma.

### Rota de texto — ✅ CORRIGIDA e medida (2026-08-01)

**Resultado final na página de referência**, máquina ociosa, modelo descarregado
antes (o tempo inclui a carga):

| Rota | Acurácia | Tempo |
|---|---|---|
| posicional | **100%** | 0,1 s |
| pdfplumber | **100%** | 0,5 s |
| camelot | 98,7% | 0,8 s |
| ocr | 99,3% | 3,0 s |
| **texto (`qwen3:4b`)** | **100%** | **1340,8 s** |

155 de 155 campos, zero erros, zero omissões, em 31 itens. É o número que faltava
para a comparação ter **os dois lados na mesma régua e na mesma máquina**: o
modelo empata com as melhores determinísticas e custa ~2700× mais tempo.

#### A correção que resolveu, e as três que não resolveram

O defeito era o modelo devolver a **umidade** — primeira coluna — no campo de
carboidrato, perdendo a contagem ao passar pelo `NA` do colesterol.

| Tentativa | Resultado |
|---|---|
| "alinhe por nome de coluna" | 60% |
| "conte as colunas do cabeçalho" | 60% |
| "marcador ocupa coluna" | 60% |
| **entregar a ordem das colunas, numerada** | **100%** |

**A diferença é de natureza, não de ênfase:** a regra pede que o modelo *infira* o
alinhamento; a sequência o *entrega*. E o perfil **já declarava** `campos_na_ordem`
— usado pelas rotas determinísticas desde sempre. As rotas por modelo nunca
recebiam; a correção foi ligar o que existia.

- [x] Declarar `energia_kj` no esquema pedido
- [x] Pedir o identificador completo (número **e** descrição)
- [x] **Entregar a ordem das colunas** ao modelo
- [x] **Fixar `seed` e `temperature: 0`** (ADR-0020)
- [x] Validar em escopo pequeno antes de rodar página inteira

> ### ⚠ O prompt que dá 100% aqui não serve a documento desconhecido
>
> Ele entrega **as colunas deste documento**. Em qualquer outro, está errado por
> construção. É limite de desenho, não de execução — e o produto precisa montar o
> prompt a partir do que o diagnóstico detecta, não do que o humano declara.
>
> Decisão em [ADR-0023](docs/adr/0023-prompt-para-estrutura-desconhecida.md).
> A peça central já existe: `calibracao.py` **descobre as colunas por geometria**,
> sem declaração prévia.

#### Duas armadilhas de medição, ambas na régua e não na extração

**Índice contra número de página.** O intervalo do perfil é **base-0**:
`range(29,30)` lê `doc[29]`, que é a **página 30**. Uma rodada inteira leu a
página errada e nada casou com o gabarito — os valores eram reais, de outros
alimentos.

**Nome de campo sem mapeamento.** A conferência comparava nomes canônicos
(`energia_kcal`) contra os nomes do documento (`Energia (kcal)`), e acusava
**zero acerto** em rotas que acertam tudo.

> A regra do projeto pegou os dois: *zero absoluto numa rota que acerta em outro
> gabarito é suspeita do instrumento, não da extração.*

### Seis modelos de visão na página de referência — medido 2026-08-01

Sequencial, máquina ociosa, descarga entre modelos, semente fixa, sem limite de
tempo. Dado bruto em `resultados/titoslaptop/modelos-pagina29.json`.

| Modelo | Tam. | Tempo | Acurácia | O que aconteceu |
|---|---|---|---|---|
| `minicpm-v4.6:1b` | 1,6 GB | 3,5 min | 0% | leu certo, **inventou as chaves** (`umidade`, `energia`) |
| `glm-ocr` | 2,2 GB | 6,0 min | 0% | leu **perfeitamente**, devolveu **objeto solto** com nomes do documento |
| `qwen3-vl:2b` | 1,9 GB | — | — | devolveu lista de textos; o conferidor quebrou (defeito do script, corrigido) |
| **`qwen3-vl:4b`** | 3,3 GB | **29,9 min** | **97,9%** | **142 acertos, 3 erros, 0 omissões** |
| `deepseek-ocr:3b` | 6,7 GB | 1,7 min | 0% | devolveu `{"item":"1","categoria":"Alimentos"}` |
| `minicpm-v4.5:8b` | 6,1 GB | 27,9 min | 20% | chaves certas, **colunas deslocadas** |

#### O achado: o gargalo é aderência ao formato, não leitura

**Nenhum dos cinco falhou por não conseguir ler a tabela.** `glm-ocr` transcreveu
a linha inteira corretamente — umidade, energia em kcal e kJ, proteína, lipídios,
colesterol, carboidrato, fibra — e mesmo assim pontuou zero, porque devolveu um
objeto solto em vez da lista pedida.

A conclusão que isso sustenta, e que a acurácia sozinha esconderia:

> Em modelo pequeno, **seguir o formato pedido é mais difícil que ler o
> documento**. O que separa 0% de 97,9% aqui não é qualidade de leitura — é
> obediência ao esquema.

É consistente com o que o projeto já mediu nos degraus de saída (ADR-0015) e
reforça a decisão de manter a saída validada, nunca confiada.

#### Os quatro medidos com esquema como gramática — e a acurácia real

A conferência oficial dá zero em três deles, e **o zero é do instrumento**. Duas
causas se somam: a geração é cortada antes do fim, e o identificador vem sem
descrição (`"1"` em vez de `"1 Arroz, integral, cozido"`), então nada casa.

Reconferindo **pelos itens completos que couberam**, casando por número:

| Modelo | Tempo | Itens lidos | Acurácia real | Desfecho |
|---|---|---|---|---|
| **`qwen3-vl:2b`** | 9,5 min | 14 | **92,9%** | `stop` |
| `glm-ocr` | 33,8 min | 14 | 64,3% | `length` |
| `minicpm-v4.6:1b` | 4,0 min | 8 | 47,5% | `stop` |
| `deepseek-ocr:3b` | 14,1 min | 10 | **0%** | `length` |

**`qwen3-vl:2b` é o achado.** Um modelo de 1,9 GB lendo a 92,9% em 9,5 min — três
vezes mais rápido que o de 3,3 GB, com acurácia próxima. É exatamente o joelho da
curva que o experimento procura, e ele apareceu no denominador comum.

**`deepseek-ocr` erra tudo o que lê**, e de forma sistemática: devolve umidade
onde se pede energia, energia onde se pede proteína. É deslocamento de coluna, não
leitura ruim — e é o único cujo resultado **confirma** o descarte que o benchmark
de terceiro havia sugerido, agora por medição própria.

> **Duas medições do mesmo modelo com desfechos diferentes é assinatura de
> orçamento, não de capacidade.** `glm-ocr` deu `stop` em 6 min sem gramática e
> `length` em 34 min com ela — a gramática restringe a decodificação, e o custo
> aparece no tempo e no corte.

#### O degrau 1 corrige o formato — e revela o problema seguinte

Refeito com o **esquema como gramática de decodificação** (degrau 1), em vez de
`format: "json"` (degrau 2, que garante JSON válido sem impor estrutura):

| | degrau 2 | degrau 1 |
|---|---|---|
| `glm-ocr` — chaves | inventadas, do documento | **as pedidas** ✅ |
| `glm-ocr` — formato | objeto solto | **lista `itens`** ✅ |
| `glm-ocr` — desfecho | `stop`, 6,0 min | **`length`, 33,8 min** |

**A gramática funcionou no que se propunha e expôs a causa seguinte:** a geração
foi **cortada** no item 15 de 31, com o JSON truncado no meio. Não é recusa nem
incapacidade — os valores até ali estavam corretos.

**A causa é o contexto, e a lacuna é de desenho:** o perfil declara **um**
contexto (12271) para todas as rotas de visão, calculado a partir da entrada do
`qwen3-vl:4b` (2376 tokens). O `glm-ocr` consome **3375** de entrada, e precisaria
de ~17000 para caber a saída de 31 itens.

> **O contexto é por modelo, não por rota.** Dois modelos com a mesma tarefa
> consomem entradas diferentes, e um número só serve mal aos dois. É a mesma
> classe de erro do ADR-0018 — parâmetro herdado onde deveria ser calculado —
> reaparecendo num nível acima.

E há o custo: a gramática levou de 6,0 a **33,8 min** no mesmo modelo. Restringir
a decodificação não é grátis, e isso entra na conta de qual degrau usar.

#### Consequência para o desenho

- **A hipótese dos degraus (H1-H3) passa a ser central**, não secundária: modelo
  que falha no esquema completo pode funcionar em JSON livre ou texto recortado.
  Cinco dos seis modelos morreram exatamente nesse ponto.
- **O contexto precisa ser calculado por modelo**, a partir da entrada medida de
  cada um — `parser.contexto.dimensionar` já faz a conta; falta o perfil aceitar
  o valor por rota e o experimento medir a entrada antes de fixá-lo.
- **Um modelo especializado em documento não é automaticamente melhor.**
  `glm-ocr` lê melhor que o vencedor e entrega pior. A comparação precisa dos dois
  eixos.
- **Este resultado é de uma configuração só.** Nenhuma hipótese variou — é o que a
  triagem nas outras máquinas existe para fazer.

> **Cuidado ao ler:** 0% aqui significa "não produziu saída aproveitável nesta
> configuração", **não** "não sabe ler". A distinção é o próprio achado.

### Rota de visão — era o timeout, e ela acerta 100%

Ela falhou com `TimeoutError` em 6350 s contra os 3600 s do perfil. **Não era a
rota falhando — era o limite chegando antes dela.** Sem limite de cliente,
termina em 77 min.

E na validação de prompt ela acertou **25 de 25 campos** em 5 itens — a extração
estava perfeita e vinha sendo **descartada**, porque o servidor entregou tudo pelo
canal de raciocínio e deixou a resposta vazia. Já corrigido: o extrator aproveita
o rascunho quando a resposta vem vazia, e a validação de estrutura continua
filtrando divagação.

Nesta amostra a rota de visão é **mais precisa que a de texto** — ela lê a imagem
e não se confunde com o `NA` no meio da linha, que é onde a de texto tropeçava.

- [x] Timeout **sem limite** na máquina de referência
- [x] Validar o prompt fatiado (5 itens) — 100%
- [ ] **Teto generoso** no pacote das outras máquinas: sem limite, travar significa
      travar para sempre, e quem está do outro lado não sabe o que fazer
- [ ] Refazer a página inteira com a ordem das colunas e o canal de raciocínio
      gravado — o que existe é anterior às duas correções

- [ ] Bateria da rota de texto — 8 casos pareados com os da visão
- [ ] Consolidar os parâmetros num só lugar: contexto, teto de saída, `dpi` e
      degrau
- [ ] **Integrar as rotas de modelo ao `resumo.json`** — hoje vivem em
      `rotas-por-modelo.json`, à parte, e a comparação entre as oito não fecha
- [ ] Varredura de degraus contra o servidor real, gravada no experimento

### O registro de ambiente

Resolvido nesta sessão:

- [x] **versão do servidor de inferência** — versões diferentes entre máquinas
      tornam os resultados incomparáveis, e antes isso passaria despercebido.
      Agora vai no `ambiente.json` e no comando `ambiente`
- [x] **memória de vídeo por caminho neutro de fabricante** — lida do registro do
      sistema (64 bits), não da interface que satura em 4 GB. Placa dedicada tem
      prioridade sobre gráfico integrado, que não declara o campo (ADR-0019)

Falta:

- [ ] **versão do driver de vídeo** — afeta desempenho e alocação de memória
- [ ] **contexto efetivamente usado** e **tokens de entrada/saída** por chamada —
      o tipo `Uso` já os carrega; falta gravá-los no resultado

> **Armadilha de ambiente, encontrada na máquina de referência.** O pacote
> instalado apontava para um **clone antigo**, e `python -m parser.cli` executava
> código desatualizado enquanto os testes rodavam o fonte correto. Uma medição
> feita assim mediria a versão errada sem nada denunciar.
>
> Verificar antes de medir: `python -c "import parser; print(parser.__file__)"`
> tem de apontar para o repositório em uso. O script das outras máquinas precisa
> conferir isso e falhar alto se divergir.

## 2. Consolidação por campo

> Decisão registrada em [ADR-0017](docs/adr/0017-consolidacao-por-campo.md),
> incluindo o limite: rotas que compartilham fonte de erro podem errar juntas,
> e a votação confirmaria o erro com confiança alta.

**Por que aqui:** é o item de maior valor do projeto inteiro, e ainda não existe.
Ele resolve **duas coisas de uma vez**.

Hoje cada extrator produz uma planilha. Escolher "a melhor" desperdiça informação:
três rotas empatam em 100%, e nenhuma acerta tudo em todas as páginas.

**A saída é votar por célula, não escolher por arquivo:**

| Situação | Ação | Confiança |
|---|---|---|
| todas as rotas concordam | preenche | alta |
| maioria concorda | preenche, **registra a divergência** | média |
| empate ou ninguém leu | **pendência humana** | — |

Isto **é** o ciclo que o consumidor corporativo pediu — "preenche o que dá, e o que
não sabe vira pendência" — e ao mesmo tempo produz a planilha única que o consumidor
pessoal precisa como entrada.

### O que se constrói agora, e o que espera medição

A distinção evita o retrabalho que a pressa produziria:

| Parte | Quando | Por quê |
|---|---|---|
| **Mecanismo** — votar, decidir, abrir pendência | **agora** (eixo A) | não muda quando chegam votantes novos; ADR-0017 já trata rota ausente |
| **Pesos** — quanto vale cada voto | **depois** das medições | rotas que leem a mesma camada de texto **erram juntas**; calibrar sem a matriz de correlação seria decidir por suposição |

Por isso os pesos entram **parametrizados**, não embutidos: o mecanismo entrega o
comportamento que o produto pede hoje, e a calibração é trocada depois sem tocar
na lógica.

**Fundação que já existe:** `src/parser/concordancia.py` **mede** divergência
entre estratégias (`comparar_estrategias`). Falta a camada que **decide**. A
`Pendencia` de `lote.py` é o encaixe da saída.

- [x] Implementar a consolidação com proveniência (quantas rotas concordaram) —
      `src/parser/consolidacao.py`, 35 testes
- [x] **Pesos parametrizados**, com o padrão uniforme declarado como provisório

### O que a primeira execução sobre dados reais revelou

A primeira rodada devolveu **56,2% de células com voto único**. A suspeita
natural — "as rotas leem pouco" — estava errada. Era **alinhamento faltando**, em
dois níveis, e nenhum deles é defeito da votação.

**Identificador.** Só **81 de ~283 itens** apareciam nas quatro rotas. A causa não
é acento: o extrator de tabela insere **espaço no meio da palavra** ao atravessar
a quebra de coluna num cabeçalho rotacionado.

| Rota | Identificador lido |
|---|---|
| posicional | `1 Arroz, integral, cozido` |
| pdfplumber | `1 Arroz, integra l, cozido` |

Dois itens, um voto cada. **200 alimentos fora da votação por um espaço.**

**Campo.** O perfil mapeava **5** campos e o documento tem **11**. Cada variante
virava coluna própria — por acento perdido no OCR (`Proteina`) ou ordem trocada
pela rotação (`Alimentar Fibra`).

#### Efeito acumulado, medido

| Etapa | Concordância | Voto único |
|---|---|---|
| inicial | 39,3% | 56,2% |
| + mapeamento parcial (5 campos) | 40,7% | 54,6% |
| + alinhamento de identificador | 60,4% | 33,3% |
| **+ mapeamento completo (11 campos)** | **79,4%** | **13,5%** |

- [x] **Ampliar o `mapeamento` do perfil** para todos os campos do documento
- [x] **Alinhar identificadores entre rotas** — normalização de acento, espaço e
      caixa antes de indexar

> **Exclusão deliberada:** `Energia (kd)` **não** entra no mapeamento. É leitura
> corrompida do OCR, não variante legítima, e acolhê-la faria o erro votar como
> se fosse boa leitura — a votação confirmaria o valor errado com confiança alta,
> que é o modo de falha que a consolidação existe para evitar. Há teste guardando.

- [ ] Rodar a consolidação sobre as **23 páginas**, não só as 9 atuais
- [ ] Investigar os **6,8% de pendência** restantes: divergência real, ou ainda
      alinhamento?
- [ ] **A votação precisa lidar com conjuntos diferentes de rotas.** Máquinas com
      mais capacidade rodam modelos que a de referência não roda, e são elas que se
      parecem com o servidor de destino. Uma rota ausente numa máquina não pode
      invalidar a consolidação, nem contar como discordância — é ausência, não voto
      contrário
- [ ] Métrica **erro × omissão**: omitir vira pendência (bom); errar entra na
      planilha errado (péssimo). Hoje contam igual na acurácia
- [ ] **Matriz de correlação de erros** entre rotas — pré-requisito da calibração,
      e resultado publicável por si: mostra quais estratégias são de fato
      independentes
- [x] ADR da decisão — [ADR-0017](docs/adr/0017-consolidacao-por-campo.md)

## 2b. Escopo: triagem e preenchimento são fases distintas

> Decisão registrada em [ADR-0016](docs/adr/0016-triagem-e-preenchimento.md),
> com a conta completa e a verificação estrutural das páginas.

**O problema, com números.** Se cada modelo rodar todas as hipóteses em todas as
páginas, a conta explode:

| | Cálculo | Resultado |
|---|---|---|
| Modelos × hipóteses | (4 visão + 5 texto) × 8 | 72 execuções por página |
| × páginas de dados | 72 × 23 | **1.656 execuções** |
| × tempo medido (~2900 s) | | **~56 dias de máquina** |

Inviável. A saída não é cortar hipóteses no escuro — é separar o que cada fase
responde.

### Fase 1 — triagem: **1 página, muitas hipóteses**

**Pergunta:** qual a melhor configuração de cada modelo?

**Página 29, e a mesma em todas as máquinas.** Foi a usada nas medições desta
sessão — texto e imagem verificados por impressão digital. Se cada máquina triasse
numa página diferente, as configurações vencedoras não seriam comparáveis.

**Uma página basta, e isso foi verificado, não suposto.** As páginas de dados são
estruturalmente idênticas:

| Página | Rotação | Palavras | Imagens | Colunas |
|---|---|---|---|---|
| 29 | 90° | 546 | 0 | 11 |
| 33 | 90° | 495 | 0 | 11 |
| 41 | 90° | 524 | 0 | 11 |
| 45 | 90° | 463 | 0 | 11 |
| 47 | 90° | 546 | 0 | 11 |

Mesma rotação, mesma sequência de unidades no cabeçalho, sem imagens. Só o conteúdo
muda. **Acrescentar páginas do mesmo formato custaria 3× o tempo sem acrescentar
informação** — o que a ferramenta faz numa, faz nas outras.

**Quando ampliar:** se aparecer página com formato diferente — tabela vertical,
outro número de colunas, imagem embutida, orientação distinta. Aí a página nova
testa algo que a 29 não testa, e entra. É critério de conteúdo, não de quantidade.

Custo: ~29 h com 4 hipóteses (as que discriminaram nesta sessão).

### Fase 2 — preenchimento: **23 páginas, 1 configuração**

**Pergunta:** qual planilha cada estratégia produz, para consolidar?

Só os sobreviventes da triagem, cada um com a configuração que venceu. Nenhuma
hipótese varia aqui — variar tornaria as planilhas incomparáveis.

Custo: ~56 h para 3 modelos sobreviventes. As 6 rotas determinísticas fazem as 23
páginas em segundos.

**O corte tem zona de empate.** Modelos que não se distinguem estatisticamente
entre si avançam **todos** — a consolidação por campo aproveita a diversidade, e
cortar por ranking dentro da margem de erro seria decisão sem base.

O limiar exato **não é fixado agora**: depende de como os resultados se
distribuírem. A amostra de uma página são ~155 valores (31 itens × 5 campos), o
que sustenta distinguir um modelo claramente ruim de um bom, mas **não** distinguir
96% de 98%. O corte será desenhado para o que a amostra sustenta, com o número
registrado junto da justificativa.

### Por que a separação é metodologicamente correta

Não é só economia. **As duas fases medem coisas diferentes:**

- A triagem mede **configuração** — variar é o objetivo.
- O preenchimento mede **estratégia** — variar seria confundir a comparação.

Rodar tudo em tudo produziria 1.656 planilhas incomparáveis entre si, porque cada
uma teria configuração diferente. A consolidação por campo exige o oposto: todas as
planilhas da mesma página, produzidas sob a mesma condição.

### Onde o escopo fica baixo, e onde abre

| Momento | Escopo | Por quê |
|---|---|---|
| Triagem | 1 página, 5 campos | descobrir configuração não exige o documento inteiro |
| Preenchimento | 23 páginas, todos os campos | é a planilha que vai para o consumidor |
| Consolidação | todas as planilhas da fase 2 | votação por campo exige o conjunto completo |

**O vencedor final aceita empate.** Três rotas determinísticas já empatam em 100%
contra o conjunto de reserva — e é justamente por isso que a consolidação por campo
é melhor que escolher uma: onde empatam, a concordância vira confiança.

## 3. TACO completo

**Escopo real, medido:** 23 páginas de dados, ~15 campos por alimento, pelo menos 3
tabelas distintas (centesimal+minerais, vitaminas, ácidos graxos). O perfil hoje
declara 9 páginas e 5 campos.

- [ ] Ampliar o perfil para as 23 páginas e todos os campos
- [ ] Gerar a planilha consolidada — serve de entrada ao consumidor pessoal **e**
      mede completude

## 4. Preparar as outras máquinas

**Por que depois:** os parâmetros descobertos nos itens 0 e 1 vão fixados no
script. Rodar antes significaria mandar configuração mal ajustada, e a comparação
mediria o ajuste em vez da máquina.

**Premissa que mudou:** as máquinas têm placas de fabricantes **diferentes**
(NVIDIA, AMD e Intel). Nada pode depender de ferramenta de um fabricante só.

### 4.1 Detecção de ambiente — verificada, não suposta

**A memória de vídeo reportada por WMI é errada acima de 4 GB.** O campo
`AdapterRAM` é inteiro de 32 bits: uma placa de 12 GB reporta 4 GB. Um script que
decidisse o modelo por esse número mandaria a máquina grande rodar como pequena.

Fonte correta, **neutra de fabricante**: o registro do Windows, em
`HardwareInformation.qwMemorySize` (64 bits). Verificado nesta máquina; as
ferramentas de fabricante servem só para confirmar.

✅ **A leitura pelo registro já está implementada** — `procedencia.py:130-168`, com
o motivo escrito no código: `Win32_VideoController.AdapterRAM` satura em 4 GB, e por
isso não é usado. Confirmado em 02/08.

- [ ] Cruzar com as demais fontes e **alertar em discordância**
- [ ] **Gráfico integrado não tem esse campo** — usa memória do sistema
      dinamicamente. É caso distinto, não erro
- [ ] **Máquina com duas placas** (integrada + dedicada) é comum em portátil:
      escolher a correta e reportar, **nunca somar**

**Lacunas confirmadas em 02/08, e nenhuma é hipotética:**

`_gpu()` tenta `nvidia-smi` e, se não houver, cai no registro do Windows. Disso
decorre:

- [ ] **Placa AMD não é detectada em lugar nenhum** — a máquina reporta "nenhuma
      GPU detectada". Falta `rocm-smi`, e no Windows a leitura do registro já
      funcionaria para AMD, mas não é alcançada quando `nvidia-smi` está ausente
      e o sistema não é Windows
- [ ] **Linux só funciona com placa NVIDIA** — sem `nvidia-smi` não há caminho
      nenhum. Falta `/sys/class/drm/*/device/mem_info_vram_total` (AMD) e
      `lspci` para o nome
- [ ] **Saber se o servidor de inferência vai mesmo usar a placa AMD.** Ter a
      placa não basta: o Ollama traz o próprio ROCm com um conjunto restrito de
      arquiteturas, e a RX 5700 XT (RDNA 1, gfx1010) **não está nele** — a
      máquina cairia para processador sem avisar. A verificação honesta é
      carregar um modelo pequeno e ler `/api/ps`, que informa a divisão real
      CPU/GPU. É medição, não inferência a partir do nome da placa
- [ ] **Quanto o sistema já consome** antes de começar — placa e processador —
      para decidir o que cabe. Sem isso, "16 GB de VRAM" pode significar 11 livres
- [ ] **Identificador estável de máquina**, para amarrar cada resultado à sua
      origem sem depender do nome que a pessoa deu ao computador

**O que o pacote de instalação faz e não faz — verificado em 02/08:**

`experimentos/scripts/1-preparar-maquina.ps1` instala o servidor de inferência e os
**14 modelos da escada** (92,9 GB), é idempotente, e um teste amarra a lista dele à
de `parser.escada` — conjunto e ordem conferidos separadamente, porque a ordem
crescente é regra do instalador (falha de rede acontece no fim, com os pequenos já
em disco) e não da escada. `2-rodar-experimento.ps1` dispara a execução.

Mas **os dois são PowerShell**, e portanto:

- [ ] **Não há caminho para Linux** — nem instalação, nem execução
- [ ] **As dependências determinísticas não são instaladas pelo script**:
      Tesseract (OCR) e Ghostscript (Camelot) são executáveis de sistema, e sem
      eles duas rotas falham na máquina de destino sem dizer por quê
- [ ] Falta um **verificador único** que rode antes de tudo e diga, numa lista, o
      que está pronto e o que falta: servidor, modelos, Tesseract, Ghostscript,
      Python, dependências, espaço em disco, placa utilizável

### 4.2 Contenção — o experimento divide a máquina com o dono dela

Um jogo aberto durante a medição contamina o tempo, e **nada no número denuncia**.
É a mesma classe de erro das duas medições concorrentes, que já custou uma
refação.

**Exclusividade de placa de vídeo não é possível**, e é limitação do sistema
operacional: o agendador é multiplexado por projeto, não há como reservá-la, e
quando a memória enche o driver despeja por prioridade — o processo em primeiro
plano ganha do nosso. Impedir outro programa de abrir exigiria privilégio
administrativo e interceptação de processos, que é comportamento de software
malicioso.

O que funciona: os **contadores de desempenho do sistema** expõem nome e
identificador do processo sem depender de fabricante. Verificado.

- [ ] Detectar o intruso e **nomeá-lo** no aviso — "feche o programa X"
- [ ] **Pausar entre chamadas, nunca durante**: matar uma geração de 20 minutos
      pela metade não recupera nada
- [ ] **Chamada interrompida não retoma — refaz.** O servidor não expõe ponto de
      retomada, e o tempo daquela medição já estaria contaminado de qualquer forma
- [ ] **Blocos pequenos** (um modelo × uma configuração × uma página) limitam a
      perda a uma chamada
- [ ] Retomar **sozinho** quando o intruso fechar, **e** aceitar tecla — mas a
      tecla **só vale com a placa livre**; senão recusa e repete o alerta

### 4.3 Contaminação silenciosa — a que produz número plausível e errado

- [ ] **Modelo que não cabe na memória cai para o processador** e fica ordens de
      grandeza mais lento. Sairia como "esta máquina é lenta"
- [ ] **Redução por temperatura**: as primeiras medições saem mais rápidas que as
      últimas, e a diferença viraria "resultado"
- [ ] Modo de economia de energia; modelo residual de rodada anterior na memória

### 4.4 Robustez e integridade

- [ ] Download falho, disco cheio, suspensão automática, reinicialização por
      atualização, antivírus
- [ ] **Servidor pré-instalado em versão diferente invalida a comparação** entre
      máquinas: detectar e registrar, não só assumir
- [ ] Impressão digital do documento: garantir que todas leem o **mesmo** arquivo
- [ ] Registrar versão de tudo — servidor, driver, interpretador, modelo
- [ ] Verificar o isolamento em clone limpo: nenhuma máquina vê o resultado da
      outra

### 4.5 Experiência de quem executa

- [ ] **Execução em blocos sequenciais**, com log em arquivo e retomada do último
      bloco concluído
- [ ] **Estimativa de tempo calibrada na própria máquina** pelo primeiro bloco —
      uma estimativa da máquina de referência erraria por fator grande
- [ ] **Saída acessível a leitor de tela** — requisito real, não hipotético.
      Barra desenhada com caracteres e sobrescrita no terminal não expõe objeto de
      acessibilidade; a primitiva nativa do interpretador expõe. Usar a nativa
- [ ] **Guia para leigos**: um comando, mensagem clara a cada passo, e o que
      enviar de volta se falhar
- [ ] **Escada de modelos** — ver `MODELOS.md` e ADR-0014. Um modelo por vez, do
      menor ao maior, até falhar

## 5. Taxonomia de características, e a coleta que ela destrava

> Taxonomia registrada em
> [ADR-0021](docs/adr/0021-taxonomia-de-caracteristicas.md), com a tabela
> completa marcada por custo de detecção.

**O entregável final do projeto** é diferente do que existe hoje. Hoje temos
*"esta rota acertou X% neste documento"*. O que serve ao consumidor é: **dado um
documento com estas características, use esta estratégia com esta configuração.**

**O vocabulário vem antes dos documentos**, e a ordem importa: sem saber o que
procurar, a coleta traz dez documentos que exercitam a mesma característica. O
vocabulário torna a coleta eficiente — poucos documentos, muitas características.

### Característica é um segundo eixo da página

A correção que o ADR-0021 registra: `triagem.Classe` responde *"o que tem nesta
página?"*; a característica responde *"como ela está codificada?"*. Uma página é
`DADOS` **e** `DIGITALIZADA` ao mesmo tempo.

E a unidade é a **página**, não o arquivo — senão o documento misto, que é o caso
difícil, se perderia num rótulo único por PDF.

### O que o diagnóstico já detecta

`src/parser/diagnostico.py` cobre **cinco** características estruturais, cada uma
com severidade e ação recomendada:

| Detectado | Severidade |
|---|---|
| página rotacionada | bloqueia |
| sem camada de texto | bloqueia |
| camada de texto parcial | alerta |
| texto vertical | alerta |
| mapa de caracteres incompleto | alerta |

Os outros seis achados do módulo descrevem **qualidade do resultado**, não
estrutura da entrada — são diagnóstico de extração, não taxonomia.

Hoje ele **descreve**. O roteiro exige que **recomende**.

- [x] Taxonomia completa, marcando **detectável hoje** × **exige código** ×
      **exige inspeção manual** — ADR-0021
- [x] **Implementar a característica como segundo eixo — 2026-08-12, e não em
      `triagem.py`.** ADR-0021 já havia corrigido essa premissa: a estrutura
      certa é `diagnostico.caracterizar_pagina(pagina) -> list[Achado]`, que
      já é multirrótulo por construção (uma página acumula quantos achados
      tiver, sem exclusividade) — não uma reforma de `triagem.Classe`, que
      continua sendo o primeiro eixo ("o que tem nesta página"), exclusivo de
      propósito. O achado que faltava fisicamente (`imagem-embutida`, que o
      ADR-0021 já catalogava como "pronta" sem o código existir) foi
      implementado nesta data. Usado em produção por `parser.planejador`
      (Cenário B) — o Cenário A ainda não decide rota a partir disto.
- [ ] **Coletar documentos por característica** (eixo B) — com cuidado de dado
      pessoal: nada que identifique alguém entra no conjunto
- [ ] Evoluir o diagnóstico de descritivo para **prescritivo**
- [ ] Benchmark de patologias, depois que os documentos existirem

> **Limite que fica declarado:** o roteiro só pode afirmar sobre característica
> **medida em documento real**. Hoje há **um** documento — tabela rotacionada,
> texto nativo, 11 colunas, sem imagem. Toda a medição descreve esse caso. Regra
> de decisão sem documento que a exercite é hipótese, não resultado.

## 5b. Ampliar o alcance

- [ ] Adapters de outros formatos: XLSX, DOCX, TXT, XML (hoje só PDF)

## 6. Relatórios e artigo

**Do produto:**

- [ ] Relatório técnico (matriz completa, acurácia por campo, limitações)
- [ ] Relatório executivo (uma página: o que ganhou, por quanto, o que custou)
- [ ] Mapa de aderência à especificação de referência — vai em `docs/_private/`

**Do artigo** — protocolo em
[ADR-0020](docs/adr/0020-pre-registro-do-protocolo.md):

- [ ] Rascunho vivo, atualizado à medida que as medições saem — escrever no fim
      obrigaria a reconstruir raciocínio já esquecido
- [ ] Tabela completa da triagem, **com os eliminados** — omiti-los impede
      verificar se o corte foi honesto
- [ ] Seção de ameaças à validade, com as mitigações e o resíduo de cada uma
- [ ] Pacote de reprodutibilidade: prompts, perfis, versões, sementes, código de
      avaliação

> **O que não entra, e é decisão, não esquecimento:** nada de domínio de
> aplicação sob confidencialidade — nem nomes, nem vocabulário setorial, que
> identifica por dedução. O material publicável é o método, as medições, a
> taxonomia e o domínio de referência de fonte aberta.

---

## Acoplamento — medido, não afirmado

Verificado em 2026-07-31 sobre os 39 módulos do pacote:

| Indicador | Resultado |
|---|---|
| **Ciclos de importação** | **nenhum** |
| Fan-in mais alto | `modelo` (20) e `portas` (15) — as abstrações |
| Fan-out mais alto | `cli` (17) e `fabrica` (11) — os pontos de composição |
| Módulos folha | 9, entre eles `contexto` e `degraus` |

A leitura: ausência de ciclos em 39 módulos indica camadas de verdade. Fan-in
concentrado nas abstrações é o padrão de ports & adapters — todos dependem do
contrato, ninguém de implementação. Fan-out alto **só** onde é trabalho conhecer
as peças; se `fabrica` tivesse fan-out baixo, a fiação estaria espalhada.

Observação sem ação por ora: `lote` importa `extratores.posicional` dentro de
funções, para calibrar layout. É import local, não dependência estrutural — mas
é o único ponto onde um módulo de orquestração cita implementação pelo nome.

## Regras que valem para tudo acima

Nascidas de defeitos reais desta sessão. Estão em
`docs/adr/` e na memória do projeto.

**Uma medição por vez — e nada mais na máquina.** Duas medições em paralelo
inflam o tempo das duas, e nada no resultado denuncia. Aconteceu, e os números
tiveram de ser refeitos.

**A regra vale para trabalho comum, não só para outra medição.** Aconteceu de
novo em 2026-07-31, e desta vez o concorrente era rodar a suíte de testes: a
primeira página da rota de texto passou de 1 h contra os 2904 s de referência.
Não havia conflito de código — os módulos eram independentes — mas **o
processador é compartilhado**, e foi ele que faltou. A bateria foi interrompida e
refeita com a máquina ociosa.

A conclusão que fica: verificar acoplamento de código **não** basta para autorizar
paralelismo. Se o resultado inclui tempo, a máquina tem de estar livre — inclusive
de teste, compilação e navegador. É a mesma classe de contaminação que o ADR-0019
prevê para as máquinas de terceiros, e ela também vale aqui.

**Ensaiar script longo antes de rodar.** Um ensaio de 15 segundos pegou um erro de
sintaxe que teria custado uma noite de medição.

**Zero absoluto em todas as estratégias é suspeita da régua, não da extração.** Uma
rota que acerta 100% num gabarito não erra 100% em outro do mesmo documento.

**Reputação escolhe o que testar; medição decide o que usar.** Dois modelos
promovidos como especializados em documento foram desqualificados em benchmark
independente.

**Escada de comparação precisa de pelo menos três origens distintas.** Concentração
alta é sinal de pesquisa rasa, não de convergência do mercado.
