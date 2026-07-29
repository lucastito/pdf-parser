# ADR-0001 — Biblioteca de extração de PDF

**Status:** aceito · **Data:** 2026-07-29

## Contexto

O parser precisa ler PDFs de texto nativo. O documento-caso usa fontes CID com
codificação `Identity-H` e mapas `ToUnicode` incompletos — **5 mapas para 31 fontes**.

Nesse cenário, os bytes armazenados no fluxo de conteúdo **não são o texto**: só o
mapa `ToUnicode` traduz um para o outro. Uma extração que ignore esse mapa produz
caracteres que passam por texto e não são — e o erro é silencioso.

## Medição

Extração ingênua (expressão regular sobre os operadores de texto do fluxo
descomprimido), no documento-caso:

| Métrica | Resultado |
|---|---|
| Caracteres extraídos | 534.129 |
| **Palavras reais (≥ 4 letras)** | **89** |
| Amostra da saída | `zUyUwUx`, `oUnHmU`, `AP�N` |

Ou seja: aparência de sucesso, conteúdo inutilizável.

Com PyMuPDF, o mesmo documento devolve texto correto, com acentuação preservada
(`Proteína`, `Lipídeos`, `Magnésio`), a 9,4 ms por página.

## Opções

| Opção | Vantagem | Desvantagem |
|---|---|---|
| Regex sobre o fluxo bruto | Sem dependência | **Corrompe em silêncio.** Descartada pela medição |
| **PyMuPDF** | Aplica `ToUnicode`; expõe coordenadas por palavra; rápido | Licença AGPL — exige atenção se houver distribuição comercial |
| pdfplumber | API agradável; boa introspecção | Mais lento; construído sobre pdfminer |
| Ferramentas de OCR | Independem da camada de texto | Desnecessário aqui — o texto existe; custo alto sem retorno |

## Decisão

**PyMuPDF** como leitor da fonte PDF.

Pesou o acesso às **coordenadas por palavra**, que a estratégia de reconstrução
posicional (ADR-0002) exige. Uma biblioteca que devolvesse apenas texto corrido não
atenderia, por melhor que fosse a decodificação.

## Consequências

- A decodificação de fontes CID deixa de ser preocupação do parser.
- A leitura fica isolada atrás da porta `FonteDocumento`: trocar a biblioteca não
  afeta extratores nem destinos.
- **A licenciar:** PyMuPDF é AGPL. Para uso interno não há questão; havendo
  distribuição do produto, avaliar licença comercial ou alternativa MIT/BSD.
- Fica registrado o princípio que a medição evidenciou: **um extrator que roda sem
  erro e grava lixo é pior do que um que falha alto.** Daí a validação obrigatória
  contra schema e a avaliação por campo.
