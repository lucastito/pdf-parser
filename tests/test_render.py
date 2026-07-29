"""Renderização de página para imagem.

O DPI é a variável que decide o experimento com modelo de visão: baixo demais e
o modelo não lê a tabela; alto demais e o custo em CPU explode. Por isso ele é
parâmetro explícito e viaja junto do resultado — comparar duas execuções com DPI
diferente seria comparar coisas distintas.
"""

import base64

import pytest

from parser.fontes.render import DpiInvalido, renderizar, renderizar_documento


class TestRenderizacao:
    def test_produz_base64_decodificavel(self, pdf_exemplo):
        imagem = renderizar(pdf_exemplo, pagina=1)
        assert base64.b64decode(imagem, validate=True)

    def test_produz_png(self, pdf_exemplo):
        """Assinatura PNG: os oito primeiros bytes."""
        bruto = base64.b64decode(renderizar(pdf_exemplo, pagina=1))
        assert bruto[:8] == b"\x89PNG\r\n\x1a\n"

    def test_dpi_maior_gera_imagem_maior(self, pdf_exemplo):
        pequena = base64.b64decode(renderizar(pdf_exemplo, pagina=1, dpi=72))
        grande = base64.b64decode(renderizar(pdf_exemplo, pagina=1, dpi=200))
        assert len(grande) > len(pequena)

    def test_pagina_inexistente_falha_claro(self, pdf_exemplo):
        with pytest.raises(ValueError, match="9999"):
            renderizar(pdf_exemplo, pagina=9999)

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            renderizar(tmp_path / "nao-existe.pdf", pagina=1)


class TestDpiValidado:
    @pytest.mark.parametrize("dpi", [0, -1, -100])
    def test_dpi_nao_positivo_e_rejeitado(self, pdf_exemplo, dpi):
        with pytest.raises(DpiInvalido):
            renderizar(pdf_exemplo, pagina=1, dpi=dpi)

    def test_dpi_absurdo_e_rejeitado(self, pdf_exemplo):
        """Um DPI muito alto esgotaria a memória antes de produzir resultado —
        falhar cedo é melhor que travar a máquina."""
        with pytest.raises(DpiInvalido, match="máximo"):
            renderizar(pdf_exemplo, pagina=1, dpi=5000)

    def test_mensagem_de_erro_cita_o_valor(self, pdf_exemplo):
        with pytest.raises(DpiInvalido, match="0"):
            renderizar(pdf_exemplo, pagina=1, dpi=0)


class TestRenderizarDocumento:
    def test_renderiza_varias_paginas(self, pdf_exemplo):
        imagens = renderizar_documento(pdf_exemplo, paginas=[1])
        assert len(imagens) == 1
        assert base64.b64decode(imagens[1], validate=True)

    def test_indexa_por_numero_de_pagina(self, pdf_exemplo):
        imagens = renderizar_documento(pdf_exemplo, paginas=[1])
        assert set(imagens) == {1}

    def test_sem_paginas_renderiza_tudo(self, pdf_exemplo):
        imagens = renderizar_documento(pdf_exemplo)
        assert len(imagens) >= 1

    def test_pagina_invalida_e_ignorada_silenciosamente_nao(self, pdf_exemplo):
        """Pedir página inexistente é erro do chamador, não algo a absorver."""
        with pytest.raises(ValueError):
            renderizar_documento(pdf_exemplo, paginas=[1, 9999])
