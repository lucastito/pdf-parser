"""Gera o material de conferência do golden set.

O arquivo produzido **não é gabarito ainda**: é uma proposta a ser conferida à mão,
valor por valor, contra o documento original. Gabarito gerado por máquina mediria o
extrator contra ele mesmo.

Reexecutar é seguro e recomendado sempre que a extração mudar: com `--verificar`, o
script compara com o arquivo existente e avisa se algo divergiu, em vez de sobrescrever
em silêncio. Isso protege o trabalho de conferência já feito.

Uso:
    python scripts/gerar_gabarito.py              # gera ou atualiza
    python scripts/gerar_gabarito.py --verificar  # só compara, não escreve
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from parser.extratores.posicional import ExtratorPosicional, LayoutTabela  # noqa: E402
from parser.fontes.pdf import FontePDF  # noqa: E402

PDF_PADRAO = Path(
    r"c:\Users\Lucas Tito\projetos\nutriflow\data\rag\sources\taco\raw\TACO.pdf"
)
DESTINO = RAIZ / "golden" / "taco-para-conferir.csv"

LAYOUT = LayoutTabela(
    x_rotulos=(110.0, 133.0),
    x_unidades=(133.0, 145.0),
    x_valores_min=145.0,
    y_identificadores_min=520.0,
    y_rotulo_max=520.0,
)

MACROS = {
    "Energia (kcal)": "energia_kcal",
    "Proteína (g)": "proteina_g",
    "Lipídeos (g)": "lipideos_g",
    "Carboidrato (g)": "carboidrato_g",
    "Fibra Alimentar (g)": "fibra_g",
}

PAGINAS = range(28, 35, 2)
LIMITE = 40


def campo_por_rotulo(campos: dict, alvo: str):
    """Casa o rótulo por conjunto de palavras, tolerando ordem e pontuação.

    O extrator monta o rótulo a partir do layout, e a ordem das palavras pode
    variar (`Fibra Alimentar` × `Alimentar Fibra`). Casar por conjunto evita que
    uma variação de ordem apareça como campo faltante.
    """
    palavras_alvo = set(re.findall(r"\w+", alvo.lower()))
    for nome, campo in campos.items():
        palavras = set(re.findall(r"\w+", nome.lower()))
        if palavras_alvo <= palavras or palavras <= palavras_alvo:
            return campo
    return None


def extrair(pdf: Path) -> list[dict]:
    documento = FontePDF(paginas=PAGINAS).carregar(str(pdf))
    registros = ExtratorPosicional(LAYOUT).extrair(documento)

    linhas = []
    for registro in registros:
        identificador = registro.campos.get("identificador")
        if not identificador or not identificador.valor:
            continue

        # Itens são numerados; cabeçalhos de seção não são.
        casamento = re.match(r"^(\d+)\s+(.*)$", identificador.valor)
        if not casamento:
            continue

        linha = {
            "numero": casamento.group(1),
            "descricao": casamento.group(2),
            "pagina_pdf": identificador.evidencia.pagina if identificador.evidencia else "",
        }
        for rotulo, coluna in MACROS.items():
            campo = campo_por_rotulo(registro.campos, rotulo)
            if campo is None or not campo.preenchido:
                linha[coluna] = ""
            elif campo.sentinela is not None:
                linha[coluna] = campo.sentinela.value
            else:
                linha[coluna] = campo.valor
            linha[f"{coluna}_ok"] = ""
        linhas.append(linha)

    return linhas[:LIMITE]


def colunas() -> list[str]:
    nomes = ["numero", "descricao", "pagina_pdf"]
    for coluna in MACROS.values():
        nomes += [coluna, f"{coluna}_ok"]
    return nomes


def divergencias(novas: list[dict], caminho: Path) -> list[str]:
    """Compara os valores extraídos com os do arquivo existente.

    As colunas de marcação (`*_ok`) são ignoradas: são do revisor, não da extração.
    """
    if not caminho.exists():
        return []

    antigas = list(csv.DictReader(caminho.open(encoding="utf-8")))
    if len(antigas) != len(novas):
        return [f"quantidade de linhas mudou: {len(antigas)} → {len(novas)}"]

    achados = []
    comparaveis = [c for c in colunas() if not c.endswith("_ok")]
    for antiga, nova in zip(antigas, novas):
        for coluna in comparaveis:
            antes, agora = str(antiga.get(coluna, "")), str(nova.get(coluna, ""))
            if antes != agora:
                achados.append(
                    f"item {nova['numero']} ({nova['descricao'][:30]}) "
                    f"{coluna}: {antes!r} → {agora!r}"
                )
    return achados


def conferencia_iniciada(caminho: Path) -> bool:
    if not caminho.exists():
        return False
    linhas = list(csv.DictReader(caminho.open(encoding="utf-8")))
    return any(
        linha.get(coluna, "").strip()
        for linha in linhas
        for coluna in colunas()
        if coluna.endswith("_ok")
    )


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--pdf", type=Path, default=PDF_PADRAO)
    argumentos.add_argument(
        "--verificar",
        action="store_true",
        help="apenas compara com o arquivo existente; não escreve",
    )
    opcoes = argumentos.parse_args()

    if not opcoes.pdf.exists():
        print(f"documento não encontrado: {opcoes.pdf}", file=sys.stderr)
        return 2

    linhas = extrair(opcoes.pdf)
    achados = divergencias(linhas, DESTINO)

    if achados:
        print(f"{len(achados)} divergência(s) em relação ao arquivo existente:")
        for achado in achados[:20]:
            print(f"  {achado}")
        if len(achados) > 20:
            print(f"  ... e mais {len(achados) - 20}")
    elif DESTINO.exists():
        print("nenhuma divergência: os valores extraídos continuam iguais")

    if opcoes.verificar:
        return 1 if achados else 0

    if achados and conferencia_iniciada(DESTINO):
        print(
            "\nA conferência já foi iniciada e os valores mudaram.\n"
            "Nada foi sobrescrito. Revise as divergências acima e, se estiverem\n"
            "corretas, apague o arquivo e gere de novo.",
            file=sys.stderr,
        )
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas())
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"\n{len(linhas)} itens escritos em {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
