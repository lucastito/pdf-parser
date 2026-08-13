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
from parser.fontes.render import _validar_dpi, renderizar
from parser.modelo import Registro
from parser.normalizacao import parse_numero  # noqa: F401 — normalização compartilhada
from parser.portas import DocumentoCanonico, Pagina, Palavra

__all__ = ["DPI_OCR", "ExtratorOCR"]

DPI_OCR = 350
"""Resolução ótima medida para esta rota (ADR-0007).

A curva não é monotônica: abaixo disto o reconhecedor perde a vírgula decimal e
produz valores dez vezes maiores; acima, a leitura da vírgula melhora mas o
alinhamento de colunas quebra, e o número de campos não localizados salta de 30
para 142. Otimizar só o reconhecimento pioraria o resultado final.
"""


def _layout_de_candidato(dados: dict) -> LayoutTabela:
    """Converte o dict de `Candidato.layout` (`parser.calibracao`) na forma
    que `ExtratorPosicional` espera — mesma conversão que `fabrica._layout`
    faz para o layout declarado no perfil; aqui a origem é a autocalibração."""
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


VARIAVEL_DE_AMBIENTE_TESSERACT = "PARSER_TESSERACT_PATH"
"""Override explícito do caminho do binário — a prioridade mais alta.

Existe porque `CAMINHOS_CONHECIDOS` abaixo é uma lista de palpites (instalação
padrão do Windows/Linux), não uma garantia: o produto vai ser instalado em
servidores variados, da empresa ou de clientes, com Tesseract em qualquer
lugar — distribuição Linux diferente, ambiente conda, Homebrew no macOS,
contêiner com layout próprio. Sem essa variável, a única saída pra um caminho
fora da lista seria editar este arquivo por máquina.
"""

CAMINHOS_CONHECIDOS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
)
"""Só conveniência de último recurso — não é garantia. `PATH` do sistema
(via `shutil.which`) é o mecanismo correto na maioria dos casos; esta lista
cobre só os locais de instalação mais comuns do instalador padrão."""


def _localizar_tesseract() -> str | None:
    """Procura o binário do Tesseract, do mais flexível pro menos.

    1. `PARSER_TESSERACT_PATH` — override explícito, necessário sempre que a
       instalação não seguir nem o `PATH` nem um dos caminhos comuns abaixo.
    2. `PATH` do sistema (`shutil.which`) — o caminho correto quando a
       instalação já expõe o binário do jeito usual do SO.
    3. `CAMINHOS_CONHECIDOS` — só os locais de instalação mais comuns; nunca
       o único mecanismo, e sempre contornável pelo item 1 sem editar código.
    """
    variavel = os.environ.get(VARIAVEL_DE_AMBIENTE_TESSERACT)
    if variavel and Path(variavel).exists():
        return variavel

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
        dpi: int = DPI_OCR,
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
        os.environ.setdefault("TESSDATA_PREFIX", str(Path(binario).parent / "tessdata"))

        indices = self.paginas or range(len(documento.paginas))
        paginas = []
        for indice in indices:
            numero = indice + 1
            imagem = Image.open(
                io.BytesIO(
                    base64.b64decode(renderizar(self.caminho_pdf, pagina=numero, dpi=self.dpi))
                )
            )
            paginas.append(
                Pagina(
                    numero=numero,
                    palavras=self._palavras(imagem, pytesseract, self._rotacao(numero)),
                )
            )

        canonico = DocumentoCanonico(identificador=documento.identificador, paginas=paginas)

        if self.layout is not None:
            return ExtratorPosicional(self.layout).extrair(canonico)

        # Sem layout declarado, autocalibra por página a partir das próprias
        # palavras que o OCR já reconheceu — a heurística de geometria não
        # sabe (nem precisa saber) que essas palavras vieram de OCR, não da
        # camada de texto nativa. Página cuja calibração falhar não trava as
        # demais: devolve o que as outras páginas renderam, e mais nada —
        # layout inventado grava lixo, que é o modo de falha que este projeto
        # existe para evitar.
        from parser.calibracao import CalibracaoFalhou, calibrar_palavras

        registros: list[Registro] = []
        for pagina in canonico.paginas:
            try:
                candidato = calibrar_palavras(pagina.palavras)
            except CalibracaoFalhou:
                continue
            documento_pagina = DocumentoCanonico(
                identificador=canonico.identificador, paginas=[pagina]
            )
            layout = _layout_de_candidato(candidato.layout)
            registros.extend(ExtratorPosicional(layout).extrair(documento_pagina))
        return registros

    def _rotacao(self, pagina: int) -> int:
        """Rotação que a página declara no documento.

        Importa porque a renderização **aplica** essa rotação, enquanto a extração
        direta de texto devolve coordenadas no espaço **não rotacionado**. Ignorar
        isso faz os dois sistemas de coordenadas divergirem, e o layout calibrado
        para um não encontra nada no outro — foi o que reduziu esta rota a dois
        registros antes da correção.
        """
        import fitz

        documento = fitz.open(self.caminho_pdf)
        try:
            return documento[pagina - 1].rotation % 360
        finally:
            documento.close()

    def _palavras(self, imagem, pytesseract, rotacao: int = 0) -> list[Palavra]:
        """Converte a saída do OCR em palavras com coordenadas.

        As coordenadas vêm em pixels da imagem renderizada; convertê-las para
        pontos tipográficos **no mesmo espaço da extração direta** é o que permite
        reusar o layout já calibrado, e é o que torna as duas rotas comparáveis.
        """
        dados = pytesseract.image_to_data(
            imagem, lang=self.idioma, output_type=pytesseract.Output.DICT
        )
        escala = 72.0 / self.dpi
        largura_pt = imagem.width * escala
        altura_pt = imagem.height * escala

        palavras = []
        for i, texto in enumerate(dados["text"]):
            if not texto.strip():
                continue
            x, y = dados["left"][i], dados["top"][i]
            largura, altura = dados["width"][i], dados["height"][i]

            if rotacao:
                palavras.append(
                    self._desrotacionar(
                        x * escala,
                        y * escala,
                        (x + largura) * escala,
                        (y + altura) * escala,
                        texto,
                        rotacao,
                        largura_pt,
                        altura_pt,
                    )
                )
                continue

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

    @staticmethod
    def _desrotacionar(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        texto: str,
        rotacao: int,
        largura: float,
        altura: float,
    ) -> Palavra:
        """Leva coordenadas da imagem renderizada de volta ao espaço do documento.

        Só as rotações retas (90, 180, 270) são tratadas — as únicas que um PDF
        declara na prática. Para 90°, o eixo horizontal da imagem corresponde ao
        vertical do documento, e a origem muda de canto.
        """
        if rotacao == 90:
            novo = (y0, largura - x1, y1, largura - x0)
        elif rotacao == 180:
            novo = (largura - x1, altura - y1, largura - x0, altura - y0)
        elif rotacao == 270:
            novo = (altura - y1, x0, altura - y0, x1)
        else:
            novo = (x0, y0, x1, y1)

        return Palavra(
            texto=texto,
            x0=min(novo[0], novo[2]),
            y0=min(novo[1], novo[3]),
            x1=max(novo[0], novo[2]),
            y1=max(novo[1], novo[3]),
        )
