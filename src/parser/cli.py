"""Interface de linha de comando — todos os comandos do projeto.

    ambiente      o que esta máquina tem e o que falta
    extrair       roda um perfil e grava nos destinos
    comparar      compara estratégias rapidamente, sem gravar
    experimento   roda tudo e grava os resultados com procedência

`comparar` serve para iterar; `experimento` produz o resultado registrado que
uma máquina contribui para a comparação. Ambos existem porque as necessidades são
diferentes: um precisa ser rápido, o outro precisa ser rastreável.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from parser.perfil import Perfil, PerfilInvalido
from parser.pipeline import Pipeline
from parser.portas import FormatoNaoSuportado

__all__ = ["main"]

MODELO_RAPIDO = "qwen3:1.7b"
MODELO_TEXTO = "qwen3:4b"
MODELO_VISAO = "qwen3-vl:4b"

MODELOS_DO_EXPERIMENTO = (MODELO_RAPIDO, MODELO_TEXTO, MODELO_VISAO)

CAMPOS_DO_EXPERIMENTO = [
    "identificador",
    "energia_kcal",
    "proteina_g",
    "lipideos_g",
    "carboidrato_g",
    "fibra_g",
]


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


def _diagnosticar(opcoes: argparse.Namespace) -> int:
    """Examina um documento antes de extrair, e diz o que pode sabotar a leitura."""
    from parser.diagnostico import Severidade, diagnosticar, relatorio

    try:
        achados = diagnosticar(opcoes.documento)
    except FileNotFoundError as erro:
        print(f"{erro}", file=sys.stderr)
        return 2

    print(f"DIAGNÓSTICO — {Path(opcoes.documento).name}\n")
    print(relatorio(achados))

    graves = [a for a in achados if a.severidade is Severidade.BLOQUEIA]
    if graves:
        print(
            f"\n{len(graves)} achado(s) que exigem tratamento antes de confiar no "
            "resultado. Ignorá-los produz extração que roda sem erro e grava lixo."
        )
        return 1
    return 0


def _ambiente(opcoes: argparse.Namespace) -> int:
    """Relata o que esta máquina tem, e o que falta para o experimento."""
    from parser.experimento import Ambiente

    ambiente = Ambiente.levantar()
    print("AMBIENTE\n")
    print(f"  máquina     : {ambiente.maquina}")
    print(f"  sistema     : {ambiente.sistema}")
    print(f"  processador : {ambiente.processador}")
    print(f"  núcleos     : {ambiente.nucleos}")
    print(f"  memória     : {ambiente.ram_total_gb} GB ({ambiente.ram_livre_gb} GB livre)")
    print(f"  gpu         : {ambiente.gpu or 'nenhuma detectada'} {ambiente.vram or ''}")
    print(f"  python      : {ambiente.python}")

    print("\nMODELOS\n")
    if not ambiente.modelos:
        print("  servidor de inferência não respondeu, ou nenhum modelo baixado.")
        print("  As estratégias determinísticas não dependem disto.")
        return 1

    presentes = {m["nome"] for m in ambiente.modelos}
    for modelo in ambiente.modelos:
        print(f"  {modelo['nome']:24s} {modelo['tamanho_gb']:>5.1f} GB  ({modelo['digest']})")

    faltando = [m for m in MODELOS_DO_EXPERIMENTO if not any(p.startswith(m) for p in presentes)]
    if faltando:
        print("\n  faltando para o experimento:")
        for modelo in faltando:
            print(f"    ollama pull {modelo}")
        return 2

    if ambiente.ram_livre_gb and ambiente.ram_livre_gb < 6.0:
        print(
            f"\n  Atenção: {ambiente.ram_livre_gb} GB livres. Feche aplicações antes "
            "de rodar um modelo de 4B."
        )
    return 0


def _experimento(opcoes: argparse.Namespace) -> int:
    """Roda todas as estratégias no mesmo ambiente e grava com procedência."""
    from parser.concordancia import comparar_estrategias
    from parser.experimento import Experimento
    from parser.extratores.biblioteca import ExtratorBiblioteca
    from parser.extratores.linear import ExtratorLinear
    from parser.extratores.posicional import ExtratorPosicional
    from parser.fontes.pdf import FontePDF

    documento = Path(opcoes.documento)
    if not documento.exists():
        print(f"documento não encontrado: {documento}", file=sys.stderr)
        return 2

    try:
        perfil = Perfil.de_arquivo(opcoes.perfil)
        layout = perfil._montar_extrator()
    except PerfilInvalido as erro:
        print(f"perfil inválido: {erro}", file=sys.stderr)
        return 2

    paginas = _intervalo_do_perfil(perfil)
    fonte = FontePDF(paginas=paginas)
    experimento = Experimento(str(documento), opcoes.destino)
    ambiente = experimento.ambiente

    print(f"máquina: {ambiente.maquina}  |  {ambiente.processador}")
    print(f"páginas: {list(paginas) if paginas else 'todas'}\n")

    print("determinísticas:")
    for nome, extrator in (
        ("posicional", layout),
        ("linear", ExtratorLinear()),
        ("biblioteca", ExtratorBiblioteca(str(documento), paginas=paginas)),
    ):
        execucao = experimento.rodar(nome, fonte, extrator, parametros={"tipo": "deterministico"})
        estado = "falhou" if execucao.erro else f"{execucao.segundos:.1f}s"
        print(f"  {nome:14s} {estado}")

    if not opcoes.sem_modelos:
        from parser.extratores.vlm import ExtratorVLM
        from parser.ollama import ClienteOllama, ExtratorModelo

        print("\ncom modelo (lento em CPU — pode levar muito tempo):")
        for nome, modelo in (("llm-rapido", MODELO_RAPIDO), ("llm-texto", MODELO_TEXTO)):
            print(f"  {nome:14s} ...", end=" ", flush=True)
            execucao = experimento.rodar(
                nome,
                fonte,
                ExtratorModelo(
                    ClienteOllama(modelo=modelo, url=opcoes.url, timeout=opcoes.timeout),
                    CAMPOS_DO_EXPERIMENTO,
                ),
                parametros={"tipo": "llm", "modelo": modelo},
            )
            print("falhou" if execucao.erro else f"{execucao.segundos:.0f}s")

        print(f"  {'vlm':14s} ...", end=" ", flush=True)
        execucao = experimento.rodar(
            "vlm",
            fonte,
            ExtratorVLM(
                ClienteOllama(modelo=MODELO_VISAO, url=opcoes.url, timeout=opcoes.timeout),
                CAMPOS_DO_EXPERIMENTO,
                str(documento),
                dpi=opcoes.dpi,
            ),
            parametros={"tipo": "vlm", "modelo": MODELO_VISAO, "dpi": opcoes.dpi},
        )
        print("falhou" if execucao.erro else f"{execucao.segundos:.0f}s")

    print(f"\n{experimento.tabela()}")
    pasta = experimento.gravar()

    saidas = {e.estrategia: e.dados for e in experimento.execucoes if e.dados}
    if len(saidas) >= 2:
        print(f"\n{comparar_estrategias(saidas).relatorio()}")

    print(f"\nresultados em: {pasta}")
    print(
        "\nAcurácia — quem acertou mais — exige o gabarito conferido à mão. Os dados\n"
        "brutos ficam salvos, então ela é calculada depois sobre estes mesmos\n"
        "resultados, sem reexecutar."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parser",
        description="Extrai dados estruturados de documentos, validados contra schema.",
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    ambiente = comandos.add_parser(
        "ambiente", help="mostra o que esta máquina tem e o que falta"
    )
    ambiente.set_defaults(funcao=_ambiente)

    diagnostico = comandos.add_parser(
        "diagnosticar",
        help="examina um documento e aponta o que pode sabotar a extração",
    )
    diagnostico.add_argument("documento", help="arquivo a examinar")
    diagnostico.set_defaults(funcao=_diagnosticar)

    extrair = comandos.add_parser("extrair", help="roda um perfil e grava nos destinos")
    extrair.add_argument("perfil", type=Path, help="arquivo de perfil (JSON)")
    extrair.add_argument("--documento", help="sobrescreve o documento do perfil")
    extrair.set_defaults(funcao=_extrair)

    comparar = comandos.add_parser(
        "comparar", help="compara estratégias no mesmo documento (rápido, sem gravar)"
    )
    comparar.add_argument("perfil", type=Path, help="arquivo de perfil (JSON)")
    comparar.add_argument("--documento", help="sobrescreve o documento do perfil")
    comparar.set_defaults(funcao=_comparar)

    experimento = comandos.add_parser(
        "experimento",
        help="roda todas as estratégias e grava os resultados com procedência",
    )
    experimento.add_argument("--documento", required=True, help="PDF a processar")
    experimento.add_argument(
        "--perfil",
        type=Path,
        default=Path("perfis/nutricional.json"),
        help="perfil que define o layout e as páginas",
    )
    experimento.add_argument("--destino", type=Path, default=Path("resultados"))
    experimento.add_argument("--dpi", type=int, default=150)
    experimento.add_argument("--url", default="http://localhost:11434")
    experimento.add_argument("--timeout", type=float, default=3600.0)
    experimento.add_argument(
        "--sem-modelos", action="store_true", help="só as estratégias determinísticas"
    )
    experimento.set_defaults(funcao=_experimento)

    opcoes = parser.parse_args(argv)
    return opcoes.funcao(opcoes)


if __name__ == "__main__":
    raise SystemExit(main())
