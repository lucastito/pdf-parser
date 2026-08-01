"""Consolidação por campo: votar por célula, não escolher planilha (ADR-0017).

A diferença entre este módulo e `concordancia.py` é de propósito, e ela importa:
aquele **mede** se as estratégias dizem o mesmo; este **decide** o que vai para a
planilha. Medir não compromete; decidir sim.

O que estes testes protegem, em ordem de gravidade:

1. **Errar calado.** Preencher com valor errado e confiança alta é a pior falha
   possível — entra na planilha e ninguém revisa. Empate tem de virar pendência.
2. **Punir a máquina modesta.** Rota que não rodou não votou; contá-la como
   discordância faria a consolidação depender de quem rodou o quê.
3. **Confundir omissão com erro.** Omitir vira trabalho humano; errar vira dado
   falso. Contá-los junto esconde a diferença.
"""

import pytest

from parser.consolidacao import Desfecho, consolidar


def _saida(**campos):
    """Uma linha de planilha, no formato serializado que as rotas produzem."""
    registro = {"campos": {}}
    for nome, valor in campos.items():
        registro["campos"][nome] = {
            "valor": valor,
            "sentinela": None,
            "origem": "ausente" if valor is None else "extraido",
            "confianca": 0.0 if valor is None else 1.0,
            "evidencia": None,
        }
    return [registro]


class TestConcordancia:
    def test_todas_concordam_preenche_com_confianca_alta(self):
        resultado = consolidar(
            {
                "posicional": _saida(identificador="Arroz", energia_kcal=124),
                "pdfplumber": _saida(identificador="Arroz", energia_kcal=124),
                "camelot": _saida(identificador="Arroz", energia_kcal=124),
            }
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.CONCORDANCIA
        assert celula.valor == 124
        assert celula.concordaram == 3

    def test_a_proveniencia_diz_quais_rotas_concordaram(self):
        """ "Confirmado por três leituras independentes" é afirmação que nenhuma
        rota sozinha sustenta — e é o que justifica a confiança alta."""
        resultado = consolidar(
            {
                "posicional": _saida(identificador="Arroz", energia_kcal=124),
                "pdfplumber": _saida(identificador="Arroz", energia_kcal=124),
            }
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert set(celula.rotas_a_favor) == {"posicional", "pdfplumber"}

    def test_diferenca_dentro_da_tolerancia_ainda_e_concordancia(self):
        """'124' e '124.0' são o mesmo número. Tratá-los como divergência
        produziria pendência onde não há dúvida."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124.0),
            }
        )

        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.CONCORDANCIA


class TestMaioria:
    def test_maioria_preenche_e_registra_a_divergencia(self):
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "c": _saida(identificador="Arroz", energia_kcal=999),
            }
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.MAIORIA
        assert celula.valor == 124
        assert celula.rotas_divergentes == ["c"]

    def test_a_divergencia_nao_se_perde_no_relatorio(self):
        """Preencher sem registrar quem discordou apagaria a única pista de que
        aquele valor merece conferência."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "c": _saida(identificador="Arroz", energia_kcal=999),
            }
        )

        assert "999" in resultado.relatorio()


class TestPendencia:
    def test_empate_vira_pendencia_e_nao_desempate_arbitrario(self):
        """Desempatar por ordem alfabética ou por 'rota preferida' produziria
        valor plausível sem base — o modo de falha mais perigoso."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=999),
            }
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.PENDENCIA
        assert celula.valor is None

    def test_ninguem_leu_vira_pendencia(self):
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=None),
                "b": _saida(identificador="Arroz", energia_kcal=None),
            }
        )

        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.PENDENCIA

    def test_um_voto_so_nao_e_concordancia(self):
        """Uma leitura sozinha não foi confirmada por ninguém. Marcá-la como
        concordância daria a ela a confiança de três leituras."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=None),
                "c": _saida(identificador="Arroz", energia_kcal=None),
            }
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.VOTO_UNICO
        assert celula.valor == 124, "o valor é aproveitado, mas sem confiança alta"

    def test_as_pendencias_sao_listadas_para_o_humano(self):
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124, proteina_g=2.5),
                "b": _saida(identificador="Arroz", energia_kcal=999, proteina_g=2.5),
            }
        )

        pendentes = [(p.item, p.campo) for p in resultado.pendencias]
        assert ("Arroz", "energia_kcal") in pendentes
        assert ("Arroz", "proteina_g") not in pendentes


class TestRotaAusente:
    """Rota que não rodou é ausência, não voto contrário (ADR-0017).

    Máquinas com mais capacidade rodam modelos que a de referência não roda — e
    são elas que se parecem com o servidor de destino. Se a ausência contasse
    como discordância, a consolidação puniria a máquina modesta por não ter
    rodado modelos grandes, e o resultado dependeria de **quem rodou o quê**.
    """

    def test_rota_que_nao_rodou_nao_conta_como_discordancia(self):
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "nao_rodou": [],
            }
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.CONCORDANCIA
        assert "nao_rodou" not in celula.rotas_divergentes

    def test_item_ausente_numa_rota_nao_invalida_o_consenso(self):
        """Cobertura e concordância são coisas diferentes, e já são medidas
        separadamente."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "c": _saida(identificador="Feijao", energia_kcal=76),
            }
        )

        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.CONCORDANCIA


class TestPesosParametrizados:
    """O peso de cada rota é parâmetro, não constante embutida.

    Razão declarada no ADR-0017: rotas que compartilham fonte de erro erram
    juntas — três leitores da mesma camada de texto podem confirmar o mesmo erro
    com "confiança alta". Calibrar isso exige a matriz de correlação de erros,
    que só existe depois das medições.

    Enquanto ela não existe, o padrão é **uniforme e declarado como provisório**.
    O que estes testes garantem é que trocar os pesos depois não exija reescrever
    a votação.
    """

    def test_o_padrao_e_uniforme(self):
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=999),
            }
        )
        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.PENDENCIA

    def test_peso_maior_desempata(self):
        resultado = consolidar(
            {
                "confiavel": _saida(identificador="Arroz", energia_kcal=124),
                "duvidosa": _saida(identificador="Arroz", energia_kcal=999),
            },
            pesos={"confiavel": 2.0, "duvidosa": 1.0},
        )

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.MAIORIA
        assert celula.valor == 124

    def test_peso_de_rota_desconhecida_e_erro(self):
        """Nome errado no dicionário de pesos passaria despercebido e a rota
        votaria com peso 1 sem ninguém notar."""
        with pytest.raises(ValueError, match="inexistente"):
            consolidar(
                {"a": _saida(identificador="Arroz", energia_kcal=124)},
                pesos={"inexistente": 2.0},
            )


class TestErroVersusOmissao:
    """Omitir e errar têm gravidade oposta, e a acurácia simples os iguala.

    Omissão vira pendência: custa trabalho humano, mas a planilha não fica
    errada. Erro entra na planilha como se fosse dado bom, e ninguém revisa.

    Um extrator que omite 20% e nunca erra é **melhor** para este caso de uso que
    um que erra 10% — e a taxa de acerto diria o contrário.
    """

    def test_conta_erro_e_omissao_separados(self):
        gabarito = {"Arroz": {"energia_kcal": 124, "proteina_g": 2.5}}
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=999, proteina_g=None),
                "b": _saida(identificador="Arroz", energia_kcal=999, proteina_g=None),
            }
        )

        placar = resultado.contra_gabarito(gabarito)
        assert placar.erros == 1, "energia_kcal foi preenchida errada"
        assert placar.omissoes == 1, "proteina_g virou pendência"
        assert placar.acertos == 0

    def test_pendencia_conta_como_omissao_e_nao_como_erro(self):
        gabarito = {"Arroz": {"energia_kcal": 124}}
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=999),
            }
        )

        placar = resultado.contra_gabarito(gabarito)
        assert placar.omissoes == 1
        assert placar.erros == 0, "empate não preencheu nada, então não errou"

    def test_taxa_de_erro_ignora_o_que_virou_pendencia(self):
        """A taxa de erro mede **entre o que foi preenchido** — misturar com o
        que não foi preenchido esconderia um extrator conservador."""
        gabarito = {"Arroz": {"energia_kcal": 124, "proteina_g": 2.5}}
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124, proteina_g=9.9),
                "b": _saida(identificador="Arroz", energia_kcal=124, proteina_g=1.1),
            }
        )

        placar = resultado.contra_gabarito(gabarito)
        assert placar.acertos == 1
        assert placar.omissoes == 1
        assert placar.taxa_de_erro == 0.0


class TestMapeamentoDeCampos:
    """Sem canonizar os nomes, cada variante vira uma célula de um voto só.

    Encontrado ao rodar sobre as saídas reais das quatro rotas determinísticas:
    **56% das células saíram como voto único**, e não porque as rotas leram
    pouco. Elas leem o mesmo campo com nomes diferentes:

    | Rota | Nome lido |
    |---|---|
    | pdfplumber | `Fibra Alimentar (g)` |
    | posicional | `Alimentar Fibra (g)` — o cabeçalho é rotacionado |
    | ocr | `Proteina (g)` — sem acento |

    Cada variante virava uma coluna própria, com uma rota votando nela. A
    votação estava certa; o alinhamento é que faltava — e o perfil já declara
    `mapeamento` justamente para isso.
    """

    def test_variantes_do_mesmo_campo_votam_juntas(self):
        resultado = consolidar(
            {
                "pdfplumber": _saida(
                    identificador="Arroz", **{"Fibra Alimentar (g)": 1.6}
                ),
                "posicional": _saida(
                    identificador="Arroz", **{"Alimentar Fibra (g)": 1.6}
                ),
                "ocr": _saida(identificador="Arroz", **{"Fibra Alimentar (g)": 1.6}),
            },
            mapeamento={"fibra_g": ["Fibra Alimentar (g)", "Alimentar Fibra (g)"]},
        )

        celula = resultado.celula("Arroz", "fibra_g")
        assert celula.desfecho is Desfecho.CONCORDANCIA
        assert celula.concordaram == 3

    def test_campo_fora_do_mapeamento_continua_com_o_nome_lido(self):
        """Mapear é opcional: campo não declarado não pode sumir da planilha."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", **{"Cinzas (g)": 0.5}),
                "b": _saida(identificador="Arroz", **{"Cinzas (g)": 0.5}),
            },
            mapeamento={"fibra_g": ["Fibra Alimentar (g)"]},
        )

        assert resultado.celula("Arroz", "Cinzas (g)").desfecho is Desfecho.CONCORDANCIA

    def test_divergencia_real_sobrevive_ao_mapeamento(self):
        """Canonizar o nome não pode mascarar discordância de valor."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", **{"Fibra Alimentar (g)": 1.6}),
                "b": _saida(identificador="Arroz", **{"Alimentar Fibra (g)": 9.9}),
            },
            mapeamento={"fibra_g": ["Fibra Alimentar (g)", "Alimentar Fibra (g)"]},
        )

        assert resultado.celula("Arroz", "fibra_g").desfecho is Desfecho.PENDENCIA


class TestSaida:
    def test_o_resultado_e_serializavel(self):
        import json

        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
            }
        )

        json.dumps(resultado.como_dados())

    def test_sem_rota_alguma_nao_quebra(self):
        resultado = consolidar({})
        assert resultado.celulas == []
