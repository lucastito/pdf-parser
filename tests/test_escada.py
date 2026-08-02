"""A escada de modelos é uma fonte só, e a alocação respeita o desenho.

Estes testes existem por um defeito medido: a lista de modelos vivia em três
lugares — o instalador em PowerShell, a constante da linha de comando e a tabela do
levantamento — e os três divergiram. O instalador ficou com 8 de 13 modelos, e o
teste que deveria pegar isso comparava justamente os dois que concordavam entre si.

O que se verifica aqui não é que o código roda: é que **o desenho do experimento
sobrevive ao código**. Uma máquina que baixe um conjunto sem modelo de visão, ou sem
uma das origens, produz resultado que não responde à pergunta — e ninguém perceberia
antes de horas de execução na máquina de outra pessoa.
"""

import pytest

from parser.escada import (
    ESCADA,
    MODELOS_DO_EXPERIMENTO,
    TODOS_OS_FABRICANTES,
    alocar,
    estendidos,
    fabricantes,
    modelo_de_falha,
    obrigatorios,
)

# (vram_gb, ram_livre_gb, placa_util, apelido) — os envelopes reais do experimento.
# A de referência entra com `placa_util=False`: a placa dela funciona e **não
# acelera** (17,1 contra 17,5 tokens/s, medido), e tratá-la como aceleradora
# produziria uma lista que levaria dias por página.
MAQUINAS = [
    (2, 15.8, False, "referência"),
    (6, 16.0, True, "6 GB"),
    (8, 16.0, True, "8 GB"),
    (12, 32.0, True, "12 GB"),
    (16, 32.0, True, "16 GB"),
]


class TestEscada:
    def test_a_escada_nao_esta_vazia(self):
        """Guarda contra todos os testes abaixo passarem por não haver nada."""
        assert len(ESCADA) >= 10

    def test_os_nomes_derivam_da_escada(self):
        assert MODELOS_DO_EXPERIMENTO == tuple(m.nome for m in ESCADA)

    def test_nao_ha_modelo_repetido(self):
        nomes = [m.nome for m in ESCADA]
        assert len(nomes) == len(set(nomes)), f"repetido em {nomes}"

    def test_ha_ao_menos_cinco_origens(self):
        """Concentração de origem já foi erro deste projeto.

        A primeira escada tinha nove modelos da mesma família. Se ela fosse ruim no
        documento testado, a conclusão registrada seria "modelos abertos não servem
        para tabela" quando o correto seria "aquela família não serve" — e isso
        muda decisão de infraestrutura (ADR-0014).
        """
        assert len(TODOS_OS_FABRICANTES) >= 5, sorted(TODOS_OS_FABRICANTES)

    def test_toda_origem_tem_um_modelo_pequeno_ou_e_declarada_grande(self):
        """Origem que só existe em porte grande não alcança máquina pequena.

        Não é defeito — é limitação a conhecer. O teste falha se **nenhuma** origem
        tiver porte pequeno, o que faria toda máquina modesta rodar uma família só.
        """
        pequenas = {m.fabricante for m in ESCADA if m.tamanho_gb <= 3.5}
        assert len(pequenas) >= 3, (
            f"só {sorted(pequenas)} têm modelo pequeno; uma máquina modesta ficaria "
            "sem diversidade de origem"
        )

    def test_ha_modelo_de_visao_e_de_texto(self):
        assert any(m.le_imagem for m in ESCADA)
        assert any(m.le_texto for m in ESCADA)

    def test_todo_modelo_declara_a_pergunta_que_responde(self):
        """Modelo que não isola variável nova não entra, por melhor que seja."""
        sem = [m.nome for m in ESCADA if not m.pergunta.strip()]
        assert not sem, f"sem justificativa de existência: {sem}"

    def test_os_tres_portes_da_familia_de_referencia_estao_presentes(self):
        """A curva de tamanho mais limpa que o experimento tem.

        Mesma origem, geração e quantização — só o tamanho muda. Perder um porte
        transforma três pontos em dois, e dois pontos não descrevem curva.
        """
        portes = sorted(
            m.tamanho_gb
            for m in ESCADA
            if m.nome.startswith("qwen3-vl:") and m.tamanho_gb < 10
        )
        assert len(portes) >= 3, f"só {len(portes)} portes pequenos da família"


@pytest.mark.parametrize("vram, ram, util, apelido", MAQUINAS, ids=[m[3] for m in MAQUINAS])
class TestAlocacaoPorMaquina:
    """O desenho do experimento tem de sobreviver em toda máquina.

    Cada uma destas asserções corresponde a uma exigência declarada: sem elas, uma
    máquina rodaria por horas e produziria dado que não responde à pergunta.
    """

    def test_roda_ao_menos_um_de_visao_e_um_de_texto(self, vram, ram, util, apelido):
        """Uma máquina sem as duas rotas não compara rotas — e é a comparação que
        o experimento existe para fazer."""
        a = alocar(vram, ram, placa_util=util)
        todos = a["obrigatorio"] + a["estendido"]
        assert any(m.le_imagem for m in todos), f"{apelido} sem modelo de visão"
        assert any(m.le_texto for m in todos), f"{apelido} sem modelo de texto"

    def test_alcanca_todas_as_origens(self, vram, ram, util, apelido):
        """Cobertura de fabricante é requisito, não sobra.

        O limite de tempo, sozinho, tirava a família independente da máquina sem
        aceleração — justamente a que existe como controle de origem. `alocar`
        completa com o menor modelo de cada origem ausente, aceitando que rode
        devagar: um ponto lento de uma família é melhor que nenhum.
        """
        a = alocar(vram, ram, placa_util=util)
        presentes = fabricantes(a["obrigatorio"] + a["estendido"])
        faltando = TODOS_OS_FABRICANTES - presentes
        assert not faltando, f"{apelido} não roda nenhum modelo de {sorted(faltando)}"

    def test_o_obrigatorio_cabe_na_placa(self, vram, ram, util, apelido):
        """Obrigatório é o que roda acelerado — é o que torna as máquinas
        comparáveis entre si."""
        for m in alocar(vram, ram, placa_util=util)["obrigatorio"]:
            assert m.tamanho_gb <= vram, (
                f"{apelido}: {m.nome} ({m.tamanho_gb} GB) não cabe em {vram} GB de "
                "placa e não deveria estar no conjunto acelerado"
            )

    def test_o_de_falha_nao_esta_entre_os_esperados(self, vram, ram, util, apelido):
        """Baixá-lo duas vezes desperdiça banda; contá-lo como esperado inverteria
        a leitura — a falha dele **é** o dado."""
        a = alocar(vram, ram, placa_util=util)
        esperados = {m.nome for m in a["obrigatorio"] + a["estendido"]}
        for m in a["falha"]:
            assert m.nome not in esperados


class TestGradacaoEntreMaquinas:
    def test_maquina_maior_nunca_roda_menos_que_a_menor(self):
        """Se uma máquina maior rodasse menos, a curva inverteria sem razão física."""
        anterior = 0
        for vram, ram, util, apelido in MAQUINAS[1:]:
            a = alocar(vram, ram, placa_util=util)
            quantos = len(a["obrigatorio"]) + len(a["estendido"])
            assert quantos >= anterior, f"{apelido} roda menos que a máquina anterior"
            anterior = quantos

    def test_a_placa_maior_acelera_mais_modelos(self):
        """O conjunto acelerado tem de crescer com a placa — é o que a comparação
        entre envelopes mede."""
        tamanhos = [len(obrigatorios(v)) for v, _, _, _ in MAQUINAS]
        assert tamanhos == sorted(tamanhos), tamanhos
        assert tamanhos[-1] > tamanhos[0], "placa maior não acelerou mais nada"


class TestLimites:
    def test_memoria_nao_e_o_unico_limite(self):
        """Sem teto de tempo, a máquina sem aceleração baixaria a escada inteira.

        Ela tem memória de sobra e placa que não acelera: pelo critério de memória,
        levaria os modelos de 20 GB e gastaria dias por página. O teto existe para
        que o conjunto continue medindo o que se propõe.
        """
        sem_teto = [m for m in ESCADA if m.tamanho_gb <= 2 + 15.8 * 0.60]
        com_teto = alocar(2, 15.8, placa_util=False)
        todos = com_teto["obrigatorio"] + com_teto["estendido"]
        assert len(todos) < len(sem_teto), "o teto de tempo não restringiu nada"

    def test_placa_util_muda_o_resultado(self):
        """A distinção precisa ter consequência — senão o parâmetro é decorativo.

        E ela vem de **medição**: a placa da máquina de referência funciona e não
        acelera. Inferir pelo nome da peça produziria a lista errada.
        """
        com = estendidos(2, 15.8, placa_util=True)
        sem = estendidos(2, 15.8, placa_util=False)
        assert len(sem) > len(com), "declarar a placa inútil não mudou nada"

    def test_maquina_que_comporta_tudo_nao_tem_modelo_de_falha(self):
        """`None` é resultado: significa que a máquina não encontrou o próprio
        limite nesta escada."""
        assert modelo_de_falha(64, 128) is None

    def test_maquina_pequena_tem_modelo_de_falha_proximo(self):
        """O teto é relativo à máquina: a pequena não baixa 20 GB à toa."""
        falha = modelo_de_falha(6, 16, placa_util=True)
        assert falha is not None
        maior = max(m.tamanho_gb for m in ESCADA)
        assert falha.tamanho_gb < maior, "escolheu o maior da escada, não o próximo"
