"""Interface de linha de comando.

Estava com **zero cobertura**, e foi assim que um defeito sério passou: o script
`experimentos/scripts/2-rodar-experimento.ps1` chama `parser.cli experimento`, e
esse comando nunca existiu. O script quebraria na máquina de terceiro, no passo
principal, com "invalid choice: 'experimento'".

O teste que mais importa aqui é o que compara **o que os scripts chamam** com o
que a CLI oferece. Documentação e script podem prometer o que quiserem; só o
código diz o que existe.

Nada aqui processa documento de verdade: o que se verifica é a fiação — que os
comandos existam, que as opções cheguem, e que erro de usuário vire mensagem e
código de saída em vez de rastreio de pilha.
"""

import re
from pathlib import Path

import pytest

from parser.cli import main

RAIZ = Path(__file__).resolve().parents[1]
SCRIPTS = RAIZ / "experimentos" / "scripts"


def _comandos_da_cli() -> set[str]:
    """Os subcomandos que a CLI realmente aceita."""
    with pytest.raises(SystemExit):
        main(["--help"])
    # `--help` sai antes de listar; a lista vem do próprio argparse via erro.
    with pytest.raises(SystemExit) as saida:
        main(["comando-que-nao-existe"])
    assert saida.value.code != 0
    return _comandos_declarados()


def _comandos_declarados() -> set[str]:
    fonte = (RAIZ / "src" / "parser" / "cli.py").read_text(encoding="utf-8")
    return set(re.findall(r'add_parser\(\s*"([a-z-]+)"', fonte))


class TestContratoComOsScripts:
    """O que os scripts chamam tem de existir na CLI.

    Sem esta verificação, um comando removido ou nunca implementado só aparece na
    máquina de quem for rodar — e a mensagem do argparse não sugere que o defeito
    está no script.
    """

    def test_todo_comando_chamado_por_script_existe(self):
        disponiveis = _comandos_declarados()
        chamados = set()

        for script in SCRIPTS.glob("*.ps1"):
            texto = script.read_text(encoding="utf-8-sig")
            for achado in re.findall(r'"-m",\s*"parser\.cli",\s*"([a-z-]+)"', texto):
                chamados.add(achado)
            for achado in re.findall(r"parser\.cli\s+([a-z-]+)", texto):
                chamados.add(achado)

        faltando = chamados - disponiveis
        assert not faltando, (
            f"script chama comando inexistente: {sorted(faltando)}. "
            f"A CLI oferece: {sorted(disponiveis)}"
        )

    def test_toda_opcao_passada_por_script_existe(self):
        """Opção inexistente derruba o script tão fatalmente quanto comando errado.

        O argparse rejeita `--dpi` desconhecido com código 2, e o script para no
        passo principal — na máquina de terceiro, sem ninguém para depurar.
        """
        fonte = (RAIZ / "src" / "parser" / "cli.py").read_text(encoding="utf-8")
        declaradas = set(re.findall(r'add_argument\(\s*"(--[a-z-]+)"', fonte))

        usadas = set()
        for script in SCRIPTS.glob("*.ps1"):
            texto = script.read_text(encoding="utf-8-sig")
            if "parser.cli" not in texto:
                continue
            usadas.update(re.findall(r'"(--[a-z-]+)"', texto))

        faltando = usadas - declaradas
        assert not faltando, (
            f"script passa opção inexistente: {sorted(faltando)}. "
            f"A CLI aceita: {sorted(declaradas)}"
        )

    def test_a_cli_oferece_os_comandos_documentados(self):
        """O docstring do módulo lista os comandos; a lista tem de bater."""
        fonte = (RAIZ / "src" / "parser" / "cli.py").read_text(encoding="utf-8")
        cabecalho = fonte.split('"""')[1]
        declarados = _comandos_declarados()

        for comando in declarados:
            assert comando in cabecalho, (
                f"comando {comando!r} existe e não está no cabeçalho do módulo — "
                "quem lê o arquivo não fica sabendo dele"
            )


class TestComandosBasicos:
    def test_sem_argumento_falha_pedindo_comando(self):
        with pytest.raises(SystemExit) as saida:
            main([])
        assert saida.value.code != 0

    def test_comando_desconhecido_falha(self):
        with pytest.raises(SystemExit) as saida:
            main(["inventado"])
        assert saida.value.code != 0

    def test_diagnosticar_arquivo_inexistente_nao_estoura(self, tmp_path, capsys):
        """Erro de usuário vira mensagem e código, nunca rastreio de pilha."""
        assert main(["diagnosticar", str(tmp_path / "nao-existe.pdf")]) == 2
        assert capsys.readouterr().err.strip()

    def test_calibrar_arquivo_inexistente_nao_estoura(self, tmp_path, capsys):
        assert main(["calibrar", str(tmp_path / "nao-existe.pdf")]) == 2
        assert capsys.readouterr().err.strip()

    def test_ingerir_pasta_inexistente_nao_estoura(self, tmp_path, capsys):
        assert main(["ingerir", str(tmp_path / "nao-existe")]) == 2
        assert capsys.readouterr().err.strip()

    def test_perfil_invalido_vira_mensagem(self, tmp_path, capsys):
        perfil = tmp_path / "p.json"
        perfil.write_text("{ isto nao e json", encoding="utf-8")

        assert main(["ingerir", str(tmp_path), "--perfil", str(perfil)]) == 2
        assert "perfil" in capsys.readouterr().err.lower()


class TestIngestao:
    def test_pasta_vazia_roda_e_relata(self, tmp_path, capsys):
        entrada = tmp_path / "vazia"
        entrada.mkdir()

        assert main(["ingerir", str(entrada)]) == 0
        assert "0" in capsys.readouterr().out

    def test_perfil_com_mapeamento_ambiguo_vira_mensagem(self, tmp_path, capsys):
        import json

        entrada = tmp_path / "e"
        entrada.mkdir()
        perfil = tmp_path / "p.json"
        perfil.write_text(
            json.dumps(
                {
                    "nome": "t",
                    "rotas": {},
                    "mapeamento": {"a": ["Rótulo X"], "b": ["Rótulo X"]},
                }
            ),
            encoding="utf-8",
        )

        assert main(["ingerir", str(entrada), "--perfil", str(perfil)]) == 2
        erro = capsys.readouterr().err
        assert "perfil" in erro.lower()
        assert "Rótulo X" in erro
