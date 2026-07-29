"""Fonte de entrada para PDF com texto nativo.

Usa PyMuPDF, que aplica os mapas ``ToUnicode`` ao decodificar fontes CID. Isso
importa: em documentos com ``Identity-H`` e mapas incompletos, ler os operadores
de texto diretamente do stream produz caracteres que *parecem* texto mas não são
— e o erro passa silencioso até alguém conferir o dado à mão.

Este adapter não interpreta estrutura. Ele entrega palavras com coordenadas e
deixa a reconstrução para o extrator, que é o componente que varia entre os
braços da comparação.
"""

from __future__ import annotations

from pathlib import Path

import fitz

from parser.portas import DocumentoCanonico, Pagina, Palavra

__all__ = ["FontePDF"]


class FontePDF:
    """Lê PDF de texto nativo, preservando a posição de cada palavra."""

    def __init__(self, *, paginas: range | None = None) -> None:
        """
        Args:
            paginas: intervalo de páginas (base 0) a carregar. ``None`` carrega
                todas. Útil para iterar sobre um documento longo sem pagar o
                custo de lê-lo inteiro a cada execução.
        """
        self.paginas = paginas

    def carregar(self, caminho: str) -> DocumentoCanonico:
        arquivo = Path(caminho)
        if not arquivo.exists():
            raise FileNotFoundError(f"arquivo não encontrado: {caminho}")

        documento = fitz.open(arquivo)
        try:
            indices = self.paginas or range(documento.page_count)
            paginas = [
                self._pagina(documento[i], i + 1)
                for i in indices
                if 0 <= i < documento.page_count
            ]
        finally:
            documento.close()

        return DocumentoCanonico(identificador=arquivo.name, paginas=paginas)

    @staticmethod
    def _pagina(pagina: fitz.Page, numero: int) -> Pagina:
        palavras = [
            Palavra(texto=w[4], x0=w[0], y0=w[1], x1=w[2], y1=w[3])
            for w in pagina.get_text("words")
            if w[4].strip()
        ]
        return Pagina(numero=numero, palavras=palavras)
