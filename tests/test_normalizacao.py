"""Normalização de texto e número — cobre E3 (sentinelas) e E4 (decimal com vírgula).

Esta é a camada que corrompe em silêncio: um `Tr` virando `0.0` não levanta exceção,
só produz um número errado que ninguém audita. Daí a densidade de testes aqui.
"""

import pytest

from parser.normalizacao import (
    ValorNaoReconhecido,
    normalizar_texto,
    parse_numero,
)
from parser.modelo import Sentinela


class TestDecimalComVirgula:
    @pytest.mark.parametrize(
        "bruto,esperado",
        [
            ("3,86", 3.86),
            ("0,5", 0.5),
            ("124", 124.0),
            ("1405", 1405.0),
            ("73,3", 73.3),
            ("-2,5", -2.5),
        ],
    )
    def test_converte_virgula_decimal(self, bruto, esperado):
        valor, sentinela = parse_numero(bruto)
        assert valor == pytest.approx(esperado)
        assert sentinela is None

    def test_ponto_decimal_tambem_funciona(self):
        """Nem todo documento usa vírgula; o parser não deve presumir a locale."""
        valor, _ = parse_numero("3.86")
        assert valor == pytest.approx(3.86)

    def test_espacos_ao_redor_sao_ignorados(self):
        valor, _ = parse_numero("  12,5  ")
        assert valor == pytest.approx(12.5)

    def test_separador_de_milhar_com_ponto(self):
        valor, _ = parse_numero("1.405,5")
        assert valor == pytest.approx(1405.5)


class TestSentinelas:
    @pytest.mark.parametrize(
        "bruto,esperada",
        [
            ("Tr", Sentinela.TRACO),
            ("tr", Sentinela.TRACO),
            ("TR", Sentinela.TRACO),
            ("NA", Sentinela.NAO_ANALISADO),
            ("na", Sentinela.NAO_ANALISADO),
            ("*", Sentinela.NAO_APLICAVEL),
        ],
    )
    def test_reconhece_sentinelas(self, bruto, esperada):
        valor, sentinela = parse_numero(bruto)
        assert sentinela is esperada
        assert valor is None, "sentinela nunca deve produzir valor numérico"

    @pytest.mark.parametrize("bruto", ["Tr", "NA", "*"])
    def test_sentinela_nunca_vira_zero(self, bruto):
        """O erro mais perigoso: `Tr` somado como 0 falseia qualquer total."""
        valor, sentinela = parse_numero(bruto)
        assert valor != 0.0
        assert valor is None
        assert sentinela is not None

    def test_zero_literal_nao_e_sentinela(self):
        valor, sentinela = parse_numero("0")
        assert valor == 0.0
        assert sentinela is None


class TestValoresNaoReconhecidos:
    @pytest.mark.parametrize("bruto", ["", "   ", "abc", "12abc", "—", "?"])
    def test_valor_ininteligivel_falha_alto(self, bruto):
        """Falhar alto é melhor que gravar lixo: o silêncio é o modo de falha caro."""
        with pytest.raises(ValorNaoReconhecido):
            parse_numero(bruto)

    def test_mensagem_de_erro_cita_o_valor(self):
        with pytest.raises(ValorNaoReconhecido, match="xyz"):
            parse_numero("xyz")


class TestNormalizacaoDeTexto:
    def test_colapsa_espacos_internos(self):
        assert normalizar_texto("Arroz,   integral   cozido") == "Arroz, integral cozido"

    def test_remove_espacos_nas_bordas(self):
        assert normalizar_texto("  Feijão  ") == "Feijão"

    def test_preserva_acentuacao(self):
        """Perder acento aqui contaminaria qualquer busca textual a jusante."""
        assert normalizar_texto("Açúcar, mascavo") == "Açúcar, mascavo"

    def test_junta_palavra_quebrada_por_espacos(self):
        """O PDF-caso emite texto espaçado letra a letra em alguns trechos."""
        assert normalizar_texto("A L I M E N T O") == "ALIMENTO"

    def test_nao_junta_palavras_normais(self):
        assert normalizar_texto("Arroz integral") == "Arroz integral"

    def test_remove_hifenizacao_de_quebra_de_linha(self):
        assert normalizar_texto("Carbo-\nidrato") == "Carboidrato"

    def test_remove_hifenizacao_quando_quebra_virou_espaco(self):
        """Ao extrair de PDF a quebra de linha costuma chegar como espaço."""
        assert normalizar_texto("Carbo- idrato") == "Carboidrato"

    def test_preserva_hifen_legitimo_de_palavra_composta(self):
        """`pré-cozida` aparece no corpus e não pode perder o hífen."""
        assert normalizar_texto("pré-cozida") == "pré-cozida"
        assert normalizar_texto("meio-a-meio") == "meio-a-meio"

    def test_texto_vazio(self):
        assert normalizar_texto("   ") == ""


class TestHeuristicaDeJuncaoNaoCorrompe:
    """A junção de letras isoladas é heurística, e heurística erra.

    O limiar de 4+ letras consecutivas existe para que texto legítimo com letras
    isoladas sobreviva intacto. Estes testes fixam a fronteira: são eles que
    impedem a regra de ficar agressiva demais numa refatoração futura.
    """

    @pytest.mark.parametrize(
        "texto",
        [
            "vitamina A e C",
            "p H do meio",
            "A B",
            "tipo A",
            "vitamina D",
            "sal e água",
        ],
    )
    def test_texto_legitimo_com_letras_isoladas_fica_intacto(self, texto):
        assert normalizar_texto(texto) == texto

    def test_tres_letras_isoladas_nao_juntam(self):
        """Abaixo do limiar: preferir não mexer a arriscar corromper."""
        assert normalizar_texto("A B C") == "A B C"

    def test_quatro_letras_isoladas_juntam(self):
        assert normalizar_texto("A B C D") == "ABCD"

    def test_junta_apenas_o_trecho_espacado(self):
        """O resto da frase não pode ser afetado pela junção."""
        assert normalizar_texto("Tabela A L I M E N T O completa") == (
            "Tabela ALIMENTO completa"
        )

    def test_acentuacao_sobrevive_a_juncao(self):
        assert normalizar_texto("A Ç Ú C A R") == "AÇÚCAR"
