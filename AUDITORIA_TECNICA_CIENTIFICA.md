# Auditoria técnica e científica do PDF Parser

**Data da auditoria:** 2 de agosto de 2026  
**Escopo:** código-fonte, testes, documentação, ADRs, scripts, configurações e artefatos experimentais presentes no repositório.  
**Objetivo avaliado:** construir um parser híbrido — determinístico, OCR, LLM e VLM — capaz de extrair dados de PDFs heterogêneos e, paralelamente, produzir um benchmark publicável sobre modelos, rotas e restrições de hardware.

## 1. Parecer executivo

O projeto tem uma fundação de engenharia acima da média para um trabalho ainda experimental. Há uma preocupação real com proveniência, distinção entre ausência e erro, unidades, validação, rotas substituíveis, registro de decisões e preservação de resultados negativos. A documentação não tenta esconder hipóteses refutadas, o que é excelente prática científica.

Entretanto, **o sistema ainda não sustenta a alegação de interpretar “qualquer PDF” nem uma comparação científica conclusiva entre modelos**. O maior risco não está no número de modelos, e sim na validade da medição: o avaliador atual pode atribuir 100% a uma rota que também invente centenas de linhas; o holdout já influenciou correções; a verdade de referência deriva parcialmente de uma das próprias rotas; e os experimentos não registram configuração suficiente para reprodução.

### Veredito por dimensão

| Dimensão | Maturidade atual | Parecer |
|---|---:|---|
| Modelagem do domínio | 4/5 | Boa semântica de campos, evidência, sentinelas e unidades. |
| Arquitetura interna | 3/5 | Boas portas e adaptadores, mas a ingestão principal ainda está presa ao extrator posicional. |
| Cobertura real de PDFs | 1/5 | Validada essencialmente em uma família documental e um layout. |
| Avaliação científica | 2/5 | Ideias corretas, mas métricas e independência experimental têm falhas críticas. |
| Reprodutibilidade | 2/5 | Há inventários e artefatos, porém faltam ambiente travado e manifesto completo por execução. |
| Segurança e privacidade | 1/5 | PDFs e respostas são tratados como dados confiáveis; faltam isolamento e política de dados. |
| Testes e qualidade | 4/5 | Suite extensa e bem segmentada; faltam testes sistêmicos adversariais e automação de CI. |
| Prontidão para artigo | 2/5 | Adequado como estudo piloto; ainda não como evidência de generalização ampla. |
| Prontidão operacional | 2/5 | Útil para um domínio conhecido; não pronto para entrada arbitrária não confiável. |

**Conclusão:** preservar a base existente, mas tratar a fase atual como **protótipo experimental/piloto**. A prioridade deve ser consertar o instrumento de avaliação, formar um corpus independente e diversificado, tornar cada execução reprodutível e colocar limites de segurança antes de ampliar o catálogo de modelos.

## 2. Método e limites desta auditoria

Foram examinados aproximadamente **125 arquivos textuais, 19,3 mil linhas, 24 ADRs e 38 módulos de teste**, além do PDF TACO e dos resultados salvos. A auditoria incluiu leitura estática, execução segmentada dos testes, Black, Flake8, `pip check`, inspeção de dependências instaladas e confronto com fontes primárias da literatura e das ferramentas.

Esta é uma auditoria do repositório observado. Não houve repetição integral dos ensaios com todos os modelos, GPUs e documentos, portanto alegações de desempenho são avaliadas pela qualidade do protocolo e pelos artefatos disponíveis, não por uma nova campanha experimental.

Convenções usadas:

- **Fato:** diretamente observado em código, documentação, teste ou resultado.
- **Inferência:** conclusão técnica derivada de um ou mais fatos.
- **Recomendação:** mudança proposta; não é apresentada como resultado já demonstrado.

## 3. O que está bem feito e deve ser preservado

1. **Falha explícita em vez de corrupção silenciosa.** A preocupação de distinguir campo ausente, não legível, inválido e resposta cortada está alinhada ao risco real do produto.
2. **Proveniência por campo.** `Campo`, `Evidencia`, origem, página e texto bruto formam uma boa base para auditabilidade.
3. **Normalização e unidades como conceitos do domínio.** O uso de Pint e a validação de schema são mais seguros do que conversões dispersas.
4. **Portas e adaptadores.** `FonteDocumento`, `Extrator` e `Destino` permitem substituir mecanismos e testar componentes isoladamente.
5. **ADRs honestos.** Hipóteses inválidas e resultados negativos foram preservados. Isso reduz viés retrospectivo.
6. **Baselines determinísticos.** Comparar modelos com PyMuPDF, pdfplumber, Camelot e OCR é cientificamente indispensável.
7. **Separação conceitual entre erro e omissão.** Essa distinção é central para uma aplicação em que um número incorreto pode ser mais caro do que uma abstenção.
8. **Rastreamento inicial de modelos e documentos.** Hash do documento e inventário/digest de modelos mostram a direção correta.
9. **Testes numerosos.** Há boa cobertura unitária de casos de domínio, degraus, mapeamento, consolidação e CLI.
10. **Ausência de envio automático.** O fluxo não faz `push` por conta própria, reduzindo um risco operacional importante.

## 4. Achados críticos — prioridade P0

### P0.1 — A métrica principal não penaliza alucinações de itens

**Fato:** o avaliador percorre os itens/campos do golden e procura correspondências na saída. Registros extras não entram como falsos positivos. Identificadores duplicados podem ser sobrescritos silenciosamente durante a indexação.

**Evidência concreta:** no holdout existem rotas com **278–309 itens extraídos para apenas 10 itens de referência** e ainda assim acurácia de 100%. Na página 29, o Camelot retorna 62 registros para 31 esperados e obtém 153/155 nos campos avaliados.

**Impacto:** a métrica denominada “acurácia” é, na prática, algo próximo a recall condicional dos campos do golden. Ela não mede precisão de detecção, duplicação, linhas inventadas ou qualidade ponta a ponta. Um parser pode acrescentar cem linhas falsas sem perder pontos.

**Correção obrigatória:**

- alinhar itens por chave validada ou matching bipartido explícito;
- contabilizar `TP`, `FP`, `FN`, duplicatas e itens sem chave;
- publicar precisão, recall e F1 de itens;
- calcular métricas de campo apenas após o matching;
- preservar e reportar saídas não casadas;
- falhar diante de chaves duplicadas, em vez de sobrescrever;
- renomear a métrica histórica para evitar interpretação retroativa indevida.

### P0.2 — O holdout deixou de ser independente

**Fato:** a documentação registra que o holdout revelou problemas de alinhamento/sentinelas e que o código foi corrigido em resposta.

**Inferência:** esse conjunto passou a ser dado de desenvolvimento/validação. Chamá-lo de teste final subestima o viés de adaptação.

**Correção obrigatória:** congelar um **novo teste final intocado**, em documentos e templates nunca vistos; manter o holdout atual rotulado como desenvolvimento. A separação precisa ocorrer por documento, origem e família de layout — nunca por páginas aleatórias do mesmo PDF.

### P0.3 — A verdade de referência não é suficientemente independente

**Fato:** o `taco.csv` foi inicialmente produzido pela rota posicional e depois revisado. A anotação disponível não demonstra dois anotadores independentes, cegamento, adjudicação nem concordância interanotador.

**Impacto:** a rota que originou a pré-anotação pode ser favorecida e erros sistemáticos podem sobreviver à revisão.

**Correção obrigatória:** criar manual de anotação; usar no mínimo dois anotadores independentes nos conjuntos de teste; ocultar a identidade/saída das rotas; adjudicar divergências; versionar correções; medir concordância antes da adjudicação. Gerar pré-rótulos é aceitável no treino, mas não para o teste final sem controles fortes.

### P0.4 — O protocolo dos degraus não é o protocolo executado

**Fato:** [`src/parser/cli.py`](src/parser/cli.py) percorre apenas `vlm` e `llm`, omitindo as variantes menores, e instancia `SaidaEmDegraus` sem propagar contexto, seed, temperatura, modo de raciocínio e limite de tokens definidos na rota. O texto do prompt também não é idêntico ao caminho normal de produção.

**Impacto:** a tese de “mesmo modelo, mesmo prompt e mesma configuração; muda apenas a restrição de saída” não é verdadeira. H1–H3 comparam configurações compostas e prompts diferentes, não isolam um único fator.

**Correção obrigatória:** construir uma única `ConfigExecucao` imutável, serializável e compartilhada entre produção e experimento. Gerar os degraus como transformação de apenas um atributo; testar igualdade de todos os demais atributos e hash do prompt.

### P0.5 — O pipeline principal não roteia conforme as características do documento

**Fato:** [`src/parser/lote.py`](src/parser/lote.py) carrega o PDF e chama diretamente `ExtratorPosicional`. A triagem atual classifica páginas como dados/contexto/descartável, mas não seleciona OCR, tabela, layout, LLM ou VLM a partir de características observadas.

**Impacto:** a arquitetura descrita é mais ampla do que o produto executável. Um PDF escaneado, manuscrito, multicoluna ou com tabela não semelhante ao TACO não recebe automaticamente a rota adequada.

**Correção obrigatória:** implementar diagnóstico de página/documento, planejador de rotas, execução com orçamento e validação/fallback. A taxonomia deve ser executável e produzir evidência, não apenas um ADR.

### P0.6 — Entrada arbitrária é processada sem uma fronteira de segurança

**Fato:** PDFs não confiáveis passam por bibliotecas nativas, renderização, OCR e extratores no mesmo processo, sem sandbox, limite de tempo, RAM, pixels totais, páginas ou tamanho descomprimido. Respostas e trechos podem ser gravados integralmente.

**Impacto:** exposição a falhas do parser nativo, negação de serviço, decompression bombs, vazamento de conteúdo e comprometimento da estação. Um limite de DPI não limita uma página de dimensões gigantes.

**Correção obrigatória:** executar ingestão em worker isolado e de baixo privilégio; impor limites de arquivo, páginas, dimensões, pixels, CPU, RAM e tempo; atualizar dependências; detectar criptografia, reparo, anexos e ações; fazer quarentena/antimalware quando cabível; separar armazenamento bruto de resultados publicáveis.

### P0.7 — O ambiente não é reproduzível

**Fato:** o `pyproject.toml` usa limites inferiores abertos e não declara várias dependências efetivamente usadas: pdfplumber, Camelot, pytesseract, Pillow, psutil e executáveis do sistema. Não há lockfile, CI ou matriz de sistemas operacionais. Tags de modelos são mutáveis.

**Impacto:** duas máquinas podem executar código semanticamente diferente. Resultados não podem ser atribuídos apenas a modelo/VRAM.

**Correção obrigatória:** ambientes travados por sistema operacional/backend; versões e hashes; manifesto de Tesseract/Ghostscript/Ollama/driver; digest real do modelo por execução; CI para o núcleo; snapshot completo do ambiente em cada run.

## 5. Arquitetura e pipeline

### 5.1 Arquitetura-alvo recomendada

```text
entrada não confiável
    ↓
admissão segura ── hash, MIME real, criptografia, limites, quarentena
    ↓
inventário documental ── páginas, texto nativo, imagens, fontes, rotação, anexos
    ↓
diagnóstico por página/região ── layout, colunas, tabela, OCR, manuscrito, ilegível
    ↓
planejador de rotas ── capacidade × custo × hardware × política de dados
    ↓
extração em regiões ── determinística / OCR / tabela / LLM / VLM
    ↓
normalização comum ── tipos, unidades, locale, sentinelas
    ↓
validação e reconciliação ── schema, regras, evidência, desacordo, abstenção
    ↓
saída canônica + trilha de auditoria + fila humana
```

O documento não deve escolher uma única rota global. Páginas e regiões podem exigir mecanismos diferentes. Uma tabela nativa pode usar Camelot enquanto um cabeçalho escaneado usa OCR e uma anotação manuscrita vai para VLM ou revisão humana.

### 5.2 Diagnóstico executável

Criar atributos mensuráveis, com estado `presente`, `ausente`, `incerto` e evidência:

- texto nativo útil e sua cobertura espacial;
- página imagem/scan e qualidade estimada;
- rotação global e por bloco;
- número de colunas e ordem de leitura;
- linhas de tabela, células mescladas, tabela sem bordas e continuação entre páginas;
- fontes incorporadas, mapeamento Unicode anômalo e caracteres substitutos;
- escrita manual;
- baixa legibilidade, contraste e resolução;
- formulários, checkboxes, assinaturas e fórmulas;
- páginas enormes, anexos, criptografia e reparo do arquivo.

Cada detector precisa de unidade de teste, golden próprio, limiar versionado e taxa de erro conhecida. Quando a confiança do diagnóstico for baixa, o planejador deve tentar rotas complementares ou se abster.

### 5.3 Contratos e proveniência

O modelo atual mistura **origem epistemológica** com **método de obtenção**. Um valor emitido por LLM/VLM é marcado como extraído, ainda que possa ser inferido ou alucinado; `texto_bruto` pode conter a resposta do modelo, e não a evidência exata do PDF.

Separar pelo menos:

- `natureza`: presente_no_documento, derivado, inferido, fornecido_externamente;
- `metodo`: pymupdf, pdfplumber, camelot, ocr, llm, vlm, humano;
- `artefato`: documento/hash, página, bbox/polígono, imagem e citação literal;
- `execucao`: modelo/digest, prompt/hash, parâmetros, backend e versão;
- `validacao`: regras aplicadas, resultado, desacordos e motivo de abstenção;
- `score`: valor técnico não calibrado; usar `probabilidade` somente após calibração.

`CONFIANCA_MODELO = 0.8` é um número arbitrário e não é usado como probabilidade calibrada na consolidação. Renomeá-lo para score heurístico ou removê-lo até medir Brier score/ECE e confiabilidade por subgrupo.

### 5.4 Saída estruturada de modelos

Em [`src/parser/degraus.py`](src/parser/degraus.py), o schema exige principalmente o contêiner `itens`; falta tornar campos internos obrigatórios e proibir propriedades desconhecidas quando essa for a intenção. A validação posterior aceita estruturas fracas e o adaptador filtra silenciosamente elementos inválidos.

Além disso, `done_reason=length` só é tratado de modo especial em uma condição limitada. Uma resposta não vazia cortada pode começar com JSON válido/balanceado e ser aceita, omitindo o restante.

Recomendações:

- qualquer término por limite deve ser falha explícita ou saída parcial marcada;
- validar o objeto inteiro com Pydantic/JSON Schema após a geração;
- não converter estrutura inválida em lista vazia;
- testar truncamento após um primeiro item válido, duplicatas, campos extras e tipos incorretos;
- separar “JSON sintaticamente válido” de “resultado semanticamente completo”.

### 5.5 Seleção de rotas

[`src/parser/fabrica.py`](src/parser/fabrica.py) exclui somente `llm` e `vlm` quando `incluir_modelos=False`; `llm-menor` e `vlm-menor` podem continuar ativos. Isso viola a expectativa de `--sem-modelos` e pode disparar cargas caras.

Em vez de nomes especiais, cada rota deve declarar capacidades e propriedades: `usa_modelo`, `modalidade`, `requer_gpu`, VRAM estimada, contexto máximo, suporte de backend, custo e política de privacidade. Filtros devem operar sobre essas propriedades.

## 6. Validade científica e desenho experimental

### 6.1 O que o corpus atual permite afirmar

O TACO é útil como estudo de caso para tabela rotacionada com texto nativo. Páginas distintas do mesmo arquivo não constituem evidência independente de generalização de layout. O máximo defensável atualmente é:

> “Generalização interna entre páginas de uma mesma família/layout foi observada no caso TACO.”

Não é defensável concluir “qualquer PDF”, “generalização para PDFs” ou superioridade ampla de um modelo.

Benchmarks atuais ilustram a escala do problema: OmniDocBench cobre tipos e atributos diversos e mede texto, fórmulas, tabelas e ordem de leitura; DocLayNet contém 80.863 páginas anotadas e 11 classes de layout; trabalhos recentes como Dr. DocBench e MPDocBench-Parse enfatizam páginas difíceis, domínios especializados e estrutura entre páginas. Essas referências devem orientar a diversidade, não ser usadas como um número mágico de amostra ([OmniDocBench](https://arxiv.org/abs/2412.07626), [DocLayNet](https://arxiv.org/abs/2206.01062), [Dr. DocBench](https://arxiv.org/abs/2606.01393), [MPDocBench-Parse](https://arxiv.org/abs/2605.22100)).

### 6.2 Corpus recomendado

Usar três camadas, com licenças e proveniência explícitas:

1. **Benchmarks públicos:** OmniDocBench, DocLayNet, PubTables-1M/PubTabNet/FinTabNet quando compatíveis com a tarefa, OCRBench v2 para capacidades OCR/VLM.
2. **Corpus de estresse controlado:** PDFs sintéticos/fatoriais variando uma característica por vez — rotação, blur, DPI, compressão, colunas, fonte, ruído, tabela sem borda, células mescladas.
3. **Corpus real:** documentos de múltiplos domínios, fontes, idiomas, décadas, scanners e famílias de template, com governança de privacidade.

Dividir por **documento, template, organização/origem e transformação ancestral** para evitar vazamento. Uma versão rotacionada do mesmo PDF não pode cair em treino e teste diferentes. Deduplicar por hash exato e similaridade visual/textual.

### 6.3 Taxonomia multifatorial

Um PDF pode ter várias dificuldades simultâneas. Usar rótulos multilabel por página/região e registrar severidade. A análise deve reportar desempenho global e por característica/interação, com intervalos amplos onde a amostra for pequena.

Sugestão mínima:

- camada: nativo, scan, híbrido;
- estrutura: simples, multicoluna, tabela, formulário, fórmula, figura;
- degradação: rotação, blur, ruído, baixa resolução, compressão;
- tipografia: Unicode anômalo, fonte incomum, escrita manual;
- escala: página única, multipágina, continuidade entre páginas;
- legibilidade: legível, ambíguo, humanamente ilegível;
- idioma/script e domínio.

### 6.4 Métricas adequadas

| Subtarefa | Métricas principais |
|---|---|
| Detecção de itens | precisão, recall, F1, duplicatas, falsos itens por página |
| Campos categóricos | macro/micro F1, matriz de confusão, abstenção |
| Números/unidades | match exato, erro absoluto/relativo por campo, erro de unidade |
| Texto/OCR | CER, WER, distância de edição normalizada |
| Tabelas | estrutura/células, TEDS ou GriTS, spanning cells |
| Layout | IoU/mAP por classe, ordem de leitura |
| Página/documento | sucesso completo, cobertura e taxa de falha |
| Confiança | risk–coverage, Brier score, ECE, seletividade |
| Operação | tempo frio/quente, pico de VRAM/RAM, energia, falhas, disco |

O repositório [Docling Eval](https://github.com/DS4SD/docling-eval) pode servir de referência de integração de datasets e métricas. O repositório oficial do [OmniDocBench](https://github.com/opendatalab/OmniDocBench) documenta métricas como distância de edição, TEDS e ordem de leitura.

A tolerância relativa global de 1% não deve valer indistintamente para todos os campos. Definir tolerância absoluta e relativa por campo/unidade antes da avaliação, incluindo comportamento próximo de zero, e publicar análise de sensibilidade.

### 6.5 Unidade estatística e dependência

Células da mesma linha/página/documento não são independentes. McNemar em células e bootstrap de campos superestimam a amostra efetiva.

Plano recomendado:

- declarar documento como unidade primária;
- usar bootstrap por cluster no nível do documento;
- usar modelos hierárquicos/mistos para páginas e campos aninhados;
- comparar rotas de forma pareada nos mesmos documentos;
- predefinir desfecho primário, efeito mínimo relevante, alfa, repetições e correção por múltiplas comparações;
- publicar distribuição, intervalo de confiança e tamanho de efeito, não apenas p-valor;
- realizar análise de poder ou justificar formalmente estudo exploratório.

Com um documento, inferência estatística sobre população de PDFs não é válida, independentemente do número de células.

### 6.6 Hipóteses causais

As hipóteses atuais frequentemente alteram vários fatores:

- degraus mudam restrição e prompt;
- página versus chunks muda chamadas, contexto e tarefa;
- modelo “thinking” versus outro modelo muda treinamento e arquitetura;
- contexto pode mudar offload, memória e backend.

Se o objetivo for causal, alterar um fator por vez e verificar programaticamente a igualdade dos demais. Se isso não for possível, formular como comparação entre **configurações completas**, sem atribuir a diferença a um único mecanismo.

### 6.7 VRAM e heterogeneidade de máquinas

Comparar máquinas de 2, 4, 6, 8, 12 e 16 GB não identifica o efeito causal da VRAM: fabricante, geração, driver, backend, CPU, RAM, energia e temperatura também mudam. Tratar como benchmark observacional de configurações reais.

Registrar por execução:

- GPU, fabricante, arquitetura, driver e backend;
- VRAM nominal, livre antes, pico e reserva do sistema;
- camadas/offload na GPU e spill para CPU;
- CPU, RAM livre/pico, armazenamento;
- versão do SO/Ollama/runtime;
- potência, temperatura e throttling quando possível;
- tempo de carregamento separado de prompt/eval;
- falha por OOM, timeout ou backend incompatível.

Para isolar VRAM, usar a mesma máquina/GPU com limite de memória controlado, quando tecnicamente válido. Realizar aquecimento, múltiplas repetições e ordem randomizada/bloqueada; separar execução fria e quente.

### 6.8 Contexto dos modelos

Os scripts usam `NATIVO_MINIMO = 32768` global. A página oficial do [DeepSeek-OCR no Ollama](https://www.ollama.com/library/deepseek-ocr) informa contexto de 8K para o artefato exibido. Solicitar 32K como se fosse capacidade nativa pode alterar memória, falhar ou tornar a comparação inválida.

Criar catálogo versionado por **digest**, com contexto nativo/verificado, quantização, tamanho real, multimodalidade, template, stop tokens, suporte a schema e backend mínimo. Nunca inferir capacidade pelo nome/tag.

### 6.9 Pré-registro

Um ADR versionado é valioso, mas o Git permite reescrita e parte dos dados já foi observada. Rotular os resultados existentes como piloto/exploratórios. Antes da coleta confirmatória, registrar protocolo, golden congelado, exclusões, métricas, hipóteses e análise em serviço com registro imutável/time-stamped, como o [OSF Registries](https://help.osf.io/article/330-welcome-to-registrations). A lista de verificação do [NeurIPS](https://neurips.cc/public/guides/PaperChecklist) é uma boa auditoria de reprodutibilidade, número de execuções e recursos computacionais.

## 7. Engenharia de software e qualidade

### 7.1 Dependências e empacotamento

- criar `uv.lock`, lock equivalente ou ambientes Conda por backend;
- declarar extras como `tables`, `ocr`, `experiments`, `nvidia`, `amd`;
- detectar executáveis de sistema e falhar com mensagem acionável;
- definir matriz suportada de Python; a auditoria ocorreu em Python 3.14, enquanto a formatação aponta para 3.10 e o script prepara 3.12;
- adicionar entry point de console no pacote;
- gerar SBOM e executar auditoria de vulnerabilidades/licenças;
- pinçar modelos por digest, não por tag.

O PyMuPDF tem licenciamento AGPL ou comercial, segundo a [FAQ oficial](https://pymupdf.readthedocs.io/en/latest/faq/index.html). O modo de distribuição/serviço do produto deve passar por revisão de licença; não basta mencionar “licença” em um teste.

### 7.2 Persistência e concorrência

Em [`src/parser/medicao.py`](src/parser/medicao.py), a trava usa verificação seguida de escrita, que não é uma aquisição atômica. Dois processos podem observar ausência e ambos escrever. Resultados JSON também são gravados diretamente; interrupção pode corrompê-los, e backup com resolução de segundos pode colidir.

Usar criação exclusiva atômica (`O_CREAT|O_EXCL`) com token/owner, expiração segura e teste multiprocessos. Para artefatos, escrever em arquivo temporário no mesmo volume, `flush/fsync` quando necessário e `os.replace`. Todo run deve ter ID único, manifesto e estado `started/completed/failed`.

### 7.3 Estado imutável

`ConfigDict(frozen=True)` não congela profundamente listas/dicionários aninhados. Preferir tuplas e mappings imutáveis ou cópias defensivas, especialmente em configurações usadas para comparação científica.

### 7.4 Qualidade automatizada

Estado observado:

- Black: passou em 79 arquivos;
- `pip check`: passou;
- Flake8: uma falha `F841` em `src/parser/medicao.py:81`;
- os blocos executáveis da suite passaram, com 8 skips dependentes de documento;
- o módulo `tests/test_medicao.py` não completou de forma confiável no executor desta auditoria e deve ser reexecutado localmente/CI;
- houve uma regressão transitória observada em código local durante a auditoria e posteriormente revertida; ela não é reportada como bug atual.

Adicionar CI com versões suportadas, type checker (Pyright/mypy), cobertura com limiar por módulo crítico, Ruff/Flake8, auditoria de dependências e testes de propriedades/fuzzing. Testes unitários não substituem corpus adversarial de PDFs reais e malformados.

### 7.5 Testes faltantes prioritários

- avaliador com saída extra, duplicata e chave ausente;
- truncamento depois de JSON parcialmente válido;
- `--sem-modelos` garantindo zero cliente de modelo;
- igualdade de configuração entre braços experimentais;
- corrida real de aquisição de lock;
- crash durante escrita de resultado;
- PDFs criptografados, corrompidos, enormes, com página gigante e anexos;
- prompt injection contido no PDF e tentativa de exfiltração;
- CSV com células iniciadas por `=`, `+`, `-`, `@`;
- separação sem vazamento entre derivados do mesmo documento;
- determinismo e repetibilidade por backend;
- golden com discordância e adjudicação.

## 8. Segurança, privacidade e cadeia de suprimentos

### 8.1 Modelo de ameaça mínimo

Atacantes ou acidentes podem explorar: parser nativo, consumo de recursos, conteúdo sensível, instruções adversariais ao modelo, endpoint remoto, planilhas geradas e dependências/modelos comprometidos.

A [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) recomenda validação de tipo/tamanho, limites, antivírus/sandbox e CDR conforme o contexto. Para este projeto, adicionar:

- MIME por conteúdo e validação estrutural;
- limite antes e depois de renderização/descompressão;
- processo isolado, usuário sem privilégios e diretório temporário privado;
- timeouts e cotas de CPU/RAM/pixels;
- atualização rápida de parsers nativos;
- política para PDFs criptografados/reparados e conteúdo incorporado;
- logs sem texto documental por padrão.

### 8.2 Modelos locais e remotos

O cliente aceita URL configurável. Isso permite enviar texto/imagens a outro host sem uma barreira de consentimento. Exigir opção explícita `--allow-remote`, TLS, allowlist, aviso de classificação do dado, autenticação e registro do destino. A API local do Ollama não exige autenticação, conforme a [documentação oficial](https://docs.ollama.com/api/authentication); ela deve permanecer em loopback ou atrás de controle de acesso.

Conteúdo do PDF deve ser tratado como dado, nunca como instrução de sistema. Prompts precisam delimitar o documento, proibir ações externas e validar toda saída. Isso reduz, mas não elimina, prompt injection.

### 8.3 Dados e publicação

Evidências, vizinhanças, respostas completas e hostname podem revelar conteúdo e identidade. Definir:

- classificação e base legal/consentimento;
- minimização e redação;
- criptografia em repouso e trânsito;
- controle de acesso e retenção;
- ID pseudônimo da máquina com mapa privado separado;
- dataset público separado do armazenamento bruto;
- revisão automática e humana antes de commit/publicação.

O script que cria commits de resultados deve operar somente em artefatos classificados como publicáveis. O padrão mais seguro é não versionar resultados brutos de clientes.

### 8.4 CSV e planilhas

Valores extraídos que começam por `=`, `+`, `-` ou `@` podem virar fórmulas ao abrir CSV em planilhas. Escapar células não confiáveis no exportador CSV e manter o valor original em formato estruturado seguro.

### 8.5 Guardas de commit

O hook de confidencialidade é útil como defesa adicional, mas:

- hooks locais podem ser ignorados e não substituem CI/server-side;
- a lista externa pode faltar em um clone e o comportamento é permissivo;
- a função de exceção ignora uma linha inteira quando encontra qualquer trecho permitido, permitindo que outro trecho proibido na mesma linha passe.

Corrigir a exceção para remover apenas o span permitido e escanear o restante; adicionar teste de linha mista; executar scanner no CI e secret scanning. `.gitignore` não protege conteúdo já rastreado.

### 8.6 Cadeia de suprimentos

Instalações por `pip`, `winget` e `ollama pull` sem versões/digests travados dificultam reprodução e aumentam risco. Verificar hashes/assinaturas quando disponíveis, usar registry confiável, salvar SBOM e política de atualização. Modelos também são dependências executáveis e precisam de inventário e licença.

## 9. Documentação e coerência interna

Foram encontrados sinais de deriva:

- README declara contagens de testes como valor fixo, que envelhece rapidamente;
- o README do golden ainda descreve a criação do arquivo que já existe;
- ADR de consolidação diz que a implementação não começou, mas há módulo e testes;
- tabelas de modelos/hardware misturam estimativas com fatos e podem ficar obsoletas;
- a alegação de generalização é mais forte que a evidência;
- “schema-constrained” não elimina a necessidade de validação posterior;
- o prompt combina orientação por posição com a frase “nunca por posição”, criando ambiguidade;
- a licença do TACO não está acompanhada, no repositório, de evidência primária suficiente;
- há árvores antigas e novas de resultados, tornando ambíguo qual é a fonte canônica.

Recomendações:

- gerar contagem de testes, modelos e resultados automaticamente;
- adicionar status/última verificação a cada ADR;
- separar fato medido, estimativa e hipótese;
- criar glossário de métrica e escopo de suporte;
- definir uma única raiz canônica, append-only, para runs;
- adicionar `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CITATION.cff` e datasheet/model cards do corpus.

## 10. Reprodutibilidade por execução

Cada execução deve salvar um manifesto autocontido antes de iniciar e completá-lo ao final:

```yaml
run_id: uuid
status: started|completed|failed
code:
  git_commit: ...
  dirty: true|false
  diff_hash: ...
data:
  document_sha256: ...
  golden_version: ...
  split: train|dev|test
route:
  name: ...
  config_hash: ...
model:
  tag: ...
  digest: ...
  quantization: ...
  context: ...
prompt:
  template_version: ...
  sha256: ...
decoding:
  seed: ...
  temperature: ...
  max_tokens: ...
environment:
  os: ...
  python: ...
  lock_hash: ...
  ollama: ...
  backend: ...
  driver: ...
hardware:
  cpu: ...
  ram_free_before: ...
  gpu: ...
  vram_nominal: ...
  vram_free_before: ...
measurement:
  repetitions: ...
  warmup: ...
  peak_ram: ...
  peak_vram: ...
  load_s: ...
  prompt_s: ...
  eval_s: ...
```

Atualmente o caminho principal registra essencialmente DPI em parte dos resultados; isso é insuficiente para reconstruir a execução.

## 11. Roadmap priorizado

### Fase 0 — corrigir o instrumento (1–2 semanas)

1. Corrigir falsos positivos/duplicatas no avaliador e renomear métricas históricas.
2. Corrigir `--sem-modelos`, truncamento e validação estrutural.
3. Unificar `ConfigExecucao` e manifesto de run.
4. Fixar dependências e catálogo de modelos por digest/contexto.
5. Reclassificar o holdout atual como desenvolvimento.
6. Corrigir lock/escrita atômica e Flake8.

**Gate:** nenhuma rota recebe nota perfeita com registros extras; toda execução é reproduzível por manifesto.

### Fase 1 — segurança e arquitetura mínima (2–4 semanas)

1. Admissão segura, limites e worker isolado.
2. Diagnóstico executável para nativo/scan/rotação/colunas/tabela.
3. Planejador de rotas por página/região com orçamento e fallback.
4. Proveniência separando natureza, método, evidência e validação.
5. CI, type checking, dependency audit e testes adversariais.

**Gate:** PDFs inválidos/hostis falham de forma limitada; nenhum modelo remoto é usado sem consentimento explícito.

### Fase 2 — corpus e piloto metodológico (4–8 semanas)

1. Manual de anotação, dois anotadores e adjudicação.
2. Benchmarks públicos + corpus de estresse + corpus real.
3. Split por documento/template/origem e deduplicação.
4. Métricas por subtarefa e característica.
5. Piloto para estimar variância, custo e tamanho amostral.

**Gate:** concordância documentada, teste final congelado, métricas e análise pré-especificadas.

### Fase 3 — estudo confirmatório (8–12+ semanas)

1. Pré-registro imutável.
2. Campanha randomizada/bloqueada, com repetições e monitoramento de hardware.
3. Análise em nível de documento, intervalos e múltiplas comparações.
4. Auditoria de erros, abstenção, subgrupos e custo.
5. Pacote de reprodução com código, ambiente, manifests e dados permitidos.

**Gate:** conclusões limitadas ao domínio amostrado, com incerteza e falhas publicadas.

## 12. Estratégia de produto para “qualquer PDF”

“Qualquer PDF” não é um requisito testável como garantia absoluta. Existem arquivos criptografados sem senha, corrompidos, vazios, adversariais ou humanamente ilegíveis. Converter a frase em um contrato operacional:

- aceitar qualquer arquivo que satisfaça a política de admissão;
- diagnosticar capacidades e limitações;
- extrair com evidência quando suportado;
- abster-se de modo explícito quando não houver evidência suficiente;
- encaminhar para revisão humana;
- nunca transformar incerteza em dado silenciosamente.

Definir SLOs por envelope, por exemplo: taxa de ingestão segura, cobertura, precisão condicionada à aceitação, taxa de abstenção, tempo e memória. O objetivo empresarial correto é **maximizar cobertura com risco controlado**, não prometer infalibilidade.

## 13. Alegações publicáveis hoje e depois das correções

### Defensável hoje

- foi construída uma arquitetura experimental híbrida com múltiplas rotas;
- um estudo piloto em um PDF tabular rotacionado revelou diferenças de custo e comportamento;
- output estruturado, contexto e modalidade apresentaram problemas que motivam hipóteses futuras;
- a distinção entre omissão e erro orienta o desenho do sistema.

### Não defensável hoje

- o melhor modelo para cada característica de PDF;
- generalização para qualquer PDF;
- efeito causal da VRAM;
- acurácia ponta a ponta de 100%;
- superioridade estatística de uma rota em população ampla.

### Potencialmente defensável após o roadmap

- desempenho comparativo em um universo de documentos explicitamente definido;
- curvas de risco–cobertura e custo–qualidade por configuração de hardware;
- benefício incremental de rotas híbridas sob protocolo controlado;
- taxonomia de falhas e recomendações reproduzíveis por característica.

## 14. Critérios de aceite antes de submeter o artigo

- [ ] Golden independente, dupla anotação e concordância reportada.
- [ ] Teste final nunca usado para desenvolvimento.
- [ ] Split sem vazamento de documento/template/derivação.
- [ ] Falsos positivos, duplicatas e abstenções entram na métrica.
- [ ] Unidade estatística e análise por cluster predefinidas.
- [ ] Repetições, warmup, ordem e efeito mínimo definidos.
- [ ] Configuração integral e digest por execução.
- [ ] Dependências e modelos travados.
- [ ] Resultados brutos imutáveis; análises regeneráveis.
- [ ] Segurança/privacidade/licenças documentadas.
- [ ] Claims limitados ao corpus e acompanhados de incerteza.
- [ ] Falhas e resultados negativos publicados.
- [ ] Artefato reproduzido em pelo menos uma máquina independente.

## 15. Prioridade final

Se apenas cinco mudanças forem possíveis agora, fazer nesta ordem:

1. **Consertar o avaliador para penalizar itens inventados e duplicados.**
2. **Criar um novo teste final independente, com anotação dupla.**
3. **Registrar e travar integralmente ambiente, modelo, prompt e parâmetros.**
4. **Implementar diagnóstico/roteamento real por página ou região.**
5. **Isolar e limitar o processamento de PDFs não confiáveis.**

Essas mudanças aumentam mais a credibilidade científica e a segurança do produto do que adicionar novos modelos neste momento.

