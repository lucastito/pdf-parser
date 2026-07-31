"""Harness de avaliação.

Estes testes existem porque o harness é o que decide quais conclusões podem ser
defendidas. Um comparador que arredonda a favor produz relatório bonito e
argumento falso — e ninguém percebe, porque o erro está no instrumento de medida.
"""

from parser.avaliacao import Veredito, avaliar
from parser.modelo import Campo, Evidencia, Registro, Sentinela

EV = Evidencia(pagina=1, texto_bruto="x")


def _registro(**valores) -> Registro:
    campos = {}
    for nome, valor in valores.items():
        if valor is None:
            campos[nome] = Campo.ausente()
        elif isinstance(valor, Sentinela):
            campos[nome] = Campo[float].extraido(sentinela=valor, evidencia=EV)
        elif isinstance(valor, str):
            campos[nome] = Campo[str].extraido(valor=valor, evidencia=EV)
        else:
            campos[nome] = Campo[float].extraido(valor=valor, evidencia=EV)
    return Registro(campos=campos, fonte="teste")


class TestComparacaoNumerica:
    def test_valor_identico_e_acerto(self):
        r = avaliar("e", {"a": _registro(x=124.0)}, {"a": {"x": 124.0}})
        assert r.acuracia == 1.0

    def test_formatacao_diferente_nao_e_erro(self):
        """`"42"` e `42.0` são o mesmo número; acusá-los seria ruído."""
        r = avaliar("e", {"a": _registro(x=42.0)}, {"a": {"x": "42"}})
        assert r.acuracia == 1.0

    def test_virgula_decimal_no_gabarito(self):
        r = avaliar("e", {"a": _registro(x=2.6)}, {"a": {"x": "2,6"}})
        assert r.acuracia == 1.0

    def test_valor_diferente_e_erro(self):
        r = avaliar("e", {"a": _registro(x=124.0)}, {"a": {"x": 999.0}})
        assert r.acuracia == 0.0
        assert r.comparacoes[0].resultados[0].veredito is Veredito.ERRO

    def test_diferenca_dentro_da_tolerancia(self):
        r = avaliar("e", {"a": _registro(x=100.5)}, {"a": {"x": 100.0}}, tolerancia=0.01)
        assert r.acuracia == 1.0

    def test_diferenca_acima_da_tolerancia(self):
        r = avaliar("e", {"a": _registro(x=105.0)}, {"a": {"x": 100.0}}, tolerancia=0.01)
        assert r.acuracia == 0.0

    def test_zero_esperado_usa_tolerancia_absoluta(self):
        """Erro relativo é indefinido em zero; sem tratamento daria divisão por zero."""
        assert avaliar("e", {"a": _registro(x=0.0)}, {"a": {"x": 0.0}}).acuracia == 1.0
        assert avaliar("e", {"a": _registro(x=5.0)}, {"a": {"x": 0.0}}).acuracia == 0.0


class TestSentinelasEAusencia:
    def test_sentinela_correta_e_acerto(self):
        r = avaliar("e", {"a": _registro(x=Sentinela.TRACO)}, {"a": {"x": "traco"}})
        assert r.acuracia == 1.0

    def test_sentinela_trocada_por_zero_e_erro(self):
        """O erro mais caro do domínio precisa aparecer como erro no relatório."""
        r = avaliar("e", {"a": _registro(x=0.0)}, {"a": {"x": "traco"}})
        assert r.acuracia == 0.0

    def test_sentinela_errada_e_erro(self):
        r = avaliar("e", {"a": _registro(x=Sentinela.TRACO)}, {"a": {"x": "nao_analisado"}})
        assert r.acuracia == 0.0

    def test_campo_ausente_quando_esperado_e_faltou(self):
        r = avaliar("e", {"a": _registro(x=None)}, {"a": {"x": 124.0}})
        assert r.comparacoes[0].resultados[0].veredito is Veredito.FALTOU

    def test_registro_inteiro_ausente_conta_como_faltou(self):
        r = avaliar("e", {}, {"a": {"x": 124.0}})
        assert r.comparacoes[0].resultados[0].veredito is Veredito.FALTOU
        assert r.acuracia == 0.0

    def test_valor_inventado_conta_como_sobrou(self):
        """Penaliza o extrator que preenche o que o documento não afirma."""
        r = avaliar("e", {"a": _registro(x=1.0)}, {"a": {"x": None}})
        assert r.comparacoes[0].resultados[0].veredito is Veredito.SOBROU
        assert r.acuracia == 0.0

    def test_ausencia_corretamente_reconhecida_e_acerto(self):
        r = avaliar("e", {"a": _registro(x=None)}, {"a": {"x": None}})
        assert r.acuracia == 1.0


class TestMetricaPorCampo:
    def test_campo_sistematicamente_errado_aparece(self):
        """O ponto central: a média esconde, a visão por campo revela."""
        obtidos = {f"item{i}": _registro(bom=1.0, ruim=999.0) for i in range(10)}
        gabarito = {f"item{i}": {"bom": 1.0, "ruim": 1.0} for i in range(10)}

        r = avaliar("e", obtidos, gabarito)
        assert r.acuracia == 0.5  # média esconde
        por_campo = r.por_campo()
        assert por_campo["bom"] == 1.0
        assert por_campo["ruim"] == 0.0  # visão por campo revela

    def test_piores_campos_ordena_do_pior(self):
        obtidos = {"a": _registro(x=1.0, y=999.0, z=1.0)}
        gabarito = {"a": {"x": 1.0, "y": 1.0, "z": 1.0}}
        piores = avaliar("e", obtidos, gabarito).piores_campos(limite=1)
        assert piores[0][0] == "y"

    def test_acuracia_de_gabarito_vazio(self):
        assert avaliar("e", {}, {}).acuracia == 0.0


class TestComparacaoEntreExtratores:
    def test_dois_extratores_no_mesmo_gabarito(self):
        """A1 na prática: mesma régua, extratores diferentes."""
        gabarito = {"a": {"x": 124.0, "y": 2.6}}
        bom = avaliar("bom", {"a": _registro(x=124.0, y=2.6)}, gabarito)
        ruim = avaliar("ruim", {"a": _registro(x=999.0, y=2.6)}, gabarito)

        assert bom.acuracia > ruim.acuracia
        assert bom.acuracia == 1.0
        assert ruim.acuracia == 0.5

    def test_tempo_e_registrado(self):
        r = avaliar("e", {}, {}, segundos=1.5)
        assert r.segundos == 1.5


class TestSentinelaNoGabarito:
    """O gabarito escreve a sentinela como o documento; o extrator a normaliza.

    Medido: o gabarito traz `Tr` (o texto impresso), e o extrator devolve
    `traco` (o nome da sentinela no modelo). São o mesmo valor — "presente em
    quantidade desprezível" — mas a comparação textual os tratava como erro.

    O efeito é uma acurácia injustamente baixa: uma extração perfeita perdia
    ponto por causa da grafia. Pior, o erro se concentra nos campos que mais têm
    sentinela (fibra, lipídeos), sugerindo defeito sistemático onde não há.
    """

    def _comparar(self, esperado: str, sentinela):
        from parser.avaliacao import avaliar
        from parser.modelo import Campo, Evidencia, Registro

        ev = Evidencia(pagina=1, texto_bruto=esperado)
        registro = Registro(
            campos={"fibra_g": Campo[float].extraido(sentinela=sentinela, evidencia=ev)},
            fonte="d.pdf",
        )
        return avaliar("t", {"i": registro}, {"i": {"fibra_g": esperado}})

    def test_traco_do_documento_casa_com_a_sentinela(self):
        from parser.modelo import Sentinela

        for grafia in ("Tr", "tr", "TR", "traço", "traco"):
            resultado = self._comparar(grafia, Sentinela.TRACO)
            assert resultado.acuracia == 1.0, f"{grafia!r} não casou com a sentinela"

    def test_nao_analisado_casa_em_qualquer_grafia(self):
        from parser.modelo import Sentinela

        for grafia in ("NA", "na", "N/A", "nao_analisado"):
            resultado = self._comparar(grafia, Sentinela.NAO_ANALISADO)
            assert resultado.acuracia == 1.0, f"{grafia!r} não casou"

    def test_sentinela_diferente_continua_sendo_erro(self):
        """Reconhecer grafia não pode virar aceitar sentinela trocada.

        `Tr` afirma "presente em quantidade desprezível"; `NA` afirma "não
        sabemos". Confundi-las corrompe qualquer soma a jusante (ADR-0004).
        """
        from parser.modelo import Sentinela

        assert self._comparar("Tr", Sentinela.NAO_ANALISADO).acuracia == 0.0

    def test_sentinela_nao_casa_com_numero(self):
        """`Tr` não é zero, e nunca pode ser aceito como tal."""
        from parser.modelo import Sentinela

        assert self._comparar("0", Sentinela.TRACO).acuracia == 0.0
