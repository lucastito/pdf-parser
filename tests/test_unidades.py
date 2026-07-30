"""Conversão de unidade de medida (RF-7, SPEC §4.3).

Existe porque RF-7 exige saída com tipo **e unidade**, e até aqui a unidade era
texto inerte dentro do rótulo: `"Energia (kcal)"` servia para desambiguar o
mapeamento e nunca para converter. O sintoma disso é `Origem.DERIVADO`, definido
e validado no modelo — com "conversão de unidade" no próprio docstring — sem que
nada no sistema o produzisse.

O que estes testes fixam, acima de tudo, é a **agnosticidade**: o núcleo sabe
converter e não sabe que "kcal" existe. Toda unidade citada aqui chega por perfil,
como chegaria a unidade de um documento de qualquer outro contexto.
"""

import pytest

from parser.modelo import Campo, Evidencia, Origem, Registro, Sentinela
from parser.unidades import (
    ConversaoImpossivel,
    Conversor,
    UnidadeDesconhecida,
)

EV = Evidencia(pagina=3, texto_bruto="124", bbox=(10.0, 20.0, 30.0, 40.0))


def _registro(campos: dict[str, Campo]) -> Registro:
    return Registro(campos=campos, fonte="documento.pdf")


def _extraido(valor: float, confianca: float = 1.0) -> Campo:
    return Campo[float].extraido(valor=valor, evidencia=EV, confianca=confianca)


class TestConversao:
    """U1 — converter a unidade que o perfil declarar."""

    def test_converte_para_a_unidade_alvo_declarada(self):
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        saida = conversor.aplicar(_registro({"energia": _extraido(1000.0)}))
        assert saida.campos["energia"].valor == pytest.approx(4184.0, rel=0.01)

    def test_converte_massa(self):
        """Nada no conversor é específico de energia."""
        conversor = Conversor({"massa": {"de": "g", "para": "mg"}})
        saida = conversor.aplicar(_registro({"massa": _extraido(2.5)}))
        assert saida.campos["massa"].valor == pytest.approx(2500.0)

    def test_unidade_igual_a_alvo_nao_altera_o_valor(self):
        conversor = Conversor({"massa": {"de": "g", "para": "g"}})
        saida = conversor.aplicar(_registro({"massa": _extraido(2.5)}))
        assert saida.campos["massa"].valor == pytest.approx(2.5)


class TestProveniencia:
    """U2 — o campo convertido conta que foi convertido."""

    def test_campo_convertido_vira_derivado(self):
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        saida = conversor.aplicar(_registro({"energia": _extraido(100.0)}))
        assert saida.campos["energia"].origem is Origem.DERIVADO

    def test_preserva_a_evidencia_do_valor_original(self):
        """A auditoria tem de chegar ao texto bruto no documento."""
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        saida = conversor.aplicar(_registro({"energia": _extraido(100.0)}))
        evidencia = saida.campos["energia"].evidencia
        assert evidencia is not None
        assert evidencia.texto_bruto == "124"
        assert evidencia.pagina == 3

    def test_propaga_a_confianca_sem_eleva_la(self):
        """Converter não acrescenta conhecimento."""
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        saida = conversor.aplicar(_registro({"energia": _extraido(100.0, confianca=0.6)}))
        assert saida.campos["energia"].confianca == pytest.approx(0.6)


class TestFalhaAlto:
    """U3 — converter errado em silêncio é o pior desfecho possível."""

    def test_dimensao_incompativel_falha_na_construcao(self):
        """Falha ao construir, não ao aplicar: é erro de perfil.

        Descobri-lo na carga custa um erro imediato; descobri-lo na aplicação
        custa um lote de 164 páginas processado até o campo aparecer.
        """
        with pytest.raises(ConversaoImpossivel) as erro:
            Conversor({"proteina": {"de": "g", "para": "kcal"}})
        assert "proteina" in str(erro.value)

    def test_valor_nao_numerico_falha_ao_aplicar(self):
        """O que só se descobre com o dado na mão falha na aplicação."""
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        campo = Campo[str].extraido(valor="cento e vinte", evidencia=EV)
        with pytest.raises(ConversaoImpossivel) as erro:
            conversor.aplicar(_registro({"energia": campo}))
        assert "energia" in str(erro.value)

    def test_unidade_desconhecida_falha_alto(self):
        with pytest.raises(UnidadeDesconhecida) as erro:
            Conversor({"x": {"de": "quilogrelo", "para": "g"}})
        assert "quilogrelo" in str(erro.value)

    def test_regra_incompleta_falha_alto(self):
        with pytest.raises(UnidadeDesconhecida):
            Conversor({"x": {"para": "g"}})


class TestAtravessamIntactos:
    """U4 e U5 — o que não se converte não pode ser corrompido."""

    def test_sentinela_nao_se_converte(self):
        """`Tr` em grama continua `Tr`: não há número a multiplicar."""
        campo = Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV)
        conversor = Conversor({"fibra": {"de": "g", "para": "mg"}})
        saida = conversor.aplicar(_registro({"fibra": campo}))
        assert saida.campos["fibra"].sentinela is Sentinela.TRACO
        assert saida.campos["fibra"].origem is Origem.EXTRAIDO

    def test_campo_ausente_continua_ausente(self):
        conversor = Conversor({"fibra": {"de": "g", "para": "mg"}})
        saida = conversor.aplicar(_registro({"fibra": Campo.ausente()}))
        assert saida.campos["fibra"].origem is Origem.AUSENTE
        assert saida.campos["fibra"].valor is None

    def test_campo_sem_regra_passa_intacto(self):
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        saida = conversor.aplicar(_registro({"proteina": _extraido(2.6)}))
        assert saida.campos["proteina"].valor == pytest.approx(2.6)
        assert saida.campos["proteina"].origem is Origem.EXTRAIDO

    def test_conversor_vazio_devolve_o_registro_identico(self):
        """Sem unidade-alvo declarada, nenhuma medição anterior muda de valor."""
        entrada = _registro({"energia": _extraido(124.0), "proteina": _extraido(2.6)})
        saida = Conversor({}).aplicar(entrada)
        assert saida == entrada

    def test_identificador_nao_e_tocado(self):
        campo = Campo[str].extraido(valor="Arroz", evidencia=EV)
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        saida = conversor.aplicar(_registro({"identificador": campo}))
        assert saida.campos["identificador"].valor == "Arroz"


class TestLote:
    def test_aplica_todos_preserva_a_ordem(self):
        conversor = Conversor({"energia": {"de": "kcal", "para": "kJ"}})
        registros = [_registro({"energia": _extraido(v)}) for v in (100.0, 200.0)]
        saida = conversor.aplicar_todos(registros)
        assert [r.campos["energia"].valor for r in saida] == pytest.approx(
            [418.4, 836.8], rel=0.01
        )


class TestAgnosticidade:
    """U6 — o núcleo não pode conhecer unidade de domínio algum."""

    def test_conversor_nao_traz_unidade_embutida(self):
        """Toda unidade chega por configuração, nunca por padrão no código."""
        assert Conversor({}).regras == {}

    def test_de_perfil_le_a_tabela_declarada(self):
        from parser.configuracao import Perfil

        perfil = Perfil(nome="x", unidades={"energia": {"de": "kcal", "para": "kJ"}})
        conversor = Conversor.de_perfil(perfil)
        saida = conversor.aplicar(_registro({"energia": _extraido(1000.0)}))
        assert saida.campos["energia"].valor == pytest.approx(4184.0, rel=0.01)

    def test_perfil_sem_unidades_produz_conversor_inerte(self):
        from parser.configuracao import Perfil

        conversor = Conversor.de_perfil(Perfil(nome="x"))
        entrada = _registro({"energia": _extraido(124.0)})
        assert conversor.aplicar(entrada) == entrada
