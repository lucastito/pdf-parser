"""Configuração declarativa: perfis e prompts fora do código.

O que estes testes protegem: que a equipe que herdar o projeto possa mudar
resolução, layout, campos, modelo ou prompt **sem editar Python** — e que um
parâmetro esquecido caia num default documentado em vez de erro obscuro.

O risco oposto também é testado: configuração não pode virar depósito de opções
acopladas. Cada rota é independente, e o perfil falha na carga se estiver
inconsistente.
"""

import json

import pytest

from parser.configuracao import (
    ConfiguracaoInvalida,
    carregar_perfil,
    carregar_prompt,
)

PERFIL_MINIMO = {
    "nome": "exemplo",
    "documento": "doc.pdf",
    "rotas": {"posicional": {"layout": {"x_rotulos": [110, 133]}}},
}


def _escrever(tmp_path, dados, nome="p.json"):
    caminho = tmp_path / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


class TestCargaDePerfil:
    def test_carrega_perfil_minimo(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, PERFIL_MINIMO))
        assert p.nome == "exemplo"

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="não encontrado"):
            carregar_perfil(tmp_path / "nao-existe.json")

    def test_json_invalido_falha_claro(self, tmp_path):
        caminho = tmp_path / "ruim.json"
        caminho.write_text("{isto não é json", encoding="utf-8")
        with pytest.raises(ConfiguracaoInvalida, match="JSON"):
            carregar_perfil(caminho)

    def test_sem_nome_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="nome"):
            carregar_perfil(_escrever(tmp_path, {"rotas": {}}))

    def test_sem_rotas_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="rotas"):
            carregar_perfil(_escrever(tmp_path, {"nome": "x"}))


class TestDefaultsDocumentados:
    """Parâmetro omitido cai em default seguro, não em erro obscuro."""

    def test_resolucao_do_ocr_tem_default(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, {**PERFIL_MINIMO, "rotas": {"ocr": {}}}))
        assert p.rota("ocr").dpi == 350

    def test_resolucao_do_vlm_tem_default(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, {**PERFIL_MINIMO, "rotas": {"vlm": {}}}))
        assert p.rota("vlm").dpi == 150

    def test_tolerancia_tem_default(self, tmp_path):
        assert carregar_perfil(_escrever(tmp_path, PERFIL_MINIMO)).tolerancia == 0.01

    def test_perfil_sobrepoe_o_default(self, tmp_path):
        dados = {**PERFIL_MINIMO, "rotas": {"ocr": {"dpi": 200}}}
        assert carregar_perfil(_escrever(tmp_path, dados)).rota("ocr").dpi == 200

    def test_default_cita_a_origem_do_valor(self):
        """Um número sem procedência é um número que ninguém pode questionar."""
        from parser.configuracao import DEFAULTS

        for chave, definicao in DEFAULTS.items():
            assert definicao.get("origem"), f"{chave} sem origem documentada"


class TestExtensibilidade:
    """Modelo novo, documento novo e formato novo entram sem tocar em código."""

    def test_modelo_novo_e_so_configuracao(self, tmp_path):
        dados = {
            **PERFIL_MINIMO,
            "rotas": {"vlm": {"modelo": "modelo-que-nao-existe-ainda:8b", "dpi": 200}},
        }
        rota = carregar_perfil(_escrever(tmp_path, dados)).rota("vlm")
        assert rota.modelo == "modelo-que-nao-existe-ainda:8b"
        assert rota.dpi == 200

    def test_endereco_do_servidor_e_configuravel(self, tmp_path):
        dados = {**PERFIL_MINIMO, "rotas": {"vlm": {"url": "http://servidor:11434"}}}
        assert (
            carregar_perfil(_escrever(tmp_path, dados)).rota("vlm").url
            == "http://servidor:11434"
        )

    def test_rota_desconhecida_falha_claro(self, tmp_path):
        """Nome de rota errado é erro de digitação, e deve aparecer como tal."""
        dados = {**PERFIL_MINIMO, "rotas": {"rota-inventada": {}}}
        with pytest.raises(ConfiguracaoInvalida, match="rota-inventada"):
            carregar_perfil(_escrever(tmp_path, dados))

    def test_rotas_sao_independentes(self, tmp_path):
        """Configurar uma rota não pode afetar outra."""
        dados = {**PERFIL_MINIMO, "rotas": {"ocr": {"dpi": 400}, "vlm": {"dpi": 100}}}
        p = carregar_perfil(_escrever(tmp_path, dados))
        assert p.rota("ocr").dpi == 400
        assert p.rota("vlm").dpi == 100

    def test_rota_ausente_e_reportada(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, PERFIL_MINIMO))
        with pytest.raises(ConfiguracaoInvalida, match="ocr"):
            p.rota("ocr")


class TestPrompt:
    def test_carrega_prompt_de_arquivo(self, tmp_path):
        caminho = tmp_path / "p.md"
        caminho.write_text(
            "# Título\n\n## Instrução\n\nExtraia os itens.\n\n"
            "## Guardrails\n\n- Não estime valores.\n",
            encoding="utf-8",
        )
        p = carregar_prompt(caminho)
        assert "Extraia os itens" in p.instrucao
        assert "Não estime" in p.guardrails

    def test_instrucao_e_guardrails_viajam_juntos(self, tmp_path):
        """O texto enviado ao modelo inclui os guardrails — separá-los na hora do
        envio anularia o propósito de tê-los escrito."""
        caminho = tmp_path / "p.md"
        caminho.write_text(
            "## Instrução\n\nFaça X.\n\n## Guardrails\n\n- Não faça Y.\n", encoding="utf-8"
        )
        texto = carregar_prompt(caminho).texto()
        assert "Faça X" in texto
        assert "Não faça Y" in texto

    def test_sem_secao_de_instrucao_falha_claro(self, tmp_path):
        caminho = tmp_path / "p.md"
        caminho.write_text("# Só um título\n", encoding="utf-8")
        with pytest.raises(ConfiguracaoInvalida, match="Instrução"):
            carregar_prompt(caminho)

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="não encontrado"):
            carregar_prompt(tmp_path / "nao-existe.md")

    def test_registra_a_versao_do_prompt(self, tmp_path):
        """Comparar rodadas exige distinguir mudança de prompt de mudança de modelo."""
        caminho = tmp_path / "p.md"
        caminho.write_text(
            "## Instrução\n\nFaça X.\n\n## Histórico\n\n- v2: ajustado\n- v1: inicial\n",
            encoding="utf-8",
        )
        assert carregar_prompt(caminho).impressao_digital


class TestPerfisDoProjeto:
    """Contra os arquivos reais, não fixtures."""

    def test_perfis_existentes_carregam(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        perfis = list((raiz / "perfis").glob("*.json"))
        assert perfis, "nenhum perfil no projeto"
        for caminho in perfis:
            carregar_perfil(caminho)

    def test_prompts_existentes_carregam(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        prompts = list((raiz / "prompts").glob("*.md"))
        assert prompts, "nenhum prompt no projeto"
        for caminho in prompts:
            carregar_prompt(caminho)
