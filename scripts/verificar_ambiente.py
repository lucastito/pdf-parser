"""Verifica se o ambiente suporta as estratégias baseadas em modelo.

Serve a dois propósitos:

1. **Falhar cedo, com mensagem clara** — melhor descobrir agora que o servidor
   não responde do que depois de baixar gigabytes.
2. **Capturar a procedência** — processador, memória, modelos e suas etiquetas
   exatas. Uma medição de tempo sem esse contexto é inútil semanas depois, e
   duas execuções em máquinas diferentes não podem ser confrontadas sem ele.

Ao rodar em uma máquina nova, é o primeiro comando.

Uso:
    python scripts/verificar_ambiente.py
    python scripts/verificar_ambiente.py --url http://outro-servidor:11434
    python scripts/verificar_ambiente.py --json
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

URL_PADRAO = "http://localhost:11434"

MODELOS_ESPERADOS = {
    "qwen3:1.7b": "iteração rápida",
    "qwen3:4b": "modelo de texto",
    "qwen3-vl:4b": "modelo de visão",
}

RAM_MINIMA_GB = 6.0
"""Abaixo disto um modelo de 4B quantizado não carrega com folga."""


def _memoria() -> dict:
    total = livre = None
    try:
        if platform.system() == "Windows":
            saida = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "$c=Get-CimInstance Win32_ComputerSystem;"
                    "$o=Get-CimInstance Win32_OperatingSystem;"
                    "Write-Output \"$($c.TotalPhysicalMemory) $($o.FreePhysicalMemory)\"",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            partes = saida.stdout.split()
            if len(partes) == 2:
                total = int(partes[0]) / 1024**3
                livre = int(partes[1]) / 1024**2
        else:
            info = Path("/proc/meminfo").read_text()
            linhas = dict(
                (linha.split(":")[0], linha.split()[1]) for linha in info.splitlines() if ":" in linha
            )
            total = int(linhas["MemTotal"]) / 1024**2
            livre = int(linhas.get("MemAvailable", linhas["MemFree"])) / 1024**2
    except Exception:
        pass
    return {"total_gb": total, "livre_gb": livre}


def _gpu() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        saida = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        linha = saida.stdout.strip().splitlines()[0]
        nome, memoria, driver = (p.strip() for p in linha.split(","))
        return {"nome": nome, "memoria": memoria, "driver": driver}
    except Exception:
        return None


def _modelos(url: str) -> tuple[list[dict] | None, str | None]:
    """Consulta os modelos disponíveis. Devolve (modelos, erro)."""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=10) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return dados.get("models", []), None
    except urllib.error.URLError as erro:
        return None, str(erro.reason if hasattr(erro, "reason") else erro)
    except Exception as erro:  # noqa: BLE001 - qualquer falha vira diagnóstico
        return None, str(erro)


def levantar(url: str) -> dict:
    memoria = _memoria()
    modelos, erro = _modelos(url)
    return {
        "sistema": platform.system(),
        "processador": platform.processor() or platform.machine(),
        "python": platform.python_version(),
        "memoria": memoria,
        "gpu": _gpu(),
        "servidor": {"url": url, "disponivel": modelos is not None, "erro": erro},
        "modelos": [
            {"nome": m.get("name"), "tamanho_gb": round(m.get("size", 0) / 1024**3, 1)}
            for m in (modelos or [])
        ],
    }


def relatar(ambiente: dict) -> int:
    print("AMBIENTE\n")
    print(f"  sistema      : {ambiente['sistema']}")
    print(f"  processador  : {ambiente['processador']}")
    print(f"  python       : {ambiente['python']}")

    memoria = ambiente["memoria"]
    if memoria["total_gb"]:
        print(
            f"  memória      : {memoria['total_gb']:.1f} GB total, "
            f"{memoria['livre_gb']:.1f} GB livre"
        )

    gpu = ambiente["gpu"]
    if gpu:
        print(f"  gpu          : {gpu['nome']} ({gpu['memoria']}, driver {gpu['driver']})")
    else:
        print("  gpu          : sem GPU dedicada detectada — os modelos rodarão em CPU")

    print("\nSERVIDOR DE INFERÊNCIA\n")
    servidor = ambiente["servidor"]
    if not servidor["disponivel"]:
        print(f"  {servidor['url']} — indisponível ({servidor['erro']})")
        print("\n  As estratégias baseadas em modelo não podem rodar.")
        print("  As estratégias determinísticas não dependem disto e continuam funcionando.")
        return 1

    print(f"  {servidor['url']} — respondendo")
    disponiveis = {m["nome"] for m in ambiente["modelos"]}
    if ambiente["modelos"]:
        print("\n  modelos presentes:")
        for modelo in ambiente["modelos"]:
            print(f"    {modelo['nome']:32s} {modelo['tamanho_gb']:>5.1f} GB")
    else:
        print("\n  nenhum modelo baixado")

    print("\nMODELOS DO EXPERIMENTO\n")
    faltando = []
    for nome, papel in MODELOS_ESPERADOS.items():
        # Etiqueta exata importa: `modelo` e `modelo:tag` podem ser modelos distintos.
        presente = nome in disponiveis or any(d.startswith(f"{nome}-") for d in disponiveis)
        marca = "presente" if presente else "FALTA"
        print(f"  {nome:20s} {papel:20s} {marca}")
        if not presente:
            faltando.append(nome)

    if faltando:
        print("\n  para baixar:")
        for nome in faltando:
            print(f"    ollama pull {nome}")

    livre = ambiente["memoria"].get("livre_gb")
    if livre and livre < RAM_MINIMA_GB:
        print(
            f"\n  Atenção: {livre:.1f} GB livres — abaixo dos {RAM_MINIMA_GB} GB "
            "recomendados. Feche aplicações antes de rodar um modelo de 4B."
        )

    return 0 if not faltando else 2


def main(argv: list[str] | None = None) -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--url", default=URL_PADRAO, help="endereço do servidor")
    argumentos.add_argument(
        "--json", action="store_true", help="saída em JSON, para registro de procedência"
    )
    opcoes = argumentos.parse_args(argv)

    ambiente = levantar(opcoes.url)
    if opcoes.json:
        print(json.dumps(ambiente, ensure_ascii=False, indent=2))
        return 0
    return relatar(ambiente)


if __name__ == "__main__":
    raise SystemExit(main())
