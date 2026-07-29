"""Extração via pdfplumber — a ferramenta que a especificação de referência propõe.

Entra na comparação para responder uma pergunta concreta: *a biblioteca que a
equipe usaria por padrão resolve este documento?* A resposta, qualquer que seja,
vale mais que argumento.

O `table_settings` usa estratégia `text`, não `lines`: o documento-caso não tem
linhas de grade, então detecção por borda não tem o que detectar. Dar à ferramenta
sua melhor configuração possível é parte de comparar honestamente — vencer contra
uma versão mal configurada não prova nada.
"""

from __future__ import annotations

from pathlib import Path

from parser.extratores._tabular import registros_de_matriz
from parser.modelo import Registro
from parser.portas import DocumentoCanonico

__all__ = ["ExtratorPdfplumber"]

AJUSTES = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
}


class ExtratorPdfplumber:
    """Usa a detecção de tabela do pdfplumber.

    Precisa do arquivo original, não do formato canônico — limitação real da
    abordagem, e um dos pontos em que ela é menos substituível que a
    reconstrução posicional.
    """

    def __init__(self, caminho_pdf: str, *, paginas: range | None = None) -> None:
        self.caminho_pdf = caminho_pdf
        self.paginas = paginas

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        import pdfplumber

        arquivo = Path(self.caminho_pdf)
        if not arquivo.exists():
            raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

        registros: list[Registro] = []
        with pdfplumber.open(arquivo) as pdf:
            indices = self.paginas or range(len(pdf.pages))
            for indice in indices:
                if not 0 <= indice < len(pdf.pages):
                    continue
                pagina = pdf.pages[indice]
                for matriz in pagina.extract_tables(AJUSTES) or []:
                    registros.extend(
                        registros_de_matriz(matriz, indice + 1, documento.identificador)
                    )
        return registros
