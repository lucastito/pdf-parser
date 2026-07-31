# pdf-parser

Lê documentos, extrai o que interessa e entrega **dados validados contra schema**.
Aponte-o para uma pasta; ele consolida numa saída única e sinaliza o que precisa de
atenção humana.

O núcleo é **agnóstico**: não presume o tipo de documento nem os campos. O schema, o
layout e o destino são configuração — não código.

## Instalação

```powershell
git clone https://github.com/lucastito/pdf-parser.git
cd pdf-parser
git config core.hooksPath .githooks
python -m pip install -e ".[dev]"
```

O `git config` importa: os hooks de verificação não viajam no clone.

## Uso

A ordem dos comandos é a ordem natural de adoção de um documento novo:

```powershell
python -m parser.cli ambiente                    # esta máquina tem o necessário?
python -m parser.cli diagnosticar doc.pdf        # há algo que sabota a leitura?
python -m parser.cli calibrar doc.pdf --json     # qual o layout deste documento?
python -m parser.cli ingerir ./entrada --saida ./saida/dados.csv
```

Os três primeiros são diagnóstico; o quarto é o trabalho.

### Ingerir uma pasta

```powershell
python -m parser.cli ingerir ./entrada `
    --perfil perfis/nutricional.json `
    --saida ./saida/consolidado.csv
```

Gera três arquivos, porque servem a três leitores:

| Arquivo | Para quem |
|---|---|
| `consolidado.csv` | o sistema de destino |
| `consolidado.log` | quem acompanha a execução |
| `consolidado.erros.json` | quem precisa corrigir a entrada |
| `consolidado.pendencias.json` | quem vai revisar o que falta |

**Um arquivo com problema não interrompe o lote.** Numa pasta de cem documentos,
abortar no terceiro desperdiçaria os outros noventa e sete. Cada falha é registrada
com o motivo e a ação recomendada.

**O layout é decidido por arquivo:** calibração automática quando a confiança basta,
perfil informado como alternativa, falha explícita se nenhum servir. Uma pasta com
documentos de origens diferentes funciona sem configuração por arquivo.

### Medir antes de confiar

```powershell
python -m parser.cli avaliar gabarito.csv --perfil perfis/X.json --documento doc.pdf
python -m parser.cli comparar --perfil perfis/X.json --documento doc.pdf
```

`avaliar` mede acurácia por campo contra um gabarito conferido à mão. `comparar` mede
concordância entre estratégias, sem gabarito — sinal útil, mas não prova:
estratégias podem errar igual.

Para uma rodada que fica registrada:

```powershell
python -m parser.cli experimento --perfil perfis/X.json --documento doc.pdf
```

`comparar` imprime e esquece; `experimento` **grava** os dados brutos com
procedência (máquina, processador, parâmetros, data), numa pasta por máquina. A
acurácia é calculada depois, sobre os mesmos dados, sem reexecutar nada.

Uma trava impede duas rodadas simultâneas na mesma máquina: elas disputariam o
mesmo processador e os tempos das duas ficariam inflados, sem que nada no
resultado denunciasse. Rodada contaminada que parece válida é pior que rodada
ausente.

## Configuração

Trocar de contexto é trocar de perfil:

```json
{
  "nome": "exemplo",
  "paginas": [28, 31, 2],
  "mapeamento": { "campo_destino": ["Rótulo no documento"] },
  "unidades": { "energia_kj": { "de": "kcal", "para": "kJ" } },
  "esquema": {
    "identificador": { "tipo": "texto", "obrigatorio": true },
    "energia_kj": { "tipo": "numero", "minimo": 0 }
  },
  "rotas": {
    "posicional": { "layout": { "x_rotulos": [110, 133], "...": "..." } },
    "ocr": { "dpi": 350 },
    "vlm": { "modelo": "qwen3-vl:4b", "prompt": "prompts/extracao-tabela-visao.md" }
  }
}
```

Use `parser calibrar --json` para descobrir o layout de um documento novo — ele
imprime o recorte pronto para colar.

**`mapeamento`** traduz o rótulo do documento para o nome que o destino espera.
Sem ele, uma extração perfeita mede zero de acurácia.

**`unidades`** converte para a unidade que o destino usa. O campo convertido sai
marcado como *derivado*, preservando a evidência do valor original. Sem declaração,
nada é convertido — nenhum resultado anterior muda de valor.

**`esquema`** descreve a saída esperada: coluna, tipo e restrições. É verificado
**antes de gravar**, porque dado inválido que chega ao destino já contaminou o
consumidor. Sem declaração, não há verificação de conjunto.

Nos três casos a regra é a mesma: o núcleo não conhece campo, unidade nem domínio.
Tudo entra por arquivo, e trocar de contexto é trocar de perfil.

Os prompts ficam em [prompts/](prompts/), em arquivos com a instrução, os guardrails
e a **justificativa de cada regra**. Sem a justificativa, a próxima pessoa remove uma
regra por parecer redundante e reintroduz um problema resolvido.

## Por que documento não é trivial

Três características medidas em um documento real, que quebram ferramentas maduras:

| Característica | Efeito |
|---|---|
| Página com rotação declarada | detectores de tabela encontram **zero** tabelas |
| Cabeçalho partido em duas linhas | lido como dado: `{"Carbo-": "idrato"}` |
| Fontes com mapa de caracteres incompleto | leitura direta do fluxo produz texto corrompido |

O comando `diagnosticar` detecta essas e outras, **com a ação recomendada** — porque
diagnóstico sem ação é só reclamação.

A conclusão que orienta o desenho: **um extrator que roda sem erro e grava lixo é
pior do que um que falha alto.**

## Formatos

Implementado: **PDF**.

Declaráveis no perfil e ainda não implementados: XLSX, CSV, JSON, DOCX, imagem, ZIP.
Eles falham alto quando usados, em vez de devolver resultado vazio — vazio parece
sucesso.

## Estrutura

```
pdf-parser/
├── src/parser/
│   ├── fontes/            leitura por formato
│   ├── extratores/        posicional, pdfplumber, camelot, ocr, llm, vlm
│   ├── destinos/          csv, json
│   ├── lote.py            uma pasta → uma saída
│   ├── diagnostico.py     o que sabota a leitura
│   ├── calibracao.py      descobre layout
│   ├── configuracao.py    perfis e prompts
│   ├── gabarito.py        acurácia contra valores conferidos
│   └── cli.py
├── perfis/  prompts/      configuração
├── entrada/  saida/       para uso
├── experimentos/          validação das decisões (dispensável para operar)
└── docs/adr/              decisões, com os números que as sustentam
```

## Qualidade

Python 3.10+ · `pytest` · PEP 8 · `black` · `flake8`.

```powershell
python -m pytest --cov=src
```

Alguns testes precisam de um documento de validação e são saltados sem ele:

```powershell
$env:PARSER_DOCUMENTO_CASO = "C:\caminho\documento.pdf"
python -m pytest
```

## Decisões

Cada decisão de arquitetura está em [docs/adr/](docs/adr/), com a medição que a
sustenta. Vale a leitura de quem for evoluir o código: várias registram o número que
resultaria de fazer diferente, incluindo casos em que a hipótese inicial se mostrou
errada.

O que ainda falta, com ordem e justificativa, está em
[experimentos/PLANO.md](experimentos/PLANO.md).
