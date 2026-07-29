"""Destino JSON — formato completo, com proveniência preservada.

Complementa o CSV: onde aquele achata para consumo por planilha, este preserva
origem, confiança e evidência de cada campo. É o formato que permite auditar
uma extração meses depois e o que sustenta o round-trip sem perda.
"""

from __future__ import annotations

import json
from pathlib import Path

from parser.modelo import Registro

__all__ = ["DestinoJSON"]


class DestinoJSON:
    def __init__(self, caminho: str | Path, *, indentacao: int = 2) -> None:
        self.caminho = Path(caminho)
        self.indentacao = indentacao

    def gravar(self, registros: list[Registro]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conteudo = [r.model_dump(mode="json") for r in registros]
        self.caminho.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=self.indentacao),
            encoding="utf-8",
        )
