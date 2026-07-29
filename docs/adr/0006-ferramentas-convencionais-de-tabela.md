# ADR-0006 — Ferramentas convencionais de extração de tabela

**Status:** aceito · **Data:** 2026-07-29 · **Revisado:** 2026-07-29 (correção material)

> **Retificação.** A primeira versão deste documento registrou 0% de acurácia para
> pdfplumber e Camelot e concluiu que produziam "volume sem conteúdo". **Estava
> errado.** O 0% era artefato do nosso código de adaptação, não das bibliotecas.
> Com o tratamento correto, ambas alcançam ~100%. O erro e sua correção ficam
> registrados porque são parte do método.

## Contexto

Antes de defender uma reconstrução própria, é preciso medir as ferramentas que uma
equipe usaria por padrão. Argumento perde para evidência.

## O erro inicial, e o que o revelou

A primeira medição deu 0% para pdfplumber e Camelot, com 133 e 104 registros. A
leitura tentadora era: *"produzem volume convincente e acertam nada"*.

A pergunta que desfez isso: **por que a rotação da página afetaria apenas o OCR?**
A página declara `rotation=90`, e isso muda o que cada ferramenta enxerga.

Três defeitos nossos, encadeados:

1. **Rotação não tratada.** Com `rotation=90` ativa, `extract_tables` encontra
   **zero** tabelas. Desrotacionada, encontra uma com 67 linhas — e os dados estão
   íntegros.
2. **Alinhamento por cabeçalho.** O cabeçalho detectado é lixo (rotacionado, partido
   em várias linhas), mas as **linhas de dados** estão corretas e na ordem. Insistir
   no cabeçalho descartava dado bom por causa de metadado ruim.
3. **Alinhamento de item por nome.** As ferramentas fragmentam texto no meio da
   palavra (`"Arroz, integra l, cozido"`). Casar por nome descartava itens cujos
   valores estavam perfeitos. O número do item é inequívoco e basta.

## Medição corrigida

Duas páginas, mesmo documento canônico, mesma normalização, acurácia contra gabarito
conferido à mão (40 itens × 5 campos):

| Estratégia | Acurácia | Itens | Tempo | Observação |
|---|---|---|---|---|
| Reconstrução posicional | **100,0%** | 64 | **0,1 s** | tautológico — gerou o gabarito |
| **pdfplumber** | **100,0%** | 63 | 0,8 s | desrotacionado, alinhado por posição |
| OCR (350 dpi) | 99,5% | 64 | 6,9 s | ver ADR-0007 |
| **Camelot** (stream) | **99,0%** | 94 | 0,4 s | idem pdfplumber |
| Detector de borda | 0% | 4 | 0,4 s | sem grade, nada a detectar |
| Leitura linear | 0% | 0 | 0,0 s | ordem de leitura não corresponde à estrutura |

## Decisão

**As ferramentas convencionais resolvem este documento.** A reconstrução posicional
deixa de se justificar por acurácia — empata — e passa a se justificar por:

- **velocidade**: 0,1 s contra 0,4–0,8 s, sem escrever arquivo temporário;
- **independência de arquivo**: opera sobre o formato canônico, não sobre o PDF, o
  que a torna a única estratégia plenamente substituível na arquitetura;
- **evidência por campo**: devolve a coordenada de cada valor, não só a linha.

Nenhuma dessas é razão para descartar as bibliotecas. Elas ficam no código como
alternativas de primeira classe, e **para quem começa de novo, adotá-las é escolha
defensável.**

## O que este ADR passa a sustentar

Não sustenta mais "as ferramentas prontas falham". Sustenta algo mais útil:

> Documento com página rotacionada, cabeçalho partido e nomes fragmentados exige
> **camada de adaptação** — desrotação, alinhamento posicional, casamento por
> identificador. Com ela, ferramentas maduras funcionam. Sem ela, produzem volume
> que parece dado e não é.

O valor está na camada de adaptação, não em substituir a biblioteca.

## Lição de método

O 0% inicial era plausível: havia diagnóstico coerente (cabeçalho partido virando
dado), evidência aparente (`{'Carbo-': 'idrato'}`) e conclusão alinhada à hipótese
que se queria confirmar. **Faltou testar a hipótese contrária.**

O que expôs o erro foi uma pergunta externa — *por que a rotação afetaria só o OCR?*
— não a análise interna. Registrar isso é parte do rigor: a conclusão anterior teria
sido apresentada como resultado, e qualquer verificação de terceiro a derrubaria.
