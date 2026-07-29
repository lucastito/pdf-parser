"""Triagem de página — cobre RF-3 (decidir a rota por página).

O que estes testes protegem: que nada seja descartado em silêncio. Uma página
classificada errada como descartável some do pipeline sem deixar rastro, e o
prejuízo só aparece quando alguém nota a informação faltando lá na frente.
"""

import pytest

from parser.portas import DocumentoCanonico, Pagina, Palavra
from parser.triagem import Classe, Triagem, triar


_LEXICO = ["alimento", "cozido", "integral", "fonte", "tabela", "método", "amostra"]


def _palavras(qtd: int, *, numericas: bool = False, x: float = 200.0) -> list[Palavra]:
    """Gera palavras de teste.

    O texto não numérico não pode conter dígitos: `"palavra1"` seria contado como
    token numérico e falsearia a densidade que a triagem mede.
    """
    return [
        Palavra(
            texto=str(i) if numericas else _LEXICO[i % len(_LEXICO)],
            x0=x + i,
            y0=100.0,
            x1=x + i + 8,
            y1=108.0,
        )
        for i in range(qtd)
    ]


def _pagina(numero: int, palavras: list[Palavra]) -> Pagina:
    return Pagina(numero=numero, palavras=palavras)


class TestClassificacao:
    def test_pagina_vazia_e_descartavel(self):
        assert triar(_pagina(1, [])).classe is Classe.DESCARTAVEL

    def test_pagina_com_poucas_palavras_e_descartavel(self):
        """Capa e folha de rosto: pouquíssimo texto, nenhum dado."""
        assert triar(_pagina(1, _palavras(6))).classe is Classe.DESCARTAVEL

    def test_pagina_densa_em_numeros_e_dados(self):
        pagina = _pagina(29, _palavras(400, numericas=True))
        assert triar(pagina).classe is Classe.DADOS

    def test_pagina_densa_em_texto_e_contexto(self):
        """Metodologia e tabelas auxiliares: texto abundante, poucos números."""
        pagina = _pagina(22, _palavras(300))
        assert triar(pagina).classe is Classe.CONTEXTO

    def test_pagina_media_com_texto_e_contexto(self):
        assert triar(_pagina(10, _palavras(80))).classe is Classe.CONTEXTO


class TestRastreabilidade:
    """Nada pode sumir sem registro — nem o que é descartado."""

    def test_triagem_registra_o_motivo(self):
        resultado = triar(_pagina(1, _palavras(3)))
        assert resultado.motivo
        assert isinstance(resultado.motivo, str)

    def test_triagem_registra_as_metricas_que_decidiram(self):
        resultado = triar(_pagina(29, _palavras(400, numericas=True)))
        assert resultado.total_palavras == 400
        assert resultado.proporcao_numerica > 0.9

    def test_triagem_preserva_o_numero_da_pagina(self):
        assert triar(_pagina(42, _palavras(10))).pagina == 42

    def test_descartavel_tambem_e_contabilizado(self):
        """O ponto central: descartar não é ignorar."""
        resultado = triar(_pagina(1, []))
        assert resultado.pagina == 1
        assert resultado.classe is Classe.DESCARTAVEL
        assert resultado.motivo


class TestTriagemDeDocumento:
    def _documento(self) -> DocumentoCanonico:
        return DocumentoCanonico(
            identificador="doc.pdf",
            paginas=[
                _pagina(1, _palavras(3)),
                _pagina(2, _palavras(300)),
                _pagina(3, _palavras(400, numericas=True)),
            ],
        )

    def test_classifica_todas_as_paginas(self):
        triagem = Triagem.do_documento(self._documento())
        assert len(triagem.resultados) == 3

    def test_nenhuma_pagina_fica_sem_classe(self):
        triagem = Triagem.do_documento(self._documento())
        assert all(r.classe is not None for r in triagem.resultados)

    def test_filtra_por_classe(self):
        triagem = Triagem.do_documento(self._documento())
        assert [p.numero for p in triagem.paginas_de(Classe.DADOS)] == [3]
        assert [p.numero for p in triagem.paginas_de(Classe.CONTEXTO)] == [2]
        assert [p.numero for p in triagem.paginas_de(Classe.DESCARTAVEL)] == [1]

    def test_resumo_soma_todas_as_paginas(self):
        """Se a soma do resumo não bate com o total, algo sumiu."""
        documento = self._documento()
        triagem = Triagem.do_documento(documento)
        assert sum(triagem.resumo().values()) == len(documento.paginas)

    def test_documento_sem_paginas(self):
        triagem = Triagem.do_documento(
            DocumentoCanonico(identificador="vazio.pdf", paginas=[])
        )
        assert triagem.resultados == []
        assert sum(triagem.resumo().values()) == 0


class TestLimiaresConfiguraveis:
    """Os limiares são heurística, e heurística precisa ser ajustável."""

    def test_limiar_de_densidade_numerica_configuravel(self):
        pagina = _pagina(1, _palavras(300, numericas=True))
        assert triar(pagina, proporcao_numerica_minima=0.5).classe is Classe.DADOS
        assert triar(pagina, proporcao_numerica_minima=1.1).classe is Classe.CONTEXTO

    def test_limiar_de_palavras_minimas_configuravel(self):
        pagina = _pagina(1, _palavras(20))
        assert triar(pagina, palavras_minimas=50).classe is Classe.DESCARTAVEL
        assert triar(pagina, palavras_minimas=10).classe is Classe.CONTEXTO

    def test_limiar_negativo_e_rejeitado(self):
        with pytest.raises(ValueError):
            triar(_pagina(1, _palavras(10)), palavras_minimas=-1)
