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

from parser.consolidacao import Desfecho, consolidar, materializar


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

    def test_o_gabarito_casa_por_identificador_normalizado(self):
        """O gabarito é transcrito à mão e pode ter outra grafia do mesmo item.

        Sem normalizar dos dois lados, o item não casa e **some do placar** — nem
        acerto, nem erro, nem omissão. Zero silencioso é pior que erro, porque a
        acurácia continua parecendo boa sobre uma amostra menor do que se pensa.
        """
        resultado = consolidar(
            {
                "a": _saida(identificador="1 Arroz, integra l", energia_kcal=124),
                "b": _saida(identificador="1 Arroz, integral", energia_kcal=124),
            }
        )

        placar = resultado.contra_gabarito({"1 Arroz, integra l": {"energia_kcal": 124}})
        assert placar.acertos == 1, "o item sumiu do placar por diferença de grafia"

    def test_item_identificado_so_pelo_numero_ainda_casa(self):
        """Modelo pequeno devolve `"1"` onde as demais rotas dão `"1 Arroz…"`.

        Medido em 2026-08-01: três dos quatro modelos testados devolveram o
        identificador **sem a descrição**, apesar de o prompt pedir os dois. A
        conferência acusava **0%** — e a leitura estava certa: `qwen3-vl:2b`
        acertava 92,9% dos campos que produziu.

        Zero por não casar a chave é o pior tipo de erro de medição: parece
        incapacidade do modelo e é defeito do instrumento. O número do item já
        identifica sem ambiguidade neste documento, e usá-lo como reserva
        recupera a comparação sem afrouxar nada — o valor continua sendo
        conferido contra o gabarito.
        """
        resultado = consolidar(
            {
                "a": _saida(identificador="1", energia_kcal=124),
                "b": _saida(identificador="1", energia_kcal=124),
            }
        )

        placar = resultado.contra_gabarito(
            {"1 Arroz, integral, cozido": {"energia_kcal": 124}}
        )
        assert placar.acertos == 1, "o item sumiu do placar por falta da descrição"

    def test_numeros_diferentes_continuam_sem_casar(self):
        """A reserva por número não pode casar itens distintos."""
        resultado = consolidar(
            {
                "a": _saida(identificador="2", energia_kcal=360),
                "b": _saida(identificador="2", energia_kcal=360),
            }
        )

        placar = resultado.contra_gabarito(
            {"1 Arroz, integral, cozido": {"energia_kcal": 124}}
        )
        assert placar.acertos == 0
        assert placar.erros == 0

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
                "pdfplumber": _saida(identificador="Arroz", **{"Fibra Alimentar (g)": 1.6}),
                "posicional": _saida(identificador="Arroz", **{"Alimentar Fibra (g)": 1.6}),
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


class TestAlinhamentoDeIdentificador:
    """Sem normalizar o identificador, o mesmo item vira dois e ninguém vota.

    Medido sobre as saídas reais: apenas **81 de ~283 itens** apareciam nas
    quatro rotas. A causa não é acento nem maiúscula — é **espaço espúrio no
    meio da palavra**, que o extrator de tabela insere ao atravessar a quebra de
    coluna num cabeçalho rotacionado:

    | Rota | Identificador lido |
    |---|---|
    | posicional | `1 Arroz, integral, cozido` |
    | pdfplumber | `1 Arroz, integra l, cozido` |

    São o mesmo alimento. Sem alinhar, cada um vira um item de uma rota só, e
    204 itens ficam fora da votação por um espaço.
    """

    def test_espaco_no_meio_da_palavra_nao_separa_o_item(self):
        resultado = consolidar(
            {
                "posicional": _saida(
                    identificador="1 Arroz, integral, cozido", energia_kcal=124
                ),
                "pdfplumber": _saida(
                    identificador="1 Arroz, integra l, cozido", energia_kcal=124
                ),
            }
        )

        assert len(resultado.celulas) == 1, "o item foi contado duas vezes"
        celula = resultado.celulas[0]
        assert celula.desfecho is Desfecho.CONCORDANCIA
        assert celula.concordaram == 2

    def test_acento_e_caixa_tambem_nao_separam(self):
        """O OCR devolve sem acento; a comparação não pode depender disso."""
        resultado = consolidar(
            {
                "posicional": _saida(identificador="102 Carálho, cozido", proteina_g=1.0),
                "ocr": _saida(identificador="102 CARALHO, COZIDO", proteina_g=1.0),
            }
        )

        assert len(resultado.celulas) == 1

    def test_itens_realmente_diferentes_continuam_separados(self):
        """Normalizar não pode colapsar alimentos distintos — seria pior que o
        problema que resolve, porque misturaria valores de itens diferentes."""
        resultado = consolidar(
            {
                "a": _saida(identificador="100 Brocolis, cozido", energia_kcal=25),
                "b": _saida(identificador="101 Brocolis, cru", energia_kcal=35),
            }
        )

        assert len(resultado.celulas) == 2

    def test_o_identificador_exibido_e_o_mais_legivel(self):
        """A planilha final mostra a versão com acento e sem espaço quebrado,
        não a normalizada — que serve para casar, não para ler."""
        resultado = consolidar(
            {
                "pdfplumber": _saida(identificador="1 Arroz, integra l", energia_kcal=124),
                "posicional": _saida(identificador="1 Arroz, integral", energia_kcal=124),
            }
        )

        assert resultado.celulas[0].item == "1 Arroz, integral"


class TestColunaFantasma:
    """Campo que **nenhuma** rota leu não vira pendência — vira nada.

    Encontrado na análise das pendências reais: **158 das 251** eram de um campo
    só, `Energia ⏸`, que o OCR inventou ao ler um cabeçalho corrompido. A coluna
    existe no cabeçalho e **todos os valores são nulos**.

    Pendência é pedido de trabalho humano. Mandar alguém revisar 158 células
    vazias de uma coluna que não existe no documento é ruído que **esconde as
    pendências verdadeiras** — no caso, 3.

    A distinção que importa: campo lido por alguém e sem consenso é pendência
    legítima; campo que ninguém leu em item nenhum é artefato de extração.
    """

    def test_campo_sem_nenhum_valor_nao_entra_na_planilha(self):
        resultado = consolidar(
            {
                "boa": [
                    _saida(identificador=f"Item {i}", energia_kcal=100 + i)[0]
                    for i in range(20)
                ],
                "ocr": [
                    _saida(identificador=f"Item {i}", **{"Energia —": None})[0]
                    for i in range(20)
                ],
            }
        )

        campos = {c.campo for c in resultado.celulas}
        assert "Energia —" not in campos
        assert "energia_kcal" in campos

    def test_com_um_item_so_a_coluna_vazia_continua_sendo_pendencia(self):
        """Um item não é evidência de coluna fantasma — é campo não lido.

        Sem esta ressalva, a regra descartaria a única pendência de uma extração
        pequena, que é exatamente onde a revisão humana mais importa.
        """
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=None),
                "b": _saida(identificador="Arroz", energia_kcal=None),
            }
        )

        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.PENDENCIA
        assert resultado.campos_vazios == []

    def test_campo_com_valor_em_algum_item_continua_valendo(self):
        """Nulo em um item não condena a coluna: dado esparso é dado."""
        resultado = consolidar(
            {
                "a": [
                    _saida(identificador="Arroz", fibra_g=None)[0],
                    _saida(identificador="Feijao", fibra_g=8.5)[0],
                ],
                "b": [
                    _saida(identificador="Arroz", fibra_g=None)[0],
                    _saida(identificador="Feijao", fibra_g=8.5)[0],
                ],
            }
        )

        campos = {c.campo for c in resultado.celulas}
        assert "fibra_g" in campos, "a coluna tem dado no Feijao"

    def test_um_valor_solto_nao_salva_a_coluna_fantasma(self):
        """O caso real: `Energia —` aparece em 159 itens e **um** tem valor `=`.

        Exigir vazio absoluto deixaria a coluna passar por causa desse único
        resíduo — 0,3% de preenchimento — e as 158 pendências continuariam
        afogando as 3 verdadeiras. O critério é proporção, não ausência total.
        """
        registros_boa = [
            _saida(identificador=f"Item {i}", energia_kcal=100 + i)[0] for i in range(200)
        ]
        registros_ocr = [
            _saida(identificador=f"Item {i}", **{"Energia —": None})[0] for i in range(200)
        ]
        registros_ocr[0] = _saida(identificador="Item 0", **{"Energia —": "="})[0]

        resultado = consolidar({"boa": registros_boa, "ocr": registros_ocr})

        assert "Energia —" in resultado.campos_vazios
        assert "Energia —" not in {c.campo for c in resultado.celulas}

    def test_campo_esparso_legitimo_sobrevive(self):
        """Um campo presente em 10% dos itens é dado raro, não artefato.

        O limiar precisa separar os dois casos, e é por isso que ele é baixo:
        cortar campo esparso legítimo perderia dado real.
        """
        registros = [
            _saida(identificador=f"Item {i}", colesterol_mg=None)[0] for i in range(100)
        ]
        for i in range(10):
            registros[i] = _saida(identificador=f"Item {i}", colesterol_mg=5.0)[0]

        resultado = consolidar({"a": registros, "b": list(registros)})

        assert "colesterol_mg" not in resultado.campos_vazios

    def test_a_coluna_descartada_e_relatada(self):
        """Sumir com uma coluna em silêncio esconderia extração defeituosa."""
        resultado = consolidar(
            {
                "boa": [
                    _saida(identificador=f"Item {i}", energia_kcal=100 + i)[0]
                    for i in range(20)
                ],
                "ocr": [
                    _saida(identificador=f"Item {i}", **{"Energia —": None})[0]
                    for i in range(20)
                ],
            }
        )

        assert "Energia —" in resultado.campos_vazios


class TestItemExclusivo:
    """Item lido por uma só rota, entre várias consultadas, não é voto único.

    Lacuna registrada em PLANO.md (pendência P-1.1/P0.1, achado das auditorias
    de 02/08): a rota `"consolidado"` chamava `consolidar()` com todos os itens
    de todas as rotas, inclusive os que só uma delas produziu. Um item assim
    virava `VOTO_UNICO` com confiança 0,9 — quase tão alta quanto concordância
    plena —, sem checar se veio de uma rota propensa a inventar linha. Medido:
    `camelot` devolveu 62 registros para uma página de ~31.

    A distinção que importa: item lido por **algumas** rotas (cobertura
    parcial genuína) continua com confiança normal — só o caso extremo, uma
    única rota entre várias consultadas, vira pendência.
    """

    def test_item_lido_por_uma_so_rota_entre_varias_vira_pendencia(self):
        resultado = consolidar(
            {
                "pdfplumber": _saida(identificador="Arroz", energia_kcal=124),
                "posicional": _saida(identificador="Arroz", energia_kcal=124),
                "camelot": _saida(identificador="Item Fantasma", energia_kcal=999),
            }
        )

        celula = resultado.celula("Item Fantasma", "energia_kcal")
        assert celula.desfecho is Desfecho.ITEM_EXCLUSIVO
        assert not celula.preenche
        assert celula.valor is None

    def test_item_exclusivo_nao_e_confundido_com_voto_unico_de_campo(self):
        """Voto único de **campo** (item lido por todas, só uma preencheu este
        campo) continua sendo aproveitado — é caso diferente, já coberto por
        `TestPendencia.test_um_voto_so_nao_e_concordancia`."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=None),
                "c": _saida(identificador="Item Fantasma", energia_kcal=999),
            }
        )

        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.VOTO_UNICO
        assert resultado.celula("Item Fantasma", "energia_kcal").desfecho is (
            Desfecho.ITEM_EXCLUSIVO
        )

    def test_cobertura_parcial_genuina_nao_e_penalizada(self):
        """Item lido por 2 de 3 rotas, com as duas concordando, continua
        concordância normal — só a leitura solitária é suspeita."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "c": _saida(identificador="Feijao", energia_kcal=76),
            }
        )

        assert resultado.celula("Arroz", "energia_kcal").desfecho is Desfecho.CONCORDANCIA

    def test_com_uma_unica_rota_ativa_nao_ha_item_exclusivo(self):
        """Sem outra rota para comparar, a única leitura disponível continua
        sendo aproveitada como voto único — é o caso do Cenário A
        (`pipeline.Pipeline`, um extrator por documento)."""
        resultado = consolidar({"a": _saida(identificador="Arroz", energia_kcal=124)})

        celula = resultado.celula("Arroz", "energia_kcal")
        assert celula.desfecho is Desfecho.VOTO_UNICO
        assert celula.valor == 124

    def test_item_exclusivo_vira_pendencia_para_o_humano_com_motivo_proprio(self):
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "camelot": _saida(identificador="Item Fantasma", energia_kcal=999),
            }
        )

        pendencia = next(p for p in resultado.pendencias if p.item == "Item Fantasma")
        assert "fabricação" in pendencia.motivo or "só" in pendencia.motivo

    def test_item_exclusivo_nao_entra_na_planilha_materializada(self):
        """O bug real: o valor fabricado ia para o CSV/JSON como dado com
        confiança 0,9. Depois da correção, vira ausente — trabalho humano, não
        dado publicado."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "camelot": _saida(identificador="Item Fantasma", energia_kcal=999),
            }
        )

        registros = materializar(resultado, fonte="teste")
        fantasma = next(
            r for r in registros if r.campos["identificador"].valor == "Item Fantasma"
        )
        assert fantasma.campos["energia_kcal"].origem.value == "ausente"

    def test_o_valor_nao_confirmado_fica_visivel_para_conferencia(self):
        """Pendência não é sumir com o dado — é não publicá-lo sem revisão.
        Quem for conferir precisa ver o que a rota solitária leu."""
        resultado = consolidar(
            {
                "a": _saida(identificador="Arroz", energia_kcal=124),
                "b": _saida(identificador="Arroz", energia_kcal=124),
                "camelot": _saida(identificador="Item Fantasma", energia_kcal=999),
            }
        )

        assert "999" in resultado.relatorio()


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
