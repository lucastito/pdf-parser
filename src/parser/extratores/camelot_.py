"""Extração via Camelot — outra ferramenta que a especificação de referência propõe.

O Camelot tem dois modos, e a escolha aqui não é arbitrária:

- ``lattice`` detecta tabela por linhas de grade e **exige Ghostscript**. O
  documento-caso não tem grade, então o modo não tem o que detectar.
- ``stream`` infere colunas por alinhamento de texto e não depende de Ghostscript.
  É o modo adequado, e é o padrão aqui.

Usar o modo apropriado é parte de comparar honestamente: derrotar a ferramenta na
configuração errada não prova nada sobre ela.
"""

from __future__ import annotations

from pathlib import Path

from parser.extratores._tabular import registros_por_posicao
from parser.extratores.pdfplumber_ import CAMPOS_NA_ORDEM
from parser.modelo import Registro
from parser.portas import DocumentoCanonico

__all__ = ["ExtratorCamelot"]


class ExtratorCamelot:
    """Usa a detecção de tabela do Camelot."""

    def __init__(
        self,
        caminho_pdf: str,
        *,
        paginas: range | None = None,
        modo: str = "stream",
        campos: list[str] | None = None,
    ) -> None:
        self.caminho_pdf = caminho_pdf
        self.paginas = paginas
        self.modo = modo
        self.campos = campos or CAMPOS_NA_ORDEM

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        import camelot

        arquivo = Path(self.caminho_pdf)
        if not arquivo.exists():
            raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

        # O Camelot numera páginas a partir de 1, ao contrário do resto do projeto.
        if self.paginas is not None:
            paginas = ",".join(str(i + 1) for i in self.paginas)
        else:
            paginas = "all"

        try:
            tabelas = camelot.read_pdf(str(arquivo), pages=paginas, flavor=self.modo)
        except Exception as erro:  # noqa: BLE001
            # A ferramenta não conseguir ler é resultado do experimento, e precisa
            # aparecer como tal — não como exceção que interrompe a rodada.
            raise RuntimeError(
                f"camelot ({self.modo}) não processou o documento: {type(erro).__name__}: {erro}"
            ) from erro

        registros: list[Registro] = []
        for tabela in tabelas:
            matriz = tabela.df.values.tolist()
            if not matriz:
                continue
            # Alinhamento por posição, e não por cabeçalho: o cabeçalho detectado
            # vem rotacionado e partido, mas as linhas de dados estão na ordem.
            registros.extend(
                registros_por_posicao(
                    matriz, int(tabela.page), documento.identificador, self.campos
                )
            )
        return registros
