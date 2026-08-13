# O que procurar em PDF — lista de coleta

> Companheiro do [ADR-0021](../../docs/adr/0021-taxonomia-de-caracteristicas.md).
> Ali está o porquê; aqui está o que buscar, em linguagem de quem vai procurar.
>
> **Marque o que encontrar.** O que ficar sem marca vira limitação declarada no
> relatório — não buraco silencioso.

## Confirmadas em documento real de produção, fora deste corpus (2026-08-13)

Investigação de desenvolvimento contra os dois documentos reais de um
cenário corporativo separado (Cenário B, fora deste repositório —
proveniência e redistribuição diferentes deste corpus, **não** entram
aqui como coleta) confirmou de verdade, com sonda
implementada e validada (`ADR-0021`): **item 6** (duas ou mais colunas de
texto — inclusive coluna de comentário de revisão reservada, geometricamente
a mesma característica), **item 13** (página em paisagem) e **item 16**
(tabela com fundo colorido/listras, sem grade). Observados de verdade mas
ainda sem sonda (exigem reconstrução de tabela ou inspeção visual/LLM):
**item 4** (células mescladas/cabeçalho hierárquico) e **item 8** (gráfico
com números ao lado). Isso não marca ☑ abaixo — a checklist é sobre a
coleta *deste* corpus — mas confirma que valem a pena priorizar quando
achar exemplar redistribuível.

## Antes de começar: três regras

**1. Poucos documentos, muitas características.** O objetivo não é volume. Um PDF
que traz três características novas vale mais que dez que repetem o mesmo caso.
Cada documento novo custa horas de execução em cinco máquinas.

**2. Nada de dado pessoal.** Nome, CPF, endereço, telefone, e-mail, foto de
pessoa, dado de saúde identificável. Se o documento é bom mas tem dado pessoal:
descarte, ou use uma versão pública/anonimizada na origem. **Não** conte com
tarjar depois — o arquivo original fica no repositório e o texto continua
extraível por baixo da tarja.

**3. Só o que pode ser redistribuído.** Preferir órgão público, licença aberta,
ou documento que autorize reprodução. Se a licença proíbe, ele pode ser usado
para medir mas **não** pode entrar no pacote de reprodutibilidade — e isso reduz
o valor dele. Anotar a licença de cada um.

**Tamanho:** 5 a 20 páginas é o ideal. Documento gigante custa tempo de execução
sem acrescentar característica.

---

## Prioridade 1 — o que falta e mais importa

Hoje o projeto tem **um** documento: tabela rotacionada, texto nativo, 11
colunas, sem imagem. Tudo abaixo é território não coberto.

| # | O que procurar | Como reconhecer | Encontrei |
|---|---|---|---|
| 1 | **Tabela sem grade** | tabela alinhada só por espaço, sem linhas separando colunas | ☐ |
| 2 | **PDF digitalizado** | o texto não é selecionável; é foto de papel | ☐ |
| 3 | **Digitalização torta** | a página aparece inclinada, como escaneada de canto | ☐ |
| 4 | **Células mescladas** | um título que cobre duas ou mais colunas abaixo dele | ☐ |
| 5 | **Tabela que atravessa páginas** | a mesma tabela continua na página seguinte | ☐ |
| 6 | **Duas ou mais colunas de texto** | texto em colunas lado a lado, como jornal ou artigo | ☐ |
| 7 | **Documento misto** | uma parte digitada, outra escaneada, **no mesmo arquivo** | ☐ |

O número 7 é o mais valioso e o mais difícil de achar de propósito. Costuma
aparecer em processo com anexo digitalizado, ou relatório com certificado
escaneado ao final.

## Prioridade 2 — completa a cobertura

| # | O que procurar | Como reconhecer | Encontrei |
|---|---|---|---|
| 8 | **Gráfico com os números ao lado** | gráfico acompanhado da tabela que o gerou | ☐ |
| 9 | **Registro que ocupa várias linhas** | um item da tabela cuja descrição quebra em 2-3 linhas | ☐ |
| 10 | **Digitalização ruim** | manchada, com sombra, texto fraco ou borrado | ☐ |
| 11 | **Formulário preenchido** | campos com valores, caixas de marcação | ☐ |
| 12 | **Nota de rodapé numérica** | números logo abaixo da tabela, que não são dados dela | ☐ |
| 13 | **Página em paisagem** | página deitada, mais larga que alta | ☐ |
| 14 | **Tabela com subtotais** | linhas de "total" no meio, misturadas com os dados | ☐ |

O número 12 parece bobo e não é: é a origem clássica de linha fantasma na
extração — o extrator lê o rodapé como se fosse mais um registro.

## Prioridade 3 — se aparecer, aproveite

| # | O que procurar | Encontrei |
|---|---|---|
| 15 | Manuscrito (preenchido à mão) | ☐ |
| 16 | Tabela com fundo colorido / listras | ☐ |
| 17 | Número em formato estrangeiro (1,234.56 em vez de 1.234,56) | ☐ |
| 18 | Documento em outro idioma | ☐ |
| 19 | PDF gerado por digitalizador antigo (fonte estranha, texto sujo) | ☐ |

---

## Variedade de origem — não colete tudo do mesmo tipo

Dez relatórios financeiros exercitam poucas características. Espalhe entre
categorias diferentes, e anote a de cada documento:

| Categoria | Onde costuma haver | Peguei |
|---|---|---|
| **Relatório técnico com tabela** | órgão público, instituto de pesquisa | ☐ |
| **Relatório financeiro** | balanço, demonstrativo, prestação de contas | ☐ |
| **Manual / ficha técnica** | especificação de equipamento, bula | ☐ |
| **Artigo científico** | repositório aberto, periódico de acesso livre | ☐ |
| **Norma / regulamento** | legislação, resolução, portaria | ☐ |
| **Boletim estatístico** | censo, pesquisa, indicador | ☐ |

**Onde procurar sem problema de licença:** portais de transparência, institutos
públicos de estatística e pesquisa, repositórios de acesso aberto, agências
reguladoras, diários oficiais.

---

## Para cada documento coletado, anote

Sem isso o documento não entra no experimento — a procedência é o que torna o
resultado reproduzível.

```
arquivo:        nome-do-arquivo.pdf
origem:         URL ou instituição
licença:        aberta / uso permitido / restrita
categoria:      relatório técnico | financeiro | manual | artigo | norma | boletim
características: os números da lista acima que ele exercita — ex.: 1, 4, 12
páginas:        quantas, e quais têm tabela
dado pessoal:   nenhum  (se houver, o documento não entra)
```

## Meta

**8 a 12 documentos** cobrindo as 7 características de prioridade 1 e o máximo da
prioridade 2, espalhados por pelo menos 4 categorias.

Menos que isso deixa buracos que viram limitação; muito mais custa tempo de
execução sem acrescentar informação — cada documento roda em cinco máquinas.

> **Um documento pode marcar várias características de uma vez**, e esses são os
> melhores. Um boletim estatístico digitalizado, torto, com tabela sem grade que
> atravessa páginas marca quatro de uma vez.
