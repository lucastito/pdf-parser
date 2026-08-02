# Corpus de PDFs do experimento

Tudo que diz respeito aos documentos de entrada vive aqui — os arquivos, o de-para,
o critério de seleção e o método da busca. Fora desta pasta ficam só código, teste
e ADR.

| Arquivo | O que é |
|---|---|
| [`manifest.yaml`](manifest.yaml) | de-para: PDF → SHA-256, páginas, proveniência, licença, características confirmadas por página |
| [`CARACTERISTICAS.md`](CARACTERISTICAS.md) | as 19 características procuradas — roteiro operacional do [ADR-0021](../../docs/adr/0021-taxonomia-de-caracteristicas.md) |
| [`TRIAGEM.md`](TRIAGEM.md) | como o corpus foi montado: varredura de 743 PDFs, critérios de exclusão e o que a busca **não** achou |
| `*.pdf` | os documentos |

## Cobertura

As 19 características possuem pelo menos um caso confirmado:

| # | Característica | Caso principal | Páginas |
|---:|---|---|---:|
| 1 | tabela sem grade | `lendo - indicado pelo daniel - bav088.pdf` | 8 |
| 2 | PDF digitalizado | `NASA_NACA-TN-117.pdf` | 1–6 |
| 3 | digitalização torta | `NARA_JFK_104-10095-10314_skew.pdf` | 31 |
| 4 | células mescladas | `Team Canvas - v. 0.8.pdf` | 1 |
| 5 | tabela entre páginas | `A Value-Based Review Process for Prioritizing Artifacts(1).pdf` | 7–8 |
| 6 | duas ou mais colunas | `TitoEtAl_ICEIS2017.pdf` | 1–8 |
| 7 | documento misto | `software.pdf` | 3 e 5 versus demais |
| 8 | gráfico com tabela-fonte | `10.1.1.465.2896.pdf` | 3–4 |
| 9 | registro multilinha | `lendo - indicado pelo daniel - bav088.pdf` | 8 |
| 10 | digitalização ruim | `NASA_NACA-TN-117.pdf` | 1–6 |
| 11 | formulário preenchido | `NARA_JFK_104-10337-10011.pdf` | 29, 30 e 51 |
| 12 | nota numérica abaixo da tabela | `NASA_MODIS_MCST_1991.pdf` | 11–12 |
| 13 | página em paisagem | `TRADE-OFF ANALYSIS FOR REQUIREMENTS SELECTION.pdf` | 12 |
| 14 | subtotais no corpo | `TRADE-OFF ANALYSIS FOR REQUIREMENTS SELECTION.pdf` | 16 |
| 15 | manuscrito/preenchido à mão | `NARA_JFK_104-10337-10011.pdf` | 23–30 e 51 |
| 16 | tabela colorida/listrada | `10.1.1.465.2896.pdf` | 3 |
| 17 | número em formato estrangeiro | `BMC_Surgery_2025_Recovery.pdf` | 6–7 |
| 18 | outro idioma | `NASA_NACA-TN-117.pdf` | 1–6 |
| 19 | digitalizador antigo/texto sujo | `NARA_JFK_104-10095-10314_skew.pdf` | 17, 20, 29 e 31 |

O documento NARA da característica 3 é maior que a faixa ideal, mas a página 31 é um
caso real, público e visualmente inequívoco de scan inclinado. O documento NARA da
característica 11 contém tanto campos preenchidos quanto caixas marcadas, evitando a
ambiguidade do exemplo CMS.

## Por que a impressão digital

Uma rodada que não diz **qual** arquivo leu não é reproduzível. O `sha256` de cada
documento está no manifesto e é verificado pela suíte: se o arquivo for trocado ou
corrompido, o teste acusa antes de alguém gastar horas medindo o documento errado.

Para conferir à mão:

```powershell
Get-FileHash experimentos\pdf\TACO.pdf -Algorithm SHA256
```

## Proveniência e redistribuição

O `status` de cada documento no manifesto responde a **duas perguntas diferentes**,
e confundi-las é o erro a evitar:

- **usar no experimento** — todos os 19 podem ser lidos e medidos;
- **redistribuir** — nem todos. `status: local` significa *"existe na máquina de
  quem coletou"*, **não** *"licença de redistribuição confirmada"*.

Situação por grupo, levantada em 2026-08-02:

| Grupo | Documentos | Redistribuição |
|---|---:|---|
| Domínio público (governo dos EUA) | 5 | permitida — obra federal sem direito autoral |
| CC-BY / CC-BY-SA | 3 | permitida, com atribuição |
| TACO | 1 | permitida com citação da fonte |
| Artigos de coautoria própria | 3 | direitos podem ser da editora; há link oficial |
| CC-BY-NC-**ND** | 1 | **`ND` colide com gerar derivados** — mesma cláusula que excluiu a TBCA |
| Editora comercial, sem origem aberta | 6 | não confirmada |

Os arquivos estão versionados **por decisão explícita, para viabilizar o
experimento**, com a situação registrada acima em vez de omitida. Se algum precisar
sair, o manifesto diz exatamente qual, qual característica ele cobre, e por onde
obtê-lo de novo.

**Ao trocar um documento**, prefira substituto de licença aberta que cubra a mesma
característica — a característica é o requisito, o arquivo é intercambiável.

## Acrescentar um documento

1. Copie para esta pasta e calcule o `sha256`.
2. Acrescente a entrada em [`manifest.yaml`](manifest.yaml): arquivo, hash, páginas,
   `status`, `source`, `license` quando houver, e as características **por página**,
   com a evidência que justifica cada uma.
3. Registre o hash em `tests/test_documentos.py`.
4. Se o documento for virar caso de medição, crie o perfil em `perfis/`.

O passo 3 não é burocracia: é o que impede uma troca silenciosa de arquivo invalidar
uma comparação entre máquinas.
