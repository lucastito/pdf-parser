"""Arnês de medição: garante que um número medido seja confiável.

Existe por uma falha real deste projeto. Duas medições foram deixadas rodando ao
mesmo tempo, na mesma máquina. Elas disputaram o mesmo processador e cada uma
inflou o tempo da outra — os segundos das duas viraram lixo, e não havia nada no
resultado que denunciasse isso. Quem lesse os números depois não teria como saber.

O projeto inteiro se apoia em comparar tempos (ADR-0005). Uma medição que não
pode ser confrontada com outra não vale o custo de tê-la feito.

O que o arnês garante, e que estes testes protegem:

**Exclusão mútua.** Duas medições não rodam ao mesmo tempo na mesma máquina. A
segunda falha alto em vez de contaminar as duas.

**Procedência gravada junto do número.** Máquina, modelo, parâmetros e data saem
no mesmo arquivo do resultado. Número sem contexto é inútil semanas depois.

**Condição declarada.** Se havia outra carga na máquina, isso é registrado — um
tempo medido com a máquina ocupada não é comparável com um medido em máquina
ociosa, e a diferença tem de ser visível.
"""

import json

import pytest

from parser.medicao import (
    MedicaoEmAndamento,
    Medicao,
    travar,
)


class TestExclusaoMutua:
    """Duas medições simultâneas contaminam as duas — a segunda tem de falhar."""

    def test_segunda_medicao_simultanea_falha(self, tmp_path):
        with travar(tmp_path / "trava"):
            with pytest.raises(MedicaoEmAndamento):
                with travar(tmp_path / "trava"):
                    pass

    def test_trava_libera_ao_terminar(self, tmp_path):
        with travar(tmp_path / "trava"):
            pass
        # Não deve levantar: a primeira terminou.
        with travar(tmp_path / "trava"):
            pass

    def test_trava_libera_mesmo_com_erro(self, tmp_path):
        """Medição que falha no meio não pode deixar a máquina travada."""
        with pytest.raises(ValueError):
            with travar(tmp_path / "trava"):
                raise ValueError("falha no meio da medição")

        with travar(tmp_path / "trava"):
            pass

    def test_mensagem_diz_o_que_esta_rodando(self, tmp_path):
        with travar(tmp_path / "trava", descricao="degraus do modelo de visão"):
            with pytest.raises(MedicaoEmAndamento) as erro:
                with travar(tmp_path / "trava"):
                    pass

        assert "degraus do modelo de visão" in str(erro.value)


class TestProcedencia:
    """Número sem contexto é inútil semanas depois."""

    def test_resultado_carrega_maquina_e_data(self, tmp_path):
        medicao = Medicao(nome="teste", raiz=tmp_path)
        with medicao:
            medicao.registrar("caso-a", {"segundos": 1.0})

        dados = json.loads((tmp_path / "teste.json").read_text(encoding="utf-8"))
        assert dados["ambiente"]["maquina"]
        assert dados["quando"]
        assert dados["nome"] == "teste"

    def test_resultado_carrega_os_parametros_declarados(self, tmp_path):
        """Sem os parâmetros, duas rodadas parecem comparáveis e não são."""
        medicao = Medicao(
            nome="teste", raiz=tmp_path, parametros={"modelo": "m:4b", "dpi": 150}
        )
        with medicao:
            medicao.registrar("caso-a", {"segundos": 1.0})

        dados = json.loads((tmp_path / "teste.json").read_text(encoding="utf-8"))
        assert dados["parametros"]["modelo"] == "m:4b"
        assert dados["parametros"]["dpi"] == 150

    def test_cada_caso_guarda_o_que_foi_medido(self, tmp_path):
        medicao = Medicao(nome="teste", raiz=tmp_path)
        with medicao:
            medicao.registrar("caso-a", {"segundos": 1.5, "tokens": 10})
            medicao.registrar("caso-b", {"segundos": 2.5, "tokens": 20})

        dados = json.loads((tmp_path / "teste.json").read_text(encoding="utf-8"))
        assert len(dados["casos"]) == 2
        assert dados["casos"][0]["nome"] == "caso-a"
        assert dados["casos"][0]["segundos"] == 1.5

    def test_grava_mesmo_se_a_medicao_falhar_no_meio(self, tmp_path):
        """O que já foi medido não pode se perder por causa do que faltou."""
        medicao = Medicao(nome="teste", raiz=tmp_path)
        with pytest.raises(RuntimeError):
            with medicao:
                medicao.registrar("caso-a", {"segundos": 1.0})
                raise RuntimeError("servidor caiu")

        dados = json.loads((tmp_path / "teste.json").read_text(encoding="utf-8"))
        assert len(dados["casos"]) == 1
        assert dados["interrompida"] is True


class TestCondicaoDaMaquina:
    """Tempo medido com a máquina ocupada não é comparável com máquina ociosa."""

    def test_registra_a_carga_no_inicio(self, tmp_path):
        medicao = Medicao(nome="teste", raiz=tmp_path)
        with medicao:
            medicao.registrar("caso-a", {"segundos": 1.0})

        dados = json.loads((tmp_path / "teste.json").read_text(encoding="utf-8"))
        assert "condicao" in dados
        assert "ram_livre_gb" in dados["condicao"]

    def test_medicao_sem_caso_algum_ainda_grava_o_contexto(self, tmp_path):
        """Rodada que não mediu nada é resultado: diz que a tentativa aconteceu."""
        medicao = Medicao(nome="vazia", raiz=tmp_path)
        with medicao:
            pass

        dados = json.loads((tmp_path / "vazia.json").read_text(encoding="utf-8"))
        assert dados["casos"] == []
        assert dados["ambiente"]["maquina"]


class TestReprodutibilidade:
    def test_nome_do_arquivo_vem_do_nome_da_medicao(self, tmp_path):
        with Medicao(nome="degraus-visao", raiz=tmp_path):
            pass
        assert (tmp_path / "degraus-visao.json").exists()

    def test_rodada_nova_nao_apaga_a_anterior(self, tmp_path):
        """Sobrescrever resultado apaga a evidência de que algo mudou."""
        with Medicao(nome="teste", raiz=tmp_path) as primeira:
            primeira.registrar("a", {"segundos": 1.0})
        with Medicao(nome="teste", raiz=tmp_path) as segunda:
            segunda.registrar("a", {"segundos": 2.0})

        anteriores = list(tmp_path.glob("teste.*.json"))
        assert anteriores, "a rodada anterior foi perdida"
