"""Leitura de vocabulário a partir de uma planilha de schema.

A suíte não depende de nenhuma planilha real: constrói uma sintética, no
mesmo formato (cabeçalho MODULE/SUBGROUP/PARAMETER/DESCRIPTION, com linhas de
seção que só preenchem a primeira célula) que a planilha de projeto real
segue — sem carregar dado de negócio no repositório.
"""

from pathlib import Path

import pytest

from parser.vocabulario import CampoEsperado, carregar_campos_do_xlsx


def _planilha(caminho: Path, linhas: list[tuple], *, aba: str = "DADOS") -> Path:
    import openpyxl

    workbook = openpyxl.Workbook()
    planilha = workbook.active
    planilha.title = aba
    for linha in linhas:
        planilha.append(linha)
    workbook.save(caminho)
    return caminho


LINHAS_TIPICAS = [
    ("Título da planilha", None, None, None),
    ("Instrução de preenchimento", None, None, None),
    ("MODULE", "SUBGROUP", "PARAMETER", "DESCRIPTION"),
    ("SEÇÃO: CAMPOS GERAIS", None, None, None),
    ("Geral", "Localização", "Profundidade de Projeto", "Profundidade de referência."),
    ("Geral", "Localização", "Nome do Local", "Nome do local do campo."),
    ("SEÇÃO: CAMPOS DE POÇO", None, None, None),
    ("Poço", "Tabela", "Nome do Poço", "Identificador de cada poço."),
]


class TestCarregarCamposDoXlsx:
    def test_le_os_campos_ignorando_secoes(self, tmp_path):
        caminho = _planilha(tmp_path / "schema.xlsx", LINHAS_TIPICAS)

        campos = carregar_campos_do_xlsx(caminho, aba="DADOS")

        nomes = {c.nome for c in campos}
        assert nomes == {"Profundidade de Projeto", "Nome do Local", "Nome do Poço"}

    def test_secao_nao_entra_como_campo(self, tmp_path):
        caminho = _planilha(tmp_path / "schema.xlsx", LINHAS_TIPICAS)
        campos = carregar_campos_do_xlsx(caminho, aba="DADOS")
        nomes = {c.nome for c in campos}
        assert "SEÇÃO: CAMPOS GERAIS" not in nomes
        assert "SEÇÃO: CAMPOS DE POÇO" not in nomes

    def test_descricao_e_lida(self, tmp_path):
        caminho = _planilha(tmp_path / "schema.xlsx", LINHAS_TIPICAS)
        campos = carregar_campos_do_xlsx(caminho, aba="DADOS")
        (profundidade,) = [c for c in campos if c.nome == "Profundidade de Projeto"]
        assert profundidade.descricao == "Profundidade de referência."

    def test_campo_duplicado_entra_uma_vez(self, tmp_path):
        linhas = [*LINHAS_TIPICAS, ("Geral", "Localização", "Nome do Local", "de novo")]
        caminho = _planilha(tmp_path / "schema.xlsx", linhas)
        campos = carregar_campos_do_xlsx(caminho, aba="DADOS")
        nomes = [c.nome for c in campos]
        assert nomes.count("Nome do Local") == 1

    def test_aba_sem_cabecalho_reconhecivel_falha_claro(self, tmp_path):
        caminho = _planilha(tmp_path / "vazia.xlsx", [("nada", "aqui", "disso")])
        with pytest.raises(ValueError, match="cabeçalho"):
            carregar_campos_do_xlsx(caminho, aba="DADOS")

    def test_aba_sem_campo_algum_falha_claro(self, tmp_path):
        linhas = [("MODULE", "SUBGROUP", "PARAMETER", "DESCRIPTION")]
        caminho = _planilha(tmp_path / "so-cabecalho.xlsx", linhas)
        with pytest.raises(ValueError, match="campo"):
            carregar_campos_do_xlsx(caminho, aba="DADOS")


class TestCampoEsperado:
    def test_rotulos_inclui_nome_e_sinonimos(self):
        campo = CampoEsperado(nome="Profundidade", sinonimos=("Depth", "Water Depth"))
        assert campo.rotulos() == ("Profundidade", "Depth", "Water Depth")

    def test_sem_sinonimo_rotulos_e_so_o_nome(self):
        assert CampoEsperado(nome="X").rotulos() == ("X",)
