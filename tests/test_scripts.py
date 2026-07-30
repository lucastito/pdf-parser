"""Os scripts de execução em outra máquina precisam ser executáveis lá.

Estes testes existem por uma falha real: os dois scripts estavam gravados em
UTF-8 **sem BOM**, e o Windows PowerShell 5.1 — o que vem instalado por padrão —
lê arquivo sem BOM usando a página de código ANSI do sistema. Toda acentuação
vira byte inválido, e o script **não compila**: falha com erro de sintaxe numa
linha que está sintaticamente correta.

O modo de falha é péssimo de diagnosticar: a mensagem aponta chave ou parêntese
desbalanceado, não encoding. E só aparece na máquina de terceiro, que é
exatamente onde não há ninguém para depurar.

Verificar isto na suíte é barato e vale por não descobrir na hora da execução.
"""

from pathlib import Path

import pytest

_PASTA = Path(__file__).resolve().parents[1] / "experimentos" / "scripts"
SCRIPTS = sorted(_PASTA.glob("*.ps1"))

BOM = b"\xef\xbb\xbf"


def test_existem_scripts_para_verificar():
    """Se a pasta mudar de lugar, os testes abaixo passariam vazios."""
    assert SCRIPTS, "nenhum script .ps1 encontrado em experimentos/scripts"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
class TestCodificacao:
    def test_tem_bom(self, script: Path):
        """Sem BOM, o PowerShell 5.1 lê como ANSI e a acentuação quebra o parser."""
        assert script.read_bytes().startswith(BOM), (
            f"{script.name} está sem BOM. O Windows PowerShell 5.1 vai lê-lo como "
            "ANSI e falhar com erro de sintaxe enganoso."
        )

    def test_e_utf8_valido(self, script: Path):
        conteudo = script.read_bytes()[len(BOM) :]
        conteudo.decode("utf-8")  # levanta UnicodeDecodeError se não for

    def test_nao_usa_operador_indisponivel_no_powershell_5(self, script: Path):
        """`&&` e `||` são erro de sintaxe no PowerShell 5.1.

        Funcionam no PowerShell 7. Como a máquina de terceiro provavelmente só tem
        o 5.1, usá-los faria o script quebrar só lá.
        """
        texto = script.read_text(encoding="utf-8-sig")
        linhas_com_erro = [
            (n, linha.strip())
            for n, linha in enumerate(texto.splitlines(), 1)
            if ("&&" in linha or "||" in linha) and not linha.strip().startswith("#")
        ]
        assert not linhas_com_erro, (
            f"{script.name} usa && ou || fora de comentário: {linhas_com_erro}. "
            "São erro de sintaxe no Windows PowerShell 5.1."
        )


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
class TestRaizDoProjeto:
    """O script precisa achar a raiz do repositório, não a pasta acima dele.

    Os dois calculavam `Split-Path -Parent $PSScriptRoot`, que a partir de
    `experimentos/scripts/` dá `experimentos/` — falta um nível. O `Set-Location`
    ia parar numa pasta sem `tests/` nem `src/`, o pytest não achava nada, e o
    script concluía "testes falharam" com a suíte inteira passando.

    O efeito é pior que travar: o script para no passo 1 com um diagnóstico
    errado, e quem for rodar vai procurar defeito no clone.
    """

    def test_sobe_dois_niveis_ate_a_raiz(self, script: Path):
        texto = script.read_text(encoding="utf-8-sig")
        assert "Split-Path -Parent (Split-Path -Parent $PSScriptRoot)" in texto, (
            f"{script.name} não sobe até a raiz do repositório. De "
            "experimentos/scripts/ são dois níveis, não um."
        )

    def test_a_raiz_calculada_contem_o_projeto(self, script: Path):
        """Confere contra a árvore real, não contra a fórmula."""
        raiz = script.parent.parent.parent
        assert (raiz / "pyproject.toml").exists()
        assert (raiz / "tests").is_dir()
        assert (raiz / "src" / "parser").is_dir()


class TestInstrucoesDeUso:
    r"""As instruções nos scripts e no README precisam ser executáveis como estão.

    Os scripts vão para a raiz do repositório antes de rodar, então o caminho a
    digitar é `.\experimentos\scripts\...`. As instruções diziam `.\scripts\...`,
    que só funcionaria de dentro de `experimentos/` — e quem seguisse ao pé da
    letra receberia "caminho não encontrado".
    """

    def _textos(self):
        raiz = _PASTA.parent.parent
        arquivos = list(_PASTA.glob("*.ps1")) + [raiz / "experimentos" / "README.md"]
        return [(a, a.read_text(encoding="utf-8-sig")) for a in arquivos if a.exists()]

    def test_instrucoes_usam_o_caminho_a_partir_da_raiz(self):
        erradas = []
        for arquivo, texto in self._textos():
            for numero, linha in enumerate(texto.splitlines(), 1):
                if r".\scripts" + "\\" in linha:
                    erradas.append(f"{arquivo.name}:{numero}")

        assert not erradas, (
            f"instrução com caminho relativo a experimentos/, não à raiz: {erradas}. "
            "Os scripts fazem Set-Location para a raiz antes de rodar."
        )

    def test_o_caminho_citado_existe_de_fato(self):
        raiz = _PASTA.parent.parent
        for nome in ("1-preparar-maquina.ps1", "2-rodar-experimento.ps1"):
            assert (raiz / "experimentos" / "scripts" / nome).exists()
