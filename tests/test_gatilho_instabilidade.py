"""O gatilho de −1.2 (`_gatilho_instabilidade.py`) precisa provar que funciona
contra um caso real de contaminação entre testes — não só existir.

Monta um projeto sintético de 2 arquivos onde um suja um módulo compartilhado
e o outro só falha se essa sujeira sobreviver — exatamente o padrão que as
auditorias de 02/08 relataram ("passa isolado, falha no conjunto"). Roda como
subprocesso, porque o gatilho reexecuta o teste falho num processo novo, e
isso não pode contaminar (nem ser contaminado pel)o processo desta suíte.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ_DESTE_REPO = Path(__file__).resolve().parents[1]
PASTA_TESTS = RAIZ_DESTE_REPO / "tests"


def _montar_projeto_com_contaminacao(tmp_path):
    (tmp_path / "conftest.py").write_text(
        'pytest_plugins = ["_gatilho_instabilidade"]\n', encoding="utf-8"
    )
    (tmp_path / "_estado_compartilhado.py").write_text("valor = 'limpo'\n", encoding="utf-8")
    (tmp_path / "test_a_polui.py").write_text(
        "import _estado_compartilhado as estado\n\n\n"
        "def test_polui():\n"
        "    estado.valor = 'poluido'\n",
        encoding="utf-8",
    )
    (tmp_path / "test_b_le.py").write_text(
        "import _estado_compartilhado as estado\n\n\n"
        "def test_falha_se_poluido():\n"
        "    assert estado.valor == 'limpo'\n",
        encoding="utf-8",
    )


def _rodar_suite_sintetica(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PASTA_TESTS)
    env["PARSER_LIMIAR_DIAGNOSTICO"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestGatilhoDeInstabilidade:
    def test_captura_evidencia_quando_um_teste_contamina_o_outro(self, tmp_path):
        _montar_projeto_com_contaminacao(tmp_path)

        resultado = _rodar_suite_sintetica(tmp_path)

        assert resultado.returncode != 0, (
            "a suíte sintética deveria falhar (contaminação entre testes); "
            f"saída:\n{resultado.stdout}"
        )

        arquivos = list((tmp_path / "diagnostico-instabilidade").glob("*.json"))
        assert arquivos, "nenhuma evidência foi gravada para a falha"

        dados = json.loads(arquivos[0].read_text(encoding="utf-8"))
        assert "test_falha_se_poluido" in dados["teste_que_falhou"]

    def test_a_ordem_registrada_mostra_quem_contaminou_antes(self, tmp_path):
        _montar_projeto_com_contaminacao(tmp_path)
        _rodar_suite_sintetica(tmp_path)

        caminho = next((tmp_path / "diagnostico-instabilidade").glob("*.json"))
        dados = json.loads(caminho.read_text(encoding="utf-8"))

        ordem = dados["ordem_dos_testes_ate_aqui"]
        indice_poluidor = next(i for i, n in enumerate(ordem) if "test_polui" in n)
        indice_falho = next(i for i, n in enumerate(ordem) if "test_falha_se_poluido" in n)
        assert (
            indice_poluidor < indice_falho
        ), "a ordem gravada não mostra o teste que contaminou rodando antes do que falhou"

    def test_confirma_o_padrao_das_auditorias_passa_isolado_falha_no_conjunto(self, tmp_path):
        """O sinal mais importante: o mesmo teste, sozinho, passa. É
        exatamente o que as duas auditorias de 02/08 relataram."""
        _montar_projeto_com_contaminacao(tmp_path)
        _rodar_suite_sintetica(tmp_path)

        caminho = next((tmp_path / "diagnostico-instabilidade").glob("*.json"))
        dados = json.loads(caminho.read_text(encoding="utf-8"))

        assert dados["passou_isolado"] is True

    def test_nao_dispara_em_execucao_pequena_abaixo_do_limiar(self, tmp_path):
        """TDD normal roda um arquivo só — não pode gerar reexecução nem
        arquivo de diagnóstico a cada teste vermelho de propósito."""
        (tmp_path / "conftest.py").write_text(
            'pytest_plugins = ["_gatilho_instabilidade"]\n', encoding="utf-8"
        )
        (tmp_path / "test_falha_de_proposito.py").write_text(
            "def test_x():\n    assert False\n", encoding="utf-8"
        )

        env = dict(os.environ)
        env["PYTHONPATH"] = str(PASTA_TESTS)
        # Sem PARSER_LIMIAR_DIAGNOSTICO: usa o padrão (100), bem acima de 1 teste.
        subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q"],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert not (tmp_path / "diagnostico-instabilidade").exists()

    def test_nao_reexecuta_a_si_mesmo(self, tmp_path):
        """A reexecução isolada roda com a variável de guarda ligada — se ela
        não bloqueasse, uma falha reexecutada geraria outra reexecução, sem
        fim, cada uma abrindo um processo novo."""
        _montar_projeto_com_contaminacao(tmp_path)

        resultado = _rodar_suite_sintetica(tmp_path)

        # Duas falhas no total: a original (no conjunto) e nada mais — a
        # reexecução isolada roda num processo à parte, fora da contagem
        # desta suíte, e por sua vez não deveria produzir um segundo arquivo.
        arquivos = list((tmp_path / "diagnostico-instabilidade").glob("*.json"))
        assert len(arquivos) == 1, f"esperado 1 arquivo de diagnóstico, achou {len(arquivos)}"
        assert resultado.returncode != 0
