# ADR-0007 — Rota por OCR e a escolha de resolução

**Status:** aceito · **Data:** 2026-07-29

> **Retificação de 2026-08-12.** O número desta ADR (**84,5%**, medido contra
> o gabarito de 40 itens que a própria estratégia de reconstrução direta
> gerou — ver "Ressalva" no fim) ficou parado enquanto o número correto
> avançou em outro lugar: `PLANO.md` já registra **99,5%** contra o mesmo
> gabarito principal (tabela "Contra o conjunto de reserva"), e `REQUISITOS.md`
> RF-2 cita o mesmo par (99,5% / 78% no conjunto de reserva). A auditoria de
> 02/08 confirmou a divergência (`AUDITORIA-2026-08-02.md`) e ela ficou sem
> corrigir até agora. **O que causou a melhoria de 84,5% para 99,5% não está
> documentado em nenhum ADR** — é uma lacuna de rastreabilidade em si, não só
> um número desatualizado; investigar antes de citar 84,5% ou 99,5% como se
> fossem a mesma medição.

## Contexto

A extração por OCR é requisito em dois lugares (RF-2 do projeto e critério de
aceitação da especificação de referência) e é a única rota possível para documento
digitalizado. O documento-caso tem texto nativo, então não precisa de OCR — e isso
é uma **vantagem experimental**: renderizar a página como imagem e passá-la por OCR
cria um caso em que a resposta certa é conhecida, permitindo medir exatamente
quanto a rota por imagem degrada.

## Primeiro resultado: 2 registros, 0% — e era defeito nosso

A rota produziu 2 registros contra 64 da extração direta. A leitura fácil seria
"OCR não serve para este documento". Investigar mostrou o contrário:

| | OCR | Extração direta |
|---|---|---|
| Palavras reconhecidas | **546** | 546 |
| x máximo | 751 | 523 |
| y máximo | 527 | 748 |
| Palavras na faixa de itens | 1 | 172 |

O reconhecimento era **perfeito** — as mesmas 546 palavras. As coordenadas estavam
em eixos trocados.

**Causa:** a página declara `rotation=90`. A renderização **aplica** essa rotação;
a extração direta de texto devolve coordenadas no espaço **não rotacionado**. Os
dois sistemas divergiam, e o layout calibrado para um não encontrava nada no outro.

Corrigido com transformação inversa explícita para rotações retas. Depois da
correção: 64 registros, **77%** de acurácia.

Fica a lição de método: *2 registros* parecia resultado e era bug. Sem comparar
palavra por palavra contra a rota direta, a conclusão errada teria sido registrada
como achado.

## Modo de falha: a vírgula decimal

Todos os erros restantes têm a mesma forma:

```
"4,8" → 48.0      "8,5" → 85.0      "4,5" → 45.0
```

Não é erro de dígito — é **omissão da vírgula**, produzindo valores dez vezes
maiores. Falha sistemática e previsível, não ruído.

Isso importa além do OCR: um valor dez vezes maior é plausível o suficiente para
passar por validação de tipo e faixa. Só a comparação com gabarito o revela.

## A curva de resolução não é monotônica

| DPI | Acurácia | Erros de vírgula | Campos não encontrados |
|---|---|---|---|
| 200 | 77,0% | 8 | 30 |
| 250 | 82,0% | 6 | 30 |
| 300 | 83,0% | 4 | 30 |
| **350** | **84,5%** | **1** | 30 |
| 400 | 29,0% | 0 | **142** |

Duas forças opostas:

- **mais resolução recupera a vírgula** — 8 erros a 200 dpi, 1 a 350;
- **resolução excessiva quebra o alinhamento** — a 400 dpi a vírgula é lida
  perfeitamente, mas 142 campos deixam de ser localizados: a tolerância do layout,
  expressa em pontos tipográficos, não acompanha a granularidade maior.

Ou seja: a 400 dpi o OCR lê melhor e a reconstrução acerta menos. Otimizar só o
reconhecimento pioraria o resultado final.

## Decisão

**350 dpi** como padrão para a rota por OCR.

O valor é registrado com cada execução: resolução é variável do experimento, e
duas rodadas em resoluções diferentes não são comparáveis entre si.

## Consequências

- A rota por OCR passa a ser a **segunda melhor** estratégia medida (84,5%), atrás
  apenas da reconstrução direta.
- Fica quantificado o custo da rota por imagem: cerca de 15 pontos de acurácia e
  ordens de grandeza mais tempo. Para documento com texto nativo, não se justifica;
  para digitalizado, é a única opção e agora tem número associado.
- A tolerância do layout deveria escalar com a resolução. Não escala hoje — está em
  aberto, e é o que explica o colapso a 400 dpi.
- Os 30 campos não encontrados nas resoluções boas são um piso que a correção de
  rotação não resolveu. Merece investigação separada.

## Ressalva

A medição usa o gabarito de 40 itens, que foi **gerado pela estratégia de
reconstrução direta** e apenas conferido. Isso não afeta a validade dos números do
OCR — ele é uma estratégia independente —, mas a comparação com a estratégia que
gerou o gabarito permanece assimétrica até que exista um conjunto de reserva
transcrito às cegas.
