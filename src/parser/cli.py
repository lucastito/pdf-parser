"""Interface de linha de comando.

Dois modos, correspondendo aos dois usos do projeto:

``extrair``   roda um perfil sobre um documento e grava nos destinos.
``comparar``  roda várias estratégias sobre o mesmo documento e mostra a matriz.

O segundo é a razão de o projeto existir: permitir afirmar, com número, que uma
abordagem é melhor que outra para um documento específico.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from parser.perfil import Perfil, PerfilInvalido
from parser.pipeline import Pipeline
from parser.portas import FormatoNaoSuportado

__all__ = ["main"]


def _extrair(opcoes: argparse.Namespace) -> int:
    try:
        perfil = Perfil.de_arquivo(opcoes.perfil)
        pipeline = perfil.montar()
    except PerfilInvalido as erro:
        print(f"perfil inválido: {erro}", file=sys.stderr)
        return 2

    documento = opcoes.documento or perfil.documento
    if not documento:
        print(
            "informe o documento (argumento --documento ou campo 'documento' no perfil)",
            file=sys.stderr,
        )
        return 2

    try:
        resultado = pipeline.executar(documento)
    except FormatoNaoSuportado as erro:
        print(f"formato não suportado: {erro}", file=sys.stderr)
        return 3
    except FileNotFoundError as erro:
        print(f"{erro}", file=sys.stderr)
        return 2

    print(resultado.resumo())
    if perfil.destinos:
        for destino in perfil.destinos:
            print(f"gravado    : {destino.get('caminho')}")
    return 0


def _comparar(opcoes: argparse.Namespace) -> int:
    """Roda várias estratégias sobre o mesmo documento e tabula o resultado."""
    from parser.extratores.biblioteca import ExtratorBiblioteca
    from parser.extratores.linear import ExtratorLinear
    from parser.fontes.pdf import FontePDF

    try:
        perfil = Perfil.de_arquivo(opcoes.perfil)
    except PerfilInvalido as erro:
        print(f"perfil inválido: {erro}", file=sys.stderr)
        return 2

    documento = opcoes.documento or perfil.documento
    if not documento:
        print("informe o documento", file=sys.stderr)
        return 2

    paginas = _intervalo_do_perfil(perfil)
    fonte = FontePDF(paginas=paginas)

    estratégias = {
        "posicional": perfil._montar_extrator(),
        "linear (piso)": ExtratorLinear(),
        "biblioteca pronta": ExtratorBiblioteca(documento, paginas=paginas),
    }

    print(f"documento: {Path(documento).name}\n")
    cabecalho = f"{'estratégia':22s} {'registros':>10s} {'campos':>8s} {'cobertura':>10s} {'tempo':>9s}"
    print(cabecalho)
    print("-" * len(cabecalho))

    for nome, extrator in estratégias.items():
        try:
            resultado = Pipeline(fonte, extrator, []).executar(documento)
        except Exception as erro:  # noqa: BLE001 - relatar falha é o ponto
            print(f"{nome:22s} {'falhou':>10s}  {type(erro).__name__}")
            continue

        campos = sum(len(r.campos) for r in resultado.extraidos)
        cobertura = (
            sum(r.cobertura for r in resultado.extraidos) / len(resultado.extraidos)
            if resultado.extraidos
            else 0.0
        )
        print(
            f"{nome:22s} {resultado.registros:10d} {campos:8d} "
            f"{cobertura:9.0%} {resultado.segundos:8.2f}s"
        )

    print(
        "\nEstes números medem cobertura e volume, não acurácia."
        "\nCobertura alta com valores errados é pior que cobertura baixa —"
        "\na acurácia exige o gabarito conferido à mão."
    )
    return 0


def _intervalo_do_perfil(perfil: Perfil) -> range | None:
    paginas = perfil.fonte.get("paginas")
    if not paginas:
        return None
    return range(*paginas) if isinstance(paginas, list) else paginas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parser",
        description="Extrai dados estruturados de documentos, validados contra schema.",
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    extrair = comandos.add_parser("extrair", help="roda um perfil e grava nos destinos")
    extrair.add_argument("perfil", type=Path, help="arquivo de perfil (JSON)")
    extrair.add_argument("--documento", help="sobrescreve o documento do perfil")
    extrair.set_defaults(funcao=_extrair)

    comparar = comandos.add_parser(
        "comparar", help="compara estratégias de extração no mesmo documento"
    )
    comparar.add_argument("perfil", type=Path, help="arquivo de perfil (JSON)")
    comparar.add_argument("--documento", help="sobrescreve o documento do perfil")
    comparar.set_defaults(funcao=_comparar)

    opcoes = parser.parse_args(argv)
    return opcoes.funcao(opcoes)


if __name__ == "__main__":
    raise SystemExit(main())
