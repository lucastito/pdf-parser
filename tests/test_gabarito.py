"""Carga do gabarito e medição de acurácia.

O que estes testes protegem: que uma correção escrita pelo revisor seja tratada
como o valor correto, e não descartada. Se o carregador ignorasse a coluna de
marcação, mediria a acurácia contra os valores que o extrator produziu — ou seja,
contra si mesmo, sempre 100%.
"""

import pytest

from parser.avaliacao import Veredito
from parser.gabarito import Gabarito, GabaritoInvalido, medir_acuracia
from parser.modelo import Campo, Evidencia, Registro, Sentinela

EV = Evidencia(pagina=29, texto_bruto="x")


def _csv(tmp_path, conteudo: str, nome: str = "g.csv"):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def _registro(identificador: str, **valores) -> Registro:
    campos = {"identificador": Campo[str].extraido(valor=identificador, evidencia=EV)}
    for nome, valor in valores.items():
        if valor is None:
            campos[nome] = Campo.ausente()
        elif isinstance(valor, Sentinela):
            campos[nome] = Campo[float].extraido(sentinela=valor, evidencia=EV)
        else:
            campos[nome] = Campo[float].extraido(valor=valor, evidencia=EV)
    return Registro(campos=campos, fonte="d.pdf")


CABECALHO = "numero,descricao,pagina_pdf,proteina_g,proteina_g_ok"


class TestCarga:
    def test_le_formato_de_conferencia(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"))
        assert g.itens["1 Arroz"]["proteina_g"] == "2.6"
        assert g.conferidos == 1
        assert g.completo

    def test_le_formato_simples_sem_coluna_ok(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, "numero,descricao,proteina_g\n1,Arroz,2.6\n"))
        assert g.itens["1 Arroz"]["proteina_g"] == "2.6"

    def test_tolera_bom_de_planilha(self, tmp_path):
        """Planilha grava BOM, que entraria no nome da primeira coluna."""
        caminho = tmp_path / "bom.csv"
        caminho.write_bytes(b"\xef\xbb\xbf" + f"{CABECALHO}\n1,Arroz,29,2.6,ok\n".encode())
        assert Gabarito.de_arquivo(caminho).itens["1 Arroz"]["proteina_g"] == "2.6"

    def test_campo_nao_conferido_conta_como_pendente(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,\n"))
        assert g.conferidos == 0
        assert g.total == 1
        assert not g.completo

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(GabaritoInvalido, match="não encontrado"):
            Gabarito.de_arquivo(tmp_path / "nao-existe.csv")

    def test_arquivo_vazio_falha_claro(self, tmp_path):
        with pytest.raises(GabaritoInvalido, match="vazio"):
            Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n"))

    def test_sem_colunas_obrigatorias_falha_claro(self, tmp_path):
        with pytest.raises(GabaritoInvalido, match="numero"):
            Gabarito.de_arquivo(_csv(tmp_path, "a,b\n1,2\n"))

    def test_sem_campo_de_valor_falha_claro(self, tmp_path):
        with pytest.raises(GabaritoInvalido, match="campo de valor"):
            Gabarito.de_arquivo(_csv(tmp_path, "numero,descricao\n1,Arroz\n"))


class TestCorrecaoDoRevisor:
    """A parte que mais importa: a correção precisa virar o valor de referência."""

    def test_marca_diferente_de_ok_e_o_valor_correto(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,999.0,2.6\n"))
        assert g.itens["1 Arroz"]["proteina_g"] == "2.6"
        assert g.correcoes == 1

    def test_correcao_faz_a_estrategia_errar(self, tmp_path):
        """Sem isto, a acurácia seria medida contra o próprio erro do extrator."""
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,999.0,2.6\n"))
        r = medir_acuracia("e", [_registro("1 Arroz", proteina_g=999.0)], g)
        assert r.acuracia == 0.0

    @pytest.mark.parametrize("marca", ["ok", "OK", "x", "sim", "v"])
    def test_marcas_de_conferido_nao_sao_valores(self, tmp_path, marca):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,{marca}\n"))
        assert g.itens["1 Arroz"]["proteina_g"] == "2.6"
        assert g.correcoes == 0


class TestMedicao:
    def test_valor_correto_acerta(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"))
        assert medir_acuracia("e", [_registro("1 Arroz", proteina_g=2.6)], g).acuracia == 1.0

    def test_valor_errado_erra(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"))
        assert medir_acuracia("e", [_registro("1 Arroz", proteina_g=99.0)], g).acuracia == 0.0

    def test_item_ausente_conta_como_faltante(self, tmp_path):
        """O extrator deveria ter encontrado — ausência é falha, não neutro."""
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"))
        r = medir_acuracia("e", [], g)
        assert r.comparacoes if hasattr(r, "comparacoes") else True
        assert r.acuracia == 0.0
        assert r.comparacoes[0].resultados[0].veredito is Veredito.FALTOU

    def test_identificador_com_espaco_extra_ainda_alinha(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"))
        assert medir_acuracia("e", [_registro("  1 Arroz  ", proteina_g=2.6)], g).acuracia == 1.0

    def test_sentinela_no_gabarito(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,traco,ok\n"))
        r = medir_acuracia("e", [_registro("1 Arroz", proteina_g=Sentinela.TRACO)], g)
        assert r.acuracia == 1.0

    def test_sentinela_confundida_com_zero_erra(self, tmp_path):
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,traco,ok\n"))
        assert medir_acuracia("e", [_registro("1 Arroz", proteina_g=0.0)], g).acuracia == 0.0

    def test_acuracia_por_campo(self, tmp_path):
        conteudo = (
            "numero,descricao,proteina_g,proteina_g_ok,fibra_g,fibra_g_ok\n"
            "1,A,2.6,ok,1.0,ok\n2,B,3.0,ok,2.0,ok\n"
        )
        g = Gabarito.de_arquivo(_csv(tmp_path, conteudo))
        r = medir_acuracia(
            "e",
            [_registro("1 A", proteina_g=2.6, fibra_g=99.0),
             _registro("2 B", proteina_g=3.0, fibra_g=99.0)],
            g,
        )
        por_campo = r.por_campo()
        assert por_campo["proteina_g"] == 1.0
        assert por_campo["fibra_g"] == 0.0


class TestTautologia:
    def test_registra_quem_gerou_o_gabarito(self, tmp_path):
        """A acurácia de quem gerou o gabarito não é medição independente, e o
        relatório precisa poder dizer isso."""
        g = Gabarito.de_arquivo(
            _csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"), gerado_por="posicional"
        )
        assert g.gerado_por == "posicional"


class TestGabaritoReal:
    """Contra o arquivo de verdade, não uma fixture."""

    def test_carrega_o_gabarito_do_projeto(self):
        from pathlib import Path

        caminho = Path(__file__).resolve().parent.parent / "golden" / "taco.csv"
        if not caminho.exists():
            pytest.skip("gabarito ainda não conferido")

        g = Gabarito.de_arquivo(caminho, gerado_por="posicional")
        assert len(g.itens) == 40
        assert g.campos == ["energia_kcal", "proteina_g", "lipideos_g", "carboidrato_g", "fibra_g"]
        assert g.total == 200
        assert g.completo
