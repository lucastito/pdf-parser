"""Extração por palavra-chave: o degrau entre "sem tabela" e "manda pro modelo".

Estes testes usam texto corrido construído à mão — o que se quer proteger é o
casamento de rótulo com valor por proximidade, não a extração de um documento
real (isso vem depois, com vocabulário e página reais).
"""

from parser.extratores.palavra_chave import (
    CONFIANCA_PALAVRA_CHAVE,
    ExtratorPorPalavraChave,
)
from parser.portas import DocumentoCanonico, Pagina, Palavra
from parser.vocabulario import CampoEsperado


def _pagina(numero: int, texto: str) -> Pagina:
    """Uma página cujo `.texto` é exatamente a string dada.

    `Pagina.texto` junta `palavras` com espaço — uma palavra só, com o texto
    completo, reproduz a string sem reformatar espaçamento.
    """
    return Pagina(numero=numero, palavras=[Palavra(texto=texto, x0=0, y0=0, x1=1, y1=1)])


def _documento(*paginas: Pagina, identificador: str = "relatorio.pdf") -> DocumentoCanonico:
    return DocumentoCanonico(identificador=identificador, paginas=list(paginas))


class TestAcharPertoDoRotulo:
    def test_acha_valor_apos_o_rotulo(self):
        pagina = _pagina(1, "A Profundidade de Projeto considerada é de 1850 m no local.")
        extrator = ExtratorPorPalavraChave(
            [
                CampoEsperado(
                    nome="profundidade_projeto", sinonimos=("Profundidade de Projeto",)
                )
            ]
        )

        (registro,) = extrator.extrair(_documento(pagina))

        assert registro.campos["profundidade_projeto"].valor == 1850.0

    def test_acha_por_sinonimo_quando_nome_canonico_nao_aparece(self):
        campo = CampoEsperado(nome="lamina_dagua", sinonimos=("Water Depth", "profundidade"))
        pagina = _pagina(1, "The Water Depth at this site is approximately 1850 m.")

        (registro,) = ExtratorPorPalavraChave([campo]).extrair(_documento(pagina))

        assert registro.campos["lamina_dagua"].valor == 1850.0

    def test_case_insensitive(self):
        campo = CampoEsperado(nome="pressao", sinonimos=("PRESSÃO INICIAL",))
        pagina = _pagina(1, "pressão inicial medida: 320 bar.")

        (registro,) = ExtratorPorPalavraChave([campo]).extrair(_documento(pagina))

        assert registro.campos["pressao"].valor == 320.0

    def test_confianca_e_menor_que_extracao_deterministica(self):
        campo = CampoEsperado(nome="x", sinonimos=("valor x",))
        pagina = _pagina(1, "o valor x medido foi 10.")

        (registro,) = ExtratorPorPalavraChave([campo]).extrair(_documento(pagina))

        assert registro.campos["x"].confianca == CONFIANCA_PALAVRA_CHAVE
        assert registro.campos["x"].confianca < 1.0

    def test_evidencia_preserva_o_texto_bruto_e_a_vizinhanca(self):
        campo = CampoEsperado(nome="x", sinonimos=("valor x",))
        pagina = _pagina(1, "o valor x medido foi 10 m no ponto A.")

        (registro,) = ExtratorPorPalavraChave([campo]).extrair(_documento(pagina))

        evidencia = registro.campos["x"].evidencia
        assert evidencia.texto_bruto == "10"
        assert "ponto A" in evidencia.vizinhanca


class TestAusenciaEhOmissaoNaoInvencao:
    def test_rotulo_ausente_nao_produz_campo(self):
        campo = CampoEsperado(nome="pressao", sinonimos=("pressão inicial",))
        pagina = _pagina(1, "Este relatório descreve a metodologia de amostragem.")

        registros = ExtratorPorPalavraChave([campo]).extrair(_documento(pagina))

        assert registros == []

    def test_rotulo_sem_valor_por_perto_nao_inventa(self):
        campo = CampoEsperado(nome="pressao", sinonimos=("pressão inicial",))
        # Rótulo presente, mas nenhum número na janela de busca depois dele.
        texto = "pressão inicial " + ("texto sem número " * 20)
        pagina = _pagina(1, texto)

        registros = ExtratorPorPalavraChave([campo]).extrair(_documento(pagina))

        assert registros == []

    def test_pagina_sem_achado_nenhum_nao_gera_registro(self):
        campos = [
            CampoEsperado(nome="a", sinonimos=("alfa",)),
            CampoEsperado(nome="b", sinonimos=("beta",)),
        ]
        pagina = _pagina(1, "Nada de alfa nem de beta nesta página.")

        registros = ExtratorPorPalavraChave(campos).extrair(_documento(pagina))

        assert registros == []


class TestMultiplosCampos:
    def test_dois_campos_na_mesma_pagina_entram_no_mesmo_registro(self):
        campos = [
            CampoEsperado(nome="profundidade", sinonimos=("Water Depth",)),
            CampoEsperado(nome="pressao", sinonimos=("Initial Pressure",)),
        ]
        pagina = _pagina(
            1, "Water Depth: 1850 m. Initial Pressure: 320 bar. Fim do parágrafo."
        )

        (registro,) = ExtratorPorPalavraChave(campos).extrair(_documento(pagina))

        assert registro.campos["profundidade"].valor == 1850.0
        assert registro.campos["pressao"].valor == 320.0

    def test_campo_encontrado_numa_pagina_e_ausente_na_outra(self):
        campos = [CampoEsperado(nome="profundidade", sinonimos=("Water Depth",))]
        pagina_1 = _pagina(1, "Water Depth: 1850 m.")
        pagina_2 = _pagina(2, "Metodologia de amostragem, sem valor nenhum aqui.")

        registros = ExtratorPorPalavraChave(campos).extrair(_documento(pagina_1, pagina_2))

        assert len(registros) == 1
        assert registros[0].campos["profundidade"].valor == 1850.0


class TestRespeitaAPorta:
    def test_extrair_devolve_lista_de_registro(self):
        from parser.portas import Extrator

        assert isinstance(ExtratorPorPalavraChave([]), Extrator)

    def test_sem_campo_algum_nao_acha_nada(self):
        pagina = _pagina(1, "Water Depth: 1850 m.")
        assert ExtratorPorPalavraChave([]).extrair(_documento(pagina)) == []
