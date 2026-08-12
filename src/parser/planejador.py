"""Decide, por página, qual rota de extração usar — sem estrutura declarada.

Este módulo existe para que o parser aceite qualquer PDF sem que um humano (ou
uma IA generalista, lendo o arquivo antes de rodar) declare `layout` ou
`campos_na_ordem` no perfil para cada documento novo. A agnosticidade não vem
de uma geometria "inteligente o bastante para qualquer tabela" — isso é
pesquisa sem fim. Vem do **roteamento**: tentar os caminhos baratos primeiro —
todos eles, parametrizados só pelo que a própria página revela — e escalar
honestamente para o modelo local quando nenhum reconhece a estrutura, nunca
fingir sucesso (ADR-0024).

Quatro níveis de custo, na ordem em que são tentados:

1. Sinal que o PDF já entrega de graça — camada de texto ausente, densidade
   numérica, imagem embutida (`parser.diagnostico`, `parser.triagem`).
2. Inspeção e extração determinística barata: geometria da página
   (`parser.calibracao`) descobre layout e ordem de colunas; posicional,
   pdfplumber, Camelot e PyMuPDF são **todos** tentados com esses mesmos
   parâmetros — nenhum deles tem nome de campo embutido. Quando mais de um
   produz resultado e concorda o bastante (`parser.concordancia`), o valor
   final vem de votar célula a célula entre eles (`parser.consolidacao`,
   ADR-0017) — nunca de escolher "a melhor" planilha e descartar o resto.
2b. Ainda determinístico, e o último antes do modelo: procurar valor por
   proximidade de rótulo (`parser.extratores.palavra_chave`), quando um
   vocabulário de campo esperado foi declarado. Serve à página sem tabela
   (`Classe.CONTEXTO`) e à página com tabela cujas ferramentas do nível 2
   não bastaram — casamento **exato** de rótulo, deliberadamente
   conservador; afrouxar isso é decisão de negócio, não deste módulo.
3. Rota de texto por modelo, com a ordem de colunas descoberta por geometria
   quando houver estrutura parcial (ADR-0023) — nunca digitada à mão. A rota
   de visão (VLM) entra de dois jeitos: como escalada final, quando nada
   determinístico bastou e a página não tem imagem; e como **complemento**,
   sempre que a página tiver imagem embutida — nesse caso ela roda em
   conjunto com o que já foi decidido para o resto da página, nunca no lugar
   dele, porque texto e imagem podem trazer informação diferente na mesma
   página.

O nível 2 **executa** ferramentas determinísticas baratas como parte de
decidir — isso não colide com "não executa" abaixo, que se refere só a rede e
modelo. Nenhuma chamada de rede ou de modelo acontece aqui: quando a decisão é
nível 3, este módulo decide que um modelo é necessário, mas quem de fato o
chama é `parser.fabrica` + `parser.lote`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parser.calibracao import CalibracaoFalhou, calibrar, descobrir_nomes_de_coluna
from parser.concordancia import comparar_estrategias
from parser.consolidacao import consolidar, materializar
from parser.diagnostico import caracterizar_pagina
from parser.portas import DocumentoCanonico, Pagina
from parser.triagem import Classe, triar
from parser.vocabulario import CampoEsperado

__all__ = [
    "CONFIANCA_MINIMA_DE_CALIBRACAO",
    "LIMIAR_DE_CONCORDANCIA",
    "DecisaoDeRota",
    "planejar",
]

CONFIANCA_MINIMA_DE_CALIBRACAO = 0.75
"""Abaixo disto, o layout descoberto por geometria não é usado como layout único."""

LIMIAR_DE_CONCORDANCIA = 0.80
"""Abaixo disto, duas rotas determinísticas discordam demais para confiar sem
segunda medição. Ponto de partida declarado, não calibrado — revisar quando
houver documentos variados o bastante para medir onde o corte deveria estar.
"""


@dataclass(frozen=True)
class DecisaoDeRota:
    """A rota escolhida para uma página, e por que — nunca sem motivo.

    `rota` é uma das strings que `parser.fabrica` sabe montar: ``"posicional"``,
    ``"pdfplumber"``, ``"camelot"``, ``"ocr"``, ``"llm"``, ``"vlm"`` — ou
    ``"nenhuma"`` quando a página não entra na extração (hoje só
    `Classe.DESCARTAVEL`: pouco conteúdo pra tentar algo).
    """

    pagina: int
    rota: str
    nivel: int
    motivo: str
    confianca: float | None = None
    layout: dict[str, Any] | None = None
    ordem_das_colunas: list[str] | None = None
    registros: list[dict] | None = None
    """Só preenchido quando `rota == "consolidado"`: o resultado já
    materializado da votação célula a célula (`parser.consolidacao`).
    Reexecutar as ferramentas determinísticas na hora de extrair de verdade
    duplicaria o trabalho — a votação já rodou aqui, e é determinística."""


def planejar(
    caminho: str | Path,
    documento: DocumentoCanonico,
    *,
    vocabulario: list[CampoEsperado] | None = None,
) -> list[DecisaoDeRota]:
    """Decide a rota de cada página de `documento`.

    `documento` já traz as páginas a considerar — quem chama decide o
    intervalo, como hoje. Reabre o arquivo uma vez via `fitz` para os sinais
    que `DocumentoCanonico` não carrega (rotação, orientação do texto),
    reaproveitado entre as páginas em vez de reaberto a cada uma.

    Args:
        vocabulario: campos esperados pelo destino (`parser.vocabulario`).
            Sem ele, o nível 2b (palavra-chave) não roda — não há o que
            procurar — e a escalada vai direto de determinístico para modelo.

    Uma página com imagem embutida ganha uma **segunda** decisão — visão
    (`vlm`), complementar à rota principal — sempre que a principal não for
    já `vlm`. Nunca substitui: texto e imagem podem trazer informação
    diferente na mesma página, e escolher só uma arriscaria nunca olhar a
    outra. É por isso que o retorno pode ter mais de uma decisão para o
    mesmo número de página.
    """
    import fitz

    arquivo = Path(caminho)
    aberto = fitz.open(arquivo)
    try:
        decisoes: list[DecisaoDeRota] = []
        for pagina in documento.paginas:
            achados = {a.codigo for a in caracterizar_pagina(aberto, pagina.numero)}
            primaria = _planejar_pagina(caminho, aberto, pagina, vocabulario, achados)
            decisoes.append(primaria)
            if primaria.rota != "vlm" and "imagem-embutida" in achados:
                decisoes.append(
                    DecisaoDeRota(
                        pagina=pagina.numero,
                        rota="vlm",
                        nivel=3,
                        motivo=(
                            "imagem embutida — leitura visual complementar à "
                            "rota principal desta página"
                        ),
                    )
                )
        return decisoes
    finally:
        aberto.close()


def _planejar_pagina(
    caminho: str | Path,
    aberto,
    pagina: Pagina,
    vocabulario: list[CampoEsperado] | None,
    achados: set[str],
) -> DecisaoDeRota:
    numero = pagina.numero

    # Nível 1, primeiro de tudo: sem camada de texto, a densidade numérica que
    # a triagem mede não significa nada (zero palavras é zero de qualquer
    # jeito) — checar isso antes evita que uma página escaneada seja descartada
    # como "sem conteúdo" em vez de roteada para reconhecimento óptico.
    if "sem-camada-de-texto" in achados:
        return DecisaoDeRota(
            pagina=numero,
            rota="ocr",
            nivel=1,
            motivo="sem camada de texto — reconhecimento óptico necessário",
        )

    resultado_triagem = triar(pagina)

    if resultado_triagem.classe is Classe.DESCARTAVEL:
        return DecisaoDeRota(
            pagina=numero,
            rota="nenhuma",
            nivel=0,
            motivo=f"triagem: {resultado_triagem.motivo}",
        )

    if resultado_triagem.classe is Classe.CONTEXTO:
        # Texto real, mas não é tabela densa — as ferramentas de tabela do
        # nível 2 não têm o que reconhecer aqui, então não se tenta
        # calibração nem descoberta de coluna. Ainda vale o nível 2b: o
        # parágrafo pode citar exatamente o valor que o schema pede.
        decisao = _tentar_palavra_chave(pagina, vocabulario)
        if decisao is not None:
            return decisao
        return DecisaoDeRota(
            pagina=numero,
            rota="llm",
            nivel=3,
            motivo=f"triagem: {resultado_triagem.motivo} — sem tabela, prompt genérico",
        )

    # A partir daqui: Classe.DADOS, com camada de texto — nível 2.
    candidato = None
    motivo_calibracao: str | None = None
    try:
        candidato = calibrar(caminho, paginas=[numero])
    except CalibracaoFalhou as erro:
        motivo_calibracao = str(erro)

    # Ordem de colunas: descoberta uma vez, reaproveitada por pdfplumber,
    # Camelot e (se precisar escalar) pelo prompt do modelo — nunca declarada
    # à mão em lugar nenhum destes usos (ADR-0023).
    colunas = (
        descobrir_nomes_de_coluna(
            caminho, pagina=numero, layout=candidato.layout if candidato else None
        )
        or None
    )

    resultados = _tentar_deterministicos(caminho, numero, pagina, candidato, colunas)
    decisao = _decidir_entre_deterministicos(numero, resultados, candidato, colunas)
    if decisao is not None:
        return decisao

    # Nível 2b: as ferramentas de tabela não bastaram, mas ainda é
    # determinístico tentar achar valor por rótulo antes do modelo.
    decisao = _tentar_palavra_chave(pagina, vocabulario)
    if decisao is not None:
        return decisao

    # Nível 3: nada determinístico bastou, sozinho ou em concordância.
    if resultados:
        motivo = (
            f"rotas determinísticas divergiram acima do limiar "
            f"({', '.join(sorted(resultados))})"
        )
    elif candidato is not None:
        motivo = f"confiança insuficiente ({candidato.confianca:.0%})"
    else:
        motivo = f"geometria não reconheceu estrutura ({motivo_calibracao})"

    return DecisaoDeRota(
        pagina=numero,
        rota="llm",
        nivel=3,
        motivo=motivo,
        confianca=candidato.confianca if candidato else None,
        ordem_das_colunas=colunas,
    )


def _tentar_deterministicos(
    caminho: str | Path,
    numero: int,
    pagina: Pagina,
    candidato,
    colunas: list[str] | None,
) -> dict[str, list]:
    """Roda as três rotas determinísticas com os parâmetros já descobertos.

    Nenhuma delas recebe nome de campo próprio: `posicional` usa o layout que
    a geometria achou (só se confiante o bastante para ser um layout
    plausível); `pdfplumber`/`camelot` recebem a mesma ordem de colunas que o
    prompt do modelo receberia, ou nenhuma — nesse caso leem pelo cabeçalho
    que a própria ferramenta detectar. Uma rota que falhar ou não achar nada
    simplesmente não entra no dicionário devolvido; não é erro, é resultado.
    """
    from parser.extratores.camelot_ import ExtratorCamelot
    from parser.extratores.pdfplumber_ import ExtratorPdfplumber
    from parser.extratores.posicional import ExtratorPosicional
    from parser.extratores.pymupdf_ import ExtratorPymupdf

    resultados: dict[str, list] = {}

    if candidato is not None and candidato.confianca >= CONFIANCA_MINIMA_DE_CALIBRACAO:
        try:
            layout = _layout_tabela(candidato.layout)
            documento_pagina = DocumentoCanonico(
                identificador="_planejamento", paginas=[pagina]
            )
            registros = ExtratorPosicional(layout).extrair(documento_pagina)
            if registros:
                resultados["posicional"] = registros
        except Exception:  # noqa: BLE001 — rota descartada, não erro do planejamento
            pass

    documento_vazio = DocumentoCanonico(identificador="_planejamento", paginas=[])
    intervalo = range(numero - 1, numero)
    for nome, Classe_ in (
        ("pdfplumber", ExtratorPdfplumber),
        ("camelot", ExtratorCamelot),
    ):
        try:
            extrator = Classe_(str(caminho), paginas=intervalo, campos=colunas)
            registros = extrator.extrair(documento_vazio)
            if registros:
                resultados[nome] = registros
        except Exception:  # noqa: BLE001 — idem
            pass

    # PyMuPDF não aceita ordem de coluna — sempre lê pelo cabeçalho que o
    # próprio detector encontrar. Zero configuração, mas por isso mesmo não
    # garante o campo "identificador" que a concordância usa para casar item
    # entre rotas; entra na conta do mesmo jeito, e a ausência de item comum
    # (quando só ferramentas baseadas em cabeçalho concorrem) já escala
    # honestamente em vez de fingir concordância.
    try:
        extrator = ExtratorPymupdf(str(caminho), paginas=intervalo)
        registros = extrator.extrair(documento_vazio)
        if registros:
            resultados["pymupdf"] = registros
    except Exception:  # noqa: BLE001 — idem
        pass

    return resultados


def _tentar_palavra_chave(
    pagina: Pagina, vocabulario: list[CampoEsperado] | None
) -> DecisaoDeRota | None:
    """Nível 2b: acha valor por proximidade de rótulo, sem tabela nenhuma.

    Só roda se um vocabulário foi declarado — sem ele não há nome de campo
    para procurar, e o núcleo permanece agnóstico. Casamento é exato
    (`parser.extratores.palavra_chave`, deliberadamente conservador); página
    sem achado não é erro, só significa que este nível não bastou.
    """
    if not vocabulario:
        return None

    from parser.extratores.palavra_chave import ExtratorPorPalavraChave

    documento_pagina = DocumentoCanonico(identificador="_planejamento", paginas=[pagina])
    registros = ExtratorPorPalavraChave(vocabulario).extrair(documento_pagina)
    if not registros:
        return None

    achados = sorted(n for n in registros[0].campos if n != "identificador")
    return DecisaoDeRota(
        pagina=pagina.numero,
        rota="palavra_chave",
        nivel=2,
        motivo=f"achou {len(achados)} campo(s) por palavra-chave: {', '.join(achados)}",
    )


def _decidir_entre_deterministicos(
    numero: int, resultados: dict[str, list], candidato, colunas: list[str] | None
) -> DecisaoDeRota | None:
    """Decide a partir do que as rotas determinísticas encontraram — ou não decide.

    Devolve `None` quando nenhuma rota achou nada, ou quando mais de uma achou
    mas discordou demais: nos dois casos, quem chamou escala para o nível 3.
    """
    if not resultados:
        return None

    if len(resultados) == 1:
        (nome,) = resultados
        return DecisaoDeRota(
            pagina=numero,
            rota=nome,
            nivel=2,
            motivo=f"{nome}: única rota determinística com resultado nesta página",
            confianca=candidato.confianca if (candidato and nome == "posicional") else None,
            layout=candidato.layout if (candidato and nome == "posicional") else None,
            ordem_das_colunas=colunas if nome != "posicional" else None,
        )

    saidas = {
        nome: [_serializar(r) for r in registros] for nome, registros in resultados.items()
    }
    concordancia = comparar_estrategias(saidas)

    if not concordancia.itens_comuns or concordancia.taxa < LIMIAR_DE_CONCORDANCIA:
        return None

    # Mais de uma rota concordou o bastante: em vez de escolher "a melhor"
    # planilha e descartar o resto, vota célula a célula (ADR-0017) — onde
    # concordam, a confiança sobe; onde divergem, o valor entra marcado.
    votacao = consolidar(saidas)
    registros_consolidados = materializar(votacao, fonte="_planejamento")
    motivo = (
        f"consolidação célula a célula entre {', '.join(sorted(resultados))} "
        f"({concordancia.taxa:.0%} em {concordancia.itens_comuns} item(ns) comum(ns))"
    )
    return DecisaoDeRota(
        pagina=numero,
        rota="consolidado",
        nivel=2,
        motivo=motivo,
        registros=[r.model_dump(mode="json") for r in registros_consolidados],
    )


def _serializar(registro) -> dict:
    return registro.model_dump(mode="json")


def _layout_tabela(dados: dict):
    from parser.extratores.posicional import LayoutTabela

    return LayoutTabela(
        x_rotulos=tuple(dados["x_rotulos"]),
        x_unidades=tuple(dados["x_unidades"]),
        x_valores_min=dados["x_valores_min"],
        y_identificadores_min=dados["y_identificadores_min"],
        tolerancia_y=dados.get("tolerancia_y", 6.0),
        tolerancia_x=dados.get("tolerancia_x", 6.0),
        y_rotulo_max=dados.get("y_rotulo_max"),
        distancia_rotulo_max=dados.get("distancia_rotulo_max", 40.0),
    )
