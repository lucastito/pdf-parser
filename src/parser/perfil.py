"""Perfil declarativo: monta um pipeline a partir de configuração.

Trocar de contexto — outro documento, outra estratégia, outro destino — deve ser
trocar de arquivo de perfil, não editar código. É o que torna o núcleo
reutilizável entre domínios que nada têm em comum.

Formatos de entrada declarados mas ainda não implementados são montados como
adapter que **falha alto ao ser usado**. Devolver documento vazio faria o
pipeline completar com sucesso aparente sem ter lido nada — o modo de falha mais
caro, porque só aparece quando alguém nota a saída faltando muito depois.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parser.destinos.csv_ import DestinoCSV
from parser.destinos.json_ import DestinoJSON
from parser.extratores.biblioteca import ExtratorBiblioteca
from parser.extratores.linear import ExtratorLinear
from parser.extratores.posicional import ExtratorPosicional, LayoutTabela
from parser.fontes.pdf import FontePDF
from parser.fontes.stub import FonteNaoImplementada
from parser.pipeline import Pipeline
from parser.portas import Destino, Extrator, FonteDocumento

__all__ = ["Perfil", "PerfilInvalido"]

FORMATOS_PREVISTOS = ("xlsx", "csv", "json", "docx", "imagem", "zip")
"""Formatos declaráveis que ainda não têm implementação — viram stub."""


class PerfilInvalido(ValueError):
    """A configuração não descreve um pipeline montável."""


@dataclass
class Perfil:
    """Descrição declarativa de um pipeline."""

    nome: str
    fonte: dict[str, Any]
    extrator: dict[str, Any]
    destinos: list[dict[str, Any]] = field(default_factory=list)
    triar_paginas: bool = False
    apenas_dados: bool = False
    documento: str | None = None
    """Caminho padrão do documento, se o perfil for específico de um."""

    @classmethod
    def de_arquivo(cls, caminho: str | Path) -> Perfil:
        arquivo = Path(caminho)
        if not arquivo.exists():
            raise PerfilInvalido(f"perfil não encontrado: {arquivo}")

        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise PerfilInvalido(f"perfil {arquivo.name} não é JSON válido: {erro}") from erro

        faltando = {"nome", "fonte", "extrator"} - dados.keys()
        if faltando:
            raise PerfilInvalido(
                f"perfil {arquivo.name} não tem: {', '.join(sorted(faltando))}"
            )
        return cls(**dados)

    def montar(self) -> Pipeline:
        return Pipeline(
            self._montar_fonte(),
            self._montar_extrator(),
            [self._montar_destino(d) for d in self.destinos],
            triar_paginas=self.triar_paginas,
            apenas_dados=self.apenas_dados,
        )

    def _montar_fonte(self) -> FonteDocumento:
        tipo = self.fonte.get("tipo")
        if tipo == "pdf":
            paginas = self.fonte.get("paginas")
            return FontePDF(paginas=_intervalo(paginas) if paginas else None)
        if tipo in FORMATOS_PREVISTOS:
            return FonteNaoImplementada(formato=tipo)
        raise PerfilInvalido(
            f"tipo de fonte desconhecido: {tipo!r}. "
            f"Conhecidos: pdf, {', '.join(FORMATOS_PREVISTOS)}"
        )

    def _montar_extrator(self) -> Extrator:
        tipo = self.extrator.get("tipo")
        if tipo == "linear":
            return ExtratorLinear()
        if tipo == "biblioteca":
            caminho = self.extrator.get("caminho") or self.documento
            if not caminho:
                raise PerfilInvalido(
                    "extrator 'biblioteca' precisa do caminho do documento "
                    "(campo 'caminho' no extrator ou 'documento' no perfil)"
                )
            paginas = self.extrator.get("paginas")
            return ExtratorBiblioteca(caminho, paginas=_intervalo(paginas) if paginas else None)
        if tipo == "posicional":
            layout = self.extrator.get("layout")
            if not layout:
                raise PerfilInvalido(
                    "extrator 'posicional' exige 'layout' com as faixas de coordenadas"
                )
            return ExtratorPosicional(_layout(layout))
        if tipo in ("modelo", "vlm"):
            return self._montar_extrator_de_modelo(tipo)
        raise PerfilInvalido(
            f"tipo de extrator desconhecido: {tipo!r}. "
            "Conhecidos: posicional, linear, biblioteca, modelo, vlm"
        )

    def _montar_extrator_de_modelo(self, tipo: str) -> Extrator:
        from parser.ollama import ClienteOllama, ExtratorModelo

        modelo = self.extrator.get("modelo")
        if not modelo:
            raise PerfilInvalido(f"extrator {tipo!r} exige 'modelo' (ex.: 'qwen3:4b')")

        campos = self.extrator.get("campos")
        if not campos:
            raise PerfilInvalido(
                f"extrator {tipo!r} exige 'campos' — a lista que restringe a saída. "
                "Sem ela o modelo devolveria estrutura arbitrária"
            )

        cliente = ClienteOllama(
            modelo=modelo,
            url=self.extrator.get("url", "http://localhost:11434"),
            timeout=self.extrator.get("timeout", 120.0),
        )
        instrucao = self.extrator.get("instrucao")

        if tipo == "modelo":
            return ExtratorModelo(cliente, campos, instrucao=instrucao)

        from parser.extratores.vlm import ExtratorVLM
        from parser.fontes.render import DPI_PADRAO

        caminho = self.extrator.get("caminho") or self.documento
        if not caminho:
            raise PerfilInvalido(
                "extrator 'vlm' precisa do caminho do documento para renderizar as "
                "páginas (campo 'caminho' no extrator ou 'documento' no perfil)"
            )
        return ExtratorVLM(
            cliente,
            campos,
            caminho,
            instrucao=instrucao,
            dpi=self.extrator.get("dpi", DPI_PADRAO),
        )

    @staticmethod
    def _montar_destino(destino: dict[str, Any]) -> Destino:
        tipo = destino.get("tipo")
        caminho = destino.get("caminho")
        if not caminho:
            raise PerfilInvalido(f"destino {tipo!r} sem 'caminho'")
        if tipo == "csv":
            return DestinoCSV(caminho)
        if tipo == "json":
            return DestinoJSON(caminho)
        raise PerfilInvalido(
            f"tipo de destino desconhecido: {tipo!r}. Conhecidos: csv, json"
        )


def _intervalo(spec: Any) -> range:
    """Aceita `[inicio, fim]` ou `[inicio, fim, passo]`, base 0."""
    if isinstance(spec, range):
        return spec
    if isinstance(spec, list) and len(spec) in (2, 3):
        return range(*spec)
    raise PerfilInvalido(f"intervalo de páginas inválido: {spec!r} (use [inicio, fim])")


def _layout(dados: dict[str, Any]) -> LayoutTabela:
    obrigatorios = {"x_rotulos", "x_unidades", "x_valores_min", "y_identificadores_min"}
    faltando = obrigatorios - dados.keys()
    if faltando:
        raise PerfilInvalido(f"layout sem: {', '.join(sorted(faltando))}")

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
