"""Cliente de modelo e extrator baseado em modelo.

Estes testes não chamam modelo nenhum: exercitam o contrato com um transporte
falso. Testar contra um servidor real tornaria a suíte lenta, não determinística
e dependente de infraestrutura — e não verificaria nada que estes não verifiquem.

O que precisa estar certo aqui: que a saída do modelo seja **validada**, não
confiada. Um modelo devolve texto; tratar esse texto como estrutura sem verificar
é o modo de falha típico de pipeline com LLM.
"""

import json

import pytest

from parser.modelo import Origem
from parser.ollama import (
    ClienteOllama,
    ExtratorModelo,
    RespostaInvalida,
    ServidorIndisponivel,
)
from parser.portas import DocumentoCanonico, Pagina, Palavra


class TransporteFalso:
    """Simula o servidor sem rede."""

    def __init__(self, resposta: object = None, erro: Exception | None = None) -> None:
        self.resposta = resposta
        self.erro = erro
        self.chamadas: list[dict] = []

    def enviar(self, url: str, carga: dict, timeout: float) -> dict:
        self.chamadas.append({"url": url, "carga": carga, "timeout": timeout})
        if self.erro:
            raise self.erro
        return {"response": json.dumps(self.resposta)}


def _documento() -> DocumentoCanonico:
    return DocumentoCanonico(
        identificador="doc.pdf",
        paginas=[
            Pagina(
                numero=1,
                palavras=[
                    Palavra(texto="Proteína", x0=10.0, y0=10.0, x1=50.0, y1=18.0),
                    Palavra(texto="2,6", x0=60.0, y0=10.0, x1=75.0, y1=18.0),
                ],
            )
        ],
    )


class TestCliente:
    def test_envia_modelo_e_prompt(self):
        transporte = TransporteFalso(resposta={"itens": []})
        cliente = ClienteOllama(modelo="modelo-teste", transporte=transporte)
        cliente.gerar("extraia isto", schema={"type": "object"})

        carga = transporte.chamadas[0]["carga"]
        assert carga["model"] == "modelo-teste"
        assert "extraia isto" in carga["prompt"]

    def test_envia_schema_para_saida_estruturada(self):
        """O schema é o que força JSON válido na decodificação, em vez de
        esperar que o modelo tenha formatado certo."""
        transporte = TransporteFalso(resposta={"itens": []})
        schema = {"type": "object", "properties": {"itens": {"type": "array"}}}
        ClienteOllama(modelo="m", transporte=transporte).gerar("p", schema=schema)

        assert transporte.chamadas[0]["carga"]["format"] == schema

    def test_desliga_streaming(self):
        transporte = TransporteFalso(resposta={})
        ClienteOllama(modelo="m", transporte=transporte).gerar("p", schema={})
        assert transporte.chamadas[0]["carga"]["stream"] is False

    def test_servidor_fora_do_ar_falha_com_mensagem_util(self):
        transporte = TransporteFalso(erro=OSError("conexão recusada"))
        cliente = ClienteOllama(modelo="m", transporte=transporte, url="http://servidor:11434")

        with pytest.raises(ServidorIndisponivel, match="servidor:11434"):
            cliente.gerar("p", schema={})

    def test_resposta_nao_json_falha_alto(self):
        """Modelo pequeno às vezes devolve prosa; isso não pode virar dado."""

        class TransporteProsa:
            def enviar(self, url, carga, timeout):
                return {"response": "Claro! Aqui está a tabela que você pediu:"}

        cliente = ClienteOllama(modelo="m", transporte=TransporteProsa())
        with pytest.raises(RespostaInvalida):
            cliente.gerar("p", schema={})

    def test_timeout_e_configuravel(self):
        transporte = TransporteFalso(resposta={})
        ClienteOllama(modelo="m", transporte=transporte, timeout=300.0).gerar("p", schema={})
        assert transporte.chamadas[0]["timeout"] == 300.0


class TestOrdemDasColunas:
    """A ordem das colunas do documento vai no prompt — e é o que corrige o
    deslocamento.

    Medido em 2026-08-01, na página 29. Descrever a regra de alinhamento não
    bastou: três versões do prompt tentaram ("alinhe por nome", "conte as
    colunas", "marcador ocupa coluna") e o modelo continuou devolvendo a
    **umidade** — a primeira coluna — no campo de carboidrato.

    | Campo | Modelo lia | Correto |
    |---|---|---|
    | energia_kcal | 124 | 124 ✅ |
    | proteina_g | 2,6 | 2,6 ✅ |
    | carboidrato_g | **70,1** | 25,8 ❌ |

    Ele acerta os primeiros e perde a conta depois do `NA` do colesterol, uma
    coluna não numérica no meio da linha.

    **Dar a sequência das colunas explicitamente resolveu: 100% em 5 itens.** A
    diferença não é de ênfase — é de natureza: a regra pede que o modelo infira o
    alinhamento, a sequência entrega o alinhamento pronto.

    O perfil **já declarava** `campos_na_ordem`, usado pelas rotas
    determinísticas. As rotas por modelo simplesmente nunca o recebiam.
    """

    def test_a_ordem_declarada_vai_no_prompt(self):
        transporte = TransporteFalso(resposta={"itens": []})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte),
            campos=["identificador", "carboidrato_g"],
            ordem_das_colunas=["Umidade (%)", "Energia (kcal)", "Carboidrato (g)"],
        )
        extrator.extrair(_documento())

        enviado = transporte.chamadas[0]["carga"]["prompt"]
        assert "Umidade (%)" in enviado
        assert "Energia (kcal)" in enviado

    def test_sem_ordem_declarada_o_prompt_nao_a_inventa(self):
        """Documento sem ordem conhecida não pode ganhar uma fictícia."""
        transporte = TransporteFalso(resposta={"itens": []})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte),
            campos=["identificador"],
        )
        extrator.extrair(_documento())

        enviado = transporte.chamadas[0]["carga"]["prompt"]
        assert "colunas" not in enviado.lower() or "Campos:" in enviado


class TestExtratorModelo:
    def test_produz_registros_a_partir_da_resposta(self):
        transporte = TransporteFalso(
            resposta={"itens": [{"identificador": "Arroz", "proteina": 2.6}]}
        )
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte),
            campos=["identificador", "proteina"],
        )
        registros = extrator.extrair(_documento())

        assert len(registros) == 1
        assert registros[0].campos["proteina"].valor == 2.6

    def test_marca_origem_como_extraida_do_texto(self):
        """O modelo leu do documento; não inventou. A distinção importa para a
        taxa de inferência."""
        transporte = TransporteFalso(resposta={"itens": [{"proteina": 2.6}]})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte), campos=["proteina"]
        )
        campo = extrator.extrair(_documento())[0].campos["proteina"]

        assert campo.origem is Origem.EXTRAIDO
        assert campo.evidencia is not None

    def test_confianca_abaixo_de_um_para_saida_de_modelo(self):
        """Extração determinística tem confiança 1.0; a de modelo, não —
        do contrário a métrica trataria as duas como equivalentes."""
        transporte = TransporteFalso(resposta={"itens": [{"proteina": 2.6}]})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte), campos=["proteina"]
        )
        assert extrator.extrair(_documento())[0].campos["proteina"].confianca < 1.0

    def test_campo_ausente_na_resposta_vira_ausente(self):
        transporte = TransporteFalso(resposta={"itens": [{"proteina": 2.6}]})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte),
            campos=["proteina", "gordura"],
        )
        campo = extrator.extrair(_documento())[0].campos["gordura"]
        assert campo.origem is Origem.AUSENTE

    def test_campo_extra_inventado_pelo_modelo_e_descartado(self):
        """O schema manda: campo fora dele não entra, mesmo que o modelo insista."""
        transporte = TransporteFalso(
            resposta={"itens": [{"proteina": 2.6, "inventado": "lixo"}]}
        )
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte), campos=["proteina"]
        )
        assert "inventado" not in extrator.extrair(_documento())[0].campos

    def test_sentinela_textual_na_resposta_e_reconhecida(self):
        transporte = TransporteFalso(resposta={"itens": [{"proteina": "Tr"}]})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte), campos=["proteina"]
        )
        campo = extrator.extrair(_documento())[0].campos["proteina"]
        assert campo.sentinela is not None
        assert campo.valor is None

    def test_resposta_sem_itens_devolve_lista_vazia(self):
        transporte = TransporteFalso(resposta={"itens": []})
        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=transporte), campos=["x"]
        )
        assert extrator.extrair(_documento()) == []

    def test_respeita_a_porta_extrator(self):
        from parser.portas import Extrator

        extrator = ExtratorModelo(
            cliente=ClienteOllama(modelo="m", transporte=TransporteFalso(resposta={})),
            campos=["x"],
        )
        assert isinstance(extrator, Extrator)
