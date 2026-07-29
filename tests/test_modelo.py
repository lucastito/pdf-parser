"""Invariantes do modelo de dados — cobre V2 (todo campo carrega origem e evidência).

O que estes testes protegem: um valor nunca deve circular sem dizer de onde veio.
Se essas invariantes cederem, a métrica de taxa de inferência passa a mentir.
"""

import pytest
from pydantic import ValidationError

from parser.modelo import Campo, Evidencia, Origem, Registro, Sentinela

EV = Evidencia(pagina=1, bbox=(0.0, 0.0, 10.0, 10.0), texto_bruto="3,86")


class TestCampoAusente:
    def test_ausente_nao_carrega_valor(self):
        with pytest.raises(ValidationError, match="AUSENTE não pode carregar valor"):
            Campo[float](valor=1.0, origem=Origem.AUSENTE, confianca=0.0)

    def test_ausente_exige_confianca_zero(self):
        with pytest.raises(ValidationError, match="confianca 0.0"):
            Campo[float](origem=Origem.AUSENTE, confianca=1.0)

    def test_construtor_ausente_e_valido(self):
        campo = Campo[float].ausente()
        assert campo.valor is None
        assert campo.confianca == 0.0
        assert not campo.preenchido


class TestCampoCoerencia:
    def test_valor_e_sentinela_sao_mutuamente_exclusivos(self):
        with pytest.raises(ValidationError, match="valor e sentinela ao mesmo tempo"):
            Campo[float](
                valor=0.0,
                sentinela=Sentinela.TRACO,
                origem=Origem.EXTRAIDO,
                evidencia=EV,
            )

    def test_sem_valor_nem_sentinela_deve_ser_ausente(self):
        with pytest.raises(ValidationError, match="deve ter origem AUSENTE"):
            Campo[float](origem=Origem.EXTRAIDO, evidencia=EV)

    @pytest.mark.parametrize("origem", [Origem.EXTRAIDO, Origem.DERIVADO])
    def test_extraido_e_derivado_exigem_evidencia(self, origem):
        with pytest.raises(ValidationError, match="exige evidencia"):
            Campo[float](valor=1.0, origem=origem)

    def test_inferido_dispensa_evidencia(self):
        """Valor inferido não tem origem no documento — exigir evidência seria incoerente."""
        campo = Campo[float](valor=1.0, origem=Origem.INFERIDO, confianca=0.7)
        assert campo.evidencia is None
        assert campo.preenchido

    def test_confianca_fora_do_intervalo_e_rejeitada(self):
        with pytest.raises(ValidationError):
            Campo[float](valor=1.0, origem=Origem.EXTRAIDO, evidencia=EV, confianca=1.5)


class TestCampoSentinela:
    def test_sentinela_e_campo_preenchido(self):
        """`Tr` afirma algo: 'presente em quantidade desprezível'."""
        campo = Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV)
        assert campo.preenchido
        assert campo.valor is None
        assert campo.sentinela is Sentinela.TRACO

    def test_sentinela_nao_e_zero(self):
        traco = Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV)
        zero = Campo[float].extraido(valor=0.0, evidencia=EV)
        assert traco != zero
        assert traco.valor is not zero.valor

    def test_traco_difere_de_nao_analisado(self):
        """'Desprezível' e 'não medimos' são afirmações diferentes."""
        traco = Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV)
        na = Campo[float].extraido(sentinela=Sentinela.NAO_ANALISADO, evidencia=EV)
        assert traco != na


class TestEvidencia:
    def test_vizinhanca_e_opcional(self):
        assert Evidencia(pagina=1, texto_bruto="1,5").vizinhanca is None

    def test_vizinhanca_preserva_contexto(self):
        """Um `1,5` isolado não diz se é grama, porcentagem ou índice."""
        ev = Evidencia(pagina=1, texto_bruto="1,5", vizinhanca="0,8 1,5 2,3")
        assert ev.vizinhanca == "0,8 1,5 2,3"

    def test_texto_bruto_sobrevive_a_normalizacao(self):
        """O original tem de continuar acessível depois de qualquer limpeza."""
        campo = Campo[float].extraido(
            valor=3.86,
            evidencia=Evidencia(pagina=1, texto_bruto="3,86"),
        )
        assert campo.valor == 3.86
        assert campo.evidencia.texto_bruto == "3,86"


class TestCampoImutabilidade:
    def test_campo_e_imutavel(self):
        campo = Campo[float].extraido(valor=1.0, evidencia=EV)
        with pytest.raises(ValidationError):
            campo.valor = 2.0


class TestRegistroMetricas:
    def _registro(self, campos):
        return Registro(campos=campos, fonte="teste")

    def test_taxa_inferencia_zero_quando_tudo_extraido(self):
        reg = self._registro(
            {
                "a": Campo[float].extraido(valor=1.0, evidencia=EV),
                "b": Campo[float].extraido(valor=2.0, evidencia=EV),
            }
        )
        assert reg.taxa_inferencia == 0.0

    def test_taxa_inferencia_conta_inferido_e_derivado(self):
        reg = self._registro(
            {
                "a": Campo[float].extraido(valor=1.0, evidencia=EV),
                "b": Campo[float](valor=2.0, origem=Origem.INFERIDO, confianca=0.5),
                "c": Campo[float](valor=3.0, origem=Origem.DERIVADO, evidencia=EV),
                "d": Campo[float].extraido(valor=4.0, evidencia=EV),
            }
        )
        assert reg.taxa_inferencia == 0.5

    def test_taxa_inferencia_ignora_campos_ausentes(self):
        """Campo ausente não afirma nada; incluí-lo faria um registro vazio
        parecer bem-fundamentado."""
        reg = self._registro(
            {
                "a": Campo[float].extraido(valor=1.0, evidencia=EV),
                "b": Campo[float].ausente(),
                "c": Campo[float].ausente(),
            }
        )
        assert reg.taxa_inferencia == 0.0

    def test_taxa_inferencia_de_registro_sem_campos_preenchidos(self):
        reg = self._registro({"a": Campo[float].ausente()})
        assert reg.taxa_inferencia == 0.0

    def test_sentinela_conta_como_extraida(self):
        """A sentinela foi lida do documento, não suposta."""
        reg = self._registro(
            {"a": Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV)}
        )
        assert reg.taxa_inferencia == 0.0

    def test_cobertura(self):
        reg = self._registro(
            {
                "a": Campo[float].extraido(valor=1.0, evidencia=EV),
                "b": Campo[float].ausente(),
                "c": Campo[float].extraido(sentinela=Sentinela.NAO_ANALISADO, evidencia=EV),
                "d": Campo[float].ausente(),
            }
        )
        assert reg.cobertura == 0.5

    def test_cobertura_de_registro_vazio(self):
        assert self._registro({}).cobertura == 0.0
