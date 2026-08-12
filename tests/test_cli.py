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


class TestVarreduraNoExperimento:
    """O comando de experimento roda todos os degraus, não só até o primeiro.

    O erro que motivou estes testes foi um nome não importado dentro da função de
    varredura — invisível porque nada a exercitava. Uma função só chamada com
    servidor de inferência no ar é uma função sem teste.
    """

    def _perfil_com_modelo(self, tmp_path, documento):
        import json

        perfil = tmp_path / "p.json"
        perfil.write_text(
            json.dumps(
                {
                    "nome": "t",
                    "documento": str(documento),
                    "rotas": {
                        "vlm": {
                            "modelo": "modelo-inexistente:0b",
                            "campos": ["identificador"],
                            "dpi": 72,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return perfil

    def _documento(self, tmp_path):
        import fitz

        caminho = tmp_path / "d.pdf"
        documento = fitz.open()
        documento.new_page().insert_text((72, 72), "texto")
        documento.save(caminho)
        documento.close()
        return caminho

    def test_varredura_roda_e_registra_mesmo_sem_servidor(self, tmp_path, capsys):
        """Servidor fora do ar é resultado do experimento, não interrupção."""
        import json

        documento = self._documento(tmp_path)
        perfil = self._perfil_com_modelo(tmp_path, documento)
        destino = tmp_path / "res"

        codigo = main(
            [
                "experimento",
                "--perfil",
                str(perfil),
                "--destino",
                str(destino),
            ]
        )

        assert codigo in (0, 1)
        resumos = list(destino.glob("*/resumo.json"))
        assert resumos, "o experimento não gravou nada"

        dados = json.loads(resumos[0].read_text(encoding="utf-8"))
        assert "extras" in dados, "a varredura não foi registrada no resumo"

    def _perfil_com_modelo_llm(self, tmp_path, documento):
        import json

        perfil = tmp_path / "p.json"
        perfil.write_text(
            json.dumps(
                {
                    "nome": "t",
                    "documento": str(documento),
                    "rotas": {
                        "llm": {
                            "modelo": "modelo-inexistente:0b",
                            "campos": ["identificador"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return perfil

    def test_varredura_da_rota_llm_usa_o_texto_da_pagina(self, tmp_path, capsys):
        """A rota `llm` monta o prompt a partir do texto extraído da página, não
        de imagem renderizada — é o único branch de `_varrer_degraus` que a
        rota `vlm`, já coberta acima, não exercita."""
        import json

        documento = self._documento(tmp_path)
        perfil = self._perfil_com_modelo_llm(tmp_path, documento)
        destino = tmp_path / "res"

        codigo = main(
            [
                "experimento",
                "--perfil",
                str(perfil),
                "--destino",
                str(destino),
            ]
        )

        assert codigo in (0, 1)
        dados = json.loads(next(destino.glob("*/resumo.json")).read_text(encoding="utf-8"))
        assert "degraus-llm" in dados["extras"]

    def test_sem_degraus_pula_a_varredura(self, tmp_path):
        import json

        documento = self._documento(tmp_path)
        perfil = self._perfil_com_modelo(tmp_path, documento)
        destino = tmp_path / "res"

        main(
            [
                "experimento",
                "--perfil",
                str(perfil),
                "--destino",
                str(destino),
                "--sem-degraus",
            ]
        )

        dados = json.loads(next(destino.glob("*/resumo.json")).read_text(encoding="utf-8"))
        assert not dados["extras"], "varredura rodou apesar de --sem-degraus"


class TestAvaliarRegistra:
    """A acurácia é o resultado mais valioso do experimento — e se perdia.

    O comando `avaliar` imprimia na tela e não gravava nada. Fechado o terminal,
    o número sumia, e refazer custa uma execução inteira.

    Tudo que rodamos aqui é experimento: o produto é agnóstico ao tema, e o
    documento nutricional é um caso de teste como qualquer outro seria. Logo, a
    medição de acurácia pertence a `experimentos/resultados/`, com a mesma
    procedência das demais.
    """

    def _cenario(self, tmp_path):
        import json

        import fitz

        documento = tmp_path / "d.pdf"
        pdf = fitz.open()
        pagina = pdf.new_page(width=595, height=842)
        pagina.insert_text((112, 400.0), "Energia ")
        pagina.insert_text((165, 400.0), "(kcal) ")
        for i, valor in enumerate(["124", "360"]):
            pagina.insert_text((230 + i * 70, 400.0), valor + " ")
        for i, nome in enumerate(["Um", "Dois"]):
            pagina.insert_text((230 + i * 70, 600), nome + " ")
        pdf.save(documento)
        pdf.close()

        gabarito = tmp_path / "g.csv"
        gabarito.write_text(
            "numero,descricao,energia_kcal,energia_kcal_ok\n"
            "1,Um,124.0,ok\n"
            "2,Dois,360.0,ok\n",
            encoding="utf-8",
        )

        perfil = tmp_path / "p.json"
        perfil.write_text(
            json.dumps(
                {
                    "nome": "t",
                    "documento": str(documento),
                    "mapeamento": {"energia_kcal": ["Energia (kcal)"]},
                    "rotas": {
                        "posicional": {
                            "layout": {
                                "x_rotulos": [110.0, 160.0],
                                "x_unidades": [160.0, 200.0],
                                "x_valores_min": 200.0,
                                "y_identificadores_min": 550.0,
                                "y_rotulo_max": 550.0,
                            }
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return documento, gabarito, perfil

    def test_avaliacao_fica_gravada_com_procedencia(self, tmp_path):
        import json

        _, gabarito, perfil = self._cenario(tmp_path)
        destino = tmp_path / "res"

        main(
            [
                "avaliar",
                str(gabarito),
                "--perfil",
                str(perfil),
                "--destino",
                str(destino),
            ]
        )

        arquivos = list(destino.glob("*/acuracia*.json"))
        assert arquivos, "a acurácia não foi gravada"

        dados = json.loads(arquivos[0].read_text(encoding="utf-8"))
        assert dados["maquina"]
        assert dados["quando"]
        assert dados["gabarito"]
        assert dados["rotas"], "nenhuma rota foi medida"

    def test_grava_acuracia_por_campo(self, tmp_path):
        """O número agregado esconde qual campo falha — e é esse que se corrige."""
        import json

        _, gabarito, perfil = self._cenario(tmp_path)
        destino = tmp_path / "res"

        main(["avaliar", str(gabarito), "--perfil", str(perfil), "--destino", str(destino)])

        dados = json.loads(next(destino.glob("*/acuracia*.json")).read_text(encoding="utf-8"))
        primeira = next(iter(dados["rotas"].values()))
        assert "acuracia" in primeira
        assert "por_campo" in primeira

    def test_gabaritos_diferentes_nao_se_sobrescrevem(self, tmp_path):
        """Gabarito principal e conjunto de reserva medem coisas diferentes.

        O principal foi gerado por uma estratégia e conferido — a acurácia dela é
        tautológica. O reserva foi transcrito às cegas, e é a única medição
        independente. Uma sobrescrever a outra apagaria justamente a que vale
        como evidência.
        """
        _, gabarito, perfil = self._cenario(tmp_path)
        reserva = tmp_path / "holdout.csv"
        reserva.write_text("numero,descricao,energia_kcal\n1,Um,124.0\n", encoding="utf-8")
        destino = tmp_path / "res"

        for alvo in (gabarito, reserva):
            main(["avaliar", str(alvo), "--perfil", str(perfil), "--destino", str(destino)])

        arquivos = {p.name for p in destino.glob("*/acuracia*.json")}
        assert len(arquivos) == 2, f"uma medição apagou a outra: {arquivos}"


class TestComparar:
    """`comparar` roteia por `montar_todas` + `Pipeline` e imprime a
    concordância. Como o resto deste arquivo, não processa documento de
    verdade — os extratores são substituídos por dublês (`monkeypatch`), e o
    que se confere é a fiação: o relatório sai quando há 2+ saídas, uma rota
    que falha na extração não derruba o comando, e menos de 2 saídas não
    chama uma comparação que não teria o que comparar.
    """

    def _documento(self, tmp_path):
        import fitz

        caminho = tmp_path / "d.pdf"
        pdf = fitz.open()
        pdf.new_page().insert_text((72, 72), "texto")
        pdf.save(caminho)
        pdf.close()
        return caminho

    def _perfil(self, tmp_path, documento):
        import json

        perfil = tmp_path / "p.json"
        perfil.write_text(
            json.dumps({"nome": "t", "documento": str(documento), "rotas": {}}),
            encoding="utf-8",
        )
        return perfil

    def _registro(self, identificador: str):
        from parser.modelo import Campo, Evidencia, Registro

        ev = Evidencia(pagina=1, texto_bruto=identificador)
        return Registro(
            campos={
                "identificador": Campo[str].extraido(valor=identificador, evidencia=ev),
                "energia_kcal": Campo[float].extraido(valor=124.0, evidencia=ev),
            },
            fonte="d.pdf",
        )

    def _extrator_falso(self, resultado):
        """`resultado` é a lista de registros a devolver, ou uma exceção a levantar."""

        class _Extrator:
            def extrair(_self, documento):
                if isinstance(resultado, Exception):
                    raise resultado
                return resultado

        return _Extrator()

    def test_duas_rotas_concordando_imprime_o_relatorio(self, tmp_path, capsys, monkeypatch):
        documento = self._documento(tmp_path)
        perfil = self._perfil(tmp_path, documento)
        registro = self._registro("1 X")
        monkeypatch.setattr(
            "parser.fabrica.montar_todas",
            lambda perfil, incluir_modelos: {
                "a": self._extrator_falso([registro]),
                "b": self._extrator_falso([registro]),
            },
        )

        codigo = main(["comparar", "--perfil", str(perfil), "--documento", str(documento)])

        assert codigo == 0
        assert "concordância geral" in capsys.readouterr().out

    def test_rota_que_falha_na_extracao_nao_derruba_o_comando(
        self, tmp_path, capsys, monkeypatch
    ):
        documento = self._documento(tmp_path)
        perfil = self._perfil(tmp_path, documento)
        registro = self._registro("1 X")
        monkeypatch.setattr(
            "parser.fabrica.montar_todas",
            lambda perfil, incluir_modelos: {
                "boa": self._extrator_falso([registro]),
                "ruim": self._extrator_falso(RuntimeError("falhou de propósito")),
            },
        )

        codigo = main(["comparar", "--perfil", str(perfil), "--documento", str(documento)])

        assert codigo == 0
        assert "falhou" in capsys.readouterr().out

    def test_menos_de_duas_saidas_nao_chama_a_comparacao(self, tmp_path, capsys, monkeypatch):
        """Uma rota só (ou nenhuma com registro) não tem com o que comparar —
        chamar `comparar_estrategias` aqui produziria o relatório vazio
        ("apenas 1 estratégia"), que é ruído, não informação."""
        documento = self._documento(tmp_path)
        perfil = self._perfil(tmp_path, documento)
        registro = self._registro("1 X")
        monkeypatch.setattr(
            "parser.fabrica.montar_todas",
            lambda perfil, incluir_modelos: {
                "unica": self._extrator_falso([registro]),
                "vazia": self._extrator_falso([]),
            },
        )

        codigo = main(["comparar", "--perfil", str(perfil), "--documento", str(documento)])

        assert codigo == 0
        assert "concordância geral" not in capsys.readouterr().out


class TestAvaliarValidacoes:
    """Branches de erro de `_avaliar` que a CLI real alcança.

    Deixado de fora de propósito: o branch `perfil is None` (`cli.py:256-257`).
    Tanto `avaliar` quanto `comparar` declaram `--perfil` como `required=True`
    no argparse — esse `if` é defensivo, e `main()` nunca chega a executá-lo.
    Forçar isso exigiria construir um `Namespace` à mão simulando um estado
    que a CLI real não produz: cobertura de linha sem cobertura de
    comportamento.
    """

    def _documento(self, tmp_path):
        import fitz

        caminho = tmp_path / "d.pdf"
        pdf = fitz.open()
        pdf.new_page().insert_text((72, 72), "texto")
        pdf.save(caminho)
        pdf.close()
        return caminho

    def _perfil(self, tmp_path, *, documento=None, rotas=None):
        import json

        perfil = tmp_path / "p.json"
        conteudo = {"nome": "t", "rotas": rotas if rotas is not None else {}}
        if documento is not None:
            conteudo["documento"] = str(documento)
        perfil.write_text(json.dumps(conteudo), encoding="utf-8")
        return perfil

    def _gabarito_simples(self, tmp_path):
        gabarito = tmp_path / "g.csv"
        gabarito.write_text("numero,descricao,energia_kcal\n1,Um,124.0\n", encoding="utf-8")
        return gabarito

    def test_gabarito_inexistente_vira_mensagem(self, tmp_path, capsys):
        documento = self._documento(tmp_path)
        perfil = self._perfil(tmp_path, documento=documento)

        codigo = main(["avaliar", str(tmp_path / "nao-existe.csv"), "--perfil", str(perfil)])

        assert codigo == 2
        assert capsys.readouterr().err.strip()

    def test_sem_documento_no_perfil_nem_na_linha_de_comando(self, tmp_path, capsys):
        perfil = self._perfil(tmp_path, documento=None)
        gabarito = self._gabarito_simples(tmp_path)

        codigo = main(["avaliar", str(gabarito), "--perfil", str(perfil)])

        assert codigo == 2
        assert "documento" in capsys.readouterr().err.lower()

    def test_gabarito_incompleto_avisa_quantos_faltam(self, tmp_path, capsys):
        documento = self._documento(tmp_path)
        perfil = self._perfil(tmp_path, documento=documento)
        gabarito = tmp_path / "g.csv"
        gabarito.write_text(
            "numero,descricao,energia_kcal,energia_kcal_ok\n"
            "1,Um,124.0,ok\n"
            "2,Dois,360.0,\n",
            encoding="utf-8",
        )
        destino = tmp_path / "res"

        codigo = main(
            ["avaliar", str(gabarito), "--perfil", str(perfil), "--destino", str(destino)]
        )

        assert codigo == 0
        assert "1 de 2 valores conferidos" in capsys.readouterr().out

    def test_rota_que_falha_ao_montar_conta_como_erro(self, tmp_path, capsys):
        """`posicional` sem `layout` levanta `ConfiguracaoInvalida` na
        montagem — o laço de `_avaliar` precisa registrar isso como erro da
        rota, não deixar subir e derrubar a avaliação inteira."""
        documento = self._documento(tmp_path)
        perfil = self._perfil(tmp_path, documento=documento, rotas={"posicional": {}})
        gabarito = self._gabarito_simples(tmp_path)
        destino = tmp_path / "res"

        codigo = main(
            ["avaliar", str(gabarito), "--perfil", str(perfil), "--destino", str(destino)]
        )

        assert codigo == 1
        assert "falhou" in capsys.readouterr().out


class TestDocumentoDaLinhaDeComando:
    """`--documento` precisa chegar às rotas que abrem o arquivo.

    Quatro das seis rotas — pdfplumber, camelot, ocr e biblioteca — precisam do
    caminho do PDF, não do formato canônico. Elas o buscavam só em
    `perfil.documento`, então um `--documento` informado na linha de comando era
    ignorado e as quatro falhavam com "perfil precisa de 'documento'".

    O efeito é uma avaliação silenciosamente incompleta: duas rotas medidas, quatro
    "falhadas" por motivo que não é delas. Quem lesse a tabela concluiria que as
    ferramentas não funcionam.
    """

    def _perfil_multirrota(self, tmp_path):
        import json

        perfil = tmp_path / "p.json"
        perfil.write_text(
            json.dumps(
                {
                    "nome": "t",
                    "rotas": {
                        "posicional": {
                            "layout": {
                                "x_rotulos": [110.0, 160.0],
                                "x_unidades": [160.0, 200.0],
                                "x_valores_min": 200.0,
                                "y_identificadores_min": 550.0,
                            }
                        },
                        "pdfplumber": {},
                        "pymupdf": {},
                    },
                }
            ),
            encoding="utf-8",
        )
        return perfil

    def test_documento_da_linha_de_comando_chega_as_rotas(self, tmp_path, capsys):
        import fitz

        documento = tmp_path / "d.pdf"
        pdf = fitz.open()
        pdf.new_page().insert_text((72, 72), "texto")
        pdf.save(documento)
        pdf.close()

        gabarito = tmp_path / "g.csv"
        gabarito.write_text(
            "numero,descricao,energia_kcal,energia_kcal_ok\n1,Um,124.0,ok\n",
            encoding="utf-8",
        )

        main(
            [
                "avaliar",
                str(gabarito),
                "--perfil",
                str(self._perfil_multirrota(tmp_path)),
                "--documento",
                str(documento),
                "--destino",
                str(tmp_path / "res"),
            ]
        )

        saida = capsys.readouterr().out
        assert (
            "precisa de 'documento'" not in saida
        ), "o --documento da linha de comando não chegou às rotas que abrem o arquivo"
