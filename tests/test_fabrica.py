"""Montagem de estratégias a partir do perfil.

Este módulo estava com **zero cobertura** — e é o único lugar que sabe traduzir
nome de rota em classe. Sem teste aqui, um perfil válido podia deixar de montar
sem que nada acusasse até alguém rodar a CLI.

Foi assim que apareceu a divergência do padrão de resolução: `Rota` criado em
código ficava com dpi 0 e a rota de visão morria com "dpi deve ser positivo",
enquanto o mesmo perfil vindo de JSON funcionava.

Nada aqui contacta servidor nem lê documento: montar é só construir o objeto.
"""

import pytest

from parser.configuracao import ConfiguracaoInvalida, Perfil, Rota
from parser.fabrica import ROTAS, montar_extrator, montar_todas
from parser.portas import Extrator


def _perfil(**rotas: Rota) -> Perfil:
    return Perfil(nome="teste", documento="documento.pdf", rotas=rotas)


LAYOUT = {
    "x_rotulos": [110.0, 160.0],
    "x_unidades": [160.0, 200.0],
    "x_valores_min": 200.0,
    "y_identificadores_min": 550.0,
}


class TestMontagem:
    def test_toda_rota_conhecida_tem_montador(self):
        from parser.configuracao import ROTAS_CONHECIDAS

        assert set(ROTAS) == set(ROTAS_CONHECIDAS), (
            "rota declarável no perfil sem montador — ou o contrário — falharia "
            "só em execução"
        )

    def test_monta_posicional_com_layout(self):
        perfil = _perfil(posicional=Rota(nome="posicional", layout=LAYOUT))
        assert isinstance(montar_extrator(perfil, "posicional"), Extrator)

    def test_posicional_sem_layout_falha_claro(self):
        perfil = _perfil(posicional=Rota(nome="posicional"))
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(perfil, "posicional")
        assert "layout" in str(erro.value)

    def test_layout_incompleto_nomeia_o_que_falta(self):
        perfil = _perfil(posicional=Rota(nome="posicional", layout={"x_rotulos": [1.0, 2.0]}))
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(perfil, "posicional")
        assert "x_valores_min" in str(erro.value)

    def test_rota_sem_implementacao_falha_claro(self):
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(_perfil(), "inexistente")
        assert "inexistente" in str(erro.value)

    def test_rota_nao_declarada_no_perfil_falha_claro(self):
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(_perfil(), "posicional")
        assert "posicional" in str(erro.value)


class TestRotasDeModelo:
    """As rotas por modelo carregam parâmetros que são variáveis de experimento."""

    def _perfil_vlm(self, **extras) -> Perfil:
        return _perfil(
            vlm=Rota(nome="vlm", modelo="m:4b", extras={"campos": ["a", "b"], **extras})
        )

    def test_aplica_a_resolucao_padrao_da_rota(self):
        """Sem dpi declarado, vale o padrão medido — não zero."""
        from parser.configuracao import DEFAULTS

        extrator = montar_extrator(self._perfil_vlm(), "vlm")
        assert extrator.dpi == DEFAULTS["vlm.dpi"]["valor"]

    def test_rota_de_modelo_exige_campos(self):
        perfil = _perfil(vlm=Rota(nome="vlm", modelo="m:4b"))
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(perfil, "vlm")
        assert "campos" in str(erro.value)

    def test_rota_de_modelo_exige_modelo(self):
        perfil = _perfil(vlm=Rota(nome="vlm", extras={"campos": ["a"]}))
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(perfil, "vlm")
        assert "modelo" in str(erro.value)

    def test_degrau_maximo_do_perfil_chega_ao_extrator(self):
        from parser.degraus import Degrau

        extrator = montar_extrator(self._perfil_vlm(degrau_maximo="json-livre"), "vlm")
        assert extrator.saida.degrau_maximo is Degrau.JSON_LIVRE

    def test_degrau_maximo_desconhecido_falha_nomeando_os_validos(self):
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(self._perfil_vlm(degrau_maximo="inventado"), "vlm")
        assert "inventado" in str(erro.value)
        assert "esquema-completo" in str(erro.value)

    def test_sem_degrau_declarado_a_descida_fica_livre(self):
        assert montar_extrator(self._perfil_vlm(), "vlm").saida.degrau_maximo is None

    def test_raciocinar_do_perfil_chega_ao_extrator(self):
        assert montar_extrator(self._perfil_vlm(raciocinar=True), "vlm").saida.raciocinar
        assert not montar_extrator(self._perfil_vlm(), "vlm").saida.raciocinar

    def test_documento_ausente_falha_claro(self):
        perfil = Perfil(
            nome="t", rotas={"vlm": Rota(nome="vlm", modelo="m:4b", extras={"campos": ["a"]})}
        )
        with pytest.raises(ConfiguracaoInvalida) as erro:
            montar_extrator(perfil, "vlm")
        assert "documento" in str(erro.value)


class TestMontarTodas:
    def test_monta_as_rotas_declaradas(self):
        perfil = _perfil(
            posicional=Rota(nome="posicional", layout=LAYOUT), linear=Rota(nome="linear")
        )
        assert set(montar_todas(perfil)) == {"posicional", "linear"}

    def test_pode_excluir_as_rotas_de_modelo(self):
        """Máquina sem servidor de inferência ainda roda o resto do experimento."""
        perfil = _perfil(
            posicional=Rota(nome="posicional", layout=LAYOUT),
            vlm=Rota(nome="vlm", modelo="m:4b", extras={"campos": ["a"]}),
        )
        assert set(montar_todas(perfil, incluir_modelos=False)) == {"posicional"}

    def test_rota_que_nao_monta_e_omitida_sem_derrubar_as_outras(self, capsys):
        """Uma dependência ausente não pode custar o experimento inteiro."""
        perfil = _perfil(
            posicional=Rota(nome="posicional", layout=LAYOUT),
            camelot=Rota(nome="camelot"),
            vlm=Rota(nome="vlm"),  # sem modelo nem campos: não monta
        )
        montadas = montar_todas(perfil)

        assert "posicional" in montadas
        assert "vlm" not in montadas
        assert "vlm" in capsys.readouterr().out, "a omissão precisa ser relatada"
