"""Monta estratégias de extração a partir de um perfil declarativo.

É o único lugar do projeto que sabe qual nome de rota corresponde a qual classe.
Concentrar isso aqui tem uma consequência prática: adicionar uma estratégia nova é
registrá-la nesta tabela e escrever a classe — nada mais no projeto muda.

O perfil não sabe o que é uma classe Python, e o extrator não sabe o que é um
arquivo de configuração. Esta camada traduz entre os dois.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from parser.configuracao import ConfiguracaoInvalida, Perfil, Rota, carregar_prompt
from parser.extratores.posicional import ExtratorPosicional, LayoutTabela
from parser.portas import DocumentoCanonico, Extrator

if TYPE_CHECKING:
    from parser.planejador import DecisaoDeRota
    from parser.vocabulario import CampoEsperado

__all__ = [
    "ROTAS",
    "RotaNaoConfigurada",
    "montar_extrator",
    "montar_extrator_para_decisao",
    "montar_todas",
]


class RotaNaoConfigurada(Exception):
    """A rota que o roteador decidiu (`parser.planejador`) exige configuração
    que não foi informada — por exemplo, nível 3 sem nenhum modelo declarado.

    Diferente de `ConfiguracaoInvalida`: aqui a ausência é esperada (nem todo
    lote tem modelo configurado) e quem chama trata como pendência para
    revisão humana, não como erro de operador.
    """


def _posicional(perfil: Perfil, rota: Rota) -> Extrator:
    if not rota.layout:
        raise ConfiguracaoInvalida(
            "rota 'posicional' exige 'layout' com as faixas de coordenadas"
        )
    return ExtratorPosicional(_layout(rota.layout))


def _linear(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.extratores.linear import ExtratorLinear

    return ExtratorLinear()


def _biblioteca(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.extratores.pymupdf_ import ExtratorPymupdf

    return ExtratorPymupdf(_documento(perfil), paginas=perfil.intervalo_de_paginas())


def _pdfplumber(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.extratores.pdfplumber_ import ExtratorPdfplumber

    return ExtratorPdfplumber(
        _documento(perfil),
        paginas=perfil.intervalo_de_paginas(),
        campos=rota.campos_na_ordem or perfil.campos_na_ordem or None,
        desrotacionar=rota.extras.get("desrotacionar", True),
    )


def _camelot(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.extratores.camelot_ import ExtratorCamelot

    return ExtratorCamelot(
        _documento(perfil),
        paginas=perfil.intervalo_de_paginas(),
        modo=rota.extras.get("modo", "stream"),
        campos=rota.campos_na_ordem or perfil.campos_na_ordem or None,
    )


def _ocr(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.extratores.ocr import ExtratorOCR

    posicional = perfil.rotas.get("posicional")
    return ExtratorOCR(
        _documento(perfil),
        layout=_layout(posicional.layout) if posicional and posicional.layout else None,
        paginas=perfil.intervalo_de_paginas(),
        dpi=rota.dpi,
        idioma=rota.extras.get("idioma", "eng"),
    )


def _degrau_maximo(rota: Rota):
    """Lê o degrau de saída mais livre permitido, declarado no perfil.

    Fixá-lo é o que torna uma bateria de execuções comparável entre si (SPEC
    §4.4). Omitido, a rota desce quanto for preciso para obter saída — o que
    maximiza a chance de o modelo pequeno produzir algo, ao custo de rodadas
    potencialmente em degraus diferentes.
    """
    from parser.configuracao import ConfiguracaoInvalida
    from parser.degraus import Degrau

    declarado = rota.extras.get("degrau_maximo")
    if not declarado:
        return None

    try:
        return Degrau(declarado)
    except ValueError as erro:
        conhecidos = ", ".join(d.value for d in Degrau)
        raise ConfiguracaoInvalida(
            f"rota {rota.nome!r}: degrau_maximo {declarado!r} desconhecido. "
            f"Conhecidos: {conhecidos}"
        ) from erro


def _llm(
    perfil: Perfil, rota: Rota, *, vocabulario: list[CampoEsperado] | None = None
) -> Extrator:
    from parser.ollama import ExtratorModelo

    contexto = rota.extras.get("contexto")
    return ExtratorModelo(
        _cliente(rota),
        _campos(rota, vocabulario),
        instrucao=_instrucao(rota),
        vocabulario=vocabulario,
        # A ordem dos cabeçalhos corrige o deslocamento de coluna, e o perfil
        # já a declarava para as rotas determinísticas — faltava chegar aqui.
        ordem_das_colunas=rota.campos_na_ordem or perfil.campos_na_ordem or None,
        degrau_maximo=_degrau_maximo(rota),
        raciocinar=bool(rota.extras.get("raciocinar", False)),
        tokens_maximos=rota.extras.get("tokens_maximos"),
        # Sem 'contexto' declarado no perfil, mede a entrada de cada chamada e
        # calcula o teto a partir dela (ADR-0018) — nunca herda o padrão do
        # servidor. Com 'contexto' declarado, vale ele, sem medição: é o que
        # torna uma bateria de experimento comparável entre máquinas.
        contexto=contexto,
        contexto_automatico=contexto is None,
        nativo=rota.extras.get("nativo"),
        semente=rota.extras.get("semente"),
        temperatura=float(rota.extras.get("temperatura", 0.0)),
    )


def _vlm(
    perfil: Perfil, rota: Rota, *, vocabulario: list[CampoEsperado] | None = None
) -> Extrator:
    from parser.extratores.vlm import ExtratorVLM

    contexto = rota.extras.get("contexto")
    return ExtratorVLM(
        _cliente(rota),
        _campos(rota, vocabulario),
        _documento(perfil),
        instrucao=_instrucao(rota),
        vocabulario=vocabulario,
        ordem_das_colunas=rota.campos_na_ordem or perfil.campos_na_ordem or None,
        dpi=rota.dpi,
        degrau_maximo=_degrau_maximo(rota),
        raciocinar=bool(rota.extras.get("raciocinar", False)),
        tokens_maximos=rota.extras.get("tokens_maximos"),
        contexto=contexto,
        contexto_automatico=contexto is None,
        nativo=rota.extras.get("nativo"),
        semente=rota.extras.get("semente"),
        temperatura=float(rota.extras.get("temperatura", 0.0)),
    )


ROTAS: dict[str, Callable[[Perfil, Rota], Extrator]] = {
    "posicional": _posicional,
    "linear": _linear,
    "pymupdf": _biblioteca,
    "pdfplumber": _pdfplumber,
    "camelot": _camelot,
    "ocr": _ocr,
    "llm": _llm,
    "llm-menor": _llm,
    "vlm": _vlm,
    "vlm-menor": _vlm,
}
"""Nome da rota → como montá-la.

As variantes `-menor` usam o **mesmo** extrator: o que muda é só o modelo
declarado no perfil. Existem porque o denominador comum é um **par** de tamanhos
da mesma família (ADR-0014), e o experimento itera rotas — sem nome próprio, o
segundo tamanho não teria como ser executado nem registrado à parte.
"""
"""Nome da rota no perfil → função que a monta.

Estratégia nova entra aqui. Nada mais no projeto precisa saber dela.
"""


def montar_extrator(perfil: Perfil, nome: str) -> Extrator:
    """Monta uma estratégia. Não contacta servidor nem lê o documento."""
    if nome not in ROTAS:
        raise ConfiguracaoInvalida(
            f"rota {nome!r} não tem implementação. Conhecidas: {', '.join(sorted(ROTAS))}"
        )
    return ROTAS[nome](perfil, perfil.rota(nome))


def montar_todas(perfil: Perfil, *, incluir_modelos: bool = True) -> dict[str, Extrator]:
    """Monta todas as rotas declaradas no perfil.

    Uma rota que falhe na montagem é **omitida com o motivo**, não interrompe as
    demais: uma dependência ausente numa máquina não deve impedir a execução do
    resto do experimento.
    """
    montadas: dict[str, Extrator] = {}
    for nome in perfil.rotas:
        # Compara pela função de montagem, não pelo nome: "vlm-menor" e
        # "llm-menor" também usam modelo (ROTAS.get() as mapeia para a mesma
        # `_llm`/`_vlm`), e um filtro por string exata os deixava passar —
        # quem pedisse `--sem-modelos` ainda carregava um modelo sem aviso.
        if not incluir_modelos and ROTAS.get(nome) in (_llm, _vlm):
            continue
        try:
            montadas[nome] = montar_extrator(perfil, nome)
        except Exception as erro:  # noqa: BLE001 — a falha é dado, não interrupção
            print(f"  rota {nome!r} não montou: {type(erro).__name__}: {erro}")
    return montadas


def montar_extrator_para_decisao(
    decisao: DecisaoDeRota,
    caminho: str | Path,
    perfil: Perfil | None,
    *,
    vocabulario: list | None = None,
) -> Extrator:
    """Monta o extrator para uma página, a partir do que o roteador decidiu.

    Ao contrário de `montar_extrator`, o layout e a ordem de colunas vêm da
    própria decisão — descobertos por `parser.planejador`, nunca digitados no
    perfil. O perfil só entra para as rotas de modelo, e só pelo que é
    configuração legítima de negócio (qual modelo chamar, com que prompt) —
    nunca por como o documento está estruturado.

    Args:
        vocabulario: os mesmos campos esperados que o roteador usou para
            decidir `rota="palavra_chave"` — precisa ser o mesmo, para que a
            extração real reproduza exatamente o que a decisão encontrou.

    Levanta:
        RotaNaoConfigurada: a rota decidida exige configuração ausente — nível
            3 (`llm`/`vlm`) sem essa rota declarada no perfil, ou
            `palavra_chave` sem o vocabulário que a decidiu. OCR não levanta
            isto: sem layout declarado, autocalibra por página, e devolve
            resultado vazio para a página em que isso falhar, em vez de erro.
    """
    if decisao.rota == "posicional":
        return ExtratorPosicional(_layout(decisao.layout))

    if decisao.rota == "consolidado":
        if decisao.registros is None:
            raise ConfiguracaoInvalida(
                f"página {decisao.pagina}: decisão 'consolidado' sem registros anexados"
            )
        return _ExtratorPreComputado(decisao.registros)

    if decisao.rota == "palavra_chave":
        from parser.extratores.palavra_chave import ExtratorPorPalavraChave

        if not vocabulario:
            raise RotaNaoConfigurada(
                f"página {decisao.pagina}: rota 'palavra_chave' decidida, mas "
                "nenhum vocabulário foi informado para montar o extrator"
            )
        return ExtratorPorPalavraChave(vocabulario)

    if decisao.rota == "pdfplumber":
        from parser.extratores.pdfplumber_ import ExtratorPdfplumber

        return ExtratorPdfplumber(
            str(caminho),
            paginas=range(decisao.pagina - 1, decisao.pagina),
            campos=decisao.ordem_das_colunas,
        )

    if decisao.rota == "camelot":
        from parser.extratores.camelot_ import ExtratorCamelot

        return ExtratorCamelot(
            str(caminho),
            paginas=range(decisao.pagina - 1, decisao.pagina),
            campos=decisao.ordem_das_colunas,
        )

    if decisao.rota == "pymupdf":
        from parser.extratores.pymupdf_ import ExtratorPymupdf

        return ExtratorPymupdf(str(caminho), paginas=range(decisao.pagina - 1, decisao.pagina))

    if decisao.rota == "ocr":
        from parser.extratores.ocr import ExtratorOCR

        # Sem layout declarado no perfil, `ExtratorOCR` autocalibra por página
        # a partir das próprias palavras que o OCR reconhecer — layout do
        # perfil, quando houver, continua valendo como alternativa (útil
        # quando o ruído do OCR degrada a autocalibração num documento já
        # conhecido).
        layout = None
        posicional = perfil.rotas.get("posicional") if perfil is not None else None
        if posicional and posicional.layout:
            layout = _layout(posicional.layout)

        return ExtratorOCR(
            str(caminho), layout=layout, paginas=range(decisao.pagina - 1, decisao.pagina)
        )

    if decisao.rota in ("llm", "vlm"):
        if perfil is None:
            raise RotaNaoConfigurada(
                f"página {decisao.pagina}: rota {decisao.rota!r} necessária, mas "
                "nenhum perfil com configuração de modelo foi informado"
            )
        try:
            rota = perfil.rota(decisao.rota)
        except ConfiguracaoInvalida as erro:
            raise RotaNaoConfigurada(
                f"página {decisao.pagina}: rota {decisao.rota!r} necessária, mas o "
                f"perfil não a declara ({erro})"
            ) from erro

        # A ordem de colunas descoberta pelo roteador tem precedência sobre a
        # declarada no perfil — é o que ADR-0023 pede: o prompt reflete o que
        # foi detectado neste documento, não o que alguém digitou uma vez.
        if decisao.ordem_das_colunas:
            rota = replace(rota, campos_na_ordem=decisao.ordem_das_colunas)

        montar = _llm if decisao.rota == "llm" else _vlm
        return montar(perfil, rota, vocabulario=vocabulario)

    raise ConfiguracaoInvalida(f"decisão de rota {decisao.rota!r} não sabe montar extrator")


class _ExtratorPreComputado:
    """`Extrator` cujo resultado já foi calculado no planejamento.

    Usado só pela rota `"consolidado"`: o dado real é a votação célula a
    célula que `parser.planejador` já executou para decidir a rota — rodar
    de novo as mesmas ferramentas determinísticas aqui duplicaria o trabalho
    sem nenhum ganho, porque a votação é determinística.

    `fonte` não vem gravado no registro pré-computado — carrega o
    identificador de quando a decisão foi tomada, que é um valor de
    trabalho interno do planejador, não o documento real. É reestampado a
    partir de `documento` a cada chamada, exatamente como qualquer outro
    extrator faz.
    """

    def __init__(self, registros: list[dict]) -> None:
        self._registros = registros

    def extrair(self, documento: DocumentoCanonico) -> list:
        from parser.modelo import Registro

        return [
            Registro.model_validate({**r, "fonte": documento.identificador})
            for r in self._registros
        ]


def _documento(perfil: Perfil) -> str:
    if not perfil.documento:
        raise ConfiguracaoInvalida(
            f"perfil {perfil.nome!r} precisa de 'documento' para esta rota"
        )
    return perfil.documento


def _campos(rota: Rota, vocabulario: list[CampoEsperado] | None = None) -> list[str]:
    """Os nomes de campo que restringem a saída do modelo.

    `extras["campos"]` declarado no perfil tem precedência — é a forma
    explícita, e continua valendo mesmo com vocabulário informado, para quem
    quiser restringir a um subconjunto. Sem ele, deriva do vocabulário: é o
    que evita declarar a mesma lista de campos duas vezes, uma para a
    palavra-chave e outra para o modelo (`parser.vocabulario`).
    """
    campos = rota.extras.get("campos")
    if campos:
        return campos
    if vocabulario:
        return [c.nome for c in vocabulario]
    raise ConfiguracaoInvalida(
        f"rota {rota.nome!r} exige 'campos' — a lista que restringe a saída do modelo "
        "(ou um vocabulário declarado, que a supre automaticamente)"
    )


def _cliente(rota: Rota):
    from parser.ollama import ClienteOllama

    if not rota.modelo:
        raise ConfiguracaoInvalida(f"rota {rota.nome!r} exige 'modelo'")
    return ClienteOllama(modelo=rota.modelo, url=rota.url, timeout=rota.timeout)


def _instrucao(rota: Rota) -> str | None:
    """Carrega o prompt do arquivo, se o perfil apontar um.

    O prompt em arquivo carrega os guardrails e a justificativa de cada regra —
    contexto que uma constante em código não tem onde guardar.
    """
    if not rota.prompt:
        return None
    return carregar_prompt(rota.prompt).texto()


def _layout(dados: dict) -> LayoutTabela:
    faltando = {
        "x_rotulos",
        "x_unidades",
        "x_valores_min",
        "y_identificadores_min",
    } - dados.keys()
    if faltando:
        raise ConfiguracaoInvalida(f"layout sem: {', '.join(sorted(faltando))}")
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
