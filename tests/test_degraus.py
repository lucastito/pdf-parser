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

        São **três** hipóteses medidas e refutadas: restrição de formato,
        raciocínio, e o teto de saída. A terceira custou uma sessão inteira, e é
        a que mais engana — o sintoma de corte é idêntico ao de resposta vazia.
        """
        transporte = TransporteRoteirizado(VAZIO, VAZIO, VAZIO)
        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        mensagem = str(erro.value).lower()
        assert "restrição" in mensagem or "restricao" in mensagem
        assert "raciocínio" in mensagem or "raciocinio" in mensagem
        assert "contexto" in mensagem, "a causa real precisa ser a primeira a checar"
        assert "prompt" in mensagem, "a pista para quando não há corte"


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


class TestTetoDeSaida:
    """O teto de saída é declarável — mas **não** é o limite que corta.

    Renomeada de `TestLimiteDeSaida`: "limite" sem qualificação sugeria que esta
    classe cobria o limite atuante, e ela cobre o outro parâmetro. Quem corta é
    o contexto — ver `TestContexto`.

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

    O que estes testes afirmam continua valendo: o teto é declarado quando
    pedido, e omitido quando não. O que mudou é a leitura da tabela acima —
    aqueles ~1900 tokens não eram o teto de saída sendo atingido, e sim a soma
    de entrada e saída batendo no contexto (ADR-0018).
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
        no modelo ou no prompt, quando a causa é um limite.

        **Aqui só se afirma que houve corte.** Qual parâmetro corrigir é assunto
        de `TestContexto`: a primeira versão deste teste aceitava mensagem que
        citasse `tokens_maximos`, e continuou verde depois de a medição refutar
        esse conselho — porque a mensagem nova cita o mesmo termo para dizer que
        **não** resolve. Asserção frouxa mantém teste vivo sem o sentido.
        """
        cortada = {"response": "", "done_reason": "length", "eval_count": 1927}
        transporte = TransporteRoteirizado(cortada, cortada, cortada)

        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte).obter("prompt")

        assert "cortad" in str(erro.value).lower() or "limite" in str(erro.value).lower()

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


class TestContexto:
    """O limite que corta é o **contexto**, não o teto de saída.

    Foram medidos os dois. Elevar `num_predict` a 16384 **não** removeu o corte:
    as respostas continuaram parando perto de 1900 tokens. Somando entrada e
    saída, quatro casos com prompts de tamanhos diferentes pararam na mesma soma
    exata:

    | caso                 | entrada + saída | soma     | `done_reason` |
    |----------------------|-----------------|----------|---------------|
    | 5 itens (coube)      | 2184 + 1581     |     3765 | `stop`        |
    | página, com valores  | 2227 + 1869     | **4096** | `length`      |
    | idem, sem raciocínio | 2233 + 1863     | **4096** | `length`      |
    | teto a 16384         | 2189 + 1907     | **4096** | `length`      |

    Prompts de tamanhos diferentes parando na mesma soma é assinatura de teto
    atingido, não de o modelo parar por conta própria. O padrão do servidor é
    4096 e limita entrada **mais** saída; uma página renderizada consome ~2200
    só de entrada.

    Ver ADR-0018.
    """

    def test_declara_o_contexto(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte, contexto=16384).obter("prompt")

        assert transporte.chamadas[0]["options"]["num_ctx"] == 16384

    def test_sem_contexto_declarado_nao_envia_a_opcao(self):
        """Sem declaração vale o padrão do servidor — que é o problema, mas
        inventar valor aqui seria número mágico (ADR-0008)."""
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte).obter("prompt")

        assert "num_ctx" not in transporte.chamadas[0].get("options", {})

    def test_contexto_e_teto_convivem(self):
        """São parâmetros distintos: um limita a soma, o outro só a saída."""
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte, contexto=8192, tokens_maximos=4096).obter("prompt")

        opcoes = transporte.chamadas[0]["options"]
        assert opcoes["num_ctx"] == 8192
        assert opcoes["num_predict"] == 4096

    def test_o_contexto_vale_em_todos_os_degraus(self):
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "x"}, {"response": json.dumps(ITENS)}
        )
        _saida(transporte, contexto=8192).obter("prompt")

        for chamada in transporte.chamadas:
            assert chamada["options"]["num_ctx"] == 8192

    def test_corte_aponta_o_contexto_e_nao_so_o_teto(self):
        """A mensagem antiga mandava elevar `tokens_maximos`, e isso não resolve.

        Foi o conselho seguido por uma sessão inteira: o teto foi elevado, o
        corte continuou, e ninguém conferiu que o número não batia. Quem depurar
        precisa ser mandado ao parâmetro certo.
        """
        cortada = {
            "response": "",
            "done_reason": "length",
            "eval_count": 1907,
            "prompt_eval_count": 2189,
        }
        transporte = TransporteRoteirizado(cortada, cortada, cortada)

        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte, tokens_maximos=16384).obter("prompt")

        mensagem = str(erro.value).lower()
        assert "contexto" in mensagem
        assert "num_ctx" in mensagem

    def test_a_mensagem_nao_manda_elevar_so_o_teto_de_saida(self):
        """Guarda contra a regressão que já aconteceu.

        Este é o teste que faltava: a versão anterior da mensagem mandava
        elevar `tokens_maximos`, e o teste que a cobria aceitava a citação do
        termo sem exigir o que se dizia dele. Aqui se afirma que, se o termo
        aparecer, é para **negar** que resolva sozinho.
        """
        cortada = {
            "response": "",
            "done_reason": "length",
            "eval_count": 1907,
            "prompt_eval_count": 2189,
        }
        transporte = TransporteRoteirizado(cortada, cortada, cortada)

        with pytest.raises(TodosOsDegrausFalharam) as erro:
            _saida(transporte, tokens_maximos=16384).obter("prompt")

        mensagem = str(erro.value).lower()
        if "tokens_maximos" in mensagem:
            assert "não resolve" in mensagem or "nao resolve" in mensagem, (
                "citar tokens_maximos sem negar que resolva reintroduz o conselho "
                f"que a medição refutou: {mensagem}"
            )

    def test_a_soma_de_entrada_e_saida_e_registrada(self):
        """Foi a **soma** que revelou a causa, e ela vinha em toda resposta.

        Sem registrá-la, o diagnóstico para no parâmetro errado — foi o que
        aconteceu.
        """
        cortada = {
            "response": "",
            "done_reason": "length",
            "eval_count": 1907,
            "prompt_eval_count": 2189,
        }
        transporte = TransporteRoteirizado(cortada, cortada, cortada)

        varredura = _saida(transporte, contexto=4096).varrer("prompt")

        motivo = varredura.tentativas[0].motivo
        assert "2189" in motivo and "1907" in motivo, motivo
        assert "4096" in motivo, motivo


class TestReprodutibilidade:
    """Geração precisa ser repetível, senão nenhuma comparação se sustenta.

    O projeto não declarava `seed` nem `temperature`, e o padrão do servidor é
    amostragem aleatória. Consequência: duas execuções da **mesma** configuração
    na **mesma** máquina podiam divergir — e, entre máquinas, a diferença de
    acurácia seria indistinguível de ruído amostral.

    Não é detalhe: o experimento inteiro existe para atribuir diferença a modelo,
    configuração ou hardware. Sem geração repetível, nenhuma das três atribuições
    é possível.

    > **Limite que fica declarado:** mesmo com `seed` fixo e temperatura zero, a
    > ordem de operações em ponto flutuante muda entre processador e placa e
    > entre arquiteturas. A variação cai muito, **não** a zero (ADR-0020).
    """

    def test_declara_semente_e_temperatura(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte, semente=7).obter("prompt")

        opcoes = transporte.chamadas[0]["options"]
        assert opcoes["seed"] == 7
        assert opcoes["temperature"] == 0

    def test_a_semente_vale_em_todos_os_degraus(self):
        """Degraus com sementes diferentes mediriam sorte, não restrição."""
        transporte = TransporteRoteirizado(
            VAZIO, {"response": "x"}, {"response": json.dumps(ITENS)}
        )
        _saida(transporte, semente=7).obter("prompt")

        for chamada in transporte.chamadas:
            assert chamada["options"]["seed"] == 7

    def test_sem_semente_declarada_a_temperatura_ainda_e_zero(self):
        """Temperatura zero é o padrão do projeto, não consequência da semente.

        Amostragem aleatória em extração de tabela não tem serventia: não há
        criatividade a exercitar, e ela só acrescenta variância ao resultado.
        """
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte).obter("prompt")

        assert transporte.chamadas[0]["options"]["temperature"] == 0

    def test_temperatura_declarada_sobrepoe_o_padrao(self):
        """Medir o efeito da temperatura é hipótese legítima — só não é o padrão."""
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        _saida(transporte, temperatura=0.7).obter("prompt")

        assert transporte.chamadas[0]["options"]["temperature"] == 0.7


class TestRespostaNoCanalDeRaciocinio:
    """Quando a resposta vem vazia e o raciocínio traz a estrutura, aproveitá-la.

    Medido em 2026-08-01, na validação do prompt: o modelo de visão produziu
    **cinco itens perfeitos** — 25 de 25 campos corretos contra o gabarito — e o
    servidor entregou tudo em `thinking`, deixando `response` vazio.

    Sem esta recuperação, o extrator descarta uma extração impecável e reporta
    "resposta vazia". O custo do descarte não é pequeno: naquela chamada foram
    **440 segundos**, e numa página inteira são 77 minutos.

    O risco oposto — aceitar divagação como se fosse resposta — é contido pela
    validação que já existe: só entra o que for JSON com a chave esperada. Texto
    de raciocínio comum não passa por ela.
    """

    def test_usa_o_raciocinio_quando_a_resposta_vem_vazia(self):
        transporte = TransporteRoteirizado(
            {"response": "", "thinking": json.dumps(ITENS), "done_reason": "stop"}
        )

        resultado = _saida(transporte).obter("prompt")

        assert resultado.dados == ITENS

    def test_a_resposta_tem_precedencia_sobre_o_raciocinio(self):
        """Se as duas vierem, a resposta é a oficial — o raciocínio é rascunho."""
        outros = {"itens": [{"identificador": "Outro", "energia_kcal": 999}]}
        transporte = TransporteRoteirizado(
            {"response": json.dumps(ITENS), "thinking": json.dumps(outros)}
        )

        resultado = _saida(transporte).obter("prompt")

        assert resultado.dados == ITENS

    def test_raciocinio_sem_estrutura_nao_vira_resposta(self):
        """Divagação em prosa continua sendo falha, não resultado."""
        transporte = TransporteRoteirizado(
            {"response": "", "thinking": "Vou analisar a tabela...", "done_reason": "stop"},
            {"response": "", "thinking": "Hmm, deixa ver...", "done_reason": "stop"},
            {"response": "", "thinking": "A tabela parece ter colunas", "done_reason": "stop"},
        )

        with pytest.raises(TodosOsDegrausFalharam):
            _saida(transporte).obter("prompt")

    def test_o_registro_diz_que_a_estrutura_veio_do_raciocinio(self):
        """Sem marcar, ninguém saberia que o modelo entregou pelo canal errado —
        e é informação sobre o modelo, não detalhe interno."""
        transporte = TransporteRoteirizado(
            {"response": "", "thinking": json.dumps(ITENS), "done_reason": "stop"}
        )

        resultado = _saida(transporte).obter("prompt")

        assert resultado.tentativas[-1].veio_do_raciocinio


class TestUsoNoResultado:
    """Os tokens precisam chegar ao **JSON**, não só à mensagem de erro.

    A distinção não é preciosismo. `test_a_soma_de_entrada_e_saida_e_registrada`
    afirma que os números aparecem no texto do motivo — texto que serve a quem
    depura na hora, e que nenhuma análise posterior consegue agregar.

    O que alimenta a curva de memória por contexto (ADR-0018) é o dado
    estruturado gravado em `experimentos/resultados/`. Se `uso` se perdesse na
    serialização, o sintoma seria silencioso: os arquivos continuariam válidos,
    só que sem a única coluna que revelou a causa da sessão passada.

    Custo zero: os números já vêm em toda resposta do servidor.
    """

    def test_o_uso_sobrevive_a_serializacao(self):
        cortada = {
            "response": "",
            "done_reason": "length",
            "eval_count": 1907,
            "prompt_eval_count": 2189,
        }
        transporte = TransporteRoteirizado(cortada, cortada, cortada)

        dados = _saida(transporte, contexto=4096).varrer("prompt").como_dados()
        json.dumps(dados)  # levanta se não for serializável

        uso = dados["tentativas"][0]["uso"]
        assert uso["entrada"] == 2189
        assert uso["saida"] == 1907
        assert uso["total"] == 4096

    def test_o_uso_e_registrado_tambem_em_sucesso(self):
        """Em falha diagnostica; em sucesso alimenta a curva de memória.

        Gravar só no fracasso deixaria a curva sem os pontos que interessam —
        são as execuções que terminam que dizem quanto contexto uma página
        realmente custa.
        """
        transporte = TransporteRoteirizado(
            {
                "response": json.dumps(ITENS),
                "done_reason": "stop",
                "eval_count": 1581,
                "prompt_eval_count": 2184,
            }
        )

        resultado = _saida(transporte, contexto=8192).obter("prompt")

        assert resultado.tentativas[-1].sucesso
        uso = resultado.tentativas[-1].uso.como_dados()
        assert uso["entrada"] == 2184
        assert uso["saida"] == 1581
        assert uso["total"] == 3765

    def test_resposta_sem_os_contadores_nao_quebra(self):
        """Servidor que omite os campos não pode derrubar a execução.

        Vale para versões diferentes entre as máquinas do experimento: ausência
        do contador é dado faltante, não falha de extração.
        """
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})

        resultado = _saida(transporte).obter("prompt")

        uso = resultado.tentativas[-1].uso.como_dados()
        assert uso["entrada"] == 0
        assert uso["saida"] == 0
        assert uso["total"] == 0


class TestRaciocinioRegistrado:
    """O canal de raciocínio precisa ser gravado, mesmo desligado no pedido.

    Custou uma medição de 77 minutos: a chamada terminou sozinha, sobrou
    contexto, gerou 5684 tokens — e a resposta veio **vazia**. O conteúdo tinha
    ido para o canal de raciocínio, que o servidor devolve preenchido **mesmo
    com `think: false`**, e que o registro descartava.

    Sem este dado, o sintoma ("vazio") é indistinguível de incapacidade do
    modelo. Com ele, a causa é imediata.
    """

    def test_o_raciocinio_e_medido_mesmo_com_think_falso(self):
        transporte = TransporteRoteirizado(
            {
                "response": json.dumps(ITENS),
                "thinking": "<think>divagando</think>",
                "eval_count": 100,
                "prompt_eval_count": 50,
            }
        )

        resultado = _saida(transporte).obter("prompt")

        assert resultado.tentativas[-1].uso.raciocinio_chars == 24

    def test_resposta_vazia_com_raciocinio_longo_fica_evidente(self):
        """O caso real: nada na resposta, tudo no raciocínio.

        Reproduz a medição de 77 min — `stop`, contexto de sobra, milhares de
        tokens gerados, resposta vazia. Os dois números juntos dizem o que
        aconteceu; nenhum deles sozinho diria.
        """
        so_raciocinio = {
            "response": "",
            "thinking": "x" * 4043,
            "done_reason": "stop",
            "eval_count": 5684,
            "prompt_eval_count": 2376,
        }
        transporte = TransporteRoteirizado(
            so_raciocinio, dict(so_raciocinio), dict(so_raciocinio)
        )

        varredura = _saida(transporte, contexto=12271).varrer("prompt")
        uso = varredura.tentativas[0].uso

        assert uso.raciocinio_chars == 4043
        assert not uso.bate_no_teto(12271), "não foi corte — sobrou contexto"

    def test_sem_campo_de_raciocinio_registra_zero(self):
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS)})
        resultado = _saida(transporte).obter("prompt")

        assert resultado.tentativas[-1].uso.raciocinio_chars == 0


class TestDuracoesDoServidor:
    """As durações vêm em toda resposta e eram descartadas.

    `eval_duration` separa o tempo de **gerar** do tempo de carregar o modelo e
    de processar a entrada. Sem essa separação, uma primeira execução — que paga
    o carregamento — parece mais lenta que as seguintes, e a diferença viraria
    "resultado" na comparação entre máquinas.

    Tokens por segundo é a métrica que torna máquinas de capacidade diferente
    comparáveis: tempo absoluto por página mistura tamanho da tarefa com
    velocidade do hardware.
    """

    def test_tokens_por_segundo_sai_da_duracao_de_geracao(self):
        transporte = TransporteRoteirizado(
            {
                "response": json.dumps(ITENS),
                "eval_count": 1000,
                "prompt_eval_count": 500,
                # Nanossegundos, como o servidor reporta: 2 s de geração.
                "eval_duration": 2_000_000_000,
                "load_duration": 500_000_000,
                "total_duration": 3_000_000_000,
            }
        )

        uso = _saida(transporte).obter("prompt").tentativas[-1].uso

        assert uso.tokens_por_segundo == 500.0
        assert uso.como_dados()["eval_s"] == 2.0
        assert uso.como_dados()["load_s"] == 0.5

    def test_sem_duracao_nao_inventa_taxa(self):
        """Dividir por zero ou supor duração produziria número plausível e falso."""
        transporte = TransporteRoteirizado({"response": json.dumps(ITENS), "eval_count": 1000})

        uso = _saida(transporte).obter("prompt").tentativas[-1].uso

        assert uso.tokens_por_segundo is None
