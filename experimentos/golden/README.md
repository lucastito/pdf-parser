# Golden set

Gabarito de avaliação: os valores que o extrator **deveria** produzir.

## Por que conferido à mão

Um gabarito gerado pelo próprio extrator mediria o extrator contra ele mesmo — o
resultado seria 100% por construção e não diria nada. A conferência humana contra
o documento original é o que dá sentido a todas as métricas.

## Arquivos

| Arquivo | Estado |
|---|---|
| `taco-para-conferir.csv` | **proposta**, ainda não conferida |
| `taco.csv` | **gabarito conferido, já existe** — é o arquivo real contra o qual a matriz de avaliação compara todos os extratores hoje |

## Como conferir

`taco-para-conferir.csv` traz 40 alimentos × 5 macronutrientes (200 valores), com
a coluna `pagina_pdf` indicando onde cada linha foi lida. Ao lado de cada valor há
uma coluna `*_ok` para marcação:

- `ok` — confere com o documento
- o **valor correto** — se estiver errado
- `?` — se estiver ambíguo ou ilegível

Ao terminar, renomeie para `taco.csv`. É contra esse arquivo que a matriz de
avaliação passa a comparar todos os extratores.

**Não conferir "por amostragem otimista".** Os erros que interessam são os
sistemáticos — uma coluna inteira deslocada produz valores plausíveis e é
justamente o que a conferência precisa pegar.

## Conjunto de reserva: como ler o número

O `holdout.csv` foi transcrito às cegas, com numeração **local** (1 a 10), não a do
documento. O mesmo alimento aparece como `1 Pão, milho, forma` no reserva e
`51 Pão, milho, forma` na extração — mesmo valor, número diferente.

Por isso o alinhamento acontece **primeiro pela descrição**, e só depois pelo
número. A ordem inversa causava um erro silencioso: `1 Pão, milho` (292 kcal) era
comparado com `1 Arroz, integral` (124 kcal), e o resultado parecia erro de
extração quando era erro de alinhamento.

**A acurácia contra o reserva mede duas coisas ao mesmo tempo.** Dos 10 itens, só 2
estão nas páginas que o perfil declara ler; os outros 8 são de seções que o
intervalo não cobre. Os 2 presentes acertam **5 de 5 campos** — leitura perfeita.
Os 8 ausentes contam como erro, e o total sai 20%.

Esse 20% não é qualidade de leitura: é **cobertura de páginas**. Para medir só a
leitura, amplie o intervalo de páginas do perfil ou compare apenas os itens
presentes. Registrar a distinção importa porque um "20%" sem contexto sugere que as
ferramentas não funcionam, quando o que falta é alcance.

## Fonte e licença

Dados extraídos da **Tabela Brasileira de Composição de Alimentos (TACO)**,
NEPA/UNICAMP, 4ª edição ampliada e revisada, Campinas, 2011.

A obra permite reprodução total ou parcial desde que citada a fonte — daí a
inclusão destes dados aqui. Fontes cuja licença proíba redistribuição não entram
neste diretório, mesmo quando disponíveis localmente.

## Limite declarado, não corrigido (auditoria externa, 2026-08-02)

`taco.csv` foi conferido por **uma pessoa só**, sem segundo anotador
independente, sem cegamento e sem adjudicação de divergência — a
`AUDITORIA_TECNICA_CIENTIFICA.md` (P0.3) aponta isso como risco real: um erro
sistemático da própria pessoa que revisou sobrevive à conferência. O
`holdout.csv` também deixou de ser um teste final independente no sentido
estrito, porque já revelou bugs que foram corrigidos em resposta (P0.2) — ele
funciona como conjunto de desenvolvimento avançado, não como holdout
intocado. Ver `PLANO.md`, seção de pendências da auditoria externa.
