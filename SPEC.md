# SPEC — pdf-parser

> Especificação **antes** do código (SDD). Testes antes da implementação (TDD).
> Esta spec descreve a **fatia 1**; o que está fora dela é marcado como *(fora da fatia 1)*.
> Requisitos numerados em [REQUISITOS.md](REQUISITOS.md). Decisões em [docs/adr/](docs/adr/).

## 1. Problema

Extrair dados de documentos heterogêneos e entregá-los como **registros validados
contra schema**, em destino configurável, sem parsing manual de texto solto.

O núcleo é **agnóstico**: não conhece formato de entrada, domínio do documento, nem
formato de saída. Formato e destino são *adapters*; o schema é *parâmetro*.

### 1.1 Por que isso não é trivial

O documento-caso da fatia 1 (tabela nutricional TACO, 164 páginas) exibe três
patologias que quebram parsers genéricos, todas **medidas**, não supostas:

| Patologia | Evidência medida | Consequência |
|---|---|---|
| Fontes CID / `Identity-H` com `ToUnicode` incompleto | 5 mapas para 31 fontes; extração ingênua produziu 89 palavras reais em 534k caracteres | Extração por regex sobre o stream **corrompe em silêncio** |
| Tabela sem linhas de grade | `find_tables()` retorna **0 tabelas** nas páginas de dados | Detectores baseados em borda não servem |
| Tabela rotacionada 90° | Cabeçalhos verticais; cada faixa de Y contém um nutriente para *todos* os alimentos | O que parece linha é coluna — exige transposição |

Some-se: decimal com vírgula, valores sentinela (`Tr`, `NA`, `*`), energia em duas
unidades (kJ e kcal).

**A conclusão que orienta o desenho:** um extrator que "roda sem erro" e grava lixo é
pior do que um que falha alto. Daí a validação obrigatória e a avaliação medida por campo.

## 2. Escopo da fatia 1

**Dentro:**
- Entrada PDF de texto nativo, com reconstrução posicional de tabela
- Schema declarativo por perfil, com proveniência por campo
- Saída CSV (primária) e JSON
- Golden set com métrica por campo
- Arquitetura que permite trocar o extrator (determinístico | modelo) sem tocar no núcleo

**Fora da fatia 1** (previsto na arquitetura, não implementado):
- OCR para digitalizados (RF-2)
- Extração por LLM/VLM (RF-4, RF-5) — a *porta* existe, a implementação vem depois
- Inferência de campos ausentes
- Adapters de outros formatos — entram como **stub que falha explicitamente**

## 3. Arquitetura

```
   ENTRADA                      NÚCLEO                        SAÍDA
   (adapters)              (agnóstico, estável)             (adapters)

   PDF      ──┐                                            ┌──►  CSV
   XLSX*    ──┤                                            ├──►  JSON
   CSV*     ──┼──►  Documento  ──►  Extrator  ──►  Registro ┼──►  banco*
   JSON*    ──┤     Canônico         (porta)      Validado  ├──►  API*
   imagem*  ──┘                         ▲                   └──►  ...
                                        │
                            ┌───────────┴───────────┐
                            │                       │
                     determinístico            modelo*
                     (fatia 1)              (LLM | VLM)

                     * = stub ou fora da fatia 1
```

Três portas, três razões:

- **`FonteDocumento`** — lê um arquivo e devolve `DocumentoCanônico`. Trocar formato de
  entrada não toca no núcleo.
- **`Extrator`** — recebe `DocumentoCanônico` + schema, devolve `RegistroValidado`.
  **É a porta que torna a comparação possível:** determinístico, LLM e VLM são
  implementações intercambiáveis, medidas pela mesma régua.
- **`Destino`** — grava `RegistroValidado`. Trocar destino não toca no núcleo.

### 3.1 Perfil: o que torna o sistema parametrizável

Um perfil é um arquivo declarativo que reúne schema, mapeamento e destino. Trocar de
contexto é trocar de perfil — sem alterar código.

```yaml
# perfis/exemplo.yaml
nome: exemplo
fonte:   { tipo: pdf, estrategia: posicional }
schema:  campos/exemplo.py      # modelo Pydantic
destino: { tipo: csv, caminho: saida/exemplo.csv }
```

## 4. Modelo de dados

### 4.1 Proveniência por campo (decisão estruturante)

Todo valor carrega **como foi obtido**. Não é enfeite: sem isso é impossível medir
extração contra inferência, e retrofitar depois exigiria reescrever todo consumidor.

```python
class Origem(StrEnum):
    EXTRAIDO = "extraido"    # lido diretamente do documento
    DERIVADO = "derivado"    # calculado a partir de campos extraídos
    INFERIDO = "inferido"    # estimado por modelo — fora da fatia 1
    AUSENTE  = "ausente"     # não encontrado; nada foi inventado

class Campo[T]:
    valor: T | None
    origem: Origem
    confianca: float           # 1.0 para extração determinística
    evidencia: Evidencia | None # página, bbox, texto bruto
```

Disso decorre uma métrica agregada — a **taxa de inferência** (proporção de campos não
extraídos diretamente) — que serve tanto de indicador de qualidade quanto de gate.

### 4.2 Valores sentinela

O documento-caso usa `Tr` (traço), `NA` (não analisado) e `*`. **Não são zero e não são
nulo.** Confundi-los corrompe qualquer cálculo a jusante. O schema os representa
explicitamente, preservando o texto bruto na evidência.

### 4.3 Unidade de medida (RF-7)

RF-7 exige saída com **tipo e unidade quando aplicável**. Até aqui a unidade existe
apenas como texto inerte dentro do rótulo — `"Energia (kcal)"` — usado para
desambiguar o mapeamento, nunca para converter. Consequência: `Origem.DERIVADO` está
definido e validado no modelo, com "conversão de unidade" no próprio docstring, e
**nada o produz**. Este é o buraco que a conversão fecha.

O documento-caso já mostra o problema em escala pequena: energia aparece em kcal *e*
em kJ, e um consumidor que espere uma das duas recebe a outra sem aviso. Um documento
de outro contexto trará o mesmo problema com outras unidades.

**A conversão é etapa permanente do pipeline; a tabela de conversão vem do perfil.**
Essa separação é o que preserva o núcleo agnóstico: o núcleo sabe *converter*, e nunca
sabe que "kcal" ou "g" existem. Sem unidade-alvo declarada, a etapa executa e não
converte nada — não por estar desligada, mas por não haver o que converter. É o mesmo
contrato do mapeamento, que também é sempre aplicado com regras vindas de fora.

Regras que a conversão obedece:

- Campo convertido sai com origem **`DERIVADO`**, preservando a evidência do valor
  original — a auditoria continua chegando ao texto bruto no documento.
- A confiança do campo original é **propagada**, nunca elevada: converter não
  acrescenta conhecimento.
- Unidade desconhecida ou incompatível (`g` → `kcal`) **falha alto**, com o nome do
  campo na mensagem. Converter errado em silêncio é o modo de falha que este projeto
  mais evita.
- Sentinela não se converte: `Tr` em grama continua `Tr`. Não há número a multiplicar.
- Sem unidade-alvo declarada, o campo passa **intacto**, com origem `EXTRAIDO`
  preservada — de modo que nenhuma medição anterior mude de valor.

### 4.4 Degraus de saída do modelo (RF-4, RF-5)

Um modelo pequeno pode devolver **resposta vazia** sem erro algum: o servidor
responde `200`, a resposta é `""`, e o extrator recebe zero item como se a página
estivesse em branco. Numa execução em lote isso vira "processado, 0 registros".

**Causa medida: corte pelo limite de CONTEXTO** — que limita entrada e saída
**somadas**, e não pelo teto de saída. Quatro hipóteses foram levantadas, e as
refutadas ficam registradas porque hipótese invalidada é resultado; sem o
registro, a busca se repete.

| Hipótese | Veredito | Evidência |
|---|---|---|
| Esquema restringido torna o caminho inalcançável | **refutada** | texto livre, sem restrição, também vem vazio |
| Canal de raciocínio consome tudo | **refutada como causa isolada** | desligar não mudou os números (152 × 152) |
| O teto de **saída** corta a geração | **refutada** | elevá-lo a 16384 não removeu o corte: continuou parando em ~1900 |
| O **contexto** corta, limitando entrada + saída | **confirmada** | quatro casos, prompts de tamanhos diferentes, mesma soma exata: **4096** |

O sinal que revelou *que havia* corte foi o `done_reason` mudando de `stop` para
`length`. O que revelou **qual limite** cortava foi a **soma de entrada e
saída** — dado que vinha em toda resposta e era descartado.

Cinco prompts na mesma página real, medidos um por vez:

| prompt | `done_reason` | tokens | resposta |
|---|---|---|---|
| descreva a imagem | `stop` | 689 | 794 chars |
| leia a tabela | `length` | 1927 | vazia |
| leia com campos | `length` | 1923 | vazia |
| leia em JSON | `length` | 1912 | vazia |
| leia com guardrails | `length` | 1887 | vazia |

Descrever uma página cabe; enumerar dezenas de itens não. Note que os totais
cortados batem no mesmo valor mesmo com prompts de tamanhos diferentes — é a
assinatura de um teto fixo sendo atingido, não de o modelo parar por conta
própria.

**Consequência de desenho:** o **contexto** e o teto de saída são **ambos**
declaráveis, e nenhum tem padrão embutido no código (ADR-0008). Declarar só o
teto de saída não basta: o contexto tem padrão do servidor — invisível — e é ele
que corta quando a entrada é grande, como acontece com imagem.

O valor certo do contexto depende de quanto a **entrada** consome, que precisa
ser **medido**, não suposto. Numa página renderizada, a entrada é a maior parte.

Os degraus permanecem por outro motivo, e é real: impedir que resposta vazia vire
"página sem dados" em silêncio, e registrar sob qual restrição cada resultado foi
obtido. No experimento, **todos** rodam — parar no primeiro sucesso destrói a
comparação entre máquinas (ADR-0013).

Regras que a estratégia obedece:

- **O degrau usado é registrado com o resultado**, e o tipo da falha também:
  `resposta-cortada`, `resposta-vazia` e `sem-estrutura` mandam procurar em
  lugares diferentes.
- **Resposta vazia é falha, não resultado vazio** — a distinção que impede uma
  página não lida de virar "página sem dados".
- O degrau final ainda valida contra o schema. Degradar a *forma* da restrição
  nunca degrada a **validação**: RF-7 vale nos três degraus.

### 4.5 Validação da saída tabular

O modelo valida **campo a campo** (Pydantic, na construção do `Registro`). Isso não
cobre invariantes do conjunto: colunas ausentes, tipo divergente entre registros,
lote heterogêneo. O destino CSV monta o cabeçalho a partir do **primeiro** registro,
então um lote em que o segundo registro tenha campo a mais perde a coluna em silêncio
— exatamente a classe de falha muda que a spec repudia em §1.1.

A validação de esquema tabular é, portanto, uma **segunda porta**, aplicada ao
conjunto antes da gravação: verifica presença de coluna, tipo e as restrições que o
perfil declarar. Como toda configuração do projeto, o esquema é declarativo e vem do
perfil — o núcleo não conhece nome de campo algum.

## 5. Requisitos verificáveis

Cada item vira teste antes da implementação (TDD).

| ID | Requisito | Como se verifica |
|---|---|---|
| **E1** | Extrair texto sem corrupção de encoding | Acentuação e caracteres especiais conferem com o gabarito |
| **E2** | Reconstruir a tabela apesar da rotação e da ausência de grade | Valores por registro conferem com o gabarito conferido à mão |
| **E3** | Distinguir sentinelas de zero e de nulo | `Tr`/`NA` nunca viram `0` nem `None` silenciosamente |
| **E4** | Converter decimal com vírgula | `"3,86"` → `3.86` |
| **V1** | Rejeitar registro fora do schema | Registro inválido falha alto, com mensagem localizável |
| **V2** | Todo campo carrega origem e evidência | Nenhum campo sai com origem indefinida |
| **U1** | Converter unidade declarada no perfil | `1000 kcal` → `4184 kJ`, dentro da tolerância |
| **U2** | Campo convertido é `DERIVADO`, com a evidência original | Origem muda; evidência aponta o texto bruto do documento |
| **U3** | Conversão impossível falha alto | `g` → `kcal` levanta erro nomeando o campo |
| **U4** | Sentinela e campo ausente atravessam intactos | `Tr` continua `Tr`; ausente continua ausente |
| **U5** | Sem unidade-alvo declarada, nada muda | Registro sai idêntico à entrada, origem preservada |
| **U6** | O núcleo não conhece unidade de domínio algum | Nenhum nome de unidade aparece fora de perfil e de teste |
| **T1** | Esquema tabular rejeita coluna ausente ou tipo divergente | Lote inválido falha alto, nomeando coluna e motivo |
| **T2** | Lote heterogêneo não perde coluna em silêncio | Registro com campo a mais é detectado antes da gravação |
| **S1** | Gravar CSV e JSON do mesmo registro validado | Round-trip preserva valores e sentinelas |
| **S2** | Formato de saída é parâmetro | Trocar destino não altera o núcleo |
| **A1** | Extrator é intercambiável | Um extrator alternativo roda o mesmo golden set sem mudar o núcleo |
| **A2** | Formato não implementado falha explicitamente | Stub levanta erro claro; nunca simula sucesso |
| **Q1** | Cobertura de teste ≥ 80% | `pytest --cov` |
| **G1** | O alinhamento do gabarito não pareia itens diferentes | Numeração divergente casa pela descrição, não por número (ADR-0012) |
| **G2** | Sentinela é comparada pelo que afirma, não pela grafia | `Tr` do documento casa com a sentinela; `Tr` nunca casa com `NA` nem com zero |
| **G3** | O conjunto de reserva mede generalização | Cobre seções não usadas no ajuste; acurácia medida contra layout novo |
| **X1** | Toda rodada registra máquina, entrada, parâmetros e condição | `experimentos/resultados/<maquina>/` com procedência (ADR-0013) |
| **X2** | O documento medido é o mesmo em todas as máquinas | Impressão digital verificada na suíte |
| **X3** | Duas medições não rodam ao mesmo tempo na mesma máquina | A segunda falha alto em vez de contaminar as duas |
| **X4** | No experimento, todos os degraus rodam — não só até o primeiro sucesso | Cada degrau registra sucesso, tipo de falha e tempo |

## 6. Avaliação

**A avaliação não é etapa final: é requisito de arquitetura.** O objetivo é permitir
afirmações defensáveis com número — inclusive negativas.

### 6.1 Golden set

- ~30–50 registros do documento-caso, **conferidos manualmente** contra o original.
- Gabarito gerado por máquina mediria o extrator contra ele mesmo — inútil por construção.
- Registrar página de origem por registro, para auditoria.
- Fonte de licença permissiva, citada. Fontes que proíbem redistribuição ficam fora.

### 6.2 Métricas

| Métrica | Aplicação |
|---|---|
| Exact match | Identificadores, categóricos, sentinelas |
| Erro relativo com tolerância | Campos numéricos (`"42"` vs `"42.0"` não é erro) |
| Similaridade textual | Campos de texto livre |
| Cobertura | Proporção de campos preenchidos |
| Taxa de inferência | Proporção não extraída diretamente |
| Latência e memória | Por página e por documento |

Métrica **por campo**, nunca só agregada: um agregado alto esconde um campo sistematicamente
errado.

### 6.3 Comparação entre extratores

Matriz `extrator × métrica` sobre o mesmo golden set. A pergunta a responder é
literalmente: *o extrator mais sofisticado compensa, neste documento?* — e a resposta
pode ser **não**. Um resultado negativo medido é resultado.

Hipóteses registradas com status **validada / invalidada / em aberto**, incluindo as que
falharem. Rerodar a matriz a cada troca de versão de componente: mudar o extrator no meio
da avaliação invalida a comparação.

### 6.4 Rigor

O golden set usado para iterar **não é holdout**. Ajustar decisões olhando o mesmo conjunto
enviesa; reservar um subconjunto não visto para o gate final.

## 7. Restrições de ambiente

O ambiente-alvo é modesto: **~2 GB de VRAM, 16 GB de RAM, CPU de baixo consumo**.
A restrição é deliberada e informa o desenho — não é acidente a ser contornado depois.

Consequências, com trade-off explícito em ADR:
- Extração determinística é o **caminho padrão**, não o plano B.
- Modelos grandes estão fora do envelope; só cabem modelos pequenos quantizados.
- Processamento por modelo tende a ser **ordens de grandeza mais lento** que a rota
  determinística — o que precisa ser medido, não assumido.

Há também um alvo de desempenho de referência: **documento de porte médio em menos de
5 minutos**. Serve de critério objetivo na matriz de comparação.

## 8. Qualidade

Python 3.10+ · `pytest` com cobertura ≥ 80% · PEP 8 · `black` · `flake8` ·
ambiente isolado · logging estruturado · erros com mensagem acionável.

## 9. Não-objetivos

Não é um produto de UI. Não infere dado ausente (fatia 1). Não implementa regras de
negócio de domínio algum — o domínio entra por schema, nunca por código. Não redistribui
documentos de origem cuja licença não permita.

## 10. Questões em aberto

1. Formatos de entrada além de PDF: nomes e amostras a confirmar antes de investir.
2. Schema do destino externo: não disponível nesta fase; mapeamento fica genérico.
3. Alvo de 5 minutos: falta o volume de referência para dimensionar.
