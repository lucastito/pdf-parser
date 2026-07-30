"""Os dois extratores de controle — o piso e a alternativa convencional.

Estavam sem teste, e isso é mais grave do que parece: os dois **são a régua**
contra a qual o extrator posicional se justifica (ADR-0002, ADR-0006). Se a régua
estiver errada, todo ganho declarado do posicional está errado junto, e ninguém
saberia.

`ExtratorLinear` é o piso: lê a página como sequência de palavras, na ordem em que
o PDF as emite. É o que se obtém sem reconstrução posicional alguma.

`ExtratorBiblioteca` é a alternativa madura: chama o detector de tabelas pronto.
Se ele resolvesse, escrever reconstrução própria seria complexidade sem retorno.

O que estes testes protegem não é acurácia — é que os dois **funcionem e falhem de
forma previsível**. Um piso que quebra não mede nada; um piso que finge sucesso
mede errado.
"""

import pytest

from parser.portas import DocumentoCanonico, Extrator, Pagina, Palavra


def _palavra(texto, x0=10.0, y0=10.0):
    return Palavra(texto=texto, x0=x0, y0=y0, x1=x0 + 30, y1=y0 + 8)


def _documento(*palavras, identificador="d.pdf"):
    return DocumentoCanonico(
        identificador=identificador,
        paginas=[Pagina(numero=1, palavras=list(palavras))],
    )


class TestExtratorLinear:
    """O piso da comparação."""

    def _extrator(self):
        from parser.extratores.linear import ExtratorLinear

        return ExtratorLinear()

    def test_respeita_a_porta_extrator(self):
        assert isinstance(self._extrator(), Extrator)

    def test_associa_rotulo_ao_valor_seguinte(self):
        registros = self._extrator().extrair(
            _documento(_palavra("Proteína (g)"), _palavra("2,6", x0=60.0))
        )
        assert registros[0].campos["Proteína (g)"].valor == pytest.approx(2.6)

    def test_reconhece_sentinela_como_sentinela(self):
        """Piso ou não, `Tr` nunca pode virar zero (ADR-0004)."""
        from parser.modelo import Sentinela

        registros = self._extrator().extrair(
            _documento(_palavra("Fibra (g)"), _palavra("Tr", x0=60.0))
        )
        campo = registros[0].campos["Fibra (g)"]
        assert campo.sentinela is Sentinela.TRACO
        assert campo.valor is None

    def test_rotulo_sem_valor_seguinte_sai_ausente(self):
        from parser.modelo import Origem

        registros = self._extrator().extrair(_documento(_palavra("Proteína (g)")))
        assert registros[0].campos["Proteína (g)"].origem is Origem.AUSENTE

    def test_pagina_sem_palavra_nao_vira_registro(self):
        vazio = DocumentoCanonico(
            identificador="d.pdf", paginas=[Pagina(numero=1, palavras=[])]
        )
        assert self._extrator().extrair(vazio) == []

    def test_pagina_sem_rotulo_reconhecivel_nao_vira_registro(self):
        """Melhor devolver nada que inventar estrutura onde não há."""
        registros = self._extrator().extrair(
            _documento(_palavra("texto"), _palavra("solto"), _palavra("124"))
        )
        assert registros == []

    def test_documento_vazio_devolve_lista_vazia(self):
        assert (
            self._extrator().extrair(DocumentoCanonico(identificador="d.pdf", paginas=[]))
            == []
        )

    def test_valor_ininteligivel_nao_vira_numero(self):
        """Texto que não é número nem sentinela não pode virar 0.0 calado."""
        registros = self._extrator().extrair(
            _documento(_palavra("Proteína (g)"), _palavra("~~~", x0=60.0))
        )
        campo = registros[0].campos["Proteína (g)"]
        assert campo.valor != 0.0

    def test_evidencia_aponta_a_pagina_e_o_texto_bruto(self):
        registros = self._extrator().extrair(
            _documento(_palavra("Proteína (g)"), _palavra("2,6", x0=60.0))
        )
        evidencia = registros[0].campos["Proteína (g)"].evidencia
        assert evidencia.pagina == 1
        assert evidencia.texto_bruto == "2,6"
        assert evidencia.bbox is not None

    def test_erra_de_forma_previsivel_em_tabela_transposta(self):
        """O piso associa ao primeiro item valores que pertencem a vários.

        É o erro característico esperado, e registrá-lo é o que dá sentido à
        comparação: o posicional existe justamente para não cometê-lo.
        """
        registros = self._extrator().extrair(
            _documento(
                _palavra("Energia (kcal)"),
                _palavra("124", x0=60.0),
                _palavra("360", x0=90.0),
                _palavra("128", x0=120.0),
            )
        )
        # Um único registro, com o primeiro valor — os outros dois se perdem.
        assert len(registros) == 1
        assert registros[0].campos["Energia (kcal)"].valor == pytest.approx(124.0)


class TestExtratorBiblioteca:
    """A alternativa convencional, contra a qual o posicional se justifica."""

    @pytest.fixture
    def pdf_com_tabela(self, tmp_path):
        import fitz

        caminho = tmp_path / "tabela.pdf"
        documento = fitz.open()
        pagina = documento.new_page(width=595, height=842)
        # Tabela com linhas de grade: o caso que o detector pronto trata bem.
        for i, linha in enumerate([("Item", "Valor"), ("Um", "124"), ("Dois", "360")]):
            y = 100 + i * 30
            pagina.insert_text((100, y), linha[0])
            pagina.insert_text((250, y), linha[1])
            pagina.draw_line(fitz.Point(90, y + 5), fitz.Point(400, y + 5))
        pagina.draw_line(fitz.Point(90, 95), fitz.Point(90, 200))
        pagina.draw_line(fitz.Point(400, 95), fitz.Point(400, 200))
        documento.save(caminho)
        documento.close()
        return caminho

    def test_respeita_a_porta_extrator(self, pdf_com_tabela):
        from parser.extratores.biblioteca import ExtratorBiblioteca

        assert isinstance(ExtratorBiblioteca(str(pdf_com_tabela)), Extrator)

    def test_extrai_sem_estourar(self, pdf_com_tabela):
        """O contrato mínimo: devolver lista de registros, não explodir."""
        from parser.extratores.biblioteca import ExtratorBiblioteca

        registros = ExtratorBiblioteca(str(pdf_com_tabela)).extrair(
            _documento(identificador="tabela.pdf")
        )
        assert isinstance(registros, list)

    def test_pdf_sem_tabela_devolve_lista_vazia(self, tmp_path):
        """Zero tabela é resultado legítimo — e é o que motivou o posicional."""
        import fitz

        from parser.extratores.biblioteca import ExtratorBiblioteca

        caminho = tmp_path / "prosa.pdf"
        documento = fitz.open()
        documento.new_page().insert_text((72, 72), "Apenas texto corrido, sem tabela.")
        documento.save(caminho)
        documento.close()

        registros = ExtratorBiblioteca(str(caminho)).extrair(_documento())
        assert registros == []

    def test_paginas_fora_do_intervalo_sao_ignoradas(self, pdf_com_tabela):
        """Índice inválido não pode estourar no meio de um lote."""
        from parser.extratores.biblioteca import ExtratorBiblioteca

        registros = ExtratorBiblioteca(str(pdf_com_tabela), paginas=range(50, 60)).extrair(
            _documento()
        )
        assert registros == []

    def test_arquivo_inexistente_falha_alto(self, tmp_path):
        from parser.extratores.biblioteca import ExtratorBiblioteca

        with pytest.raises(Exception):
            ExtratorBiblioteca(str(tmp_path / "nao-existe.pdf")).extrair(_documento())
