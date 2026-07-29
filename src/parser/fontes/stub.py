"""Adapter de entrada ainda não implementado.

Declara a intenção de suportar um formato sem fingir que o suporta. A alternativa
— devolver documento vazio — faria o pipeline inteiro completar com sucesso
aparente, e o problema só apareceria quando alguém notasse a saída vazia.
"""

from __future__ import annotations

from parser.portas import DocumentoCanonico, FormatoNaoSuportado

__all__ = ["FonteNaoImplementada"]


class FonteNaoImplementada:
    """Placeholder que falha alto para um formato conhecido mas não suportado."""

    def __init__(self, formato: str) -> None:
        self.formato = formato

    def carregar(self, caminho: str) -> DocumentoCanonico:
        raise FormatoNaoSuportado(
            f"formato {self.formato!r} ainda não é suportado (arquivo: {caminho!r}). "
            f"Implemente uma FonteDocumento para {self.formato!r} antes de usá-lo."
        )
