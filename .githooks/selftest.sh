#!/bin/sh
# Verifica que os hooks de confidencialidade bloqueiam o que devem bloquear.
# Roda num repositorio temporario descartavel — nao toca no repo real.

set -u

HOOK_DIR=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
PASS=0
FAIL=0

copiar_hooks() {
    cp "$HOOK_DIR/pre-commit" "$HOOK_DIR/commit-msg" "$HOOK_DIR/verificar.py" .githooks/
    chmod +x .githooks/pre-commit .githooks/commit-msg
}

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL+1)); }

cd "$TMP" || exit 1
git init -q .
git config user.email t@t.t
git config user.name t
mkdir -p .githooks
copiar_hooks
git config core.hooksPath .githooks

printf '\nGuarda de confidencialidade — self-test\n\n'

# --- Sem denylist: deve passar (falha aberta, por design) ---
echo "conteudo qualquer" > a.txt
git add a.txt
if git commit -q -m "primeiro" 2>/dev/null; then
    ok "sem denylist.txt, commit normal passa"
else
    bad "sem denylist.txt, commit normal deveria passar"
fi

# --- Com denylist ---
printf '# comentario ignorado\nsegredoacme\nprodutoxyz\n' > .githooks/denylist.txt

# 1. Commit limpo passa
echo "texto inocente sobre parsing de tabelas" > b.txt
git add b.txt
if git commit -q -m "docs: nota neutra" 2>/dev/null; then
    ok "commit sem termo restrito passa"
else
    bad "commit limpo foi bloqueado indevidamente"
fi

# 2. Termo no conteudo bloqueia
echo "isto menciona segredoacme no meio da linha" > c.txt
git add c.txt
if git commit -q -m "docs: teste" 2>/dev/null; then
    bad "termo no CONTEUDO nao foi bloqueado"
else
    ok "termo no conteudo bloqueia"
fi
git reset -q

# 3. Case-insensitive
echo "agora com SegredoAcme capitalizado" > d.txt
git add d.txt
if git commit -q -m "docs: teste" 2>/dev/null; then
    bad "termo capitalizado nao foi bloqueado"
else
    ok "deteccao e case-insensitive"
fi
git reset -q

# 4. Termo no NOME do arquivo bloqueia
echo "conteudo limpo" > "nota-produtoxyz.md"
git add "nota-produtoxyz.md"
if git commit -q -m "docs: teste" 2>/dev/null; then
    bad "termo no NOME DE ARQUIVO nao foi bloqueado"
else
    ok "termo em nome de arquivo bloqueia"
fi
git reset -q
rm -f "nota-produtoxyz.md"

# 5. Termo na MENSAGEM de commit bloqueia
echo "conteudo limpo" > e.txt
git add e.txt
if git commit -q -m "feat: integra com segredoacme" 2>/dev/null; then
    bad "termo na MENSAGEM nao foi bloqueado"
else
    ok "termo na mensagem de commit bloqueia"
fi
git reset -q

# 6. Arquivo ignorado nao dispara (fica fora do diff)
printf 'privado.md\n' > .gitignore
echo "segredoacme aqui dentro" > privado.md
git add .gitignore
if git commit -q -m "chore: ignore" 2>/dev/null; then
    ok "arquivo ignorado com termo nao bloqueia commit"
else
    bad "arquivo ignorado bloqueou indevidamente"
fi

# 7. Excecao libera falso positivo SEM desativar a guarda.
#    Regressao real: uma versao anterior filtrava com 'grep -F -f', que abortava
#    com acentuacao na lista e deixava passar TUDO, silenciosamente.
printf 'flocos, crua\nmanutenção terceirizada\n' > .githooks/allowlist.txt

echo "Aveia, flocos, crua" > f.txt
git add f.txt
if git commit -q -m "docs: nome de alimento" 2>/dev/null; then
    ok "excecao libera falso positivo"
else
    bad "excecao nao liberou falso positivo"
fi
git reset -q

# 8. E, com a excecao ativa, um vazamento REAL continua bloqueado.
echo "isto menciona segredoacme de verdade" > g.txt
git add g.txt
if git commit -q -m "docs: teste" 2>/dev/null; then
    bad "com allowlist ativa, vazamento real NAO foi bloqueado"
else
    ok "com allowlist ativa, vazamento real continua bloqueado"
fi
git reset -q

printf '\n  %d passaram, %d falharam\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
