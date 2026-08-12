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

import os
import tempfile
from pathlib import Path

from parser.extratores._tabular import registros_de_matriz, registros_por_posicao
from parser.modelo import Registro
from parser.portas import DocumentoCanonico

__all__ = ["ExtratorPdfplumber"]

AJUSTES = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
}


class ExtratorPdfplumber:
    """Usa a detecção de tabela do pdfplumber, sobre a página desrotacionada.

    Não assume estrutura de documento nenhuma: `campos` — a ordem dos valores
    numa linha — vem de fora (calibração geométrica, ou perfil explícito).
    Sem `campos`, a tabela é montada pelo **cabeçalho que o pdfplumber
    detectou**, não por uma ordem inventada aqui. Um extrator com fallback
    próprio de nomes de campo produziria dado plausível e errado em qualquer
    documento diferente daquele que o fallback tinha em mente — exatamente o
    modo de falha que este projeto existe para evitar.
    """

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
        self.campos = campos
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
                        registros.extend(self._materializar(matriz, numero, documento))
        finally:
            if caminho != str(arquivo):
                Path(caminho).unlink(missing_ok=True)
        return registros

    def _materializar(
        self, matriz: list[list[str | None]], numero: int, documento: DocumentoCanonico
    ) -> list[Registro]:
        """Escolhe como ler a matriz — nunca à revelia de quem chamou.

        Com `campos` conhecido (ordem descoberta ou declarada), alinha por
        posição: serve à tabela cujo cabeçalho vem rotacionado ou partido, caso
        em que o cabeçalho é lixo mas as linhas de dado estão íntegras. Sem
        `campos`, a única informação disponível é a que o próprio pdfplumber
        detectou — a primeira linha da matriz — e é dela que os nomes saem.
        """
        if self.campos:
            return registros_por_posicao(matriz, numero, documento.identificador, self.campos)
        return registros_de_matriz(matriz, numero, documento.identificador)

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

            # Nome único por execução. Antes era `_desrot_<nome do arquivo>.pdf`:
            # como o lote percorre subpastas, dois documentos homônimos — um
            # `relatorio.pdf` por cliente — escreviam no mesmo caminho, e o
            # segundo sobrescrevia o primeiro sem erro algum.
            descritor, caminho_temporario = tempfile.mkstemp(prefix="_desrot_", suffix=".pdf")
            os.close(descritor)
            destino.save(caminho_temporario)
            destino.close()
            return caminho_temporario, mapa
        finally:
            origem.close()
