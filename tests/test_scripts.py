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


class TestGuardaDeConfidencialidade:
    """A guarda precisa distinguir palavra comum de nome de produto.

    Um termo restrito curto que também é palavra comum bloqueia trabalho
    legítimo: o dado nutricional "Cereais, milho, flocos, com sal" batia com um
    nome de produto por coincidência de letras, e o commit dos dados brutos do
    experimento ficava travado.

    A correção não é abrir exceção para cada variante — texto extraído de PDF vem
    fragmentado e as variantes são infinitas. É tornar o termo restrito
    **específico**: o que identifica o cliente é a combinação com o nome do
    produto, não a palavra sozinha.

    Os casos que **devem** bloquear são lidos da própria denylist, que é ignorada
    pelo git. Escrevê-los aqui seria escrever o segredo num arquivo versionado —
    e a guarda, corretamente, recusaria o commit deste arquivo.
    """

    def _verificar(self, texto: str) -> int:
        import subprocess
        import tempfile

        raiz = _PASTA.parent.parent
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as arquivo:
            arquivo.write(texto)
            caminho = arquivo.name
        try:
            return subprocess.run(
                ["python", str(raiz / ".githooks" / "verificar.py"), "mensagem", caminho],
                capture_output=True,
                text=True,
                cwd=raiz,
            ).returncode
        finally:
            Path(caminho).unlink(missing_ok=True)

    def _termos_restritos(self) -> list[str]:
        lista = _PASTA.parent.parent / ".githooks" / "denylist.txt"
        if not lista.exists():
            pytest.skip("denylist.txt ausente — guarda não configurada neste clone")
        return [
            linha.strip()
            for linha in lista.read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.lstrip().startswith("#")
        ]

    @pytest.mark.parametrize(
        "texto",
        [
            "21 Cereais, milho, flocos, com sal",
            "Aveia, flocos, crua",
            "22 | Cereais, milh | o, flocos, se | m sal",
            "flocos de milho no cafe da manha",
            "Farinha, de milho, amarela",
        ],
    )
    def test_alimento_nao_e_bloqueado(self, texto: str):
        """Dado nutricional é domínio livre e não pode travar o trabalho."""
        assert self._verificar(texto) == 0, (
            f"dado nutricional legítimo bloqueado: {texto!r}. "
            "Termo restrito genérico demais trava trabalho honesto."
        )

    def test_todo_termo_da_denylist_e_bloqueado(self):
        """A outra direção, e a que mais importa.

        Verificar só que alimento passa seria perigoso: uma guarda que nunca
        bloqueia passaria nesse teste e não protegeria nada.
        """
        passaram = [
            termo
            for termo in self._termos_restritos()
            if self._verificar(f"integracao com {termo} no modulo") == 0
        ]
        assert not passaram, (
            f"{len(passaram)} termo(s) restrito(s) passaram pela guarda. "
            "Tornar um termo específico não pode virar deixar passar."
        )

    def test_nenhum_termo_bloqueia_vocabulario_legitimo(self):
        """O risco real não é o termo ser curto — é ele ser palavra comum.

        Foi o caso do dado nutricional: um termo genérico travou o commit dos
        dados brutos do experimento. Um termo curto mas específico (uma sigla,
        por exemplo) não causa esse problema.

        Este teste mede o que importa: se algum termo restrito bate contra o
        vocabulário normal deste projeto. É a pergunta que o comprimento só
        aproximava.
        """
        vocabulario = [
            "21 Cereais, milho, flocos, com sal",
            "Farinha, de milho, amarela",
            "operacao de leitura concluida",
            "opcao invalida no perfil",
            "download dos modelos de linguagem",
            "poder de processamento da maquina",
            "politica de retentativa do cliente",
            "extracao posicional de tabela sem grade",
            "conversao de unidade com proveniencia por campo",
            "o parser grava o resultado com procedencia",
            # Texto científico do próprio documento-caso: os métodos analíticos
            # citados na tabela nutricional. Bloquear isto impediria versionar o
            # documento que o experimento mede.
            "transferidos para eter de petroleo e eter etilico",
            "American Oil Chemists Society (AOCS)",
            "determinacao por cromatografia gasosa",
        ]
        termos = self._termos_restritos()

        colisoes = [
            (frase, termo)
            for frase in vocabulario
            for termo in termos
            if termo.lower() in frase.lower()
        ]
        assert not colisoes, (
            f"{len(colisoes)} termo(s) restrito(s) batem com vocabulário legítimo "
            f"do projeto: {[f for f, _ in colisoes]}. Termo genérico demais trava "
            "trabalho honesto — prefira a combinação que identifica o produto."
        )
