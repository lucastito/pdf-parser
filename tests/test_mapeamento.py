"""Mapeamento de rótulo do documento para nome canônico de campo.

Existe porque o documento e o consumidor falam línguas diferentes: o PDF diz
`"Proteína (g)"`, o esquema de destino diz `proteina_g`. Sem essa tradução, uma
extração perfeita mede 0% de acurácia — foi exatamente o que aconteceu antes deste
módulo existir.

O mapeamento é declarativo e por documento: o núcleo continua sem saber nada sobre
nutrição, e outro domínio entra trocando o arquivo de perfil.
"""

import pytest

from parser.mapeamento import MapeamentoInvalido, Mapeamento
from parser.modelo import Campo, Evidencia, Registro

EV = Evidencia(pagina=1, texto_bruto="x")

REGRAS = {
    "energia_kcal": ["Energia (kcal)"],
    "proteina_g": ["Proteína (g)"],
    "fibra_g": ["Fibra Alimentar (g)", "Alimentar Fibra (g)"],
}


def _registro(**campos) -> Registro:
    return Registro(
        campos={
            nome: Campo[float].extraido(valor=valor, evidencia=EV)
            for nome, valor in campos.items()
        },
        fonte="d.pdf",
    )


class TestTraducao:
    def test_traduz_rotulo_para_nome_canonico(self):
        m = Mapeamento(REGRAS)
        saida = m.aplicar(_registro(**{"Proteína (g)": 2.6}))
        assert "proteina_g" in saida.campos
        assert saida.campos["proteina_g"].valor == 2.6

    def test_aceita_variacao_de_ordem_das_palavras(self):
        """O extrator monta o rótulo pelo layout; a ordem pode variar."""
        m = Mapeamento(REGRAS)
        assert "fibra_g" in m.aplicar(_registro(**{"Alimentar Fibra (g)": 2.7})).campos
        assert "fibra_g" in m.aplicar(_registro(**{"Fibra Alimentar (g)": 2.7})).campos

    def test_ignora_diferenca_de_acento_e_caixa(self):
        """Acentuação de PDF é instável; casar por ela seria frágil."""
        m = Mapeamento(REGRAS)
        assert "proteina_g" in m.aplicar(_registro(**{"proteina (g)": 2.6})).campos
        assert "proteina_g" in m.aplicar(_registro(**{"PROTEÍNA (G)": 2.6})).campos

    def test_preserva_proveniencia(self):
        """Traduzir o nome não pode apagar de onde o valor veio."""
        m = Mapeamento(REGRAS)
        campo = m.aplicar(_registro(**{"Proteína (g)": 2.6})).campos["proteina_g"]
        assert campo.evidencia is not None
        assert campo.evidencia.texto_bruto == "x"

    def test_preserva_o_identificador(self):
        m = Mapeamento(REGRAS)
        registro = Registro(
            campos={
                "identificador": Campo[str].extraido(valor="1 Arroz", evidencia=EV),
                "Proteína (g)": Campo[float].extraido(valor=2.6, evidencia=EV),
            },
            fonte="d.pdf",
        )
        saida = m.aplicar(registro)
        assert saida.campos["identificador"].valor == "1 Arroz"


class TestCamposNaoMapeados:
    def test_campo_sem_regra_e_descartado_por_padrao(self):
        """O esquema de destino manda; sobra do documento não vira dado.

        A saída tem exatamente os campos do esquema — nem mais (o que sobrou do
        documento) nem menos (os que o documento não trouxe entram ausentes).
        """
        m = Mapeamento(REGRAS)
        saida = m.aplicar(_registro(**{"Proteína (g)": 2.6, "Cinzas (g)": 0.5}))
        assert "Cinzas (g)" not in saida.campos
        assert set(saida.campos) == set(REGRAS)

    def test_pode_preservar_nao_mapeados(self):
        m = Mapeamento(REGRAS, descartar_nao_mapeados=False)
        saida = m.aplicar(_registro(**{"Proteína (g)": 2.6, "Cinzas (g)": 0.5}))
        assert "Cinzas (g)" in saida.campos

    def test_campo_do_esquema_sem_correspondente_fica_ausente(self):
        """O consumidor espera a coluna; entregá-la ausente é melhor que omiti-la."""
        m = Mapeamento(REGRAS)
        saida = m.aplicar(_registro(**{"Proteína (g)": 2.6}))
        assert "energia_kcal" in saida.campos
        assert not saida.campos["energia_kcal"].preenchido


class TestValidacao:
    def test_regras_vazias_falham(self):
        with pytest.raises(MapeamentoInvalido):
            Mapeamento({})

    def test_rotulo_ambiguo_falha_na_construcao(self):
        """Dois campos reivindicando o mesmo rótulo é erro de configuração —
        e falhar na construção é melhor que escolher um em silêncio."""
        with pytest.raises(MapeamentoInvalido, match="ambíguo"):
            Mapeamento({"a": ["Proteína (g)"], "b": ["proteina (g)"]})

    def test_campo_sem_rotulos_falha(self):
        with pytest.raises(MapeamentoInvalido, match="sem rótulo"):
            Mapeamento({"a": []})


class TestAplicarEmLote:
    def test_traduz_lista_de_registros(self):
        m = Mapeamento(REGRAS)
        saidas = m.aplicar_todos(
            [_registro(**{"Proteína (g)": 2.6}), _registro(**{"Proteína (g)": 7.3})]
        )
        assert [r.campos["proteina_g"].valor for r in saidas] == [2.6, 7.3]

    def test_lista_vazia(self):
        assert Mapeamento(REGRAS).aplicar_todos([]) == []


class TestMapeamentoReal:
    """Contra os rótulos que o extrator realmente produz no documento-caso."""

    ROTULOS_REAIS = [
        "Umidade (%)", "Energia (kcal)", "Energia (kJ)", "Proteína (g)",
        "Lipídeos (g)", "Colesterol (mg)", "Carboidrato (g)",
        "Alimentar Fibra (g)", "Cinzas (g)", "Cálcio (mg)", "Magnésio (mg)",
    ]

    def test_mapeamento_do_perfil_cobre_os_cinco_macros(self):
        from parser.mapeamento import MAPEAMENTO_NUTRICIONAL

        m = Mapeamento(MAPEAMENTO_NUTRICIONAL)
        registro = Registro(
            campos={
                "identificador": Campo[str].extraido(valor="1 Arroz", evidencia=EV),
                **{r: Campo[float].extraido(valor=1.0, evidencia=EV) for r in self.ROTULOS_REAIS},
            },
            fonte="d.pdf",
        )
        saida = m.aplicar(registro)
        for esperado in ("energia_kcal", "proteina_g", "lipideos_g", "carboidrato_g", "fibra_g"):
            assert saida.campos[esperado].preenchido, f"{esperado} não foi mapeado"

    def test_energia_em_kj_nao_e_confundida_com_kcal(self):
        """As duas unidades coexistem na tabela; trocá-las erraria por fator ~4."""
        from parser.mapeamento import MAPEAMENTO_NUTRICIONAL

        m = Mapeamento(MAPEAMENTO_NUTRICIONAL)
        saida = m.aplicar(
            _registro(**{"Energia (kcal)": 124.0, "Energia (kJ)": 517.0})
        )
        assert saida.campos["energia_kcal"].valor == 124.0
