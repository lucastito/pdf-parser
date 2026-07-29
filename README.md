# pdf-parser

Parser de documentos **agnóstico de domínio** que extrai conteúdo estruturado e
entrega **saída validada contra schema**. O schema é parâmetro: o núcleo não presume
o tipo de documento nem os campos.

Sobre isso, um segundo objetivo: **comparar estratégias de extração com número**.
Determinística, por biblioteca pronta, por modelo de linguagem e por modelo de
visão implementam a mesma interface e são medidas pela mesma régua — de modo que
"esta abordagem é melhor" seja afirmação verificável, não preferência.

## Por que não é trivial

O documento-caso (tabela nutricional TACO, 164 páginas) tem três patologias
**medidas**, não supostas:

| Patologia | Evidência |
|---|---|
| Fontes CID com `ToUnicode` incompleto | extração ingênua rendeu 89 palavras reais em 534 mil caracteres |
| Tabela sem linhas de grade | o detector de tabelas encontra **zero** |
| Tabela rotacionada 90° | cada faixa horizontal traz *um nutriente de todos os alimentos* |

Daí a conclusão que orienta o desenho: **um extrator que roda sem erro e grava lixo
é pior do que um que falha alto.**

## Instalação

```powershell
git clone https://github.com/lucastito/pdf-parser.git
cd pdf-parser
git config core.hooksPath .githooks
python -m pip install -e ".[dev]"
```

O `git config` importa: os hooks de proteção **não viajam no clone**.

## Uso

```powershell
python -m parser.cli ambiente                              # o que a máquina tem
python -m parser.cli extrair perfis/nutricional.json # extrai e grava
python -m parser.cli comparar perfis/nutricional.json # compara, sem gravar
python -m parser.cli experimento --documento X.pdf          # roda tudo e registra
```

Trocar de contexto é trocar de perfil, não de código:

```json
{
  "fonte":    { "tipo": "pdf", "paginas": [28, 31, 2] },
  "extrator": { "tipo": "posicional", "layout": { "...": "..." } },
  "destinos": [{ "tipo": "csv", "caminho": "saida/dados.csv" }]
}
```

## Rodar o experimento em outra máquina

Dois comandos, em ordem:

```powershell
.\scripts\1-preparar-maquina.ps1
.\scripts\2-rodar-experimento.ps1 -Documento "C:\caminho\do\documento.pdf"
```

O primeiro instala Python, dependências, servidor de inferência e os três modelos
(~7 GB) e roda os testes. O segundo executa todas as estratégias, grava em
`resultados/<maquina>/`, cria a branch `experimento/<maquina>` e commita.

Depois:

```powershell
git push -u origin experimento/<maquina>
```

e abra o pull request. O push fica fora do script porque é o passo irreversível.

### Execução cega, de propósito

**Não consulte `resultados/` de outra máquina antes de rodar.** Saber o resultado
esperado enviesa a leitura de uma falha ("deve ser normal") e a decisão de insistir
num modelo lento. A comparação acontece depois, na revisão do pull request.

### Por que cada máquina roda tudo

Comparar estratégias executadas em hardwares diferentes mediria **hardware**, não
estratégia. Cada máquina produz uma rodada completa e autocontida: dentro dela
comparam-se estratégias; entre máquinas, compara-se velocidade.

De graça, isso rende um teste de reprodutibilidade — a rota determinística deve dar
resultado idêntico nas duas; as rotas com modelo podem não dar, e divergência ali é
achado sobre confiabilidade.

## Expectativas honestas de desempenho

Medido num notebook de 4 núcleos, 15 W, sem GPU utilizável:

| Estratégia | Tempo |
|---|---|
| posicional | **164 páginas em 1,55 s** |
| modelo de texto pequeno | ~45 s **por página** |
| modelo de visão | pode não completar uma página em 10 minutos |

Em CPU modesta, a rota determinística é ordens de grandeza mais rápida e a rota por
visão pode ser inviável. **Isso é resultado do experimento, não defeito dele.**

Se o modelo de visão estourar o tempo, aumente o limite ou reduza a resolução — mas
note que **resolução é variável do experimento**: duas rodadas com resoluções
diferentes não são comparáveis, e o valor é registrado no resultado justamente para
que isso não passe batido.

## Acurácia

O experimento mede velocidade, cobertura e **concordância entre estratégias**. Não
mede acurácia: para isso é preciso um gabarito conferido à mão contra o documento
original (ver [golden/README.md](golden/README.md)).

Concordância é sinal, não prova — estratégias podem errar igual, e uma estratégia
isolada pode ser a única correta.

Os dados brutos ficam salvos, então a acurácia é calculada **depois**, sobre os
mesmos resultados, sem reexecutar. Rodar antes do gabarito não desperdiça trabalho.

## Estrutura

```
pdf-parser/
├── src/parser/
│   ├── modelo.py          # proveniência por campo, sentinelas
│   ├── portas.py          # fonte, extrator, destino
│   ├── normalizacao.py    # a mesma para todas as estratégias
│   ├── fontes/            # pdf, render para imagem, stub
│   ├── extratores/        # posicional, linear, biblioteca, vlm
│   ├── destinos/          # csv, json
│   ├── triagem.py         # dados | contexto | descartável
│   ├── avaliacao.py       # métrica por campo, contra gabarito
│   ├── concordancia.py    # entre estratégias, sem gabarito
│   ├── experimento.py     # execução com procedência
│   └── cli.py
├── perfis/                # configuração declarativa
├── golden/                # gabarito de avaliação
├── scripts/               # 1-preparar-maquina, 2-rodar-experimento
├── docs/adr/              # decisões, com os números que as sustentam
├── SPEC.md                # especificação (SDD)
└── REQUISITOS.md          # requisitos numerados
```

## Qualidade

Python 3.10+ · `pytest` · PEP 8 · `black` · `flake8`.

```powershell
python -m pytest --cov=src
.\.githooks\selftest.sh      # guarda de confidencialidade
```

## Fonte dos dados

Tabela Brasileira de Composição de Alimentos (TACO), NEPA/UNICAMP, 4ª edição
ampliada e revisada, Campinas, 2011 — cuja licença permite reprodução total ou
parcial desde que citada a fonte.
