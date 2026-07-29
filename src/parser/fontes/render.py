"""Renderização de página para imagem, para consumo por modelo de visão.

É o que separa "cliente que aceita imagem" de "modelo de visão utilizável": sem
renderizar, um modelo com visão recebe texto e deixa de exercer justamente o que
o distingue — enxergar o layout.

O DPI é parâmetro explícito e deve viajar junto do resultado. Ele decide o
experimento: baixo demais e a tabela fica ilegível para o modelo; alto demais e o
custo em processador cresce sem retorno. Duas execuções com DPI diferente não são
comparáveis entre si.
"""

from __future__ import annotations

import base64
from pathlib import Path

__all__ = ["DPI_PADRAO", "DpiInvalido", "renderizar", "renderizar_documento"]

DPI_PADRAO = 150
"""Compromisso inicial: legível para tabela densa sem inviabilizar o processador."""

DPI_MAXIMO = 600
"""Acima disto a imagem consome memória sem ganho de leitura — falhar cedo é
melhor do que travar a máquina no meio de um lote."""


class DpiInvalido(ValueError):
    """O DPI pedido não produz uma imagem utilizável."""


def _validar_dpi(dpi: int) -> None:
    if dpi <= 0:
        raise DpiInvalido(f"dpi deve ser positivo, recebido: {dpi}")
    if dpi > DPI_MAXIMO:
        raise DpiInvalido(f"dpi {dpi} excede o máximo de {DPI_MAXIMO}")


def renderizar(
    caminho: str | Path, *, pagina: int, dpi: int = DPI_PADRAO
) -> str:
    """Renderiza uma página como PNG em base64.

    Args:
        pagina: número da página, começando em 1.
        dpi: resolução. Registre-o junto do resultado — é variável do experimento.

    Levanta:
        DpiInvalido: resolução fora da faixa utilizável.
        FileNotFoundError: arquivo inexistente.
        ValueError: página fora do documento.
    """
    import fitz

    _validar_dpi(dpi)

    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

    documento = fitz.open(arquivo)
    try:
        if not 1 <= pagina <= documento.page_count:
            raise ValueError(
                f"página {pagina} fora do documento (tem {documento.page_count})"
            )
        pixmap = documento[pagina - 1].get_pixmap(dpi=dpi)
        return base64.b64encode(pixmap.tobytes("png")).decode("ascii")
    finally:
        documento.close()


def renderizar_documento(
    caminho: str | Path,
    *,
    paginas: list[int] | None = None,
    dpi: int = DPI_PADRAO,
) -> dict[int, str]:
    """Renderiza várias páginas, indexadas pelo número da página.

    Uma página pedida que não exista é erro do chamador, não algo a absorver:
    ignorá-la em silêncio produziria um lote menor do que o esperado sem aviso.
    """
    import fitz

    _validar_dpi(dpi)

    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

    documento = fitz.open(arquivo)
    try:
        numeros = paginas if paginas is not None else range(1, documento.page_count + 1)
        imagens = {}
        for numero in numeros:
            if not 1 <= numero <= documento.page_count:
                raise ValueError(
                    f"página {numero} fora do documento (tem {documento.page_count})"
                )
            pixmap = documento[numero - 1].get_pixmap(dpi=dpi)
            imagens[numero] = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
        return imagens
    finally:
        documento.close()
