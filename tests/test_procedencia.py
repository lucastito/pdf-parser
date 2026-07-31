"""Procedência: o que torna duas rodadas confrontáveis — ou não.

Este módulo não tinha teste, e decide se uma comparação entre máquinas é
legítima. Duas rodadas com versões diferentes do servidor de inferência não são
comparáveis, e sem registro isso passaria em silêncio (ADR-0019).

A memória de vídeo é o outro ponto sensível: a interface padrão do Windows
reporta o campo em 32 bits, e uma placa de 12 GB aparece como 4 GB. O valor não
é aproximado — é truncado no teto, e um script que dimensionasse modelo por ele
mandaria a máquina grande rodar como pequena.
"""

from parser.procedencia import Ambiente, versao_do_servidor


class TestVersaoDoServidor:
    """Versões diferentes entre máquinas invalidam a comparação.

    Não é hipótese: mudanças no servidor alteram padrões de contexto e alocação
    de memória — exatamente o que este projeto acabou de descobrir ser decisivo
    (ADR-0018).
    """

    def test_extrai_a_versao_do_servidor(self):
        def falso(url, timeout):
            return {"version": "0.12.11"}

        assert versao_do_servidor(consultar=falso) == "0.12.11"

    def test_servidor_ausente_nao_quebra_a_rodada(self):
        """Rodada só com estratégias determinísticas não precisa do servidor."""

        def falha(url, timeout):
            raise OSError("conexão recusada")

        assert versao_do_servidor(consultar=falha) is None

    def test_resposta_sem_versao_nao_inventa_valor(self):
        def vazio(url, timeout):
            return {}

        assert versao_do_servidor(consultar=vazio) is None


class TestAmbiente:
    """O que toda rodada registra."""

    def test_levanta_sem_consultar_o_servidor(self):
        """Identificar a máquina não pode depender de rede."""
        ambiente = Ambiente.levantar(consultar_modelos=False)

        assert ambiente.maquina
        assert ambiente.sistema
        assert ambiente.python
        assert ambiente.modelos == []

    def test_carrega_os_campos_que_a_comparacao_exige(self):
        """ADR-0013 lista o que sem o quê nada é confrontável depois."""
        ambiente = Ambiente.levantar(consultar_modelos=False)

        for campo in ("maquina", "sistema", "processador", "python", "data_utc"):
            assert getattr(ambiente, campo) is not None, f"{campo} ausente"

    def test_registra_versao_do_servidor_como_campo(self):
        """Existir como campo é o que importa: ausente vira None, não some.

        Um campo que só aparece quando há valor faz a diferença entre "não foi
        medido" e "não havia servidor" desaparecer do registro.
        """
        ambiente = Ambiente.levantar(consultar_modelos=False)

        assert hasattr(ambiente, "versao_do_servidor")

    def test_serializa_com_a_versao(self):
        from dataclasses import asdict

        dados = asdict(Ambiente.levantar(consultar_modelos=False))

        assert "versao_do_servidor" in dados
