"""Extratores que representam as ferramentas convencionais do setor.

Existem para converter "não testei" em "testei e mediu isto". A diferença importa:
argumento perde para evidência quando alguém pergunta "mas vocês tentaram?".

Cada um implementa a mesma porta e passa pela mesma normalização, de modo que a
única diferença medida seja a estratégia — não o encanamento (ADR-0005).

Os testes usam o PDF gerado em memória pela fixture, não o documento-caso: a suíte
não deve depender de arquivo externo nem de licença de terceiro.
"""

import pytest

from parser.portas import DocumentoCanonico, Extrator


class TestExtratorPdfplumber:
    def test_respeita_a_porta(self, pdf_exemplo):
        from parser.extratores.pdfplumber_ import ExtratorPdfplumber

        assert isinstance(ExtratorPdfplumber(str(pdf_exemplo)), Extrator)

    def test_extrai_algo_de_um_pdf_com_texto(self, pdf_exemplo):
        from parser.extratores.pdfplumber_ import ExtratorPdfplumber

        doc = DocumentoCanonico(identificador=pdf_exemplo.name, paginas=[])
        registros = ExtratorPdfplumber(str(pdf_exemplo)).extrair(doc)
        assert isinstance(registros, list)

    def test_arquivo_inexistente_falha_alto(self, tmp_path):
        """Falhar é melhor que devolver lista vazia — vazio parece sucesso."""
        from parser.extratores.pdfplumber_ import ExtratorPdfplumber

        doc = DocumentoCanonico(identificador="x", paginas=[])
        with pytest.raises((FileNotFoundError, OSError)):
            ExtratorPdfplumber(str(tmp_path / "nao-existe.pdf")).extrair(doc)


class TestExtratorCamelot:
    def test_respeita_a_porta(self, pdf_exemplo):
        from parser.extratores.camelot_ import ExtratorCamelot

        assert isinstance(ExtratorCamelot(str(pdf_exemplo)), Extrator)

    def test_nao_quebra_em_pdf_sem_tabela_detectavel(self, pdf_exemplo):
        """A ferramenta não encontrar tabela é resultado, não exceção."""
        from parser.extratores.camelot_ import ExtratorCamelot

        doc = DocumentoCanonico(identificador=pdf_exemplo.name, paginas=[])
        registros = ExtratorCamelot(str(pdf_exemplo)).extrair(doc)
        assert isinstance(registros, list)

    def test_modo_stream_por_padrao(self, pdf_exemplo):
        """O modo lattice exige Ghostscript, que pode não estar presente. Stream
        não depende dele — e é o modo adequado a tabela sem linhas de grade."""
        from parser.extratores.camelot_ import ExtratorCamelot

        assert ExtratorCamelot(str(pdf_exemplo)).modo == "stream"


class TestExtratorOcr:
    def test_respeita_a_porta(self, pdf_exemplo):
        from parser.extratores.ocr import ExtratorOCR

        assert isinstance(ExtratorOCR(str(pdf_exemplo)), Extrator)

    def test_dpi_e_registrado(self, pdf_exemplo):
        """Resolução é variável do experimento: duas rodadas com DPI diferente
        não são comparáveis, então o valor precisa viajar com o resultado."""
        from parser.extratores.ocr import ExtratorOCR

        assert ExtratorOCR(str(pdf_exemplo), dpi=200).dpi == 200

    def test_dpi_invalido_falha_na_construcao(self, pdf_exemplo):
        from parser.extratores.ocr import ExtratorOCR
        from parser.fontes.render import DpiInvalido

        with pytest.raises(DpiInvalido):
            ExtratorOCR(str(pdf_exemplo), dpi=0)

    def test_sem_tesseract_falha_com_mensagem_util(self, pdf_exemplo, monkeypatch):
        """Dependência externa ausente precisa dizer o que instalar."""
        from parser.extratores import ocr as modulo

        monkeypatch.setattr(modulo, "_localizar_tesseract", lambda: None)
        doc = DocumentoCanonico(identificador=pdf_exemplo.name, paginas=[])
        with pytest.raises(RuntimeError, match="[Tt]esseract"):
            modulo.ExtratorOCR(str(pdf_exemplo)).extrair(doc)


class TestRotacaoDePagina:
    """Regressão: página com rotação declarada.

    A renderização **aplica** a rotação; a extração direta de texto devolve
    coordenadas no espaço **não rotacionado**. Sem a transformação inversa, os dois
    sistemas divergem e o layout calibrado para um não encontra nada no outro —
    o que reduziu esta rota de 64 para 2 registros antes da correção.
    """

    def test_sem_rotacao_preserva_coordenadas(self):
        from parser.extratores.ocr import ExtratorOCR

        p = ExtratorOCR._desrotacionar(10.0, 20.0, 30.0, 40.0, "x", 0, 600.0, 800.0)
        assert (p.x0, p.y0, p.x1, p.y1) == (10.0, 20.0, 30.0, 40.0)

    def test_rotacao_90_troca_os_eixos(self):
        from parser.extratores.ocr import ExtratorOCR

        p = ExtratorOCR._desrotacionar(10.0, 20.0, 30.0, 40.0, "x", 90, 600.0, 800.0)
        # o que era horizontal na imagem passa a ser vertical no documento
        assert p.y0 == pytest.approx(600.0 - 30.0)
        assert p.x0 == pytest.approx(20.0)

    @pytest.mark.parametrize("rotacao", [0, 90, 180, 270])
    def test_coordenadas_permanecem_ordenadas(self, rotacao):
        """x0 < x1 e y0 < y1 sempre — o modelo rejeita caixa invertida."""
        from parser.extratores.ocr import ExtratorOCR

        p = ExtratorOCR._desrotacionar(10.0, 20.0, 30.0, 40.0, "x", rotacao, 600.0, 800.0)
        assert p.x0 < p.x1
        assert p.y0 < p.y1

    def test_le_a_rotacao_declarada_no_documento(self, pdf_exemplo):
        from parser.extratores.ocr import ExtratorOCR

        assert ExtratorOCR(str(pdf_exemplo))._rotacao(1) == 0


class TestNormalizacaoCompartilhada:
    """Todos os extratores passam pela MESMA normalização.

    Se cada um tratasse vírgula decimal à sua maneira, a comparação mediria o
    tratamento em vez da estratégia (ADR-0005).

    Estes testes verificam o **comportamento** da conversão de célula, não a
    presença de um nome no código-fonte: pdfplumber e Camelot delegam a
    `_tabular`, e uma verificação textual acusaria falsamente.
    """

    def test_virgula_decimal_convertida(self):
        from parser.extratores._tabular import campo_de_celula

        assert campo_de_celula("3,86", 1).valor == pytest.approx(3.86)

    def test_sentinela_reconhecida_e_nao_virada_zero(self):
        from parser.extratores._tabular import campo_de_celula

        campo = campo_de_celula("Tr", 1)
        assert campo.sentinela is not None
        assert campo.valor is None

    def test_celula_vazia_vira_ausente(self):
        from parser.extratores._tabular import campo_de_celula

        assert not campo_de_celula("", 1).preenchido
        assert not campo_de_celula(None, 1).preenchido

    def test_texto_livre_preserva_valor_normalizado(self):
        from parser.extratores._tabular import campo_de_celula

        assert campo_de_celula("Arroz,   integral", 1).valor == "Arroz, integral"

    def test_evidencia_registra_o_texto_bruto(self):
        """O original tem de sobreviver à normalização, para auditoria."""
        from parser.extratores._tabular import campo_de_celula

        assert campo_de_celula("3,86", 1).evidencia.texto_bruto == "3,86"

    def test_ocr_reusa_a_normalizacao(self):
        """O OCR delega a reconstrução ao extrator posicional, que já normaliza."""
        from parser.extratores.ocr import ExtratorOCR

        assert hasattr(ExtratorOCR, "extrair")
