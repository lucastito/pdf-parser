"""Descoberta automática de layout.

Os testes que exigem o documento-caso o localizam pela variável de ambiente
`PARSER_DOCUMENTO_CASO`, e são saltados se ela não estiver definida. Embutir um
caminho de disco tornaria a suíte dependente de uma máquina específica.

Existe para eliminar o passo manual mais custoso da adoção: calibrar as faixas de
coordenadas de um documento novo. Sem isto, apontar o parser para outro arquivo
exige alguém inspecionar coordenadas à mão — trabalho que não é retrabalho de
código, mas é trabalho, e é onde a adoção emperra.

O que estes testes protegem: que a calibração **falhe claramente** quando não
encontrar estrutura, em vez de devolver um layout plausível e errado. Um layout
inventado produz extração que roda sem erro e grava lixo — exatamente o modo de
falha que o projeto inteiro tenta evitar.
"""

import os
from pathlib import Path

import pytest

from parser.calibracao import (
    CalibracaoFalhou,
    Candidato,
    calibrar,
    descobrir_paginas_de_dados,
)


def _documento_caso() -> Path:
    """O documento usado na validação, se disponível nesta máquina."""
    caminho = os.environ.get("PARSER_DOCUMENTO_CASO")
    if not caminho or not Path(caminho).exists():
        pytest.skip("defina PARSER_DOCUMENTO_CASO para rodar este teste")
    return Path(caminho)


class TestDescobertaDePaginas:
    def test_encontra_paginas_com_tabela(self):
        pdf = _documento_caso()

        paginas = descobrir_paginas_de_dados(str(pdf), limite=40)
        assert paginas, "nenhuma página de dados encontrada"
        # No documento-caso, as páginas de dados começam na 29.
        assert 29 in paginas

    def test_documento_sem_tabela_devolve_vazio(self, pdf_exemplo):
        assert descobrir_paginas_de_dados(str(pdf_exemplo)) == []

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            descobrir_paginas_de_dados(str(tmp_path / "nao-existe.pdf"))


class TestCalibracao:
    def test_calibra_o_documento_caso(self):
        """O teste que importa: o layout descoberto deve bater com o calibrado à mão."""
        pdf = _documento_caso()

        resultado = calibrar(str(pdf), paginas=[29, 31])
        layout = resultado.layout

        # Valores calibrados manualmente, que produzem 100% de acurácia.
        assert 105 <= layout["x_rotulos"][0] <= 120
        assert 128 <= layout["x_rotulos"][1] <= 140
        assert 130 <= layout["x_unidades"][0] <= 142
        assert 140 <= layout["x_valores_min"] <= 155
        assert 480 <= layout["y_identificadores_min"] <= 540

    def test_devolve_confianca(self):
        pdf = _documento_caso()

        resultado = calibrar(str(pdf), paginas=[29])
        assert 0.0 <= resultado.confianca <= 1.0
        assert resultado.confianca > 0.5, "confiança baixa no documento-caso"

    def test_registra_como_decidiu(self):
        """Calibração sem justificativa é número mágico com outro nome."""
        pdf = _documento_caso()

        resultado = calibrar(str(pdf), paginas=[29])
        assert resultado.evidencias
        for chave in ("x_rotulos", "x_valores_min", "y_identificadores_min"):
            assert any(chave in e for e in resultado.evidencias), f"{chave} sem evidência"

    def test_documento_sem_estrutura_falha_alto(self, pdf_exemplo):
        """Falhar é o comportamento correto: layout inventado grava lixo."""
        with pytest.raises(CalibracaoFalhou):
            calibrar(str(pdf_exemplo), paginas=[1])

    def test_pagina_inexistente_falha_claro(self):
        pdf = _documento_caso()

        with pytest.raises(CalibracaoFalhou, match="9999"):
            calibrar(str(pdf), paginas=[9999])


class TestCandidato:
    def test_candidato_ordena_por_confianca(self):
        alto = Candidato(layout={}, confianca=0.9, evidencias=[])
        baixo = Candidato(layout={}, confianca=0.3, evidencias=[])
        assert max([baixo, alto], key=lambda c: c.confianca) is alto


class TestLayoutCalibradoFunciona:
    """O critério final: o layout descoberto extrai corretamente?

    Um layout que passa nas verificações de forma mas não extrai dado não serve.
    """

    def test_layout_descoberto_extrai_os_itens(self):
        pdf = _documento_caso()

        from parser.extratores.posicional import ExtratorPosicional, LayoutTabela
        from parser.fontes.pdf import FontePDF

        resultado = calibrar(str(pdf), paginas=[29])
        layout = LayoutTabela(
            x_rotulos=tuple(resultado.layout["x_rotulos"]),
            x_unidades=tuple(resultado.layout["x_unidades"]),
            x_valores_min=resultado.layout["x_valores_min"],
            y_identificadores_min=resultado.layout["y_identificadores_min"],
            y_rotulo_max=resultado.layout.get("y_rotulo_max"),
        )
        documento = FontePDF(paginas=range(28, 29)).carregar(str(pdf))
        registros = ExtratorPosicional(layout).extrair(documento)

        com_numero = [
            r
            for r in registros
            if (c := r.campos.get("identificador"))
            and c.valor
            and str(c.valor)[:1].isdigit()
        ]
        assert len(com_numero) >= 25, f"só {len(com_numero)} itens extraídos"
