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


class TestInferenciaDeColunaAgnosticaDeDominio:
    """O núcleo não pode presumir nome de campo (CLAUDE.md) — sem passar
    `campos`, a inferência de "qual coluna é valor" tem de funcionar pra
    **qualquer** domínio, não só pra tabela nutricional.

    Achado real (auditoria de 2026-08-12): existia uma lista fixa
    `MACROS = ["energia_kcal", "proteina_g", ...]` — um gabarito de domínio
    diferente (financeiro, técnico, o que fosse) simplesmente não funcionava
    sem passar `campos` na mão, contornando uma suposição que não deveria
    estar no núcleo.
    """

    def test_funciona_sem_passar_campos_em_dominio_nao_nutricional(self, tmp_path):
        cabecalho = "numero,descricao,receita_mensal,receita_mensal_ok"
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{cabecalho}\n1,Filial Norte,50000,ok\n"))

        assert g.campos == ["receita_mensal"]
        assert g.itens["1 Filial Norte"]["receita_mensal"] == "50000"

    def test_metadado_sem_ok_companheira_nao_vira_campo_de_valor(self, tmp_path):
        """`pagina_pdf` não tem `pagina_pdf_ok` — é metadado, não valor a
        medir. Incluí-la infla comparações com um campo que nenhum extrator
        preenche, e o resultado pareceria pior do que é."""
        g = Gabarito.de_arquivo(_csv(tmp_path, f"{CABECALHO}\n1,Arroz,29,2.6,ok\n"))

        assert g.campos == ["proteina_g"]
        assert "pagina_pdf" not in g.campos

    def test_formato_simples_aceita_qualquer_nome_de_coluna(self, tmp_path):
        g = Gabarito.de_arquivo(
            _csv(tmp_path, "numero,descricao,temperatura_c\n1,Sensor A,36.5\n")
        )

        assert g.campos == ["temperatura_c"]


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
        assert (
            medir_acuracia("e", [_registro("  1 Arroz  ", proteina_g=2.6)], g).acuracia == 1.0
        )

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
            [
                _registro("1 A", proteina_g=2.6, fibra_g=99.0),
                _registro("2 B", proteina_g=3.0, fibra_g=99.0),
            ],
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

        caminho = (
            Path(__file__).resolve().parent.parent / "experimentos" / "golden" / "taco.csv"
        )
        if not caminho.exists():
            pytest.skip("gabarito ainda não conferido")

        g = Gabarito.de_arquivo(caminho, gerado_por="posicional")
        assert len(g.itens) == 40
        # Ordem não importa — a inferência é alfabética, não a ordem de uma
        # lista de domínio declarada à mão (ver TestInferenciaDeColunaAgnosticaDeDominio).
        assert set(g.campos) == {
            "energia_kcal",
            "proteina_g",
            "lipideos_g",
            "carboidrato_g",
            "fibra_g",
        }
        assert g.total == 200
        assert g.completo


class TestAlinhamentoPorDescricao:
    """O alinhamento não pode depender só do número do item.

    Defeito medido em 2026-07-30: o conjunto de reserva foi transcrito com
    numeração **local** (1 a 10), não a do documento. O mesmo alimento aparecia
    como `1 Pão, milho, forma` no gabarito e `51 Pão, milho, forma` na extração,
    com o **mesmo valor** de energia (292). Casando só por número, nada batia, e a
    acurácia saía 0% em todas as rotas — um zero que não media nada.

    Zero falso é pior que erro ruidoso: sugere que as ferramentas não funcionam,
    quando o defeito está no material de validação.

    O casamento por número continua valendo, e por boa razão: algumas ferramentas
    fragmentam o texto (`"Arroz, integra l"`) e casar só por nome descartaria
    itens cujos valores estão corretos. A descrição é a **segunda** chave.
    """

    def _registro(self, identificador: str, energia: float):
        from parser.modelo import Campo, Evidencia, Registro

        ev = Evidencia(pagina=1, texto_bruto="x")
        return Registro(
            campos={
                "identificador": Campo[str].extraido(valor=identificador, evidencia=ev),
                "energia_kcal": Campo[float].extraido(valor=energia, evidencia=ev),
            },
            fonte="d.pdf",
        )

    def _gabarito(self, tmp_path, linhas: str):
        from parser.gabarito import Gabarito

        caminho = tmp_path / "g.csv"
        caminho.write_text("numero,descricao,energia_kcal\n" + linhas, encoding="utf-8")
        return Gabarito.de_arquivo(caminho)

    def test_numeracao_divergente_ainda_casa_pela_descricao(self, tmp_path):
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '1,"Pão, milho, forma",292\n')
        registros = [self._registro("51 Pão, milho, forma", 292.0)]

        resultado = medir_acuracia("teste", registros, gabarito)
        assert (
            resultado.acuracia == 1.0
        ), "o mesmo alimento com o mesmo valor não casou por diferença de número"

    def test_casamento_por_numero_continua_valendo(self, tmp_path):
        """Descrição fragmentada pela ferramenta não pode descartar o item."""
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '7,"Arroz, integral, cozido",124\n')
        registros = [self._registro("7 Arroz, integra l, cozido", 124.0)]

        assert medir_acuracia("teste", registros, gabarito).acuracia == 1.0

    def test_descricao_diferente_e_numero_diferente_nao_casam(self, tmp_path):
        """Casar por descrição não pode virar casar com qualquer coisa."""
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '1,"Pão, milho, forma",292\n')
        registros = [self._registro("51 Farinha, de centeio, integral", 336.0)]

        assert medir_acuracia("teste", registros, gabarito).acuracia == 0.0

    def test_valor_errado_com_descricao_certa_conta_como_erro(self, tmp_path):
        """Alinhar melhor não pode virar aceitar valor errado."""
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '1,"Pão, milho, forma",292\n')
        registros = [self._registro("51 Pão, milho, forma", 999.0)]

        assert medir_acuracia("teste", registros, gabarito).acuracia == 0.0

    def test_numero_coincidente_nao_casa_com_alimento_errado(self, tmp_path):
        """A armadilha real: número igual, alimento diferente.

        O conjunto de reserva numerava de 1 a 10; o documento tem um item 1
        diferente. Casando por número primeiro, `1 Pão, milho` (292) era comparado
        com `1 Arroz, integral` (124) — e o erro parecia de extração, quando era
        de alinhamento.

        Por isso a descrição vem antes: ela identifica o alimento, o número é
        posicional.
        """
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '1,"Pão, milho, forma",292\n')
        registros = [
            self._registro("1 Arroz, integral, cozido", 124.0),
            self._registro("51 Pão, milho, forma", 292.0),
        ]

        resultado = medir_acuracia("teste", registros, gabarito)
        assert (
            resultado.acuracia == 1.0
        ), "casou pelo número com o alimento errado em vez de casar pela descrição"

    def test_descricao_fragmentada_pela_ferramenta_ainda_casa(self, tmp_path):
        """Algumas ferramentas quebram palavras no meio: `"Arroz, integra l"`.

        Medido: o pdfplumber produz `"69 Abobora, p esco ço, crua"`. A descrição
        não bate exata, o alinhamento caía no número, e o número casava com outro
        alimento — 40% de acurácia numa rota que lê corretamente.

        Comparar sem espaços resolve, e não afrouxa: duas descrições diferentes
        continuam diferentes depois de remover espaços.
        """
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '1,"Abóbora, pescoço, crua",25\n')
        registros = [
            self._registro("1 Arroz, integral, cozido", 124.0),
            self._registro("69 Abobora, p esco ço, crua", 25.0),
        ]

        assert (
            medir_acuracia("teste", registros, gabarito).acuracia == 1.0
        ), "descrição fragmentada não casou, e o número casou com o alimento errado"

    def test_ignorar_espacos_nao_junta_alimentos_diferentes(self, tmp_path):
        from parser.gabarito import medir_acuracia

        gabarito = self._gabarito(tmp_path, '1,"Arroz, integral, cru",360\n')
        registros = [self._registro("2 Arroz, integral, cozido", 124.0)]

        assert medir_acuracia("teste", registros, gabarito).acuracia == 0.0
