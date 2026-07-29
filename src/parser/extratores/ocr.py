"""Extração por OCR — RF-2 do projeto e requisito da especificação de referência.

O documento-caso tem texto nativo, então não *precisa* de OCR. Isso é uma
vantagem experimental, não um desperdício: renderizar a página como imagem e
passá-la por OCR cria um **caso controlado** em que a resposta certa é conhecida.
Dá para medir exatamente quanto a rota por imagem degrada em relação à leitura
direta — o que um documento genuinamente digitalizado não permitiria.

O OCR reconstrói posição, então o resultado alimenta a mesma reconstrução
posicional usada na rota determinística. A diferença medida fica sendo a qualidade
do reconhecimento de caracteres, não a estratégia de montagem da tabela.
"""

from __future__ import annotations

import base64
import io
import os
import shutil
from pathlib import Path

from parser.extratores.posicional import ExtratorPosicional, LayoutTabela
from parser.fontes.render import DPI_PADRAO, _validar_dpi, renderizar
from parser.modelo import Registro
from parser.normalizacao import parse_numero  # noqa: F401 — normalização compartilhada
from parser.portas import DocumentoCanonico, Pagina, Palavra

__all__ = ["ExtratorOCR"]

CAMINHOS_CONHECIDOS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
)


def _localizar_tesseract() -> str | None:
    """Procura o binário no PATH e nos locais usuais de instalação."""
    achado = shutil.which("tesseract")
    if achado:
        return achado
    for caminho in CAMINHOS_CONHECIDOS:
        if Path(caminho).exists():
            return caminho
    return None


class ExtratorOCR:
    """Renderiza a página, reconhece o texto por OCR e reconstrói a tabela.

    O idioma padrão é inglês porque é o que costuma vir instalado. Para tabela
    numérica isso importa pouco — os números são iguais em qualquer idioma, e a
    acentuação perdida nos rótulos é tratada pela normalização compartilhada.
    """

    def __init__(
        self,
        caminho_pdf: str,
        *,
        layout: LayoutTabela | None = None,
        paginas: range | None = None,
        dpi: int = 200,
        idioma: str = "eng",
    ) -> None:
        _validar_dpi(dpi)
        self.caminho_pdf = caminho_pdf
        self.paginas = paginas
        self.dpi = dpi
        self.idioma = idioma
        self.layout = layout

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        binario = _localizar_tesseract()
        if not binario:
            raise RuntimeError(
                "tesseract não encontrado. Instale-o "
                "(winget install UB-Mannheim.TesseractOCR) e garanta que esteja no PATH."
            )

        import pytesseract
        from PIL import Image

        pytesseract.pytesseract.tesseract_cmd = binario
        os.environ.setdefault(
            "TESSDATA_PREFIX", str(Path(binario).parent / "tessdata")
        )

        indices = self.paginas or range(len(documento.paginas))
        paginas = []
        for indice in indices:
            numero = indice + 1
            imagem = Image.open(
                io.BytesIO(
                    base64.b64decode(
                        renderizar(self.caminho_pdf, pagina=numero, dpi=self.dpi)
                    )
                )
            )
            paginas.append(Pagina(numero=numero, palavras=self._palavras(imagem, pytesseract)))

        canonico = DocumentoCanonico(identificador=documento.identificador, paginas=paginas)

        if self.layout is None:
            # Sem layout não há como reconstruir a tabela; devolver o texto solto
            # seria inventar estrutura.
            return []
        return ExtratorPosicional(self.layout).extrair(canonico)

    def _palavras(self, imagem, pytesseract) -> list[Palavra]:
        """Converte a saída do OCR em palavras com coordenadas.

        As coordenadas vêm em pixels da imagem renderizada; convertê-las de volta
        para pontos tipográficos permite reusar o mesmo layout da rota direta —
        sem isso, comparar as duas exigiria dois conjuntos de coordenadas.
        """
        dados = pytesseract.image_to_data(
            imagem, lang=self.idioma, output_type=pytesseract.Output.DICT
        )
        escala = 72.0 / self.dpi

        palavras = []
        for i, texto in enumerate(dados["text"]):
            if not texto.strip():
                continue
            x, y = dados["left"][i], dados["top"][i]
            largura, altura = dados["width"][i], dados["height"][i]
            palavras.append(
                Palavra(
                    texto=texto,
                    x0=x * escala,
                    y0=y * escala,
                    x1=(x + largura) * escala,
                    y1=(y + altura) * escala,
                )
            )
        return palavras
