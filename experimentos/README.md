# Experimentos

Material de validação: os dados e resultados que sustentam as decisões registradas
em [../docs/adr/](../docs/adr/).

**Nada aqui é necessário para operar o parser.** Quem for colocá-lo num servidor
pode ignorar este diretório por completo — o produto vive na raiz e em
[../src/parser/](../src/parser/).

## O que há aqui

| Diretório | Conteúdo |
|---|---|
| `golden/` | gabarito conferido à mão e conjunto de reserva |
| `resultados/` | uma pasta por máquina, com procedência e dados brutos |
| `scripts/` | preparação de ambiente e execução de rodada |

## Por que existe

As decisões de arquitetura do produto foram tomadas com número, não por preferência.
Este diretório guarda os números — e, mais importante, os **dados brutos** que os
produziram, para que qualquer conclusão possa ser recalculada sem reexecutar nada.

Alguns resultados contrariaram a hipótese inicial. Estão registrados assim mesmo:
uma medição que invalida o que se esperava é resultado, e esconder isso tornaria o
resto suspeito.

## Rodar uma nova rodada

```powershell
.\scripts\1-preparar-maquina.ps1
.\scripts\2-rodar-experimento.ps1 -Documento "CAMINHO\DO\DOCUMENTO.pdf"
```

O primeiro instala o que falta e valida o clone. O segundo executa todas as
estratégias, grava em `resultados/<maquina>/` e commita numa branch própria.

### Execução cega, de propósito

**Não consulte `resultados/` de outra máquina antes de rodar.** Saber o resultado
esperado enviesa a leitura de uma falha ("deve ser normal") e a decisão de insistir
numa rota lenta. A comparação acontece depois, na revisão.

### Por que cada máquina roda tudo

Comparar estratégias executadas em hardwares diferentes mediria **hardware**, não
estratégia. Cada máquina produz uma rodada completa e autocontida: dentro dela
comparam-se estratégias; entre máquinas, compara-se velocidade.

Isso rende de graça um teste de reprodutibilidade — as rotas determinísticas devem
dar resultado idêntico nas duas máquinas; as rotas por modelo podem não dar, e
divergência ali é achado sobre confiabilidade.

## Construir um gabarito para outro documento

O procedimento está descrito em
[../docs/adr/0009-avaliacao-como-ferramenta-de-produto.md](../docs/adr/0009-avaliacao-como-ferramenta-de-produto.md).
O resumo: extrair uma amostra, conferir à mão, medir, e **reservar um conjunto não
visto** — porque um gabarito gerado pelo próprio extrator mede aquela estratégia
contra si mesma.
