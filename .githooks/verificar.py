"""Guarda de confidencialidade — verificação do conteúdo staged.

Substitui o encadeamento de `grep` que os hooks usavam. Motivo concreto: com
acentuação na lista de exceções, `grep -F -f` abortava neste ambiente (SIGABRT),
a saída vinha vazia e **nenhum termo era verificado**. Uma guarda que falha em
silêncio é pior que guarda nenhuma, porque passa confiança injustificada.

Aqui a comparação é feita em Python, com decodificação explícita: acento não
quebra nada, e qualquer falha inesperada bloqueia o commit em vez de liberá-lo.

Uso (chamado pelos hooks):
    python .githooks/verificar.py conteudo
    python .githooks/verificar.py mensagem <arquivo>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DENYLIST = RAIZ / ".githooks" / "denylist.txt"
ALLOWLIST = RAIZ / ".githooks" / "allowlist.txt"

VERMELHO = "\033[31m"
AMARELO = "\033[33m"
FIM = "\033[0m"


def _linhas(caminho: Path) -> list[str]:
    if not caminho.exists():
        return []
    return [
        linha.strip()
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def _coberta_por_excecao(linha: str, excecoes: list[str]) -> bool:
    """Uma linha coberta por exceção não é vazamento.

    Exemplo: `"Aveia, flocos, crua"` é nome de alimento; casa com um termo
    restrito por coincidência de substring, não por conteúdo sensível.
    """
    minuscula = linha.lower()
    return any(excecao.lower() in minuscula for excecao in excecoes)


def _achados(texto: str, termos: list[str], excecoes: list[str]) -> list[tuple[int, str, str]]:
    resultados = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if _coberta_por_excecao(linha, excecoes):
            continue
        minuscula = linha.lower()
        for termo in termos:
            if termo.lower() in minuscula:
                resultados.append((numero, termo, linha[:100]))
    return resultados


def _reportar(achados: list[tuple[int, str, str]], origem: str) -> int:
    if not achados:
        return 0

    print(f"{VERMELHO}\n=== COMMIT BLOQUEADO — termo restrito em {origem} ==={FIM}\n", file=sys.stderr)
    for numero, termo, linha in achados[:10]:
        # O termo é mascarado: o log do terminal não deve vazar o que a guarda protege.
        print(f"  linha {numero}: {termo[:3]}***  |  {linha}", file=sys.stderr)
    if len(achados) > 10:
        print(f"  ... e mais {len(achados) - 10}", file=sys.stderr)

    print(
        f"{VERMELHO}\nRemova o termo antes de commitar.{FIM}\n"
        "Material sob NDA vive em docs/_private/ ou CLAUDE.local.md (ambos ignorados).\n"
        "Se for falso positivo, acrescente a expressão a .githooks/allowlist.txt.\n",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: verificar.py conteudo | mensagem <arquivo>", file=sys.stderr)
        return 2

    termos = _linhas(DENYLIST)
    if not termos:
        print(
            f"{AMARELO}[guarda] denylist.txt ausente ou vazia — nada verificado.{FIM}",
            file=sys.stderr,
        )
        return 0

    excecoes = _linhas(ALLOWLIST)
    modo = argv[1]

    if modo == "mensagem":
        if len(argv) < 3:
            return 2
        arquivo = Path(argv[2])
        texto = arquivo.read_text(encoding="utf-8", errors="replace") if arquivo.exists() else ""
        return _reportar(_achados(texto, termos, excecoes), "mensagem de commit")

    diff = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    # Só linhas adicionadas: o que está sendo removido não é vazamento novo.
    adicionadas = "\n".join(
        linha for linha in diff.splitlines()
        if linha.startswith("+") and not linha.startswith("+++")
    )
    achados = _achados(adicionadas, termos, excecoes)

    nomes = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    achados += _achados(nomes, termos, excecoes)

    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    achados += _achados(branch, termos, excecoes)

    return _reportar(achados, "conteúdo, nome de arquivo ou branch")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as erro:  # noqa: BLE001
        # Falha inesperada bloqueia: liberar o commit sem ter verificado seria
        # exatamente o modo de falha que esta guarda existe para evitar.
        print(f"{VERMELHO}[guarda] erro ao verificar: {erro}{FIM}", file=sys.stderr)
        print("Commit bloqueado por precaução.", file=sys.stderr)
        raise SystemExit(1) from erro
