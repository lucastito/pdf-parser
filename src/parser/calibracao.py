"""Descoberta automática de layout de tabela.

Elimina o passo manual mais custoso da adoção. Sem isto, apontar o parser para um
documento novo exige alguém inspecionar coordenadas à mão para descobrir onde
ficam rótulos, unidades e valores — trabalho que não é retrabalho de código, mas é
onde a adoção emperra.

A descoberta é possível porque cada região tem **assinatura estatística distinta**,
verificada no documento-caso:

===============  =========================================================
Região           Assinatura
===============  =========================================================
unidades         quase todo token entre parênteses — `(g)`, `(mg)`, `(kcal)`
rótulos          texto sem dígito, imediatamente à esquerda das unidades
valores          alta proporção de tokens numéricos, repetida em muitas colunas
identificadores  texto longo concentrado numa faixa de Y distinta
===============  =========================================================

A assinatura das unidades é a mais confiável e serve de âncora: parênteses não
aparecem por acidente numa tabela numérica.

**Quando não encontrar estrutura, falha.** Devolver um layout plausível e errado
produziria extração que roda sem erro e grava lixo — o modo de falha que o projeto
existe para evitar.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parser.portas import Palavra

__all__ = [
    "CalibracaoFalhou",
    "Candidato",
    "calibrar",
    "calibrar_palavras",
    "descobrir_nomes_de_coluna",
    "descobrir_paginas_de_dados",
]

DISTANCIA_DE_ROTULO = 14.0
"""Até onde dois fragmentos ainda são o mesmo rótulo, em pontos.

Medido no documento-caso: `Carbo-` (y=221,0) e `idrato` (y=223,0) distam 2
pontos; `Fibra` (186,3) e `Alimentar` (178,5) distam 7,8. O rótulo seguinte
começa 30 pontos adiante. O valor separa os dois casos com folga.
"""

PASSO = 5.0
"""Granularidade da varredura de X, em pontos tipográficos."""

MIN_COLUNAS_DE_VALOR = 8
"""Menos colunas que isto não caracteriza tabela de muitos itens."""

PROPORCAO_NUMERICA_MINIMA_POR_COLUNA = 0.55
"""Fração de tokens numéricos que caracteriza faixa de valores.

Nome distinto de propósito de `PROPORCAO_NUMERICA_MINIMA_DA_PAGINA`
(`triagem.py`) — a semelhança dos nomes já causou dúvida se eram a mesma
constante duplicada. Não são: esta mede uma **coluna** isolada, dentro da
descoberta de geometria de tabela; aquela mede a **página inteira**, para
decidir `Classe.DADOS`. Escopos e valores calibrados separadamente.
"""


class CalibracaoFalhou(ValueError):
    """Não foi possível descobrir a estrutura com confiança."""


@dataclass
class Candidato:
    """Um layout descoberto, com o que sustenta cada decisão."""

    layout: dict[str, Any]
    confianca: float
    evidencias: list[str] = field(default_factory=list)

    def resumo(self) -> str:
        linhas = [f"confiança: {self.confianca:.0%}", ""]
        for chave, valor in self.layout.items():
            linhas.append(f"  {chave:26s} {valor}")
        if self.evidencias:
            linhas.append("\nComo foi decidido:")
            linhas += [f"  {e}" for e in self.evidencias]
        return "\n".join(linhas)


def _numerico(texto: str) -> bool:
    limpo = texto.strip()
    if limpo in ("Tr", "tr", "NA", "na", "*"):
        return True
    return (
        bool(limpo)
        and any(c.isdigit() for c in limpo)
        and all(c.isdigit() or c in ",.-" for c in limpo)
    )


def _unidade(texto: str) -> bool:
    limpo = texto.strip()
    return len(limpo) >= 3 and limpo.startswith("(") and limpo.endswith(")")


def descobrir_paginas_de_dados(caminho: str | Path, *, limite: int | None = None) -> list[int]:
    """Encontra as páginas que contêm tabela de dados, em numeração base 1.

    O critério é densidade numérica: página de dados tem muitos tokens numéricos
    distribuídos em muitas colunas. Metodologia e texto corrido não têm.
    """
    import fitz

    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

    documento = fitz.open(arquivo)
    try:
        encontradas = []
        total = documento.page_count if limite is None else min(limite, documento.page_count)
        for indice in range(total):
            palavras = documento[indice].get_text("words")
            if len(palavras) < 100:
                continue
            numericos = sum(1 for w in palavras if _numerico(w[4]))
            if numericos / len(palavras) >= 0.40:
                encontradas.append(indice + 1)
        return encontradas
    finally:
        documento.close()


def calibrar(caminho: str | Path, *, paginas: list[int] | None = None) -> Candidato:
    """Descobre o layout de tabela de um documento.

    Args:
        paginas: páginas a analisar, base 1. Omitido, descobre automaticamente.

    Levanta:
        CalibracaoFalhou: nenhuma estrutura reconhecível.
        FileNotFoundError: arquivo inexistente.
    """
    from parser.fontes.pdf import FontePDF

    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

    if paginas is None:
        paginas = descobrir_paginas_de_dados(arquivo, limite=60)
        if not paginas:
            raise CalibracaoFalhou(
                f"nenhuma página com densidade numérica de tabela em {arquivo.name}"
            )
        paginas = paginas[:2]

    import fitz

    documento = fitz.open(arquivo)
    try:
        total = documento.page_count
    finally:
        documento.close()

    for numero in paginas:
        if not 1 <= numero <= total:
            raise CalibracaoFalhou(f"página {numero} fora do documento (tem {total} páginas)")

    amostra: list[Palavra] = []
    for numero in paginas:
        pagina = FontePDF(paginas=range(numero - 1, numero)).carregar(str(arquivo)).paginas[0]
        amostra.extend(pagina.palavras)

    if not amostra:
        raise CalibracaoFalhou(f"páginas {paginas} não têm texto extraível")

    return _descobrir(amostra, paginas)


def calibrar_palavras(palavras: list[Palavra]) -> Candidato:
    """Descobre o layout a partir de palavras já extraídas, por qualquer meio.

    `calibrar()` lê a camada de texto nativa via `FontePDF`. Esta função não
    sabe — nem precisa saber — de onde as palavras vieram: a heurística de
    geometria opera sobre posição, não sobre a origem do texto. É o que
    permite a uma página **escaneada** se autocalibrar: o OCR já devolve
    `Palavra` com coordenada, na mesma forma que a extração nativa produz, e a
    mesma assinatura estatística (unidade entre parênteses como âncora) vale
    para as duas.

    Levanta:
        CalibracaoFalhou: nenhuma estrutura reconhecível — mesmo critério de
            `calibrar()`, propagado das mesmas funções internas.
    """
    if not palavras:
        raise CalibracaoFalhou("nenhuma palavra para calibrar")
    return _descobrir(palavras, paginas=[])


def _descobrir(palavras: list[Palavra], paginas: list[int]) -> Candidato:
    evidencias: list[str] = []

    x_unidades = _faixa_de_unidades(palavras, evidencias)
    x_valores_min = _inicio_dos_valores(palavras, x_unidades, evidencias)
    x_rotulos = _faixa_de_rotulos(palavras, x_unidades, evidencias)
    y_identificadores = _inicio_dos_identificadores(palavras, x_valores_min, evidencias)

    layout = {
        "x_rotulos": [round(x_rotulos[0], 1), round(x_rotulos[1], 1)],
        "x_unidades": [round(x_unidades[0], 1), round(x_unidades[1], 1)],
        "x_valores_min": round(x_valores_min, 1),
        "y_identificadores_min": round(y_identificadores, 1),
        "y_rotulo_max": round(y_identificadores, 1),
        "tolerancia_y": 6.0,
        "tolerancia_x": 6.0,
    }

    confianca = _avaliar(palavras, layout, evidencias)
    return Candidato(layout=layout, confianca=confianca, evidencias=evidencias)


def _faixa_de_unidades(palavras: list[Palavra], evidencias: list[str]) -> tuple[float, float]:
    """Âncora da calibração: parênteses não aparecem por acidente.

    A faixa de X onde os tokens entre parênteses se concentram é o eixo a partir do
    qual rótulos (à esquerda) e valores (à direita) são localizados.
    """
    unidades = [p for p in palavras if _unidade(p.texto)]
    if len(unidades) < 3:
        raise CalibracaoFalhou(
            f"apenas {len(unidades)} tokens entre parênteses — sem âncora de unidade. "
            "Este calibrador espera tabela cujas unidades apareçam como '(g)', '(mg)'."
        )

    xs = [p.x0 for p in unidades]
    agrupados = Counter(round(x / PASSO) * PASSO for x in xs)
    x_dominante, quantos = agrupados.most_common(1)[0]

    if quantos < 3:
        raise CalibracaoFalhou(
            "tokens de unidade dispersos, sem coluna dominante — layout não reconhecido"
        )

    na_coluna = [x for x in xs if abs(x - x_dominante) <= PASSO * 2]
    # Margem à esquerda apenas. Estender o limite superior invadiria a região de
    # valores: medido, um excesso de 2 pontos derrubou a acurácia de 100% para 77%,
    # porque a primeira coluna de valores passou a ser lida como unidade.
    inicio, fim = min(na_coluna) - PASSO, max(na_coluna) + PASSO

    evidencias.append(
        f"x_unidades [{inicio:.1f}, {fim:.1f}]: {quantos} tokens entre parênteses "
        f"concentrados em x≈{x_dominante:.0f} (de {len(unidades)} no total)"
    )
    return inicio, fim


def _inicio_dos_valores(
    palavras: list[Palavra], x_unidades: tuple[float, float], evidencias: list[str]
) -> float:
    """Primeira coluna à direita das unidades com alta densidade numérica."""
    por_coluna: dict[float, list[Palavra]] = defaultdict(list)
    for p in palavras:
        if p.x0 > x_unidades[1]:
            por_coluna[round(p.x0 / PASSO) * PASSO].append(p)

    numericas = [
        x
        for x, ps in sorted(por_coluna.items())
        if len(ps) >= 3
        and sum(1 for p in ps if _numerico(p.texto)) / len(ps)
        >= PROPORCAO_NUMERICA_MINIMA_POR_COLUNA
    ]

    if len(numericas) < MIN_COLUNAS_DE_VALOR:
        raise CalibracaoFalhou(
            f"apenas {len(numericas)} colunas com densidade numérica à direita das "
            f"unidades (mínimo {MIN_COLUNAS_DE_VALOR}) — não caracteriza tabela de itens"
        )

    # Margem à esquerda da primeira coluna: o limite é comparado com `x0`, e um
    # corte apertado descarta a primeira coluna inteira. Errar para a esquerda é
    # seguro — a faixa de unidades já delimita o outro lado.
    inicio = min(numericas) - PASSO * 3
    evidencias.append(
        f"x_valores_min {inicio:.1f}: {len(numericas)} colunas com "
        f"≥{PROPORCAO_NUMERICA_MINIMA_POR_COLUNA:.0%} de tokens numéricos, "
        f"a partir de x≈{min(numericas):.0f}"
    )
    return max(inicio, x_unidades[1])


def _faixa_de_rotulos(
    palavras: list[Palavra], x_unidades: tuple[float, float], evidencias: list[str]
) -> tuple[float, float]:
    """Texto sem dígito imediatamente à esquerda das unidades.

    O limite inferior exclui título e legenda, que ficam mais à esquerda: a busca
    para na primeira lacuna significativa.
    """
    candidatos = [p for p in palavras if p.x0 < x_unidades[0] and not _numerico(p.texto)]
    if not candidatos:
        raise CalibracaoFalhou("nenhum texto à esquerda das unidades — sem faixa de rótulos")

    colunas = sorted({round(p.x0 / PASSO) * PASSO for p in candidatos}, reverse=True)
    selecionadas = [colunas[0]]
    for anterior, atual in zip(colunas, colunas[1:]):
        if anterior - atual > PASSO * 4:  # lacuna: começou outra região
            break
        selecionadas.append(atual)

    # Margem à esquerda: rótulos de palavra longa começam antes da coluna dominante
    # (num caso medido, um rótulo hifenizado iniciava 5 pontos à esquerda dos
    # demais). Um corte apertado aqui derrubou a acurácia de 100% para 60% —
    # errar para a esquerda é seguro, porque a faixa de unidades limita o outro lado.
    inicio, fim = min(selecionadas) - PASSO, x_unidades[0]
    evidencias.append(
        f"x_rotulos [{inicio:.1f}, {fim:.1f}]: texto sem dígito em {len(selecionadas)} "
        f"colunas contíguas à esquerda das unidades, com margem de {PASSO:.0f} pt"
    )
    return inicio, fim


def _inicio_dos_identificadores(
    palavras: list[Palavra], x_valores_min: float, evidencias: list[str]
) -> float:
    """Faixa de Y onde ficam os nomes dos itens.

    Na região de valores, procura o Y a partir do qual predomina texto não numérico:
    é onde a tabela deixa de listar números e passa a nomear itens.
    """
    na_regiao = [p for p in palavras if p.x0 >= x_valores_min]
    if not na_regiao:
        raise CalibracaoFalhou("nenhuma palavra na região de valores")

    faixas: dict[float, list[Palavra]] = defaultdict(list)
    for p in na_regiao:
        faixas[round(p.y0 / 20) * 20].append(p)

    textuais = [
        y
        for y, ps in sorted(faixas.items())
        if len(ps) >= 3 and sum(1 for p in ps if not _numerico(p.texto)) / len(ps) > 0.7
    ]

    if not textuais:
        raise CalibracaoFalhou(
            "nenhuma faixa de Y predominantemente textual na região de valores — "
            "não foi possível localizar os nomes dos itens"
        )

    # O limite é o início do bloco textual contíguo mais baixo. Buscar de baixo
    # para cima e parar na primeira lacuna encontra o topo desse bloco, que é o
    # limite procurado — usar mediana ou o último Y cortaria os primeiros nomes.
    inicio = textuais[-1]
    for anterior, atual in zip(reversed(textuais), reversed(textuais[:-1])):
        if anterior - atual > 60:
            break
        inicio = atual

    # Recuo de uma faixa: o limite é comparado com `y0`, e o nome mais alto do
    # bloco ficaria de fora num corte exato.
    inicio -= 20

    evidencias.append(
        f"y_identificadores_min {inicio:.1f}: bloco textual contíguo mais baixo na "
        f"região de valores, entre {len(textuais)} faixas candidatas"
    )
    return inicio


def _avaliar(palavras: list[Palavra], layout: dict, evidencias: list[str]) -> float:
    """Confiança no layout, por verificação de consistência.

    Cada critério vale um quarto: unidades na faixa esperada, densidade numérica na
    região de valores, rótulos textuais, identificadores presentes.
    """
    pontos = 0.0

    unidades = [p for p in palavras if _unidade(p.texto)]
    # Comparação por sobreposição, não por `x0`: a unidade tem largura, e uma faixa
    # que a contenha parcialmente ainda a captura na extração.
    na_faixa = sum(
        1
        for p in unidades
        if p.x1 >= layout["x_unidades"][0] and p.x0 <= layout["x_unidades"][1]
    )
    if unidades and na_faixa / len(unidades) > 0.6:
        pontos += 0.25

    valores = [
        p
        for p in palavras
        if p.x0 >= layout["x_valores_min"] and p.y0 < layout["y_identificadores_min"]
    ]
    if valores and sum(1 for p in valores if _numerico(p.texto)) / len(valores) > 0.6:
        pontos += 0.25

    rotulos = [
        p
        for p in palavras
        if layout["x_rotulos"][0] <= p.x0 <= layout["x_rotulos"][1]
        and p.y0 < layout["y_identificadores_min"]
    ]
    if rotulos and sum(1 for p in rotulos if not _numerico(p.texto)) / len(rotulos) > 0.7:
        pontos += 0.25

    identificadores = [
        p
        for p in palavras
        if p.y0 >= layout["y_identificadores_min"] and p.x0 >= layout["x_valores_min"]
    ]
    if len(identificadores) >= 20:
        pontos += 0.25

    evidencias.append(
        f"confiança {pontos:.0%}: unidades={na_faixa}/{len(unidades)}, "
        f"tokens na região de valores={len(valores)}, rótulos={len(rotulos)}, "
        f"tokens de identificador={len(identificadores)}"
    )
    return pontos


def descobrir_nomes_de_coluna(
    caminho: str | Path, *, pagina: int, layout: dict[str, Any] | None = None
) -> list[str]:
    """Os nomes das colunas, na ordem em que aparecem no documento.

    É a peça que torna o prompt independente do documento. Hoje o modelo recebe a
    ordem das colunas porque **alguém escreveu** `campos_na_ordem` no perfil, à
    mão — o que dá 100% neste documento e não vale para nenhum outro.

    O problema não é qualidade, é comparabilidade: se cada documento tiver a
    ordem digitada por uma pessoa, a diferença medida entre estratégias inclui
    quem digitou. Descobrir pelo mesmo procedimento em todos torna o
    **procedimento** a constante (ADR-0023).

    Args:
        layout: as faixas já calibradas. Omitido, calibra a página pedida.

    Devolve lista **vazia** quando não há estrutura reconhecível — nunca nomes
    plausíveis. Nome inventado produziria um prompt que parece certo e alinha
    errado, que é o modo de falha silencioso que este projeto evita.

    ## Como funciona, e por que assim

    Os rótulos ficam numa faixa vertical estreita, à esquerda das unidades — a
    mesma que a calibração já localiza por geometria. Dentro dela, cada rótulo
    ocupa uma posição na coordenada perpendicular à leitura.

    Dois cuidados que vieram da medição, não da teoria:

    **Rótulo quebrado em fragmentos** (`Carbo-` + `idrato`, `Fibra` +
    `Alimentar`) é reunido por proximidade. Sem isso, uma coluna viraria duas e a
    ordem sairia errada.

    **A ordem segue o sentido da página.** No documento-caso, rotacionado, os
    rótulos empilham em `y` decrescente — a primeira coluna é a de maior `y`.
    Ordenar ingenuamente inverteria a tabela inteira.
    """
    from parser.fontes.pdf import FontePDF

    try:
        if layout is None:
            layout = calibrar(caminho, paginas=[pagina]).layout
        documento = FontePDF(paginas=[pagina - 1]).carregar(str(caminho))
    except (CalibracaoFalhou, FileNotFoundError, IndexError):
        return []

    if not documento.paginas:
        return []

    inicio, fim = layout["x_rotulos"]
    limite_y = layout["y_identificadores_min"]
    palavras = documento.paginas[0].palavras
    na_faixa = [
        palavra
        for palavra in palavras
        if inicio <= palavra.x0 <= fim
        and palavra.y0 < limite_y
        and not _numerico(palavra.texto)
    ]
    if not na_faixa:
        return []

    # Maior y primeiro: é o sentido de leitura da página rotacionada.
    na_faixa.sort(key=lambda p: -p.y0)

    grupos: list[list[Palavra]] = [[na_faixa[0]]]
    for anterior, atual in zip(na_faixa, na_faixa[1:]):
        if abs(anterior.y0 - atual.y0) <= DISTANCIA_DE_ROTULO:
            grupos[-1].append(atual)
        else:
            grupos.append([atual])

    # `Carbo-` + `idrato` vira `Carboidrato`; `Fibra` + `Alimentar` vira
    # `Fibra Alimentar`. O hífen no fim do fragmento é marca de quebra.
    #
    # Dentro do grupo a ordem é por **x**, não por y: os fragmentos de um rótulo
    # quebrado ficam lado a lado na horizontal, e a coordenada vertical entre
    # eles é praticamente igual — ordenar por ela devolveu `idrato Carbo-`.
    rotulos: list[tuple[float, str]] = []
    for grupo in grupos:
        texto = ""
        for palavra in sorted(grupo, key=lambda p: p.x0):
            fragmento = palavra.texto
            if texto.endswith("-"):
                texto = texto[:-1] + fragmento
            elif texto:
                texto = f"{texto} {fragmento}"
            else:
                texto = fragmento
        rotulos.append((max(p.y0 for p in grupo), texto.strip()))

    return _casar_com_unidades(rotulos, palavras, layout)


def _casar_com_unidades(
    rotulos: list[tuple[float, str]], palavras: list[Palavra], layout: dict[str, Any]
) -> list[str]:
    """Junta cada rótulo à sua unidade, e é a unidade que define a coluna.

    A distinção importa num caso que o documento-caso exibe: **`Energia` é um
    rótulo e duas colunas** — `(kcal)` e `(kJ)`. Contar rótulos daria 10 colunas
    onde há 11, e a ordem entregue ao modelo estaria errada a partir dali.

    As unidades são a âncora mais confiável da tabela (é o que sustenta a
    calibração inteira) e há **uma por coluna real**. Então elas comandam: cada
    unidade recebe o rótulo mais próximo acima dela.

    Sem unidades reconhecíveis, devolve os rótulos como estão — tabela sem
    unidade é caso legítimo, e inventar não ajudaria.
    """
    inicio, fim = layout["x_unidades"]
    limite_y = layout["y_identificadores_min"]
    unidades = [
        palavra
        for palavra in palavras
        if inicio <= palavra.x0 <= fim and palavra.y0 < limite_y and _unidade(palavra.texto)
    ]
    if not unidades:
        return [nome for _, nome in rotulos]

    unidades.sort(key=lambda p: -p.y0)
    nomes = []
    for unidade in unidades:
        # O rótulo da coluna é o mais próximo em y — no documento-caso ele fica
        # ligeiramente acima da unidade, mas a distância absoluta é o critério
        # robusto para as duas orientações.
        proximo = min(rotulos, key=lambda r: abs(r[0] - unidade.y0), default=(0.0, ""))
        nomes.append(f"{proximo[1]} {unidade.texto}".strip())
    return nomes
