"""Validação da saída tabular (SPEC §4.5).

O modelo valida campo a campo, na construção do `Registro`. O que ele não cobre é
o **conjunto**: coluna ausente, tipo divergente entre registros, lote heterogêneo.

O caso concreto que motiva o módulo está no destino CSV, que monta o cabeçalho a
partir do primeiro registro: um lote em que o segundo registro tenha um campo a
mais perde a coluna sem erro algum. É a falha muda que a spec repudia — o
extrator "roda sem erro" e grava dado incompleto.

Como toda configuração deste projeto, o esquema é declarativo e vem do perfil: o
núcleo não conhece nome de campo nem domínio.
"""

import pytest

from parser.esquema import Esquema, SaidaInvalida
from parser.modelo import Campo, Evidencia, Registro, Sentinela

EV = Evidencia(pagina=1, texto_bruto="x")

COLUNAS = {
    "identificador": {"tipo": "texto"},
    "energia_kcal": {"tipo": "numero"},
    "proteina_g": {"tipo": "numero"},
}


def _registro(campos: dict[str, Campo], fonte: str = "d.pdf") -> Registro:
    return Registro(campos=campos, fonte=fonte)


def _num(valor: float) -> Campo:
    return Campo[float].extraido(valor=valor, evidencia=EV)


def _txt(valor: str) -> Campo:
    return Campo[str].extraido(valor=valor, evidencia=EV)


def _valido() -> Registro:
    return _registro(
        {
            "identificador": _txt("Item um"),
            "energia_kcal": _num(124.0),
            "proteina_g": _num(2.6),
        }
    )


class TestAceita:
    def test_lote_conforme_passa(self):
        Esquema(COLUNAS).validar([_valido(), _valido()])

    def test_lote_vazio_passa(self):
        """Zero registro é resultado legítimo — não é violação de esquema."""
        Esquema(COLUNAS).validar([])

    def test_sentinela_satisfaz_coluna_numerica(self):
        """`Tr` é valor válido de um campo numérico, não tipo divergente."""
        registro = _registro(
            {
                "identificador": _txt("Item um"),
                "energia_kcal": Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV),
                "proteina_g": _num(2.6),
            }
        )
        Esquema(COLUNAS).validar([registro])

    def test_campo_ausente_satisfaz_coluna_declarada(self):
        """A coluna existe e está vazia — o consumidor recebe o que espera."""
        registro = _registro(
            {
                "identificador": _txt("Item um"),
                "energia_kcal": Campo.ausente(),
                "proteina_g": _num(2.6),
            }
        )
        Esquema(COLUNAS).validar([registro])


class TestRejeita:
    """T1 e T2 — o lote inválido tem de falhar antes da gravação."""

    def test_coluna_ausente_falha_nomeando_a_coluna(self):
        registro = _registro({"identificador": _txt("x"), "energia_kcal": _num(1.0)})
        with pytest.raises(SaidaInvalida) as erro:
            Esquema(COLUNAS).validar([registro])
        assert "proteina_g" in str(erro.value)

    def test_tipo_divergente_falha_nomeando_a_coluna(self):
        registro = _registro(
            {
                "identificador": _txt("x"),
                "energia_kcal": _txt("cento e vinte"),
                "proteina_g": _num(2.6),
            }
        )
        with pytest.raises(SaidaInvalida) as erro:
            Esquema(COLUNAS).validar([registro])
        assert "energia_kcal" in str(erro.value)

    def test_lote_heterogeneo_e_detectado(self):
        """O segundo registro tem campo a mais: no CSV a coluna sumiria calada."""
        segundo = _registro(
            {
                "identificador": _txt("Item dois"),
                "energia_kcal": _num(360.0),
                "proteina_g": _num(7.3),
                "sobra": _num(1.0),
            }
        )
        with pytest.raises(SaidaInvalida) as erro:
            Esquema(COLUNAS).validar([_valido(), segundo])
        assert "sobra" in str(erro.value)

    def test_mensagem_localiza_o_registro(self):
        """Falha em lote longo sem índice é falha que ninguém consegue corrigir."""
        ruim = _registro({"identificador": _txt("x")})
        with pytest.raises(SaidaInvalida) as erro:
            Esquema(COLUNAS).validar([_valido(), _valido(), ruim])
        assert "2" in str(erro.value)


class TestRestricoes:
    """O perfil pode declarar mais que tipo."""

    def test_valor_abaixo_do_minimo_falha(self):
        colunas = {
            "identificador": {"tipo": "texto"},
            "energia_kcal": {"tipo": "numero", "minimo": 0.0},
            "proteina_g": {"tipo": "numero"},
        }
        registro = _registro(
            {
                "identificador": _txt("x"),
                "energia_kcal": _num(-5.0),
                "proteina_g": _num(2.6),
            }
        )
        with pytest.raises(SaidaInvalida) as erro:
            Esquema(colunas).validar([registro])
        assert "energia_kcal" in str(erro.value)

    def test_coluna_obrigatoria_nao_pode_sair_toda_vazia(self):
        colunas = {
            "identificador": {"tipo": "texto", "obrigatorio": True},
            "energia_kcal": {"tipo": "numero"},
            "proteina_g": {"tipo": "numero"},
        }
        registro = _registro(
            {
                "identificador": Campo.ausente(),
                "energia_kcal": _num(1.0),
                "proteina_g": _num(2.6),
            }
        )
        with pytest.raises(SaidaInvalida) as erro:
            Esquema(colunas).validar([registro])
        assert "identificador" in str(erro.value)


class TestAgnosticidade:
    def test_esquema_vazio_nao_valida_nada(self):
        """Sem esquema declarado, o comportamento anterior fica intacto."""
        Esquema({}).validar([_registro({"qualquer": _num(1.0)})])

    def test_de_perfil_le_o_esquema_declarado(self):
        from parser.configuracao import Perfil

        perfil = Perfil(nome="x", esquema=COLUNAS)
        with pytest.raises(SaidaInvalida):
            Esquema.de_perfil(perfil).validar([_registro({"identificador": _txt("x")})])

    def test_perfil_sem_esquema_produz_validador_inerte(self):
        from parser.configuracao import Perfil

        Esquema.de_perfil(Perfil(nome="x")).validar([_registro({"seja_o_que_for": _num(1.0)})])
