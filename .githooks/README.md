# Hooks

Guarda que impede material sob NDA de entrar no histórico do git.

## Instalação

```sh
git config core.hooksPath .githooks
```

Necessário uma vez por clone — `core.hooksPath` é config local, não viaja no repositório.

## Como funciona

`pre-commit` verifica conteúdo staged, nomes de arquivo e nome do branch.
`commit-msg` verifica a mensagem de commit.

Ambos leem os termos de `.githooks/denylist.txt`, **um por linha**. Esse arquivo
**não é versionado** — ele contém exatamente aquilo que não pode vazar, então
versioná-lo derrotaria o propósito. Crie-o localmente:

```sh
cat > .githooks/denylist.txt <<'EOF'
# um termo por linha; comparação é case-insensitive
termo-um
termo-dois
EOF
```

Sem `denylist.txt`, os hooks avisam e deixam passar — falha aberta, de propósito:
um hook que quebra todo commit num clone novo seria desabilitado no primeiro dia.
A proteção real de conteúdo é o `.gitignore`; os hooks são a segunda camada.

## Teste

```sh
.githooks/selftest.sh
```

## Limites

- `--no-verify` contorna os hooks. Não use neste repositório.
- Só inspeciona o que está staged; arquivos ignorados nunca chegam ao diff.
- Comparação é substring case-insensitive, não busca semântica: uma paráfrase
  descrevendo o material sem usar os termos passa. O julgamento continua sendo seu.
- `core.hooksPath` é configuração **local**: não viaja no clone e não roda em CI.
  Em máquina nova, configure antes do primeiro commit.

A denylist cobre nomes próprios **e vocabulário setorial**, porque um domínio
identifica por dedução mesmo sem nome citado. Espere falsos positivos — eles são
o preço da margem de segurança. Quando um termo legítimo for bloqueado, reescreva
a frase; editar a lista deve ser exceção pensada, não reflexo.
