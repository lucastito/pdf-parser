"""Contratos das três portas — cobre A2 (stub falha explicitamente).

A porta `Extrator` é o que torna a comparação possível: se ela não for
substituível de verdade, a matriz de avaliação compara pipelines diferentes em
vez de extratores diferentes, e não mede nada.
"""

import pytest

from parser.modelo import Campo, Evidencia, Registro
from parser.portas import (
    Destino,
    DocumentoCanonico,
    Extrator,
    FonteDocumento,
    FormatoNaoSuportado,
    Pagina,
    Palavra,
)

EV = Evidencia(pagina=1, texto_bruto="x")


class TestDocumentoCanonico:
    def test_documento_expoe_paginas(self):
        doc = DocumentoCanonico(
            identificador="doc.pdf",
            paginas=[Pagina(numero=1, palavras=[]), Pagina(numero=2, palavras=[])],
        )
        assert len(doc.paginas) == 2
        assert doc.paginas[0].numero == 1

    def test_palavra_carrega_posicao(self):
        """A posição é o que permite reconstruir tabela sem linhas de grade."""
        p = Palavra(texto="124", x0=10.0, y0=20.0, x1=30.0, y1=28.0)
        assert p.texto == "124"
        assert p.x0 == 10.0

    def test_pagina_numerada_a_partir_de_um(self):
        with pytest.raises(Exception):
            Pagina(numero=0, palavras=[])

    def test_texto_da_pagina_concatena_palavras_em_ordem(self):
        pagina = Pagina(
            numero=1,
            palavras=[
                Palavra(texto="Arroz", x0=0.0, y0=0.0, x1=5.0, y1=8.0),
                Palavra(texto="integral", x0=6.0, y0=0.0, x1=12.0, y1=8.0),
            ],
        )
        assert pagina.texto == "Arroz integral"


class TestPortasSaoProtocolos:
    """As portas existem para permitir troca; se não forem substituíveis por
    qualquer objeto que respeite a forma, a arquitetura não entrega isso."""

    def test_fonte_aceita_implementacao_arbitraria(self):
        class FonteFake:
            def carregar(self, caminho: str) -> DocumentoCanonico:
                return DocumentoCanonico(identificador=caminho, paginas=[])

        fonte: FonteDocumento = FonteFake()
        assert fonte.carregar("x.pdf").identificador == "x.pdf"

    def test_extrator_aceita_implementacao_arbitraria(self):
        class ExtratorFake:
            def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
                return [
                    Registro(
                        campos={"a": Campo[float].extraido(valor=1.0, evidencia=EV)},
                        fonte=documento.identificador,
                    )
                ]

        extrator: Extrator = ExtratorFake()
        doc = DocumentoCanonico(identificador="d", paginas=[])
        assert extrator.extrair(doc)[0].fonte == "d"

    def test_destino_aceita_implementacao_arbitraria(self):
        gravados: list[Registro] = []

        class DestinoFake:
            def gravar(self, registros: list[Registro]) -> None:
                gravados.extend(registros)

        destino: Destino = DestinoFake()
        destino.gravar([Registro(campos={}, fonte="f")])
        assert len(gravados) == 1

    def test_dois_extratores_diferentes_no_mesmo_documento(self):
        """A1: trocar de extrator não exige tocar em mais nada."""

        class ExtratorA:
            def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
                return [Registro(campos={}, fonte="A")]

        class ExtratorB:
            def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
                return [Registro(campos={}, fonte="B")]

        doc = DocumentoCanonico(identificador="d", paginas=[])
        resultados = [e.extrair(doc)[0].fonte for e in (ExtratorA(), ExtratorB())]
        assert resultados == ["A", "B"]


class TestStubFalhaExplicitamente:
    """A2: um formato não implementado deve falhar alto.

    Um stub que devolve lista vazia é pior que ausência de stub: o pipeline
    completa com sucesso aparente e ninguém descobre que nada foi lido.
    """

    def test_stub_levanta_erro_ao_carregar(self):
        from parser.fontes.stub import FonteNaoImplementada

        fonte = FonteNaoImplementada(formato="xlsx")
        with pytest.raises(FormatoNaoSuportado):
            fonte.carregar("planilha.xlsx")

    def test_erro_do_stub_cita_o_formato(self):
        from parser.fontes.stub import FonteNaoImplementada

        with pytest.raises(FormatoNaoSuportado, match="xlsx"):
            FonteNaoImplementada(formato="xlsx").carregar("p.xlsx")

    def test_stub_nunca_devolve_documento_vazio(self):
        """Sucesso silencioso é o modo de falha que este teste existe para impedir."""
        from parser.fontes.stub import FonteNaoImplementada

        fonte = FonteNaoImplementada(formato="docx")
        try:
            resultado = fonte.carregar("a.docx")
        except FormatoNaoSuportado:
            return
        pytest.fail(f"stub deveria falhar, mas devolveu {resultado!r}")
