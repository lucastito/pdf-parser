"""Interface de linha de comando.

Quatro comandos bastam para operar, e a ordem entre eles é a ordem natural de
adoção de um documento novo:

    ambiente      esta máquina tem o que é necessário?
    diagnosticar  este documento tem algo que sabota a leitura?
    calibrar      qual o layout deste documento?
    ingerir       processa a pasta, consolida, lista o que precisa de atenção

Mais três, para quem quer número antes de confiar:

    avaliar       acurácia contra um gabarito próprio
    comparar      estratégias entre si, no mesmo documento
    experimento   roda tudo e grava os dados brutos, com procedência

Os três não têm dado embutido: o gabarito é sempre informado por quem usa.

`comparar` imprime e esquece; `experimento` grava, porque a acurácia é calculada
depois sobre os mesmos dados, sem reexecutar — e porque uma rodada que ninguém
consegue reproduzir não sustenta decisão nenhuma.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from parser.configuracao import ConfiguracaoInvalida, carregar_perfil

__all__ = ["main"]

MODELOS_DO_EXPERIMENTO = ("qwen3:1.7b", "qwen3:4b", "qwen3-vl:4b")
"""Modelos que os comandos de comparação esperam encontrar, se usados."""

RAM_LIVRE_RECOMENDADA_GB = 6.0
"""Abaixo disto, um modelo de 4 bilhões de parâmetros não carrega com folga."""


def _perfil(caminho: Path | None):
    """Carrega o perfil, ou devolve None se não foi informado."""
    if not caminho:
        return None
    return carregar_perfil(caminho)


def _ambiente(opcoes: argparse.Namespace) -> int:
    """Relata o que esta máquina oferece, e o que falta."""
    from parser.procedencia import Ambiente

    ambiente = Ambiente.levantar()
    print("AMBIENTE\n")
    print(f"  máquina     : {ambiente.maquina}")
    print(f"  sistema     : {ambiente.sistema}")
    print(f"  processador : {ambiente.processador}")
    print(f"  núcleos     : {ambiente.nucleos}")
    print(f"  memória     : {ambiente.ram_total_gb} GB ({ambiente.ram_livre_gb} GB livre)")
    print(f"  gpu         : {ambiente.gpu or 'nenhuma detectada'} {ambiente.vram or ''}")
    print(f"  python      : {ambiente.python}")

    print("\nSERVIDOR DE INFERÊNCIA\n")
    if not ambiente.modelos:
        print("  não respondeu, ou nenhum modelo disponível.")
        print("  As rotas determinísticas não dependem disto e continuam funcionando.")
        return 1

    presentes = {m["nome"] for m in ambiente.modelos}
    for modelo in ambiente.modelos:
        print(f"  {modelo['nome']:24s} {modelo['tamanho_gb']:>5.1f} GB  ({modelo['digest']})")

    faltando = [
        m for m in MODELOS_DO_EXPERIMENTO if not any(p.startswith(m) for p in presentes)
    ]
    if faltando:
        print("\n  para baixar:")
        for modelo in faltando:
            print(f"    ollama pull {modelo}")

    livre = ambiente.ram_livre_gb
    if livre and livre < RAM_LIVRE_RECOMENDADA_GB:
        print(
            f"\n  Atenção: {livre} GB livres, abaixo dos {RAM_LIVRE_RECOMENDADA_GB} "
            "recomendados. Feche aplicações antes de usar um modelo grande."
        )
    return 0


def _diagnosticar(opcoes: argparse.Namespace) -> int:
    """Aponta o que, no documento, pode sabotar a leitura."""
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
            f"\n{len(graves)} achado(s) a tratar antes de confiar no resultado. "
            "Ignorá-los produz extração que roda sem erro e grava lixo."
        )
        return 1
    return 0


def _calibrar(opcoes: argparse.Namespace) -> int:
    """Descobre o layout de tabela de um documento."""
    import json

    from parser.calibracao import CalibracaoFalhou, calibrar, descobrir_paginas_de_dados

    try:
        paginas = opcoes.paginas or descobrir_paginas_de_dados(opcoes.documento, limite=60)[:2]
        if not paginas:
            print(
                "nenhuma página com densidade de tabela. Informe --paginas.", file=sys.stderr
            )
            return 1
        resultado = calibrar(opcoes.documento, paginas=paginas)
    except FileNotFoundError as erro:
        print(f"{erro}", file=sys.stderr)
        return 2
    except CalibracaoFalhou as erro:
        print(f"calibração falhou: {erro}", file=sys.stderr)
        print(
            "\nFalhar é o comportamento correto: um layout inventado produziria "
            "extração que roda sem erro e grava lixo.",
            file=sys.stderr,
        )
        return 1

    print(f"CALIBRAÇÃO — {Path(opcoes.documento).name} (páginas {paginas})\n")
    print(resultado.resumo())

    if opcoes.json:
        print("\nRecorte para o perfil:\n")
        print(json.dumps({"rotas": {"posicional": {"layout": resultado.layout}}}, indent=2))

    if resultado.confianca < 0.75:
        print(
            f"\nConfiança de {resultado.confianca:.0%} é baixa. Confira alguns valores "
            "à mão antes de usar este layout."
        )
        return 1
    return 0


def _ingerir(opcoes: argparse.Namespace) -> int:
    """Processa uma pasta de documentos e consolida numa saída única."""
    from parser.esquema import EsquemaInvalido, SaidaInvalida
    from parser.lote import ingerir
    from parser.mapeamento import MapeamentoInvalido
    from parser.unidades import UnidadeInvalida

    try:
        perfil = _perfil(opcoes.perfil)
    except ConfiguracaoInvalida as erro:
        print(f"perfil inválido: {erro}", file=sys.stderr)
        return 2

    esperados = opcoes.campos or (list(perfil.mapeamento) if perfil else None)

    try:
        resultado = ingerir(
            opcoes.entrada,
            saida=opcoes.saida,
            perfil=perfil,
            campos_esperados=esperados,
            calibrar_por_arquivo=not opcoes.sem_calibrar,
        )
    except FileNotFoundError as erro:
        print(f"{erro}", file=sys.stderr)
        return 2
    except (MapeamentoInvalido, UnidadeInvalida, EsquemaInvalido) as erro:
        # Verificado antes do laço: o erro é do perfil, igual para todos os
        # arquivos. Nenhum documento foi processado, então não há perda a relatar.
        print(f"perfil inconsistente: {erro}", file=sys.stderr)
        print(
            "\nNenhum documento foi processado. Corrija o perfil e rode de novo.",
            file=sys.stderr,
        )
        return 2
    except SaidaInvalida as erro:
        # Nada foi gravado: a validação roda antes da escrita, de propósito.
        # Dado inválido que chega ao destino já contaminou o consumidor.
        print(f"saída rejeitada pelo esquema do perfil:\n{erro}", file=sys.stderr)
        print(
            "\nNada foi gravado. Corrija o esquema em 'esquema' no perfil, ou o "
            "mapeamento que produz as colunas.",
            file=sys.stderr,
        )
        return 2

    print(resultado.resumo())

    if opcoes.saida:
        saida = Path(opcoes.saida)
        print(f"\ngravado    : {saida}")
        print(f"             {saida.with_suffix('.log').name}")
        if resultado.falhas:
            print(f"             {saida.with_suffix('.erros.json').name}")
        if resultado.pendencias:
            print(f"             {saida.with_suffix('.pendencias.json').name}")

    if resultado.pendencias:
        print(
            f"\n{len(resultado.pendencias)} campo(s) que nenhum documento trouxe — "
            "é o que precisa de atenção humana."
        )

    # Falha parcial tem código próprio: quem automatiza precisa distinguir
    # "tudo certo" de "saiu resultado, mas com perdas".
    if resultado.falhas and resultado.processados:
        return 3
    if resultado.falhas:
        return 1
    return 0


def _avaliar(opcoes: argparse.Namespace) -> int:
    """Mede a acurácia da extração contra um gabarito conferido à mão."""
    from parser.fabrica import montar_extrator
    from parser.gabarito import Gabarito, GabaritoInvalido, medir_acuracia
    from parser.mapeamento import Mapeamento

    try:
        perfil = _perfil(opcoes.perfil)
        if perfil is None:
            print("informe --perfil", file=sys.stderr)
            return 2
        gabarito = Gabarito.de_arquivo(opcoes.gabarito, gerado_por=opcoes.gerado_por)
    except (ConfiguracaoInvalida, GabaritoInvalido) as erro:
        print(f"{erro}", file=sys.stderr)
        return 2

    documento = opcoes.documento or perfil.documento
    if not documento:
        print("informe --documento ou 'documento' no perfil", file=sys.stderr)
        return 2

    if not gabarito.completo:
        print(
            f"Atenção: {gabarito.conferidos} de {gabarito.total} valores conferidos. "
            "Os não conferidos entram na medição como se estivessem corretos."
        )

    from parser.fontes.pdf import FontePDF
    from parser.pipeline import Pipeline

    fonte = FontePDF(paginas=perfil.intervalo_de_paginas())
    mapeamento = Mapeamento(perfil.mapeamento) if perfil.mapeamento else None

    rotas = opcoes.rotas or [r for r in perfil.rotas if r not in ("llm", "vlm")]
    print(f"AVALIAÇÃO — {Path(documento).name}")
    print(f"gabarito: {gabarito.total} valores, {len(gabarito.itens)} itens\n")
    print(f"{'estratégia':16s} {'acurácia':>9s} {'itens':>6s}  piores campos")
    print("-" * 70)

    houve_erro = False
    for nome in rotas:
        try:
            extrator = montar_extrator(perfil, nome)
            registros = Pipeline(fonte, extrator, []).executar(documento).extraidos
            if mapeamento:
                registros = mapeamento.aplicar_todos(registros)
            resultado = medir_acuracia(nome, registros, gabarito, tolerancia=perfil.tolerancia)
            piores = ", ".join(f"{c}={t:.0%}" for c, t in resultado.piores_campos(3))
            marca = "  (gerou o gabarito)" if nome == gabarito.gerado_por else ""
            print(f"{nome:16s} {resultado.acuracia:8.1%} {len(registros):6d}  {piores}{marca}")
        except Exception as erro:  # noqa: BLE001 — relatar é o ponto
            print(f"{nome:16s} {'falhou':>9s}         {type(erro).__name__}: {erro}")
            houve_erro = True

    if gabarito.gerado_por:
        print(
            f"\nA acurácia de {gabarito.gerado_por!r} é tautológica: essa estratégia "
            "gerou o material que foi conferido, e acerta por construção. Para medi-la "
            "de forma independente, use um conjunto de reserva transcrito às cegas."
        )
    return 1 if houve_erro else 0


def _comparar(opcoes: argparse.Namespace) -> int:
    """Compara estratégias entre si, sem gabarito.

    Mede concordância: quanto as estratégias produzem o mesmo valor. É sinal útil —
    duas abordagens independentes chegando ao mesmo número provavelmente leram certo
    — mas não é prova. Estratégias podem errar igual.
    """
    from parser.concordancia import comparar_estrategias
    from parser.fabrica import montar_todas
    from parser.fontes.pdf import FontePDF
    from parser.pipeline import Pipeline

    try:
        perfil = _perfil(opcoes.perfil)
        if perfil is None:
            print("informe --perfil", file=sys.stderr)
            return 2
    except ConfiguracaoInvalida as erro:
        print(f"perfil inválido: {erro}", file=sys.stderr)
        return 2

    documento = opcoes.documento or perfil.documento
    if not documento:
        print("informe --documento ou 'documento' no perfil", file=sys.stderr)
        return 2

    fonte = FontePDF(paginas=perfil.intervalo_de_paginas())
    extratores = montar_todas(perfil, incluir_modelos=opcoes.com_modelos)

    print(f"documento: {Path(documento).name}\n")
    cabecalho = f"{'estratégia':16s} {'registros':>10s} {'campos':>8s} {'tempo':>9s}"
    print(cabecalho)
    print("-" * len(cabecalho))

    saidas = {}
    for nome, extrator in extratores.items():
        try:
            resultado = Pipeline(fonte, extrator, []).executar(documento)
            campos = sum(len(r.campos) for r in resultado.extraidos)
            print(
                f"{nome:16s} {resultado.registros:10d} {campos:8d} {resultado.segundos:8.2f}s"
            )
            if resultado.extraidos:
                saidas[nome] = [r.model_dump(mode="json") for r in resultado.extraidos]
        except Exception as erro:  # noqa: BLE001
            print(f"{nome:16s} {'falhou':>10s}           {type(erro).__name__}")

    if len(saidas) >= 2:
        print(f"\n{comparar_estrategias(saidas).relatorio()}")
    return 0


def _experimentar(opcoes: argparse.Namespace) -> int:
    """Roda todas as estratégias e grava os dados brutos com procedência.

    É o comando que o script de execução em outra máquina chama. Diferente de
    `comparar`, que só imprime, este **grava em disco** — porque a acurácia é
    calculada depois, sobre os mesmos dados, sem reexecutar nada.

    A trava de medição impede que duas rodadas disputem o mesmo processador: sem
    ela, os tempos das duas ficam inflados e nenhuma é comparável com nada.
    """
    from parser.fabrica import montar_todas
    from parser.fontes.pdf import FontePDF
    from parser.medicao import MedicaoEmAndamento, travar
    from parser.procedencia import Experimento

    try:
        perfil = _perfil(opcoes.perfil)
    except ConfiguracaoInvalida as erro:
        print(f"perfil inválido: {erro}", file=sys.stderr)
        return 2

    documento = opcoes.documento or (perfil.documento if perfil else None)
    if not documento:
        print("informe --documento ou 'documento' no perfil", file=sys.stderr)
        return 2
    if not Path(documento).exists():
        print(f"documento não encontrado: {documento}", file=sys.stderr)
        return 2
    if perfil is None:
        print("informe --perfil: sem ele não há rotas a executar", file=sys.stderr)
        return 2

    # Sobreposições da linha de comando entram no perfil antes da montagem, para
    # que o valor efetivo seja o mesmo que vai gravado na procedência. Aplicar
    # depois deixaria o registro dizendo uma coisa e a execução fazendo outra.
    for rota in perfil.rotas.values():
        if opcoes.dpi and rota.dpi:
            rota.dpi = opcoes.dpi
        if opcoes.timeout:
            rota.timeout = opcoes.timeout

    destino = Path(opcoes.destino)
    try:
        with travar(destino / ".medicao-em-andamento", descricao="experimento"):
            fonte = FontePDF(paginas=perfil.intervalo_de_paginas())
            extratores = montar_todas(perfil, incluir_modelos=not opcoes.sem_modelos)
            if not extratores:
                print("nenhuma estratégia montou — nada a medir", file=sys.stderr)
                return 1

            experimento = Experimento(documento, destino)
            print(f"EXPERIMENTO — {Path(documento).name}")
            print(f"máquina: {experimento.ambiente.maquina}\n")

            for nome, extrator in extratores.items():
                print(f"  {nome} ...", flush=True)
                execucao = experimento.rodar(
                    nome,
                    fonte,
                    extrator,
                    parametros={"dpi": perfil.rota(nome).dpi} if nome in perfil.rotas else {},
                )
                if execucao.erro:
                    print(f"    falhou: {execucao.erro}")
                else:
                    print(
                        f"    {execucao.registros} registro(s) em " f"{execucao.segundos:.1f}s"
                    )

            pasta = experimento.gravar()
    except MedicaoEmAndamento as erro:
        print(f"{erro}", file=sys.stderr)
        return 2

    print(f"\ngravado em {pasta}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parser",
        description="Extrai dados estruturados de documentos, validados contra schema.",
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    ambiente = comandos.add_parser("ambiente", help="o que esta máquina oferece")
    ambiente.set_defaults(funcao=_ambiente)

    diagnostico = comandos.add_parser(
        "diagnosticar", help="aponta o que pode sabotar a leitura de um documento"
    )
    diagnostico.add_argument("documento")
    diagnostico.set_defaults(funcao=_diagnosticar)

    calibracao = comandos.add_parser(
        "calibrar", help="descobre o layout de tabela de um documento"
    )
    calibracao.add_argument("documento")
    calibracao.add_argument("--paginas", nargs="*", type=int, help="páginas (base 1)")
    calibracao.add_argument("--json", action="store_true", help="recorte para o perfil")
    calibracao.set_defaults(funcao=_calibrar)

    lote = comandos.add_parser(
        "ingerir", help="processa uma pasta de documentos e consolida a saída"
    )
    lote.add_argument("entrada", help="pasta ou arquivo")
    lote.add_argument("--saida", help="caminho do CSV consolidado")
    lote.add_argument("--perfil", type=Path)
    lote.add_argument("--campos", nargs="*", help="campos que o destino exige")
    lote.add_argument(
        "--sem-calibrar",
        action="store_true",
        help="usa o layout do perfil para todos, sem descobrir por arquivo",
    )
    lote.set_defaults(funcao=_ingerir)

    avaliacao = comandos.add_parser(
        "avaliar", help="mede acurácia contra um gabarito conferido à mão"
    )
    avaliacao.add_argument("gabarito", help="CSV com os valores corretos")
    avaliacao.add_argument("--perfil", type=Path, required=True)
    avaliacao.add_argument("--documento")
    avaliacao.add_argument("--rotas", nargs="*", help="estratégias a avaliar")
    avaliacao.add_argument(
        "--gerado-por",
        help="estratégia que gerou o material conferido, se aplicável — a acurácia "
        "dela é tautológica e o relatório declara isso",
    )
    avaliacao.set_defaults(funcao=_avaliar)

    comparacao = comandos.add_parser(
        "comparar", help="compara estratégias entre si, sem gabarito"
    )
    comparacao.add_argument("--perfil", type=Path, required=True)
    comparacao.add_argument("--documento")
    comparacao.add_argument(
        "--com-modelos", action="store_true", help="inclui as rotas por modelo (lentas)"
    )
    comparacao.set_defaults(funcao=_comparar)

    experimento = comandos.add_parser(
        "experimento",
        help="roda todas as estratégias e grava os dados brutos com procedência",
    )
    experimento.add_argument("--perfil", type=Path, required=True)
    experimento.add_argument("--documento")
    experimento.add_argument(
        "--destino",
        default="experimentos/resultados",
        help="onde gravar a rodada, numa pasta por máquina",
    )
    experimento.add_argument(
        "--sem-modelos", action="store_true", help="pula as rotas por modelo (lentas)"
    )
    experimento.add_argument(
        "--dpi",
        type=int,
        help="sobrepõe a resolução das rotas que renderizam imagem. É variável de "
        "experimento: fica registrada com o resultado",
    )
    experimento.add_argument(
        "--timeout",
        type=float,
        help="limite por chamada ao modelo, em segundos",
    )
    experimento.set_defaults(funcao=_experimentar)

    opcoes = parser.parse_args(argv)
    return opcoes.funcao(opcoes)


if __name__ == "__main__":
    raise SystemExit(main())
