"""Extração via pdfplumber — a ferramenta que a especificação de referência propõe.

Entra na comparação para responder uma pergunta concreta: *a biblioteca que a
equipe usaria por padrão resolve este documento?*

Duas providências são necessárias para que a resposta seja justa, e ambas vieram
de medição, não de suposição:

**Desrotacionar a página.** O documento declara ``rotation=90``. Com a rotação
ativa, a detecção de tabela encontra **zero** tabelas; desrotacionada, encontra uma
com 67 linhas — e os dados estão lá, íntegros. Cobrar da ferramenta um resultado
que a rotação impede não mediria a ferramenta.

**Alinhar por posição, não por cabeçalho.** O cabeçalho detectado é lixo (vem
rotacionado e partido em várias linhas), mas as linhas de dados estão corretas e na
ordem. Insistir no cabeçalho descartaria dado bom por causa de metadado ruim.

Sem essas duas, a medição registrava 0% de acurácia — e o número era artefato do
nosso código, não limitação da biblioteca.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from parser.extratores._tabular import registros_por_posicao
from parser.modelo import Registro
from parser.portas import DocumentoCanonico

__all__ = ["CAMPOS_NA_ORDEM", "ExtratorPdfplumber"]

AJUSTES = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
}

CAMPOS_NA_ORDEM = [
    "Umidade (%)",
    "Energia (kcal)",
    "Energia (kJ)",
    "Proteína (g)",
    "Lipídeos (g)",
    "Colesterol (mg)",
    "Carboidrato (g)",
    "Fibra Alimentar (g)",
]
"""Ordem em que os valores aparecem em cada linha do documento-caso.

É configuração do documento, não do algoritmo: outro documento entra trocando esta
lista. Vem da leitura do cabeçalho impresso, verificada contra o gabarito.
"""


class ExtratorPdfplumber:
    """Usa a detecção de tabela do pdfplumber, sobre a página desrotacionada."""

    def __init__(
        self,
        caminho_pdf: str,
        *,
        paginas: range | None = None,
        campos: list[str] | None = None,
        desrotacionar: bool = True,
    ) -> None:
        self.caminho_pdf = caminho_pdf
        self.paginas = paginas
        self.campos = campos or CAMPOS_NA_ORDEM
        self.desrotacionar = desrotacionar

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        import pdfplumber

        arquivo = Path(self.caminho_pdf)
        if not arquivo.exists():
            raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

        caminho, mapa = self._preparar(arquivo)
        registros: list[Registro] = []
        try:
            with pdfplumber.open(caminho) as pdf:
                for indice, pagina in enumerate(pdf.pages):
                    numero = mapa.get(indice, indice + 1)
                    for matriz in pagina.extract_tables(AJUSTES) or []:
                        registros.extend(
                            registros_por_posicao(
                                matriz, numero, documento.identificador, self.campos
                            )
                        )
        finally:
            if caminho != str(arquivo):
                Path(caminho).unlink(missing_ok=True)
        return registros

    def _preparar(self, arquivo: Path) -> tuple[str, dict[int, int]]:
        """Devolve o caminho a ler e o mapa índice→página original.

        Sem desrotação, lê o arquivo original. Com desrotação, escreve um temporário
        contendo só as páginas pedidas, já endireitadas — e o mapa preserva a
        numeração original, para que a evidência aponte a página certa.
        """
        if not self.desrotacionar:
            return str(arquivo), {}

        import fitz

        origem = fitz.open(arquivo)
        try:
            indices = list(self.paginas or range(origem.page_count))
            if not any(origem[i].rotation for i in indices if 0 <= i < origem.page_count):
                return str(arquivo), {i: i + 1 for i, _ in enumerate(indices)}

            destino = fitz.open()
            mapa = {}
            for posicao, indice in enumerate(indices):
                if not 0 <= indice < origem.page_count:
                    continue
                pagina = origem[indice]
                rotacao = pagina.rotation
                nova = destino.new_page(
                    width=pagina.rect.height if rotacao % 180 else pagina.rect.width,
                    height=pagina.rect.width if rotacao % 180 else pagina.rect.height,
                )
                nova.show_pdf_page(nova.rect, origem, indice, rotate=-rotacao)
                mapa[posicao] = indice + 1

            temporario = Path(tempfile.gettempdir()) / f"_desrot_{arquivo.stem}.pdf"
            destino.save(str(temporario))
            destino.close()
            return str(temporario), mapa
        finally:
            origem.close()
