# Documentos do experimento

As entradas usadas nas medições. Ficam versionados para que **toda máquina meça o
mesmo arquivo** — sem isso, uma diferença de resultado entre máquinas pode ser do
documento, não do hardware nem da estratégia, e não haveria como saber qual.

| Arquivo | Origem | Impressão digital (sha256) |
|---|---|---|
| `TACO.pdf` | NEPA/UNICAMP, 4ª ed. revisada, Campinas, 2011 | `2002aec5615b5b1395aaa8fa675635bbb7f712c33f278af5e332f1cac8f108c8` |

## Por que a impressão digital

Uma rodada que não diz **qual** arquivo leu não é reproduzível. O `sha256` é
verificado pela suíte: se o arquivo for trocado ou corrompido, o teste acusa antes
de alguém gastar horas medindo o documento errado.

Para conferir à mão:

```powershell
Get-FileHash experimentos\documentos\TACO.pdf -Algorithm SHA256
```

## Licença

**Tabela Brasileira de Composição de Alimentos (TACO)** — NEPA/UNICAMP, 4ª edição
ampliada e revisada, Campinas, 2011.

A obra permite reprodução total ou parcial **desde que citada a fonte**, e é por
isso que o arquivo pode ser versionado aqui.

**Documento cuja licença não permita redistribuição não entra neste diretório**,
mesmo quando disponível na máquina de quem executa. Nesse caso, o caminho é passado
por `--documento` e o arquivo fica fora do repositório.

## Acrescentar um documento novo

1. Confirme a licença. Sem permissão explícita de redistribuição, não entra.
2. Copie para esta pasta e calcule o `sha256`.
3. Acrescente a linha na tabela acima e o registro em `tests/test_documentos.py`.
4. Crie o perfil correspondente em `perfis/`, com as páginas e o layout.

O passo 3 não é burocracia: é o que impede uma troca silenciosa de arquivo
invalidar uma comparação entre máquinas.
