"""Extrator baseado em modelo de visão.

A invariante central aqui: o modelo tem de **receber a imagem**. Um extrator de
visão que envia só texto não está exercendo nada do que se propõe a testar, e a
comparação contra a rota determinística perderia o sentido — mediria dois
leitores de texto, não texto contra visão.

Também aqui a normalização é a mesma dos demais braços (ADR-0005): se cada
estratégia limpasse à sua maneira, a diferença medida seria do encanamento.
"""

import base64
import json

import pytest

from parser.extratores.vlm import ExtratorVLM
from parser.modelo import Origem
from parser.ollama import ClienteOllama
from parser.portas import DocumentoCanonico, Pagina, Palavra


class TransporteFalso:
    def __init__(self, resposta: object) -> None:
        self.resposta = resposta
        self.chamadas: list[dict] = []

    def enviar(self, url: str, carga: dict, timeout: float) -> dict:
        self.chamadas.append(carga)
        return {"response": json.dumps(self.resposta)}


def _documento(identificador: str) -> DocumentoCanonico:
    return DocumentoCanonico(
        identificador=identificador,
        paginas=[
            Pagina(
                numero=1,
                palavras=[Palavra(texto="x", x0=0.0, y0=0.0, x1=1.0, y1=1.0)],
            )
        ],
    )


def _extrator(transporte, pdf, **kwargs):
    return ExtratorVLM(
        cliente=ClienteOllama(modelo="visao", transporte=transporte),
        campos=["identificador", "proteina"],
        caminho_pdf=str(pdf),
        **kwargs,
    )


class TestEnvioDaImagem:
    def test_envia_imagem_ao_modelo(self, pdf_exemplo):
        """Sem isto o extrator de visão não é de visão."""
        transporte = TransporteFalso({"itens": []})
        _extrator(transporte, pdf_exemplo).extrair(_documento(pdf_exemplo.name))

        assert "images" in transporte.chamadas[0]
        assert transporte.chamadas[0]["images"]

    def test_imagem_enviada_e_png_valido(self, pdf_exemplo):
        transporte = TransporteFalso({"itens": []})
        _extrator(transporte, pdf_exemplo).extrair(_documento(pdf_exemplo.name))

        bruto = base64.b64decode(transporte.chamadas[0]["images"][0])
        assert bruto[:8] == b"\x89PNG\r\n\x1a\n"

    def test_uma_chamada_por_pagina(self, pdf_exemplo):
        """Enviar o documento inteiro numa chamada estouraria o contexto e
        abandonaria a recuperação seletiva."""
        transporte = TransporteFalso({"itens": []})
        documento = DocumentoCanonico(
            identificador=pdf_exemplo.name,
            paginas=[
                Pagina(numero=1, palavras=[]),
                Pagina(numero=1, palavras=[]),
            ],
        )
        _extrator(transporte, pdf_exemplo).extrair(documento)
        assert len(transporte.chamadas) == 2

    def test_dpi_afeta_a_imagem_enviada(self, pdf_exemplo):
        tamanhos = []
        for dpi in (72, 200):
            transporte = TransporteFalso({"itens": []})
            _extrator(transporte, pdf_exemplo, dpi=dpi).extrair(
                _documento(pdf_exemplo.name)
            )
            tamanhos.append(len(transporte.chamadas[0]["images"][0]))

        assert tamanhos[1] > tamanhos[0], "DPI maior deveria produzir imagem maior"


class TestSaida:
    def test_produz_registros(self, pdf_exemplo):
        transporte = TransporteFalso(
            {"itens": [{"identificador": "Arroz", "proteina": 2.6}]}
        )
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )

        assert len(registros) == 1
        assert registros[0].campos["proteina"].valor == 2.6

    def test_confianca_menor_que_deterministica(self, pdf_exemplo):
        transporte = TransporteFalso({"itens": [{"proteina": 2.6}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        assert registros[0].campos["proteina"].confianca < 1.0

    def test_normalizacao_e_a_mesma_dos_outros_bracos(self, pdf_exemplo):
        """Vírgula decimal tratada igual em todas as estratégias."""
        transporte = TransporteFalso({"itens": [{"proteina": "2,6"}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        assert registros[0].campos["proteina"].valor == pytest.approx(2.6)

    def test_sentinela_reconhecida(self, pdf_exemplo):
        transporte = TransporteFalso({"itens": [{"proteina": "Tr"}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        campo = registros[0].campos["proteina"]
        assert campo.sentinela is not None
        assert campo.valor is None

    def test_campo_fora_do_schema_e_descartado(self, pdf_exemplo):
        transporte = TransporteFalso({"itens": [{"proteina": 2.6, "invencao": "x"}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        assert "invencao" not in registros[0].campos

    def test_origem_e_extraida(self, pdf_exemplo):
        transporte = TransporteFalso({"itens": [{"proteina": 2.6}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        assert registros[0].campos["proteina"].origem is Origem.EXTRAIDO

    def test_evidencia_registra_a_pagina(self, pdf_exemplo):
        transporte = TransporteFalso({"itens": [{"proteina": 2.6}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        assert registros[0].campos["proteina"].evidencia.pagina == 1


class TestContrato:
    def test_respeita_a_porta_extrator(self, pdf_exemplo):
        from parser.portas import Extrator

        assert isinstance(
            _extrator(TransporteFalso({}), pdf_exemplo), Extrator
        )

    def test_dpi_invalido_falha_na_construcao(self, pdf_exemplo):
        from parser.fontes.render import DpiInvalido

        with pytest.raises(DpiInvalido):
            _extrator(TransporteFalso({}), pdf_exemplo, dpi=0)


class TestDegraus:
    """A rota tem de sobreviver ao colapso do esquema restringido (SPEC §4.4).

    O modo de falha não se parece com falha: resposta vazia, `done_reason=stop`,
    HTTP 200. Sem a descida de degrau, a página vira "sem dados" em silêncio.
    """

    class TransporteQueColapsa:
        """Vazio no primeiro degrau, útil no segundo — o colapso observado."""

        def __init__(self, resposta: object) -> None:
            self.resposta = resposta
            self.chamadas: list[dict] = []

        def enviar(self, url: str, carga: dict, timeout: float) -> dict:
            self.chamadas.append(carga)
            if len(self.chamadas) == 1:
                return {"response": "", "done_reason": "stop", "eval_count": 84}
            return {"response": json.dumps(self.resposta)}

    def test_esquema_vazio_nao_vira_pagina_sem_dados(self, pdf_exemplo):
        transporte = self.TransporteQueColapsa({"itens": [{"proteina": 2.6}]})
        registros = _extrator(transporte, pdf_exemplo).extrair(
            _documento(pdf_exemplo.name)
        )
        assert registros, "o colapso do esquema virou página em branco"
        assert registros[0].campos["proteina"].valor == 2.6

    def test_degrau_usado_fica_registrado(self, pdf_exemplo):
        """Só rodadas no mesmo degrau são comparáveis (ADR-0005)."""
        from parser.degraus import Degrau

        transporte = self.TransporteQueColapsa({"itens": [{"proteina": 2.6}]})
        extrator = _extrator(transporte, pdf_exemplo)
        extrator.extrair(_documento(pdf_exemplo.name))

        assert extrator.degraus_usados == [Degrau.JSON_LIVRE]

    def test_a_imagem_acompanha_a_descida(self, pdf_exemplo):
        """Descer de degrau não pode transformar a rota de visão em rota de texto."""
        transporte = self.TransporteQueColapsa({"itens": [{"proteina": 2.6}]})
        _extrator(transporte, pdf_exemplo).extrair(_documento(pdf_exemplo.name))

        assert all("images" in carga for carga in transporte.chamadas)
