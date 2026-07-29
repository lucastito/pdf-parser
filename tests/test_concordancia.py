"""Concordância entre estratégias.

O risco que estes testes protegem: alguém ler concordância como acurácia. O
módulo mede se as estratégias dizem o mesmo, não se dizem a verdade — e o
relatório precisa deixar isso explícito, porque a tentação de concluir
"concordaram, então acertaram" é grande.
"""

from parser.concordancia import comparar_estrategias


def _registro(identificador: str, **valores):
    campos = {
        "identificador": {
            "valor": identificador, "sentinela": None,
            "origem": "extraido", "confianca": 1.0,
            "evidencia": {"pagina": 1},
        }
    }
    for nome, valor in valores.items():
        if valor is None:
            campos[nome] = {
                "valor": None, "sentinela": None, "origem": "ausente",
                "confianca": 0.0, "evidencia": None,
            }
        elif isinstance(valor, str) and not valor.replace(",", "").replace(".", "").isdigit():
            campos[nome] = {
                "valor": None, "sentinela": valor, "origem": "extraido",
                "confianca": 1.0, "evidencia": {"pagina": 1},
            }
        else:
            campos[nome] = {
                "valor": valor, "sentinela": None, "origem": "extraido",
                "confianca": 1.0, "evidencia": {"pagina": 1},
            }
    return {"campos": campos, "fonte": "d.pdf"}


class TestConcordanciaTotal:
    def test_estrategias_identicas_concordam_totalmente(self):
        dados = [_registro("Arroz", proteina=2.6)]
        r = comparar_estrategias({"a": dados, "b": list(dados)})
        assert r.taxa == 1.0

    def test_formatacao_diferente_ainda_concorda(self):
        """`42` e `42.0` são o mesmo valor; acusar divergência seria ruído."""
        r = comparar_estrategias({
            "a": [_registro("X", v=42.0)],
            "b": [_registro("X", v="42")],
        })
        assert r.taxa == 1.0


class TestDivergencia:
    def test_valores_diferentes_divergem(self):
        r = comparar_estrategias({
            "a": [_registro("X", v=2.6)],
            "b": [_registro("X", v=999.0)],
        })
        assert r.taxa == 0.0
        assert len(r.divergencias) == 1

    def test_identifica_a_estrategia_isolada(self):
        """Duas concordam, uma discorda: é onde a conferência humana rende mais."""
        r = comparar_estrategias({
            "a": [_registro("X", v=2.6)],
            "b": [_registro("X", v=2.6)],
            "c": [_registro("X", v=999.0)],
        })
        assert r.divergencias[0].isolada == "c"

    def test_sem_isolada_quando_todas_discordam(self):
        r = comparar_estrategias({
            "a": [_registro("X", v=1.0)],
            "b": [_registro("X", v=2.0)],
            "c": [_registro("X", v=3.0)],
        })
        assert r.divergencias[0].isolada is None

    def test_campo_com_menor_concordancia_aparece(self):
        r = comparar_estrategias({
            "a": [_registro("X", bom=1.0, ruim=1.0)],
            "b": [_registro("X", bom=1.0, ruim=999.0)],
        })
        assert r.por_campo["bom"] == 1.0
        assert r.por_campo["ruim"] == 0.0


class TestAlinhamento:
    def test_so_itens_comuns_entram(self):
        """Item ausente numa estratégia mede cobertura, não concordância."""
        r = comparar_estrategias({
            "a": [_registro("X", v=1.0), _registro("Y", v=2.0)],
            "b": [_registro("X", v=1.0)],
        })
        assert r.itens_comuns == 1

    def test_sem_itens_comuns_nao_ha_o_que_comparar(self):
        r = comparar_estrategias({
            "a": [_registro("X", v=1.0)],
            "b": [_registro("Y", v=1.0)],
        })
        assert r.itens_comuns == 0
        assert r.comparacoes == 0

    def test_uma_estrategia_so_nao_produz_comparacao(self):
        r = comparar_estrategias({"a": [_registro("X", v=1.0)]})
        assert r.comparacoes == 0

    def test_estrategia_vazia_e_ignorada(self):
        """Uma estratégia que falhou não deve poluir a comparação das outras."""
        r = comparar_estrategias({
            "a": [_registro("X", v=1.0)],
            "b": [_registro("X", v=1.0)],
            "falhou": [],
        })
        assert "falhou" not in r.estrategias
        assert r.taxa == 1.0

    def test_ausencia_em_todas_nao_conta(self):
        r = comparar_estrategias({
            "a": [_registro("X", v=None)],
            "b": [_registro("X", v=None)],
        })
        assert r.comparacoes == 0


class TestSentinelas:
    def test_sentinela_igual_concorda(self):
        r = comparar_estrategias({
            "a": [_registro("X", v="traco")],
            "b": [_registro("X", v="traco")],
        })
        assert r.taxa == 1.0

    def test_sentinela_contra_zero_diverge(self):
        """A confusão mais cara do domínio tem de aparecer como divergência."""
        r = comparar_estrategias({
            "a": [_registro("X", v="traco")],
            "b": [_registro("X", v=0.0)],
        })
        assert r.taxa == 0.0


class TestRelatorio:
    def test_relatorio_avisa_que_nao_e_acuracia(self):
        """Sem este aviso, concordância alta seria lida como prova de acerto."""
        r = comparar_estrategias({
            "a": [_registro("X", v=1.0)],
            "b": [_registro("X", v=1.0)],
        })
        texto = r.relatorio()
        assert "NÃO é acurácia" in texto
        assert "gabarito" in texto.lower()

    def test_relatorio_mostra_concordancia_por_par(self):
        r = comparar_estrategias({
            "a": [_registro("X", v=1.0)],
            "b": [_registro("X", v=1.0)],
        })
        assert "a × b" in r.relatorio()


class TestSemBaseParaComparar:
    """0% de concordância e "não havia o que comparar" são coisas diferentes.

    Reportar 0% quando os campos não se alinham sugeriria discordância total —
    conclusão errada a partir de ausência de dado.
    """

    def test_uma_estrategia_diz_que_falta_base(self):
        r = comparar_estrategias({"a": [_registro("X", v=1.0)]})
        texto = r.relatorio()
        assert "Sem base para comparar" in texto
        assert "0.0%" not in texto

    def test_nenhuma_estrategia_diz_que_falta_base(self):
        assert "Sem base para comparar" in comparar_estrategias({}).relatorio()

    def test_campos_desalinhados_nao_reportam_zero_por_cento(self):
        r = comparar_estrategias({
            "a": [_registro("X", campo_a=1.0)],
            "b": [_registro("Y", campo_b=1.0)],
        })
        texto = r.relatorio()
        assert "Nenhum campo comparável" in texto
        assert "concordância geral" not in texto
