# ADR-0027 — Diagnóstico da escalada: trilha auditável por página

**Status:** aceito · **Data:** 2026-08-13 · **Implementado:** 2026-08-13

## Contexto

`planejador.py` decide, por página, qual rota tentar (ADR-0024/0025), e
`DecisaoDeRota.motivo` já explica por que a rota **final** foi escolhida —
"rotas determinísticas divergiram acima do limiar", "confiança
insuficiente", etc. Registrado no `PLANO.md` em 2026-08-12 ("Diagnóstico da
escada de escalada"): isso cobre só metade do que uma auditoria de produção
precisa.

Duas lacunas reais, confirmadas lendo o código antes de desenhar a correção:

1. **As ferramentas que rodaram e não bastaram eram descartadas em
   silêncio.** `_tentar_deterministicos` tentava posicional, pdfplumber,
   Camelot e PyMuPDF, mas um `except Exception: pass` ou um resultado vazio
   simplesmente não entravam em lugar nenhum — só o `motivo` da decisão
   final citava, em prosa agregada, que "rotas divergiram", sem dizer quais
   tentaram e com que desfecho individual.
2. **O motivo é calculado no planejamento, antes de qualquer rota
   executar.** `planejador.py` nunca chama rede nem modelo (por desenho,
   ADR-0025) — só decide. Se a rota escolhida (`llm`, `vlm`, ou mesmo
   `posicional`) de fato produzir algo só se sabe depois, em `lote.py`, e
   essa informação nunca era registrada lugar nenhum.

**O que este ADR não resolve, de propósito:** um fallback real de execução
— por exemplo, se `llm` falhar de verdade ao rodar, tentar outro modelo ou
`vlm` antes de desistir da página. Isso depende de qual modelo é "principal"
e qual é "reserva" por característica, e essa escolha só existe depois do
experimento de avaliação de modelos no Cenário B (ADR-0026) — decidir agora
seria ajuste no escuro, o mesmo erro que o projeto já evitou em
`triagem.Classe` (ADR-0021, "Limite declarado") e no limiar de concordância
(ADR-0025). Este ADR entrega só a **visibilidade** sobre a escalada atual,
com um formato que não precisa mudar quando o fallback for decidido.

## Decisão

**Toda ferramenta ou modelo que de fato executa numa página gera uma
`TentativaDeRota`** (`planejador.TentativaDeRota`): rota, nível, sucesso,
motivo, contagem de registros. Uma rota que nem chega a rodar por
pré-condição não satisfeita — posicional sem confiança de calibração,
palavra-chave sem vocabulário declarado — **não** gera tentativa; essa
ausência já está explicada no `motivo` da decisão final, e fabricar uma
tentativa para "não tentei" confundiria "tentei e falhei" com "não se
aplicava".

`DecisaoDeRota` ganha um campo `tentativas: tuple[TentativaDeRota, ...]` —
tudo que rodou nesta página antes da decisão (e incluindo, quando a própria
rota vencedora já é determinística), na ordem em que rodou. Montado dentro
de `_planejar_pagina`/`_tentar_deterministicos`/`_tentar_palavra_chave`, que
deixaram de descartar falha em silêncio.

`lote.py::_processar_por_pagina` fecha a segunda lacuna: depois de chamar
`extrator.extrair(...)` de verdade, monta **mais uma** `TentativaDeRota` com
o desfecho real (sucesso e quantos registros, ou "nenhum registro
produzido") e junta com `decisao.tentativas` numa linha de auditoria por
página (`_formatar_trilha`), anexada ao `nota` que já era gravado em
`ResultadoLote.log` → `.log` ao lado do CSV (nenhum arquivo novo, nenhum
schema novo — reaproveita o mecanismo que ADR-0025 já previa e já grava em
disco).

Uma linha de exemplo, produzida de verdade contra um PDF sintético:

```
pág 1 → posicional sucesso (11 registro(s) pelo layout calibrado);
pdfplumber falhou (não achou registros); camelot falhou (não achou
registros); pymupdf falhou (não achou registros) → decisão: posicional
(posicional: única rota determinística com resultado nesta página) →
execução: sucesso (11 registro(s))
```

**Por que uma sequência, não um enum de dois passos:** hoje só existem 1-2
tentativas por nível (as determinísticas do nível 2, mais a rota final do
nível 3). O formato comporta, sem mudar de esquema, uma cadeia mais longa
quando o fallback real (llm principal → llm alternativo → vlm) for medido e
decidido — é só mais entradas na mesma tupla, anexadas por quem quer que
implemente o fallback então.

## Consequências

**A favor:** a escalada deixa de ser uma contagem agregada por rota
(`posicional×5, llm×2`) e vira uma trilha auditável por página — qual
ferramenta rodou, sucesso ou falha, e o que a rota escolhida de fato
produziu. Alimenta tanto o Cenário B (auditoria de produção, "por que essa
página virou pendência") quanto o Cenário A (é exatamente o dado bruto que
o experimento de avaliação de modelos, ADR-0026, vai precisar para decidir
qual modelo é melhor por característica).

**Contra — retifica um trade-off que ADR-0025 tinha aceitado
deliberadamente:** ADR-0025 registrava, em "Consequências", que o log por
página tornava o log mais longo e que isso era "mitigado por um resumo
agregado por rota, não por página individual". Este ADR reverte
exatamente essa mitigação — agora o log é por página, de propósito, porque
é isso que a auditoria pede. O resumo agregado continua existindo (primeira
linha do `nota`); a trilha por página vem depois, não no lugar dele.

## Limite declarado

- **Nenhum fallback de execução foi construído.** Se a rota final falhar de
  verdade em tempo de execução (exceção na chamada real do extrator, não só
  `RotaNaoConfigurada`), o comportamento não mudou: a exceção ainda
  propaga e o arquivo inteiro vira falha (`ingerir()`), sem tentar uma rota
  alternativa página a página. Só o caminho feliz (extrator retorna, com ou
  sem registros) ganha tentativa de execução registrada.
- **"Tentativa" é só o que executou.** Pré-condição não satisfeita (ex.
  posicional sem confiança suficiente) não gera `TentativaDeRota` — só o
  `motivo` da decisão final explica a ausência. Uma auditoria que queira
  saber "por que posicional nem foi tentado" precisa ler o `motivo`, não a
  lista de tentativas.
- **Verbosidade não medida.** Um documento de muitas páginas com escalada
  frequente produz um `.log` maior — não medido contra um documento real
  grande; se isso incomodar na prática, o corte é filtrar quais páginas
  entram na trilha (ex. só as que escalaram), não o desenho em si.

## Testes

`tests/test_planejador.py::TestTrilhaDeTentativas` (a trilha é construída
corretamente, tentativa por precondição não é fabricada) e
`tests/test_lote.py::TestTrilhaDeAuditoriaPorPagina` (a trilha chega ao
`.log`, com o desfecho real de execução).
