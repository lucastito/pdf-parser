# Triagem de PDFs do Google Drive para o experimento

**Data:** 2 de agosto de 2026  
**Origem examinada:** unidade local `H:\` (Google Drive)  
**Política:** somente leitura; nenhum PDF foi movido, copiado para o repositório ou publicado.

## Conclusão

Sim. [`LISTA-DE-BUSCA.md`](LISTA-DE-BUSCA.md) é o roteiro operacional do
[`ADR-0021`](../../docs/adr/0021-taxonomia-de-caracteristicas.md). Os dois estão
alinhados no objetivo, nos três eixos e na preferência por poucos documentos com
muitas características.

A lista simplifica corretamente o ADR para uso durante a coleta, mas precisa de
quatro correções antes de virar protocolo científico definitivo:

1. a classificação estrutural é por **página/região**, não apenas por arquivo;
2. “documento misto” é uma combinação de páginas, não uma classe de página;
3. características automáticas, inferidas e confirmadas visualmente devem ser
   distinguidas;
4. “nenhum nome/e-mail” conflita com a categoria artigo científico, pois autoria e
   contato editorial são parte da publicação e da atribuição da licença.

Com política de risco conservadora, a busca encontrou **três candidatos locais
fortes e redistribuíveis**, um candidato externo oficial forte e alguns documentos
de reserva. O Drive não contém, com licença e privacidade simultaneamente
confirmadas, todos os 19 casos procurados.

## Cobertura da varredura

| Resultado | Quantidade |
|---|---:|
| PDFs encontrados | 743 |
| PDFs abertos e analisados | 732 (98,5%) |
| Criptografados/fechados | 6 |
| Entradas inválidas na lixeira | 5 |
| Faixa ideal de 5–20 páginas | 205 |
| Sinal de scan | 83 |
| Sinal de documento misto | 75 |
| Alguma página em paisagem | 52 |
| Rotação declarada no PDF | 16 |
| Heurística de múltiplas colunas | 213 |
| Widget de formulário | 11 |
| Idioma provavelmente não português | 264 |
| Sinal conservador de conteúdo privado/sensível | 217 |
| Menção textual a licença aberta | 19 |

Esses números são **triagem**, não ground truth. Colunas, scan e mistura foram
confirmados visualmente apenas nos finalistas. Células mescladas, tabelas entre
páginas, manuscrito, subtotais e qualidade do scan não podem ser declarados apenas
pela heurística.

## Política de privacidade usada

Foram excluídos da seleção:

- documentos médicos, exames, faturas, informes financeiros e tributários;
- documentos jurídicos ou administrativos pessoais;
- currículos, certificados, documentos familiares e formulários identificados;
- qualquer arquivo com CPF ou forte indício de dado privado;
- scans cuja ausência de texto impossibilitasse descartar PII por conteúdo, salvo
  quando a origem oficial e pública pudesse ser comprovada externamente.

Nomes de arquivos e caminhos desses documentos não são reproduzidos neste relatório.

### Identificação pública em obras publicadas

Autoria, afiliação e contato profissional de um artigo aberto não devem ser
confundidos com prontuário, CPF ou dado familiar. Ainda assim, dado tornado público
continua sujeito à finalidade, boa-fé e direitos do titular segundo a
[LGPD, art. 7º, §§ 3º–7º](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm).
A [ANPD](https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-lanca-guia-orientativo-sobre-tratamento-de-dados-pessoais-para-fins-academicos)
esclarece que agentes acadêmicos que não sejam “órgãos de pesquisa” precisam de
outra hipótese legal aplicável à situação concreta.

Política recomendada:

- **proibir:** dado privado, sensível ou incidental sobre pessoas;
- **permitir condicionalmente:** identificação profissional já publicada, necessária
  para citação/atribuição, com fonte, finalidade e minimização documentadas;
- **não extrair para o golden:** nomes, e-mails, telefones ou endereços, mesmo quando
  aparecem licitamente no documento;
- **se a política desejada for zero dado pessoal literal:** excluir todos os artigos
  e canvases assinados, inclusive os candidatos abaixo.

## Candidatos locais aprovados tecnicamente

### 1. BaMBa — candidato principal

| Campo | Evidência |
|---|---|
| Arquivo local | `lendo - indicado pelo daniel - bav088.pdf` |
| SHA-256 | `21D4D3444C9498D6F218B55E8BF92F8B2E41CF9CB47F4ADB77AE705665C0F25F` |
| Páginas | 10 |
| Categoria | artigo científico aberto |
| Características confirmadas | **1** tabela sem grade; **6** duas colunas; **9** células/registros multilinha; **18** inglês; tabela com conteúdo girado |
| Página-chave | 8 |
| Licença | CC BY 4.0 |
| Privacidade | apenas identificação acadêmica/publicada; não usar os contatos como dados experimentais |

A página 8 contém uma tabela comparativa grande, sem grade, com muitas colunas,
conteúdo multilinha, marcadores de nota e orientação lateral. O PDF é especialmente
útil porque PyMuPDF não detectou essa tabela automaticamente.

A página oficial da Oxford University Press declara reutilização, distribuição e
reprodução irrestritas com citação adequada sob CC BY 4.0:
[BaMBa: towards the integrated management of Brazilian marine environmental data](https://academic.oup.com/database/article/doi/10.1093/database/bav088/2433221).

### 2. Apache Drill — candidato principal

| Campo | Evidência |
|---|---|
| Arquivo local | `hausenblas2013.pdf` |
| SHA-256 | `1AFFD195BF89954BC25FC75221125EE3B4297B8BF6DB7B464AFE1575B72446B6` |
| Páginas | 5 |
| Categoria | artigo técnico aberto |
| Características confirmadas | **1** tabela essencialmente sem grade; **6** duas colunas; **9** valores multilinha; **18** inglês; figuras e código |
| Página-chave | 5 |
| Licença | CC BY 3.0 US, impressa no próprio PDF |
| Privacidade | autoria e contato profissional publicados; não entram no golden |

O documento combina layout de artigo, figuras, código e uma tabela comparativa larga
na página 5. A licença está impressa na última página. A página do editor confirma que
o artigo é open access sob Creative Commons:
[Apache Drill: Interactive Ad-Hoc Analysis at Scale](https://journals.sagepub.com/doi/10.1089/big.2013.0011).

### 3. Team Canvas v0.8 — candidato complementar

| Campo | Evidência |
|---|---|
| Arquivo local | `Team Canvas - v. 0.8.pdf` |
| SHA-256 | `77830D954ABAD5C8F1827EA0885FAAE8E01219E39E518BD1CAFAACD21BF5C427` |
| Páginas | 1 — fora da faixa ideal, mas estruturalmente útil |
| Categoria | canvas/formulário vazio |
| Características confirmadas | **4** regiões/células mescladas; **13** paisagem; **18** inglês |
| Não marcar | **11**, pois o formulário não está preenchido |
| Licença | CC BY-SA 4.0, impressa no PDF e confirmada no site oficial |
| Privacidade | template vazio; nomes dos autores são atribuição pública |

O canvas tem grade irregular, áreas mescladas e hierarquia visual. É um bom teste para
layout/células, mas não substitui um formulário preenchido. O
[site oficial do Team Canvas](https://www.theteamcanvas.com/) confirma CC BY-SA 4.0.

## Candidato externo aprovado

### 4. NACA Technical Note 117 — candidato principal para scan antigo

| Campo | Evidência |
|---|---|
| Documento | `NACA-TN-117` — *The Synchronization of N.A.C.A. Flight Records* |
| Páginas | 6 |
| Categoria | relatório técnico governamental histórico |
| Características confirmadas | **2** documento escaneado com camada OCR; **10** scan degradado; **18** inglês; **19** digitalização antiga; fotografias e diagramas |
| Limitação | como há OCR oculto, não representa o subtipo estrito “imagem sem texto selecionável” |
| Direitos | NTRS: `Public` e `Work of the US Gov. Public Use Permitted` |

As páginas têm tonalidade irregular, manchas, carimbos, texto datilografado e figuras.
A página oficial documenta distribuição e situação autoral:
[NACA-TN-117 no NASA Technical Reports Server](https://ntrs.nasa.gov/citations/19930080893).

O PDF pode ser obtido da própria NASA pelo identificador `19930080893`; guardar no
manifesto a URL, data de acesso e SHA-256 após o download.

## Reservas redistribuíveis, de baixo ganho

| Documento | Páginas | Uso possível | Motivo de não priorizar |
|---|---:|---|---|
| `2018 Kanban Guide for Scrum Teams.pdf` | 8 | inglês; CC BY-SA 4.0 impressa | acrescenta quase apenas idioma |
| `Team Canvas Basic - v. 0.8.pdf` | 1 | paisagem; CC BY-SA 4.0 | mesma família/template do Team Canvas completo |
| guias Scrum/Nexus encontrados | 15–20 | documentos abertos de manual | pouca novidade estrutural |
| NACA-TN-1772 | 38 | scan histórico, páginas giradas/paisagem, OCR irregular | maior que a faixa ideal; sobrepõe o NACA-TN-117 |

O NTRS declara o NACA-TN-1772 como público e “Work of the US Gov. Public Use
Permitted” em sua
[ficha oficial](https://ntrs.nasa.gov/citations/19930082663).

## Documentos tecnicamente bons, mas não aprovados para publicação

Esses arquivos podem demonstrar uma característica, porém **não devem ser copiados
para o corpus público** sem nova autorização:

| Tipo observado | Valor técnico | Motivo da rejeição |
|---|---|---|
| artigo IEEE com páginas nativas e páginas-imagem | documento misto (**7**) e duas colunas | não há licença aberta no PDF; posse do arquivo não concede redistribuição |
| slides corporativos em paisagem | mistura de páginas-imagem e texto, cor, paisagem | material interno/proprietário, sem autorização explícita |
| guia oficial de Kanban 2021 | tabelas/figuras e 15 páginas | o PDF afirma “all rights reserved” |
| material de curso de inglês com OCR/rotação | rotação, colunas e OCR | provável material didático comercial |
| slides universitários antigos | paisagem e figuras | origem pública não equivale a licença de redistribuição |
| livros e e-books | grande variedade estrutural | compra/download não transfere direitos autorais |

A Lei 9.610/1998 deixa claro que adquirir um exemplar não transfere direitos
patrimoniais e que reprodução integral normalmente exige permissão. As exceções para
estudo/citação se referem a pequenos trechos e condições específicas:
[Lei de Direitos Autorais](https://www.planalto.gov.br/ccivil_03/leis/l9610.htm).

## Lacunas depois dos aprovados

| Nº | Característica | Situação |
|---:|---|---|
| 1 | tabela sem grade | coberta por BaMBa e Apache Drill |
| 2 | PDF digitalizado | parcialmente coberta; NACA tem scan com OCR |
| 3 | digitalização torta | **faltando** |
| 4 | células mescladas | coberta pelo Team Canvas; falta tabela de dados real |
| 5 | tabela que atravessa páginas | **faltando** |
| 6 | duas ou mais colunas | coberta pelos artigos |
| 7 | documento misto | encontrado localmente, mas sem licença segura; **faltando no corpus público** |
| 8 | gráfico com tabela dos mesmos números | **faltando** |
| 9 | registro multilinha | coberta por BaMBa/Apache |
| 10 | digitalização ruim | coberta por NACA-TN-117 |
| 11 | formulário preenchido | **faltando**; não usar formulário real com PII |
| 12 | nota numérica abaixo de tabela | **faltando** |
| 13 | paisagem | coberta pelo Team Canvas |
| 14 | subtotais no meio da tabela | **faltando** |
| 15 | manuscrito | **faltando** |
| 16 | tabela colorida/listrada | **faltando** |
| 17 | número no padrão `1,234.56` | **faltando como caso confirmado** |
| 18 | outro idioma | coberta |
| 19 | digitalizador antigo/texto sujo | coberta por NACA-TN-117 |

Não há base para marcar as lacunas como cobertas apenas porque uma heurística encontrou
imagens, rotação ou números.

## Caminho seguro para completar o corpus

### 1. Preferir documentos com licença inequívoca

Ordem de preferência:

1. CC0, domínio público ou ficha oficial dizendo `Public Use Permitted`;
2. CC BY;
3. CC BY-SA, aceitando que o pacote/derivados precisam cumprir share-alike;
4. permissão escrita específica;
5. documento restrito apenas para resultado local, fora do pacote reproduzível.

“Disponível para download”, “open access” sem licença e “documento governamental” não
são, isoladamente, autorização de redistribuição. Publicações NASA podem conter
material de terceiros; a própria
[política da NASA](https://www.nasa.gov/nasa-brand-center/images-and-media/)
manda verificar créditos e conteúdo protegido. Por isso foram escolhidas fichas do NTRS
que declaram expressamente a situação autoral.

O IBGE permite reutilizar dados selecionados com citação da fonte, mas sua página não
concede de forma inequívoca redistribuição integral de qualquer PDF:
[serviços da Biblioteca do IBGE](https://biblioteca.ibge.gov.br/biblioteca-servicos.html).
PDFs do IBGE podem ser candidatos condicionais, mediante autorização escrita ou
distribuição apenas da URL/hash, não do arquivo.

### 2. Criar documentos sintéticos para os casos de maior risco

Para formulário preenchido, manuscrito e PII, a melhor solução é produzir um PDF
inteiramente sintético, com pessoas fictícias que não correspondam a indivíduos reais,
licenciado pelo projeto. O mesmo vale para tabela multipágina, subtotais, rodapé
numérico e número estrangeiro.

O conteúdo deve usar dados CC0 ou gerados, e o layout deve variar uma característica
por vez antes de combinar fatores. Guardar o gerador, seed, fonte, licença e hash. Isso
é mais seguro e cientificamente mais controlado do que anonimizar um documento real.

### 3. Manter dois registros separados

- `corpus-publico`: somente arquivos redistribuíveis e sem dados privados;
- `avaliacao-local-restrita`: opcional, sem commit e sem compartilhamento, apenas se
  houver fundamento jurídico e utilidade que justifique o risco.

Resultados do segundo conjunto não tornam o PDF redistribuível. Para o artigo, publicar
apenas métricas agregadas que não revelem conteúdo.

## Manifesto obrigatório por documento

```yaml
id: sha256
nome_publico: ...
origem_url: ...
data_acesso: ...
sha256: ...
paginas: ...
licenca_spdx_ou_texto: ...
evidencia_licenca_url: ...
atribuição_exigida: ...
pii_privada: false
identificacao_profissional_publicada: true|false
revisao_visual_por: ...
caracteristicas:
  - codigo: 1
    paginas: [8]
    evidência: "tabela lateral sem linhas de célula"
status: aprovado|condicional|rejeitado
```

## Decisão recomendada

Começar o corpus público com **BaMBa, Apache Drill, Team Canvas e NACA-TN-117**.
Eles cobrem características reais, têm evidência verificável e não dependem de obras
pagas. Não copiar nenhum dos demais PDFs do Drive para o repositório nesta fase.

Em seguida, criar casos sintéticos controlados para as lacunas 3, 5, 7, 8, 11, 12,
14, 15, 16 e 17, e procurar mais documentos reais abertos somente quando eles
acrescentarem uma combinação ainda não medida.

Este relatório é uma triagem técnica e de risco, não parecer jurídico. Antes de tornar
o dataset público, fazer revisão formal de licença/LGPD e preservar as evidências de
autorização no manifesto.

## Adendo — artigos científicos autorizados para o experimento

**Decisão do responsável pelo projeto:** todos os artigos científicos do acervo podem
ser usados na execução experimental. Essa autorização amplia o conjunto local, mas não
altera os direitos de redistribuição: artigo sem licença aberta não deve ser copiado para
o pacote público; publicar DOI/URL, hash e métricas é uma questão separada da publicação
do PDF integral.

Após deduplicar 256 caminhos acadêmicos, foram examinados 158 PDFs únicos. A inspeção
visual confirmou os seguintes candidatos adicionais:

### `software.pdf`

| Campo | Resultado |
|---|---|
| SHA-256 | `D2D07B49300F384D5D98ED4091DEB4B0C20702F2B396130CAFABA899F18C16A1` |
| Páginas | 10 |
| Característica confirmada | **7 — documento misto** |
| Evidência | páginas 1–2, 4 e 6–10 têm texto nativo; páginas 3 e 5 são páginas-imagem com diagramas girados |
| Outras | duas colunas, tabela e múltiplas figuras |
| Distribuição | uso experimental local; licença aberta não confirmada |

É o melhor artigo local para testar um único arquivo com páginas codificadas de formas
diferentes. A página 9 vazia de outro artigo inicialmente produziu um falso positivo;
esse segundo artigo foi rejeitado como caso de documento misto.

### `simmhan2005.pdf` — *A Survey of Data Provenance in e-Science*

| Campo | Resultado |
|---|---|
| SHA-256 | `2FAF309E6046536B7AF29E5D514C9E9DA84A3133EB33C9491E2A025FCB55BDAD` |
| Páginas | 6 |
| Características confirmadas | **2 — PDF digitalizado/sem texto extraível**; **9 — células multilinha**; **18 — inglês** |
| Evidência | todas as seis páginas são imagens; página 5 contém tabela com grade e valores multilinha |
| Distribuição | uso experimental local; licença aberta não confirmada |

O scan é relativamente legível, portanto não deve ser rotulado automaticamente como
**10 — digitalização ruim**.

### `TRADE-OFF ANALYSIS FOR REQUIREMENTS SELECTION.pdf`

| Campo | Resultado |
|---|---|
| SHA-256 | `BBE7C0A3C7DF03C573F5630912601EE48389C802F01E9A153288B243158D84B3` |
| Páginas | 22 — ligeiramente acima da faixa ideal |
| Características confirmadas | **13 — página em paisagem/girada**; **14 — linha de total no corpo da tabela**; **9 — conteúdo multilinha** |
| Páginas-chave | 12, 16 e 20 |
| Evidência | página 12 tem conteúdo lateral; tabela 2 na página 16 inclui `Total size` depois dos registros; outras tabelas combinam cabeçalhos e valores densos |
| Distribuição | uso experimental local; licença aberta não confirmada |

### `A Value-Based Review Process for Prioritizing Artifacts(1).pdf`

| Campo | Resultado |
|---|---|
| SHA-256 | `93741D5460F66338A45F8BF8B53994EC195B4185197D700F63CB5E75949A14BA` |
| Páginas | 10 |
| Características confirmadas | **5 — tabela continuada**; **4 — cabeçalhos/células hierárquicas**; **9 — registros multilinha** |
| Páginas-chave | 7–8 e 10 |
| Evidência | a própria legenda registra `Table 15. Comparative results (continued)`; tabelas usam grupos de cabeçalho e células textuais longas |
| Distribuição | uso experimental local; licença aberta não confirmada |

### `facce1.pdf` — reserva para tabelas densas

| Campo | Resultado |
|---|---|
| SHA-256 | `FEFD8F4E1F93FF7FED94C51FE74C46E3707F36561A8B5FA69D633002228ED9BB` |
| Páginas | 12 |
| Características confirmadas | tabela lateral/girada, tabelas com cabeçalhos agrupados, duas colunas |
| Páginas-chave | 4, 6, 8–10 |
| Observação | a página 9 contém gráficos e tabela, mas não foi demonstrado que a tabela contém exatamente os números que geraram os gráficos; não marcar **8** ainda |
| Distribuição | uso experimental local; licença aberta não confirmada |

### Cobertura revisada

Com os artigos autorizados e o NACA-TN-117, há cobertura confirmada para:

`1, 2, 4, 5, 6, 7, 9, 10, 13, 14, 18, 19`

Continuam sem documento inequivocamente confirmado:

- **3** — scan inclinado;
- **8** — gráfico acompanhado exatamente da tabela que o gerou;
- **11** — formulário preenchido sem PII real;
- **12** — nota numérica abaixo da tabela com risco de linha fantasma;
- **15** — manuscrito;
- **16** — tabela colorida/listrada;
- **17** — número no formato `1,234.56` em uma tabela-alvo.

Portanto, os novos artigos elevam a cobertura de 6 para **12 das 19
características**, mas ainda não completam a lista.

## Segundo adendo — pastas indicadas, autoria própria e busca complementar

**Escopo adicional informado pelo responsável:** PDFs de autoria própria podem ser
usados; artigos científicos podem participar da avaliação local; a pasta da cadela-guia
deve ser excluída; e-books podem ser considerados, respeitados os direitos autorais.

### Resultado da localização

- foram encontrados **36 PDFs** sob pastas cujo nome começa por `Xant...`; os nomes e
  a inspeção amostral indicam exames, laudos, receitas e documentos veterinários. O
  conjunto foi **integralmente excluído antes da análise de conteúdo**;
- não foi localizado PDF sob um caminho literal `\auditoria\`. Há arquivos isolados
  com “auditor” no nome, mas isso não prova que sejam o conjunto mencionado e eles não
  foram incorporados;
- foram encontradas várias árvores acadêmicas e cópias de backup. A busca por autoria
  “Lucas … Tito” produziu 21 ocorrências de arquivo e **6 conteúdos únicos por SHA-256**,
  incluindo versões de dissertação/TCC e três publicações curtas. Cópias idênticas não
  contam como novos documentos experimentais;
- a dissertação de 70 páginas e compilações de TCC com 140–141 páginas estão muito
  acima da faixa ideal de 5–20 páginas. Além disso, versões com assinaturas devem ficar
  fora do corpus público enquanto não houver revisão específica dos dados de assinatura;
- a busca no Gmail não pôde ser executada: a conexão retornou
  `ACCESS_TOKEN_SCOPE_INSUFFICIENT`. Nenhuma mensagem ou anexo foi lido. É necessária
  reautenticação com escopo de leitura para retomar essa fonte.

### Novo candidato local — gráficos, tabelas-fonte e cor

#### `10.1.1.465.2896.pdf` — *Comparison of JSON and XML Data Interchange Formats: A Case Study*

| Campo | Resultado |
|---|---|
| SHA-256 | `3A091FA694250B1B6200578A15DD9B7220879043966E4694CBF47C194BC326C6` |
| Páginas | 6 |
| Categoria | artigo científico/conferência |
| Características confirmadas | **8 — gráfico acompanhado das tabelas que o geraram**; **16 — tabelas com fundo colorido e listras**; também **6** e **18** |
| Páginas-chave | 3–4 |
| Evidência | a página 3 contém as Tabelas 1–5 com cabeçalhos amarelos e linhas alternadas em cinza; a página 4 contém as Figuras 3–5, cujas séries reproduzem os valores de CPU/memória das Tabelas 4–5 |
| Origem pública encontrada | PDF no site de um dos autores, Montana State University |
| Distribuição | autorizado para avaliação local como artigo científico; nenhuma licença aberta foi encontrada, portanto não copiar para o corpus público |

A inspeção visual foi necessária: a simples coexistência das palavras `Table` e
`Figure` não demonstraria que os números são os mesmos. Neste caso, os valores das
séries dos gráficos correspondem às cinco observações das tabelas-fonte. A página do
autor mantém o [PDF público](https://www.cs.montana.edu/izurieta/pubs/caine2009.pdf),
e o registro bibliográfico identifica o trabalho como CAINE 2009, páginas 157–162:
[DBLP](https://dblp.org/rec/conf/caine/NurseitovPRI09).

### Novo candidato externo aberto — formato numérico estrangeiro

#### *Understanding the dynamics of post-surgical recovery and its predictors in resource-limited settings*

| Campo | Resultado |
|---|---|
| Páginas | 10 |
| Categoria | artigo científico aberto |
| Característica confirmada | **17 — números no formato `1,234.56` em tabela** |
| Páginas/elementos-chave | Tabelas 3 e 7; exemplos `-1,234.56`, `2,478.12` e `2,567.45` |
| Licença | CC BY-NC-ND 4.0, impressa no PDF |
| Privacidade | o artigo afirma que os dados foram anonimizados; as tabelas publicadas são agregadas/modeladas, sem identificadores de pacientes |
| Uso | redistribuição não comercial do PDF inalterado, com crédito, link da licença e sem adaptação; confirmar que o pacote experimental e sua hospedagem são não comerciais |

Fontes oficiais: [PDF da Springer/BMC](https://link.springer.com/content/pdf/10.1186/s12893-025-02786-z.pdf)
e [registro do artigo e licença](https://link.springer.com/article/10.1186/s12893-025-02786-z).

### E-book encontrado, mas não selecionado

*The Data Warehouse Toolkit, 3rd Edition* contém `31,257.98` na página PDF 326,
mas o exemplo aparece em texto corrido, não numa tabela-alvo. O arquivo tem 601
páginas, indica origem de portal de e-books e não traz autorização de redistribuição.
Ele pode servir somente como teste local restrito, mas é inferior ao artigo aberto da
BMC em adequação estrutural, tamanho e reprodutibilidade jurídica.

### Cobertura atualizada após o segundo adendo

Cobertura confirmada: `1, 2, 4, 5, 6, 7, 8, 9, 10, 13, 14, 16, 17, 18, 19` —
**15 de 19 características**.

Continuam faltando casos inequívocos e aceitáveis:

- **3** — digitalização inclinada;
- **11** — formulário preenchido sem PII real;
- **12** — nota numérica imediatamente abaixo de tabela, capaz de virar linha fantasma;
- **15** — manuscrito.

O corpus ainda não deve ser considerado fechado: além das quatro lacunas, o artigo
JSON/XML cobre 8 e 16 apenas na avaliação local enquanto sua licença não for esclarecida.
Para o pacote público, convém manter essas duas características como “cobertas
tecnicamente, pendentes de substituto redistribuível”.

## Terceiro adendo — repositórios GitHub e fontes LaTeX

**Autorização do responsável:** repositórios GitHub próprios com LaTeX e PDF também
podem ser usados quando acrescentarem valor ao experimento.

Foi feita uma inspeção somente de leitura dos checkouts locais cujo `origin` pertence à
conta `lucastito`, confirmada pela autenticação do GitHub CLI. Nenhum repositório foi
clonado, alterado, enviado ou publicado durante a triagem.

| Repositório | Material encontrado | Resultado para a lista |
|---|---|---|
| [`lucastito/dissertacao`](https://github.com/lucastito/dissertacao) | 9 arquivos `.tex`, 1 `.bib` e `tese.pdf` com 15 páginas | fonte LaTeX reproduzível, mas o PDF atual não acrescenta 3, 11, 12 ou 15 |
| `lucastito/book` | repositório privado e quatro livros não públicos | **excluído integralmente por determinação expressa do autor; não usar, copiar nem distribuir** |
| `lucastito/nutricionista_pessoal` | TACO, 164 páginas | conteúdo idêntico por SHA-256 ao `TACO.pdf` já presente no projeto; não conta novamente |
| outros repositórios próprios | PDFs técnicos/de dependência ou briefs curtos | terceiros, fora da faixa ideal ou sem ganho de cobertura |

O repositório `dissertacao` é público e identifica Lucas de Souza Tito no LaTeX, mas a
API do GitHub informa `licenseInfo: null`. O repositório `book` é privado e também não
declara licença. A autorização do autor é evidência para uso local, mas um repositório
público **sem licença não concede automaticamente direitos de reutilização a terceiros**.
Antes de incluir PDF, LaTeX ou geradores derivados no pacote reproduzível, registrar uma
licença compatível e verificar contribuições de coautores, templates, figuras e outros
materiais de terceiros.

Os fontes LaTeX continuam valiosos para a etapa seguinte: permitem gerar casos sintéticos
controlados para formulário preenchido, nota numérica e manuscrito simulado, mantendo
seed, conteúdo fictício, código-fonte e licença. Isso deve ser tratado como corpus
sintético separado, não como documento real encontrado.

## Quarto adendo — autorização refinada, publicações próprias e fontes públicas

### Limites de autorização consolidados

O responsável autorizou explicitamente o uso experimental de sua dissertação e de seus
artigos. Essa autorização **não** abrange os quatro livros privados: todo o repositório
`book` e os e-books sem licença aberta permanecem fora do corpus. A permissão do autor
também não substitui direitos do editor, de coautores, de titulares de figuras ou de
terceiros que assinaram documentos. Por isso, publicações próprias sem licença aberta
confirmada ficam na camada **local**, não no pacote público de reprodutibilidade.

A dissertação localizada é *Gerência de Data Lakes Científicos com o ξ-DL: um Estudo de
Caso da COVID-19* (UFF, 2020; DOI `10.22409/PGC.2020.m.14644777790`). A cópia de 70
páginas com assinaturas tem SHA-256
`70D092E6BA12BFA8434B4E198933E95C690EBD5D73F6F3B4E069266B2E3C228F`. Ela está acima
da faixa ideal e contém assinaturas de terceiros; pode ser medida localmente, mas não
deve ser publicada no corpus. O PDF `tese.pdf` do repositório LaTeX tem 15 páginas e é
uma versão incompleta/template, não substitui a dissertação depositada.

### Artigos de Lucas Tito confirmados em fontes oficiais

Os PDFs abaixo foram baixados de páginas oficiais e preservados, sem alteração, em
`C:\Users\Lucas Tito\projetos\pdf-parser-candidatos-locais\artigos-lucas-tito`.

| Arquivo | Publicação e evidência | Páginas | SHA-256 | Resultado técnico | Distribuição |
|---|---|---:|---|---|---|
| `TitoEtAl_ICEIS2017.pdf` | *A Systematic Mapping of Software Requirements Negotiation Techniques*, ICEIS 2017, DOI `10.5220/0006362605180525`; a página oficial lista Lucas Tito como autor | 8 | `623CD13AA6211BAE86760814A13866E54C6FC97C6D28E097A5076D7F19CFC05C` | texto nativo, duas colunas, tabelas e figuras; repete 4, 6, 9 e 18, sem fechar 3, 11, 12 ou 15 | local; o PDF declara “all rights reserved” |
| `TitoEtAl_SBBD2020_Xi-DL.pdf` | *ξ-DL: um Sistema de Gerência de Data Lake para Monitoramento de Dados da Saúde*, SBBD 2020, DOI `10.5753/sbbd.2020.13633` | 6 | `B5A85DDF99B47B9966710FCFC4FE7AEB092C0CCF27B529F1EE1B5D7D2906787C` | visualmente nítido, mas todas as páginas retornam **zero texto**: os glifos foram convertidos em contornos/caminhos vetoriais; há tabela na página 6 | local até localizar licença específica |
| `CruzEtAl_IHC2018_BlindMagic.pdf` | *Blind Magic: Uma tecnologia assistiva para cegos jogarem “Magic: The Gathering”*, IHC 2018; o PDF oficial lista Lucas Tito | 2 | `7C3EA570C248E08AE8E6E09B9C73BA7D27174206FB2B1B80BF2F31D4D1433393` | texto nativo, duas colunas e imagens; não acrescenta característica ausente | uso pessoal/sala de aula segundo o aviso do PDF; republicação exige permissão específica |

Fontes oficiais: [ICEIS/SciTePress](https://www.scitepress.org/Link.aspx?doi=10.5220%2F0006362605180525),
[PDF do SBBD/SBC](https://sol.sbc.org.br/index.php/sbbd/article/download/13633/13481)
e [PDF do IHC/SBC](https://sol.sbc.org.br/index.php/ihc_estendido/article/download/4188/4119).
Não foi confirmada publicação de Lucas Tito na BRESCI; resultados apenas semelhantes ou
de outros autores foram descartados, sem inferir autoria.

O caso do SBBD merece entrar na taxonomia como subtipo explícito de “sem camada textual”:
**texto visual composto por glifos vetoriais/curvas**, distinto tanto de texto nativo
quanto de página rasterizada. Um detector que só conte imagens classificará esse PDF
erroneamente como digital — exatamente o tipo de falha que um benchmark deve revelar.

### Novas fontes públicas para as lacunas

#### `NASA_MODIS_MCST_1991.pdf` — característica 12 confirmada

| Campo | Resultado |
|---|---|
| Origem | [NASA Goddard — apresentação MCST de 1991](https://modis.gsfc.nasa.gov/sci_team/meetings/199110/presentations/v.pdf) |
| Páginas | 22 — duas acima da faixa ideal |
| SHA-256 | `D8E32E43B9BE89D4F1723B3833684581AE54A64A6B6F431EB910EEBC8F316394` |
| Páginas-chave | PDF 11 e 12 (numeração impressa 11 e 12 de 22) |
| Característica | **12 — notas numéricas imediatamente abaixo de tabelas**; `Note 1`, `Note 2` e `Note 3`, com números e parênteses que podem virar linhas fantasmas |
| Outras propriedades | scan antigo, uma imagem por página, OCR bastante ruidoso; reforça 2, 10, 18 e 19 |
| Privacidade | nomes profissionais e telefones institucionais históricos aparecem na capa; não há dado pessoal privado, mas o corpus pode usar somente as páginas 11–12 se a metodologia permitir recortes derivados |
| Distribuição | fonte oficial NASA; verificar eventuais componentes de contratados antes de afirmar domínio público do PDF inteiro |

O arquivo foi preservado em
`C:\Users\Lucas Tito\projetos\pdf-parser-candidatos-locais\fontes-publicas`.

#### `CMS_SBC_Sample_1.pdf` — formulário preenchido, cobertura parcial de 11

| Campo | Resultado |
|---|---|
| Origem | [CMS — sample completed SBC](https://www.cms.gov/CCIIO/Resources/Regulations-and-Guidance/Downloads/Sample-completed-sbc-12-19-14-FINAL.pdf) |
| Páginas | 5 |
| SHA-256 | `460E1CAFF69505F7A8BB0F1453E8ADA65FE5D4EA75F568CC4692505C2F26016D` |
| Evidência | modelo oficial preenchido com valores fictícios (`Insurance Company 1`, período, franquias, copagamentos e exemplos de cobertura) |
| Limite | não possui widgets AcroForm e a inspeção das cinco páginas não encontrou caixas marcadas; cobre “campos com valores”, mas não a variante de checkbox |
| Privacidade | conteúdo explicitamente ilustrativo, sem pessoa real identificável |
| Distribuição | publicação oficial do governo federal dos EUA; registrar a página institucional como proveniência |

Portanto, o documento é um bom caso de formulário visual preenchido, mas **não encerra
sozinho a característica 11** se o critério experimental exigir simultaneamente caixas
marcadas. O arquivo também foi preservado na pasta local de fontes públicas.

#### Manuscrito da Library of Congress — característica 15 confirmada na origem

*Andrew Jackson to Rachel Donelson Jackson, March 27, 1824* contém quatro páginas
manuscritas. A [Library of Congress](https://www.loc.gov/resource/maj.01064_0262_0265/)
declara expressamente que seus scans digitais dos papéis de Andrew Jackson estão em
domínio público e fornece PDF completo. O download automatizado foi bloqueado pelo
desafio anti-bot da própria instituição; por isso não há cópia local nem hash e o item
fica como **candidato aprovado, pendente de ingestão manual**, não como arquivo já
incorporado. A alternativa de nove páginas
[Five separate loose-leaf pages of handwritten notes](https://www.loc.gov/resource/llmlp.Five-pages_handwritten-notes/?st=pdf)
também existe, mas a própria LoC apresenta ressalva de direitos mais fraca; o documento
de Andrew Jackson é juridicamente preferível.

### Materiais expressamente excluídos

- `HBR_LeadershipInsights.pdf`, sob `H:\Meu Drive\artigos e referências\materiais e
  outras referências`, não foi selecionado: acesso ao arquivo não equivale a licença de
  redistribuição da Harvard Business Review;
- os quatro livros privados, o repositório `book` e e-books pagos estão proibidos;
- resultados públicos com listas escolares, cadastros empresariais, registros de saúde,
  processos pessoais ou outros identificadores foram ignorados mesmo quando continham
  PDFs tecnicamente interessantes;
- arquivos da cadela-guia continuam integralmente fora da análise.

### Cobertura após este adendo

Com o PDF da NASA, a cobertura **local e confirmada** passa a
`1, 2, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 16, 17, 18, 19` — **16 de 19**.

- **11** tem um caso oficial preenchido, mas falta a variante inequívoca com checkbox
  marcado;
- **15** tem fonte pública e domínio público confirmados, mas o PDF ainda precisa ser
  baixado manualmente e hasheado;
- **3** continua sem exemplar inequivocamente inclinado.

Se a definição operacional aceitar “formulário preenchido com valores” sem exigir
checkbox, o CMS eleva a cobertura técnica para 17/19. Se o manuscrito da LoC for
baixado e validado, ela sobe para 18/19. O único buraco sem candidato aprovado continua
sendo **3 — digitalização torta**.

### Regra operacional sobre documentos acessíveis ao público

O responsável autorizou o uso experimental de qualquer documento acessível
publicamente, incluindo editais de concursos e PDFs encontrados por mecanismos de
busca. Para não misturar autorização de pesquisa com autorização de republicação, a
triagem passa a usar duas camadas:

1. **corpus local:** PDF obtido legitimamente de URL pública, sem controle de acesso e
   sem dados pessoais inadequados; pode ser medido localmente, preservando URL, data de
   acesso e hash;
2. **pacote público reproduzível:** somente ato oficial, domínio público, licença aberta,
   autorização expressa ou outra base jurídica documentalmente verificável. Quando a
   redistribuição não estiver demonstrada, publicar apenas URL, metadados, hash e script
   de obtenção, não uma cópia do PDF.

Editais emitidos como atos oficiais são candidatos especialmente fortes: o art. 8º, IV,
da Lei 9.610/1998 exclui da proteção autoral os textos de leis, decretos, regulamentos,
decisões judiciais e demais atos oficiais. Ainda assim, anexos com fotografias, projetos,
provas de terceiros ou dados pessoais devem ser avaliados separadamente. Indexação pelo
Google e ausência de aviso de copyright são evidência de acesso público, **não** prova
autônoma de licença ou domínio público. Essa distinção mantém a busca ampla sem expor o
pacote redistribuído a risco evitável.

## Quinto adendo — triagem das lixeiras locais

As lixeiras de `C:` e `H:` foram examinadas em modo somente leitura. A primeira etapa
usou apenas os metadados `$I` do Windows para reconstruir nome e caminho originais; os
PDFs `$R` não foram abertos quando o nome já demonstrava risco de dados pessoais.

Foram encontrados oito arquivos recuperáveis: dois currículos duplicados de uma
terceira pessoa, outro currículo da mesma pessoa, dois relatórios de situação fiscal, um
perfil/CV de Lucas, um `lucas_tito.pdf` em Downloads e um documento de condomínio.
Todos foram excluídos antes da inspeção de conteúdo. Currículos e perfis normalmente
contêm nome, contato e histórico profissional; documentos condominiais podem conter
endereço; e os relatórios fiscais já expõem identificador pessoal no próprio nome
original.

Resultado: **nenhum candidato experimental aproveitável foi obtido da lixeira**. Nenhum
arquivo foi restaurado, copiado, modificado ou removido. Para minimizar nova exposição,
o dossiê não registra os identificadores, caminhos completos ou nomes completos das
pessoas encontrados nesses metadados.

## Sexto adendo — corpus consolidado e cobertura encerrada

Em 2 de agosto de 2026, todos os candidatos selecionados foram consolidados em
[`../pdf/`](../pdf/). Essa passa a ser a única pasta do repositório que contém PDFs do
experimento. `TACO.pdf` também foi movido para ela. As antigas pastas temporárias de
ingestão foram removidas somente depois da comparação dos hashes das cópias.

O corpus consolidado contém **19 PDFs distintos**, sem colisão de SHA-256. O
[`manifest.yaml`](../pdf/manifest.yaml) registra, para cada arquivo, hash, número de
páginas, proveniência, status de uso e evidência por característica. O
[`README.md`](../pdf/README.md) fornece o de-para humano resumido.

As três lacunas do adendo anterior foram resolvidas por documentos públicos do National
Archives and Records Administration dos Estados Unidos:

- **3 — digitalização torta:** `NARA_JFK_104-10095-10314_skew.pdf`, especialmente a
  página 31, contém recorte escaneado com inclinação visual inequívoca;
- **11 — formulário preenchido:** `NARA_JFK_104-10337-10011.pdf`, página 29, contém
  campos preenchidos e caixas efetivamente marcadas;
- **15 — manuscrito/preenchido à mão:** o mesmo documento, páginas 23–30 e 51, contém
  formulários e anotações preenchidos à mão.

Resultado final da seleção: **19 de 19 características possuem pelo menos um candidato
local confirmado**. Isso significa cobertura da taxonomia, não equivalência de dificuldade
entre casos nem autorização automática para republicar todo o corpus. Para uma distribuição
pública, devem ser respeitados os campos `status`, `source` e `license` do manifesto; quando
a licença de redistribuição não estiver demonstrada, publique o hash e o procedimento de
obtenção em vez da cópia do arquivo.
