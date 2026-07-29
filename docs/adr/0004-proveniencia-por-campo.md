# ADR-0004 — Proveniência por campo

**Status:** aceito · **Data:** 2026-07-29

## Contexto

O parser produz registros que alimentam sistemas a jusante. Alguns valores são lidos
do documento; outros, no futuro, serão estimados por modelo quando o documento não os
trouxer. Um consumidor que receba os dois indistintamente não tem como separar o que
o documento afirma do que o sistema supôs.

Há ainda um caso mais sutil, presente no documento-caso: marcadores que substituem um
número — traço (quantidade desprezível), não analisado, não aplicável. **Não são zero
e não são nulo.** Traço afirma "presente em quantidade ínfima"; não analisado afirma
"não sabemos". Colapsar os dois em ausência — ou pior, em zero — corrompe qualquer
soma a jusante, sem erro visível.

## Decisão

Todo valor viaja acompanhado da sua procedência:

```python
class Campo[T]:
    valor: T | None
    sentinela: Sentinela | None    # traço | não analisado | não aplicável
    origem: Origem                 # extraído | derivado | inferido | ausente
    confianca: float
    evidencia: Evidencia | None    # página, bbox, texto bruto, vizinhança
```

Invariantes verificadas na construção, não por convenção:

- Valor e marcador são mutuamente exclusivos.
- Origem *ausente* implica valor nulo e confiança zero.
- Origem *extraído* ou *derivado* **exige evidência** — sem ela não há auditoria.
- Origem *inferido* dispensa evidência: não há o que apontar no documento.

Disso decorre a **taxa de inferência**: a proporção de campos preenchidos que não
foram extraídos diretamente. Campos ausentes ficam fora do cálculo — incluí-los faria
um registro vazio parecer bem fundamentado.

## Por que desde o início, e não depois

Retrofitar proveniência exigiria reescrever todo consumidor: a forma do dado muda de
`float` para um objeto composto. Adotá-la agora custa pouco; adiá-la torna o custo
proporcional ao número de integrações existentes.

Há também uma consequência prática imediata: o campo `evidencia` é o que permite
**auditar um valor suspeito sem o documento original em mãos** — situação normal
quando a saída já foi distribuída.

## Consequências

- O destino estruturado preserva proveniência integral; o destino tabular achata para
  consumo por planilha, com convenção explícita para que marcador, zero e ausência
  permaneçam distinguíveis.
- A avaliação penaliza tanto o campo faltante quanto o **valor inventado** — um
  extrator que preenche o que o documento não afirma é punido, não premiado por
  cobertura.
- Quando a inferência por modelo entrar, a métrica para acompanhá-la já existe e não
  precisará ser retroencaixada.
- Custo: a saída estruturada é maior que um simples mapa de valores. É o preço da
  auditabilidade, e foi aceito conscientemente.
