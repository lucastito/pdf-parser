"""Monta estratégias de extração a partir de um perfil declarativo.

É o único lugar do projeto que sabe qual nome de rota corresponde a qual classe.
Concentrar isso aqui tem uma consequência prática: adicionar uma estratégia nova é
registrá-la nesta tabela e escrever a classe — nada mais no projeto muda.

O perfil não sabe o que é uma classe Python, e o extrator não sabe o que é um
arquivo de configuração. Esta camada traduz entre os dois.
"""

from __future__ import annotations

from typing import Callable

from parser.configuracao import ConfiguracaoInvalida, Perfil, Rota, carregar_prompt
from parser.extratores.posicional import ExtratorPosicional, LayoutTabela
from parser.portas import Extrator

__all__ = ["ROTAS", "montar_extrator", "montar_todas"]


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
    from parser.extratores.biblioteca import ExtratorBiblioteca

    return ExtratorBiblioteca(_documento(perfil), paginas=perfil.intervalo_de_paginas())


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


def _llm(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.ollama import ClienteOllama, ExtratorModelo

    return ExtratorModelo(
        _cliente(rota),
        _campos(rota),
        instrucao=_instrucao(rota),
        degrau_maximo=_degrau_maximo(rota),
        raciocinar=bool(rota.extras.get("raciocinar", False)),
    )


def _vlm(perfil: Perfil, rota: Rota) -> Extrator:
    from parser.extratores.vlm import ExtratorVLM

    return ExtratorVLM(
        _cliente(rota),
        _campos(rota),
        _documento(perfil),
        instrucao=_instrucao(rota),
        dpi=rota.dpi,
        degrau_maximo=_degrau_maximo(rota),
        raciocinar=bool(rota.extras.get("raciocinar", False)),
    )


ROTAS: dict[str, Callable[[Perfil, Rota], Extrator]] = {
    "posicional": _posicional,
    "linear": _linear,
    "biblioteca": _biblioteca,
    "pdfplumber": _pdfplumber,
    "camelot": _camelot,
    "ocr": _ocr,
    "llm": _llm,
    "vlm": _vlm,
}
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
        if not incluir_modelos and nome in ("llm", "vlm"):
            continue
        try:
            montadas[nome] = montar_extrator(perfil, nome)
        except Exception as erro:  # noqa: BLE001 — a falha é dado, não interrupção
            print(f"  rota {nome!r} não montou: {type(erro).__name__}: {erro}")
    return montadas


def _documento(perfil: Perfil) -> str:
    if not perfil.documento:
        raise ConfiguracaoInvalida(
            f"perfil {perfil.nome!r} precisa de 'documento' para esta rota"
        )
    return perfil.documento


def _campos(rota: Rota) -> list[str]:
    campos = rota.extras.get("campos")
    if not campos:
        raise ConfiguracaoInvalida(
            f"rota {rota.nome!r} exige 'campos' — a lista que restringe a saída do modelo"
        )
    return campos


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
    faltando = {"x_rotulos", "x_unidades", "x_valores_min", "y_identificadores_min"} - dados.keys()
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
