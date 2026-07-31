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

from parser.degraus import ORDEM, Degrau, SaidaEmDegraus, TodosOsDegrausFalharam


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


class TestRaciocinio:
    """O canal de raciocínio precisa ser controlável — para poder ser medido.

    Cuidado com o que estes testes **não** afirmam. Uma versão anterior deles
    dizia que desligar o raciocínio resolvia a resposta vazia, com base num único
    teste de prompt de descrição. A medição completa não sustentou: desligado, os
    três degraus geram praticamente os mesmos tokens (152 contra 152; 1817 contra
    1844) e continuam vazios.

    O que se verifica aqui é só que a escolha existe, é explícita e vale igual em
    todos os degraus — variar raciocínio junto com restrição criaria variável
    escondida e nenhuma comparação entre degraus significaria mais nada.
    """

    def test_desliga_o_raciocinio_por_padrao(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte).obter("prompt")

        assert transporte.chamadas[0]["think"] is False

    def test_raciocinio_pode_ser_religado(self):
        """Quem quiser medir o efeito do raciocínio precisa conseguir ligá-lo."""
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte, raciocinar=True).obter("prompt")

        assert transporte.chamadas[0]["think"] is True

    def test_a_escolha_vale_em_todos_os_degraus(self):
        """Mudar de degrau não pode mudar o raciocínio: seria variável escondida."""
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "x"}, {"response": json.dumps(ITENS)}
        )
        _saida(transporte).obter("prompt")

        assert [c["think"] for c in transporte.chamadas] == [False, False, False]

    def test_vazio_em_todos_os_degraus_orienta_a_investigacao(self):
        """A mensagem tem de dizer o que já foi descartado, não repetir a busca.

        Sem isso, quem esbarrar nisso vai refazer as mesmas medições que já foram
        feitas — e chegar às mesmas duas conclusões negativas.
        """
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        mensagem = str(erro.value).lower()
        assert "prompt" in mensagem, "a mensagem precisa apontar a pista atual"
        assert "restrição" in mensagem or "restricao" in mensagem


class TestVarredura:
    """No experimento, TODOS os degraus rodam — não só até o primeiro que funciona.

    A diferença é de propósito. Em produção, parar no primeiro sucesso é o certo:
    os degraus seguintes custariam tempo sem acrescentar nada.

    No experimento é o oposto. Se a máquina A responde no degrau 1 e a máquina B
    no degrau 3, parar no primeiro sucesso significa que A nunca tentou os degraus
    2 e 3 — e a comparação entre A e B vira comparação entre restrições
    diferentes. Sem rodar todos, não há como saber se B *falharia* no degrau 1 ou
    se apenas não chegou a tentá-lo.

    Toda tentativa registra: qual degrau, se deu certo, o tipo da falha e o tempo.
    """

    def test_roda_todos_os_degraus_mesmo_com_o_primeiro_funcionando(self):
        transporte = TransporteRoteirizado(
            {"response": json.dumps(ITENS)},
            {"response": json.dumps(ITENS)},
            {"response": json.dumps(ITENS)},
        )
        varredura = _saida(transporte).varrer("prompt")

        assert len(transporte.chamadas) == 3, "parou antes de tentar todos"
        assert len(varredura.tentativas) == 3

    def test_roda_todos_mesmo_com_todos_falhando(self):
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        varredura = _saida(transporte).varrer("prompt")

        assert len(varredura.tentativas) == 3
        assert not any(t.sucesso for t in varredura.tentativas)

    def test_varredura_nao_levanta_quando_todos_falham(self):
        """Falha é o dado que se quer medir, não interrupção do experimento."""
        varredura = _saida(TransporteRoteirizado(VAZIO, VAZIO, VAZIO)).varrer("prompt")
        assert varredura.tentativas

    def test_cada_tentativa_registra_degrau_sucesso_motivo_e_tempo(self):
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "prosa"}, {"response": json.dumps(ITENS)}
        )
        varredura = _saida(transporte).varrer("prompt")

        for tentativa in varredura.tentativas:
            assert tentativa.degrau in ORDEM
            assert isinstance(tentativa.sucesso, bool)
            assert tentativa.segundos >= 0.0
            if not tentativa.sucesso:
                assert tentativa.motivo, "falha sem motivo não é comparável"

    def test_distingue_o_tipo_da_falha(self):
        """Resposta vazia e JSON malformado são achados diferentes.

        Se as duas virassem "falhou", perderia-se a informação que distingue
        problema de modelo de problema de formato.
        """
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "isto nao e json"}, {"response": json.dumps(ITENS)}
        )
        varredura = _saida(transporte).varrer("prompt")

        assert varredura.tentativas[0].tipo_de_falha == "resposta-vazia"
        assert varredura.tentativas[1].tipo_de_falha == "sem-estrutura"
        assert varredura.tentativas[2].tipo_de_falha is None

    def test_a_ordem_dos_degraus_e_sempre_a_mesma(self):
        """Ordem estável é condição para comparar máquina com máquina."""
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        varredura = _saida(transporte).varrer("prompt")

        assert [t.degrau for t in varredura.tentativas] == list(ORDEM)

    def test_resumo_serializavel_para_o_experimento(self):
        """O resultado precisa virar JSON: é o que vai para experimentos/."""
        transporte = TransporteRoteirizado(VAZIO, {"response": json.dumps(ITENS)}, VAZIO)
        varredura = _saida(transporte).varrer("prompt")

        dados = varredura.como_dados()
        json.dumps(dados)  # levanta se não for serializável
        assert len(dados["tentativas"]) == 3
        assert dados["primeiro_sucesso"] == Degrau.JSON_LIVRE.value

    def test_sem_sucesso_algum_o_resumo_diz_isso(self):
        varredura = _saida(TransporteRoteirizado(VAZIO, VAZIO, VAZIO)).varrer("prompt")
        assert varredura.como_dados()["primeiro_sucesso"] is None

    def test_varredura_ignora_degrau_maximo(self):
        """O experimento mede todos os degraus; limitar é decisão de produção."""
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        varredura = _saida(transporte, degrau_maximo=Degrau.ESQUEMA_COMPLETO).varrer("prompt")
        assert len(varredura.tentativas) == 3


class TestLimiteDeSaida:
    """Resposta cortada por limite de tokens é a causa medida do vazio.

    Cinco prompts na mesma imagem, com o raciocínio desligado:

    | prompt              | `done_reason` | tokens | resposta |
    |---------------------|---------------|--------|----------|
    | descreva a imagem   | `stop`        |    689 | 794 chars|
    | leia a tabela       | `length`      |   1927 | vazia    |
    | com campos          | `length`      |   1923 | vazia    |
    | com formato JSON    | `length`      |   1912 | vazia    |
    | com guardrails      | `length`      |   1887 | vazia    |

    O que separa os casos não é a restrição nem o texto do prompt: é o
    **tamanho da resposta pedida**. Descrever uma página cabe; enumerar dezenas
    de itens não, e a resposta é cortada no meio — voltando vazia.

    O modelo suporta 262144 tokens de contexto. O teto de ~2048 é do servidor.
    """

    def test_declara_o_limite_de_saida(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte, tokens_maximos=8192).obter("prompt")

        opcoes = transporte.chamadas[0].get("options", {})
        assert opcoes.get("num_predict") == 8192

    def test_sem_limite_declarado_nao_envia_a_opcao(self):
        """Não inventar valor: sem declaração, vale o padrão do servidor."""
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte).obter("prompt")

        assert "num_predict" not in transporte.chamadas[0].get("options", {})

    def test_resposta_cortada_e_diagnosticada_como_corte(self):
        """`length` com resposta vazia não é 'página sem dados' — é corte.

        Diagnosticar como resposta vazia genérica mandaria quem depura procurar
        no modelo ou no prompt, quando a correção é aumentar o limite.
        """
        cortada = {"response": "", "done_reason": "length", "eval_count": 1927}
        transporte = TransporteRoteirizado(cortada, cortada, cortada)

        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        mensagem = str(erro.value).lower()
        assert "cortada" in mensagem or "limite" in mensagem
        assert "num_predict" in mensagem or "tokens_maximos" in mensagem

    def test_corte_e_distinguido_de_vazio_na_varredura(self):
        """Tipos de falha diferentes agrupam resultados diferentes entre máquinas."""
        cortada = {"response": "", "done_reason": "length", "eval_count": 1927}
        transporte = TransporteRoteirizado(cortada, VAZIO, {"response": json.dumps(ITENS)})

        varredura = _saida(transporte).varrer("prompt")

        assert varredura.tentativas[0].tipo_de_falha == "resposta-cortada"
        assert varredura.tentativas[1].tipo_de_falha == "resposta-vazia"

    def test_o_limite_vale_em_todos_os_degraus(self):
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "x"}, {"response": json.dumps(ITENS)}
        )
        _saida(transporte, tokens_maximos=4096).obter("prompt")

        for chamada in transporte.chamadas:
            assert chamada["options"]["num_predict"] == 4096
