"""Degraus de saída do modelo (SPEC §4.4).

Impor um esquema JSON aninhado como gramática de decodificação é a forma mais
segura de obter saída estruturada — quando funciona. Em modelo pequeno
quantizado, pode tornar o caminho válido inalcançável: o modelo emite o token de
parada e devolve **resposta vazia**, sem erro algum.

O que torna esse modo de falha perigoso é que ele não se parece com falha. O
servidor responde `200`, a resposta é `""`, e o extrator recebe zero item — como
se a página estivesse em branco. Numa execução em lote, isso vira
"processado, 0 registros" e passa.

Estes testes não chamam modelo nenhum: exercitam o contrato com transporte falso,
pela mesma razão de `test_ollama.py`. O que verificam é que a descida de degrau
aconteça, que seja **registrada**, e que a validação não se perca no caminho.
"""

import json

import pytest

from parser.degraus import Degrau, SaidaEmDegraus, TodosOsDegrausFalharam


class TransporteRoteirizado:
    """Devolve uma resposta diferente a cada chamada, na ordem dada.

    Permite encenar exatamente o colapso observado: vazio no primeiro degrau,
    resposta útil no seguinte.
    """

    def __init__(self, *respostas: dict) -> None:
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []

    def enviar(self, url: str, carga: dict, timeout: float) -> dict:
        self.chamadas.append(carga)
        if not self.respostas:
            raise AssertionError("chamada além do roteiro")
        return self.respostas.pop(0)


ITENS = {"itens": [{"identificador": "Um", "energia_kcal": 124}]}

CAMPOS = ["identificador", "energia_kcal"]

VAZIO = {"response": "", "done_reason": "stop", "eval_count": 84}


def _saida(transporte, **kwargs) -> SaidaEmDegraus:
    from parser.ollama import ClienteOllama

    cliente = ClienteOllama(modelo="m", transporte=transporte)
    return SaidaEmDegraus(cliente, CAMPOS, **kwargs)


class TestPrimeiroDegrau:
    """Quando o esquema funciona, não se desce — descer custaria validação a mais."""

    def test_usa_esquema_completo_quando_funciona(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert resultado.degrau is Degrau.ESQUEMA_COMPLETO
        assert resultado.dados == ITENS
        assert len(transporte.chamadas) == 1

    def test_primeiro_degrau_envia_o_esquema_como_gramatica(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte).obter("prompt")

        formato = transporte.chamadas[0]["format"]
        assert isinstance(formato, dict), "o primeiro degrau tem de restringir por esquema"
        assert "itens" in formato["properties"]


class TestDescida:
    """O colapso medido: vazio com esquema, útil sem ele."""

    def test_resposta_vazia_desce_para_o_proximo_degrau(self):
        transporte = TransporteRoteirizado(VAZIO, {"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert resultado.degrau is Degrau.JSON_LIVRE
        assert resultado.dados == ITENS
        assert len(transporte.chamadas) == 2

    def test_segundo_degrau_pede_json_sem_gramatica(self):
        transporte = TransporteRoteirizado(VAZIO, {"response": json.dumps(ITENS)})
        _saida(transporte).obter("prompt")

        assert transporte.chamadas[1]["format"] == "json"

    def test_json_malformado_desce_para_texto(self):
        transporte = TransporteRoteirizado(
            VAZIO,
            {"response": "não é json"},
            {"response": f"Aqui está a tabela:\n```json\n{json.dumps(ITENS)}\n```"},
        )
        resultado = _saida(transporte).obter("prompt")

        assert resultado.degrau is Degrau.TEXTO_COM_EXTRACAO
        assert resultado.dados == ITENS

    def test_terceiro_degrau_nao_restringe_o_formato(self):
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "prosa"}, {"response": json.dumps(ITENS)}
        )
        _saida(transporte).obter("prompt")

        assert "format" not in transporte.chamadas[2]

    def test_extrai_json_embutido_em_prosa(self):
        """No último degrau o modelo fala; o JSON tem de ser recortado do meio."""
        prosa = f"Claro! Segue o resultado: {json.dumps(ITENS)} Espero ter ajudado."
        transporte = TransporteRoteirizado(VAZIO, {"response": "x"}, {"response": prosa})
        resultado = _saida(transporte).obter("prompt")

        assert resultado.dados == ITENS


class TestFalhaTotal:
    def test_todos_vazios_falha_alto(self):
        """Resposta vazia é falha, não resultado vazio.

        É a distinção que impede uma página não lida de virar 'página sem dados'.
        """
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        assert "3" in str(erro.value) or "três" in str(erro.value).lower()

    def test_mensagem_de_falha_relata_cada_degrau(self):
        transporte = TransporteRoteirizado(VAZIO, {"response": "prosa"}, VAZIO)
        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        mensagem = str(erro.value)
        assert "esquema" in mensagem.lower()
        assert "json" in mensagem.lower()

    def test_resposta_vazia_e_diagnosticada_como_tal(self):
        """Vazio com `done_reason=stop` é o colapso do esquema, não erro de rede."""
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        assert "vazia" in str(erro.value).lower()


class TestRegistro:
    """O degrau usado é variável do experimento — sem registrá-lo, nada é comparável."""

    def test_resultado_carrega_o_degrau_usado(self):
        transporte = TransporteRoteirizado(VAZIO, {"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert resultado.degrau.value
        assert resultado.degrau is not Degrau.ESQUEMA_COMPLETO

    def test_resultado_registra_as_tentativas_anteriores(self):
        transporte = TransporteRoteirizado(VAZIO, {"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert len(resultado.tentativas) == 2
        assert resultado.tentativas[0].degrau is Degrau.ESQUEMA_COMPLETO
        assert not resultado.tentativas[0].sucesso
        assert resultado.tentativas[1].sucesso

    def test_descida_e_relatada_como_achado(self):
        """Cair de degrau é informação sobre o modelo, não detalhe interno."""
        transporte = TransporteRoteirizado(VAZIO, {"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert resultado.houve_descida
        assert resultado.resumo()

    def test_sem_descida_nao_ha_achado(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert not resultado.houve_descida


class TestLimite:
    """Degradar a forma da restrição nunca degrada a validação (RF-7)."""

    def test_degrau_maximo_impede_a_descida(self):
        """Quem quiser comparar rodadas fixa o degrau; a descida invalidaria."""
        transporte = TransporteRoteirizado(VAZIO)
        with pytest.raises(TodosOsDegrausFalharam):
            _saida(transporte, degrau_maximo=Degrau.ESQUEMA_COMPLETO).obter("prompt")

        assert len(transporte.chamadas) == 1

    def test_resposta_sem_a_chave_esperada_nao_conta_como_sucesso(self):
        """JSON válido e inútil não é sucesso: a estrutura ainda tem de bater."""
        transporte = TransporteRoteirizado(
            {"response": json.dumps({"outra_coisa": 1})},
            {"response": json.dumps(ITENS)},
        )
        resultado = _saida(transporte).obter("prompt")

        assert resultado.degrau is Degrau.JSON_LIVRE
