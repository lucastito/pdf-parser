"""Extrator de controle: detecção de tabela por biblioteca pronta.

Representa a abordagem convencional — chamar o detector de tabelas de uma
biblioteca madura e usar o que ela devolver. É a alternativa contra a qual o
extrator posicional precisa se justificar: se a ferramenta padrão resolve, então
escrever reconstrução própria é complexidade sem retorno.

O resultado deste extrator é evidência, não formalidade. Se ele vencer, a
conclusão correta é adotá-lo.
"""

from __future__ import annotations

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, normalizar_texto, parse_numero
from parser.portas import DocumentoCanonico

__all__ = ["ExtratorBiblioteca"]


class ExtratorBiblioteca:
    """Usa o detector de tabelas do PyMuPDF.

    Requer o caminho do arquivo original: o detector opera sobre a página do PDF,
    não sobre o formato canônico. Isso é uma limitação real da abordagem e faz
    parte do que está sendo comparado — um extrator que precisa do arquivo bruto
    é menos substituível do que um que consome o formato canônico.
    """

    def __init__(self, caminho_pdf: str, *, paginas: range | None = None) -> None:
        self.caminho_pdf = caminho_pdf
        self.paginas = paginas

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        import fitz

        pdf = fitz.open(self.caminho_pdf)
        try:
            indices = self.paginas or range(pdf.page_count)
            registros: list[Registro] = []
            for indice in indices:
                if not 0 <= indice < pdf.page_count:
                    continue
                registros.extend(
                    self._registros_da_pagina(pdf[indice], indice + 1, documento.identificador)
                )
            return registros
        finally:
            pdf.close()

    def _registros_da_pagina(self, pagina, numero: int, fonte: str) -> list[Registro]:
        try:
            tabelas = pagina.find_tables()
        except Exception:
            return []

        registros: list[Registro] = []
        for tabela in tabelas.tables:
            linhas = tabela.extract()
            if len(linhas) < 2:
                continue
            cabecalho = [normalizar_texto(c or "") for c in linhas[0]]
            for linha in linhas[1:]:
                campos = {
                    nome: self._campo(celula, numero)
                    for nome, celula in zip(cabecalho, linha)
                    if nome
                }
                if campos:
                    registros.append(Registro(campos=campos, fonte=fonte))
        return registros

    @staticmethod
    def _campo(celula: str | None, pagina: int) -> Campo:
        texto = (celula or "").strip()
        if not texto:
            return Campo.ausente()

        evidencia = Evidencia(pagina=pagina, texto_bruto=texto)
        try:
            valor, sentinela = parse_numero(texto)
        except ValorNaoReconhecido:
            return Campo[str].extraido(valor=normalizar_texto(texto), evidencia=evidencia)
        return Campo[float].extraido(valor=valor, sentinela=sentinela, evidencia=evidencia)
