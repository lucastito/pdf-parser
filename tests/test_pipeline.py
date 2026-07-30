"""Pipeline ponta a ponta — cobre S2 (destino é parâmetro) e A1 (extrator trocável).

Estes testes verificam a promessa central da arquitetura: trocar formato de
entrada, estratégia de extração ou destino é configuração, não alteração de
código. Se essa promessa não se sustentar aqui, ela não se sustenta em lugar
nenhum — e a comparação entre extratores perde o sentido.
"""

import json

import pytest

from parser.modelo import Campo, Evidencia, Registro
from parser.pipeline import Pipeline, Resultado
from parser.portas import DocumentoCanonico, Pagina, Palavra

EV = Evidencia(pagina=1, texto_bruto="1")


class FonteFalsa:
    def __init__(self, paginas: int = 2) -> None:
        self.paginas = paginas
        self.chamadas: list[str] = []

    def carregar(self, caminho: str) -> DocumentoCanonico:
        self.chamadas.append(caminho)
        return DocumentoCanonico(
            identificador=caminho,
            paginas=[
                Pagina(
                    numero=i + 1,
                    palavras=[Palavra(texto="x", x0=0.0, y0=0.0, x1=1.0, y1=1.0)],
                )
                for i in range(self.paginas)
            ],
        )


class ExtratorFalso:
    def __init__(self, nome: str = "falso", quantos: int = 3) -> None:
        self.nome = nome
        self.quantos = quantos

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        return [
            Registro(
                campos={"v": Campo[float].extraido(valor=float(i), evidencia=EV)},
                fonte=self.nome,
            )
            for i in range(self.quantos)
        ]


class DestinoFalso:
    def __init__(self) -> None:
        self.recebidos: list[Registro] = []

    def gravar(self, registros: list[Registro]) -> None:
        self.recebidos.extend(registros)


class TestExecucao:
    def test_executa_ponta_a_ponta(self):
        destino = DestinoFalso()
        pipeline = Pipeline(FonteFalsa(), ExtratorFalso(), [destino])
        resultado = pipeline.executar("doc.pdf")

        assert isinstance(resultado, Resultado)
        assert len(destino.recebidos) == 3

    def test_resultado_relata_o_que_aconteceu(self):
        pipeline = Pipeline(FonteFalsa(paginas=5), ExtratorFalso(quantos=7), [])
        resultado = pipeline.executar("doc.pdf")

        assert resultado.paginas == 5
        assert resultado.registros == 7
        assert resultado.segundos >= 0

    def test_grava_em_varios_destinos(self):
        """S2 na prática: o mesmo registro vai para destinos diferentes."""
        a, b = DestinoFalso(), DestinoFalso()
        Pipeline(FonteFalsa(), ExtratorFalso(), [a, b]).executar("doc.pdf")

        assert len(a.recebidos) == 3
        assert len(b.recebidos) == 3

    def test_sem_destino_ainda_extrai(self):
        """Útil para medir extração sem o custo de gravar."""
        resultado = Pipeline(FonteFalsa(), ExtratorFalso(), []).executar("doc.pdf")
        assert resultado.registros == 3

    def test_troca_de_extrator_nao_muda_o_pipeline(self):
        """A1: a mesma montagem roda com estratégias diferentes."""
        saidas = []
        for extrator in (ExtratorFalso("a", 2), ExtratorFalso("b", 5)):
            destino = DestinoFalso()
            Pipeline(FonteFalsa(), extrator, [destino]).executar("doc.pdf")
            saidas.append((destino.recebidos[0].fonte, len(destino.recebidos)))

        assert saidas == [("a", 2), ("b", 5)]


class TestTriagemIntegrada:
    def test_sem_triagem_processa_tudo(self):
        resultado = Pipeline(FonteFalsa(paginas=4), ExtratorFalso(), []).executar("d.pdf")
        assert resultado.paginas == 4

    def test_com_triagem_relata_as_classes(self):
        pipeline = Pipeline(
            FonteFalsa(paginas=3), ExtratorFalso(), [], triar_paginas=True
        )
        resultado = pipeline.executar("d.pdf")
        assert resultado.triagem is not None
        assert sum(resultado.triagem.values()) == 3

    def test_triagem_nao_perde_pagina(self):
        """A soma das classes tem de fechar com o total — sempre."""
        pipeline = Pipeline(
            FonteFalsa(paginas=9), ExtratorFalso(), [], triar_paginas=True
        )
        resultado = pipeline.executar("d.pdf")
        assert sum(resultado.triagem.values()) == resultado.paginas
