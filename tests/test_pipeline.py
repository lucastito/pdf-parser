"""Pipeline ponta a ponta — cobre S2 (destino é parâmetro) e A1 (extrator trocável).

Estes testes verificam a promessa central da arquitetura: trocar formato de
entrada, estratégia de extração ou destino é configuração, não alteração de
código. Se essa promessa não se sustentar aqui, ela não se sustenta em lugar
nenhum — e a comparação entre extratores perde o sentido.
"""

import json

import pytest

from parser.modelo import Campo, Evidencia, Registro
from parser.perfil import Perfil, PerfilInvalido
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


class TestPerfil:
    def test_carrega_perfil_de_arquivo(self, tmp_path):
        arquivo = tmp_path / "p.json"
        arquivo.write_text(
            json.dumps(
                {
                    "nome": "exemplo",
                    "fonte": {"tipo": "pdf"},
                    "extrator": {"tipo": "linear"},
                    "destinos": [{"tipo": "json", "caminho": "saida.json"}],
                }
            ),
            encoding="utf-8",
        )
        perfil = Perfil.de_arquivo(arquivo)
        assert perfil.nome == "exemplo"

    def test_perfil_monta_o_pipeline(self, tmp_path):
        perfil = Perfil(
            nome="p",
            fonte={"tipo": "pdf"},
            extrator={"tipo": "linear"},
            destinos=[{"tipo": "csv", "caminho": str(tmp_path / "s.csv")}],
        )
        assert perfil.montar() is not None

    def test_tipo_de_fonte_desconhecido_falha_claro(self):
        perfil = Perfil(
            nome="p", fonte={"tipo": "inexistente"}, extrator={"tipo": "linear"}, destinos=[]
        )
        with pytest.raises(PerfilInvalido, match="inexistente"):
            perfil.montar()

    def test_tipo_de_extrator_desconhecido_falha_claro(self):
        perfil = Perfil(
            nome="p", fonte={"tipo": "pdf"}, extrator={"tipo": "magico"}, destinos=[]
        )
        with pytest.raises(PerfilInvalido, match="magico"):
            perfil.montar()

    def test_extrator_posicional_exige_layout(self):
        """Falhar na montagem é melhor que extrair vazio silenciosamente."""
        perfil = Perfil(
            nome="p", fonte={"tipo": "pdf"}, extrator={"tipo": "posicional"}, destinos=[]
        )
        with pytest.raises(PerfilInvalido, match="layout"):
            perfil.montar()

    def test_formato_nao_implementado_vira_stub(self):
        """A2: formato declarado mas não suportado falha alto ao ser usado."""
        from parser.portas import FormatoNaoSuportado

        perfil = Perfil(
            nome="p", fonte={"tipo": "xlsx"}, extrator={"tipo": "linear"}, destinos=[]
        )
        pipeline = perfil.montar()
        with pytest.raises(FormatoNaoSuportado):
            pipeline.executar("planilha.xlsx")


class TestPerfilComModelo:
    """Trocar para uma estratégia baseada em modelo deve ser editar JSON.

    Montar não contacta servidor nenhum: a conexão só acontece na execução. Isso
    permite validar a configuração sem infraestrutura.
    """

    def test_monta_extrator_de_texto(self):
        perfil = Perfil(
            nome="p",
            fonte={"tipo": "pdf"},
            extrator={"tipo": "modelo", "modelo": "m", "campos": ["a"]},
            destinos=[],
        )
        assert perfil.montar() is not None

    def test_monta_extrator_de_visao(self, pdf_exemplo):
        perfil = Perfil(
            nome="p",
            documento=str(pdf_exemplo),
            fonte={"tipo": "pdf"},
            extrator={"tipo": "vlm", "modelo": "v", "campos": ["a"], "dpi": 120},
            destinos=[],
        )
        assert perfil.montar() is not None

    def test_modelo_sem_nome_falha_claro(self):
        perfil = Perfil(
            nome="p", fonte={"tipo": "pdf"}, extrator={"tipo": "modelo", "campos": ["a"]}
        )
        with pytest.raises(PerfilInvalido, match="modelo"):
            perfil.montar()

    def test_modelo_sem_campos_falha_claro(self):
        """Sem a lista de campos o modelo devolveria estrutura arbitrária."""
        perfil = Perfil(
            nome="p", fonte={"tipo": "pdf"}, extrator={"tipo": "modelo", "modelo": "m"}
        )
        with pytest.raises(PerfilInvalido, match="campos"):
            perfil.montar()

    def test_visao_sem_documento_falha_claro(self):
        perfil = Perfil(
            nome="p",
            fonte={"tipo": "pdf"},
            extrator={"tipo": "vlm", "modelo": "v", "campos": ["a"]},
        )
        with pytest.raises(PerfilInvalido, match="caminho"):
            perfil.montar()

    def test_dpi_do_perfil_chega_ao_extrator(self, pdf_exemplo):
        perfil = Perfil(
            nome="p",
            documento=str(pdf_exemplo),
            fonte={"tipo": "pdf"},
            extrator={"tipo": "vlm", "modelo": "v", "campos": ["a"], "dpi": 220},
        )
        assert perfil.montar().extrator.dpi == 220

    def test_montar_nao_contacta_servidor(self):
        """Configuração inválida deve aparecer sem depender de infraestrutura."""
        perfil = Perfil(
            nome="p",
            fonte={"tipo": "pdf"},
            extrator={
                "tipo": "modelo",
                "modelo": "m",
                "campos": ["a"],
                "url": "http://servidor-inexistente:11434",
            },
        )
        assert perfil.montar() is not None
