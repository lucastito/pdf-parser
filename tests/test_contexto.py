"""O contexto é calculado, não adivinhado — e o cálculo tem dois lados.

Errar **para baixo** corta a resposta: a chamada inteira se perde, e o sintoma é
resposta vazia, que já custou uma sessão de investigação (ADR-0018).

Errar **para cima** também custa, e o custo não é neutro: cada token de contexto
cobra memória. Medido num modelo de 4B, contexto de 64k pede ~13 GB e não cabe
numa placa de 12 GB. Quando não cabe, o servidor despeja o modelo para o
processador e fica ordens de grandeza mais lento — falha **silenciosa**, que
sairia no resultado como "esta máquina é lenta" (ADR-0019).

Por isso o cálculo é um `min` de três coisas, e não "o maior valor possível".
"""

import pytest

from parser.contexto import CustoDeMemoria, dimensionar


class TestNecessario:
    """O que a chamada precisa: entrada medida + saída esperada + folga."""

    def test_soma_entrada_saida_e_folga(self):
        assert dimensionar(entrada=2200, saida_esperada=6000, folga=1.0) == 8200

    def test_a_folga_multiplica_o_necessario(self):
        assert dimensionar(entrada=2000, saida_esperada=2000, folga=2.0) == 8000

    def test_entrada_medida_nao_estimada(self):
        """A entrada é o termo que faltou: com imagem ela é a maior parte.

        Duas resoluções da mesma página dão entradas diferentes, e supor um
        valor foi exatamente o erro que produziu a conclusão errada.
        """
        pequena = dimensionar(entrada=800, saida_esperada=2000, folga=1.0)
        grande = dimensionar(entrada=2200, saida_esperada=2000, folga=1.0)
        assert grande > pequena


class TestLimiteDoModelo:
    """Nunca pedir mais do que o modelo comporta — o servidor recusaria."""

    def test_nao_ultrapassa_o_nativo(self):
        assert dimensionar(entrada=2000, saida_esperada=90000, nativo=32768) == 32768

    def test_abaixo_do_nativo_usa_o_necessario(self):
        assert dimensionar(entrada=1000, saida_esperada=1000, nativo=32768, folga=1.0) == 2000


class TestLimiteDeMemoria:
    """O limite que aperta na prática — e o único cujo estouro é silencioso."""

    def test_memoria_limita_mesmo_com_nativo_alto(self):
        """Um modelo de 256k de contexto não cabe numa placa pequena."""
        custo = CustoDeMemoria(peso_gb=3.0, por_token_gb=0.00015)
        usado = dimensionar(
            entrada=2000,
            saida_esperada=200000,
            nativo=262144,
            memoria_livre_gb=6.0,
            custo=custo,
        )
        assert usado < 262144
        assert custo.memoria_para(usado) <= 6.0

    def test_o_resultado_sempre_cabe_na_memoria(self):
        custo = CustoDeMemoria(peso_gb=3.6, por_token_gb=0.000153)
        for livre in (4.0, 6.0, 12.0, 24.0):
            usado = dimensionar(
                entrada=2200,
                saida_esperada=50000,
                nativo=262144,
                memoria_livre_gb=livre,
                custo=custo,
            )
            assert custo.memoria_para(usado) <= livre, f"estourou com {livre} GB livres"

    def test_sem_dado_de_memoria_nao_inventa_limite(self):
        """Omitir o dado não pode virar um teto arbitrário (ADR-0008)."""
        assert dimensionar(entrada=2000, saida_esperada=6000, folga=1.0) == 8000

    def test_memoria_insuficiente_ate_para_o_peso_e_erro_explicito(self):
        """Falhar alto é melhor que rodar em processador sem ninguém notar.

        É a contaminação silenciosa do ADR-0019: o número sairia plausível e
        seria atribuído à máquina, não à configuração.
        """
        custo = CustoDeMemoria(peso_gb=8.0, por_token_gb=0.0002)
        with pytest.raises(ValueError, match="não cabe|nao cabe"):
            dimensionar(
                entrada=2000,
                saida_esperada=4000,
                memoria_livre_gb=6.0,
                custo=custo,
            )


class TestCustoDeMemoria:
    """A curva medida: ajustada com dois pontos, previu o terceiro a 0,4%."""

    def test_reproduz_a_medicao(self):
        """4096 → 3,6 GB e 32768 → 8,0 GB, num modelo de visão de 4B."""
        custo = CustoDeMemoria.a_partir_de_dois_pontos(
            contexto_a=4096, memoria_a_gb=3.6, contexto_b=32768, memoria_b_gb=8.0
        )
        assert custo.memoria_para(4096) == pytest.approx(3.6, abs=0.05)
        assert custo.memoria_para(32768) == pytest.approx(8.0, abs=0.05)

    def test_preve_o_ponto_intermediario_medido(self):
        """O teste que separa curva ajustada de curva com poder preditivo.

        16384 foi medido em 5,5 GB e **não** entrou no ajuste.
        """
        custo = CustoDeMemoria.a_partir_de_dois_pontos(
            contexto_a=4096, memoria_a_gb=3.6, contexto_b=32768, memoria_b_gb=8.0
        )
        assert custo.memoria_para(16384) == pytest.approx(5.5, abs=0.15)

    def test_dois_pontos_iguais_nao_definem_reta(self):
        with pytest.raises(ValueError, match="distintos"):
            CustoDeMemoria.a_partir_de_dois_pontos(
                contexto_a=4096, memoria_a_gb=3.6, contexto_b=4096, memoria_b_gb=3.6
            )


class TestRegressaoDoCasoMedido:
    """O caso real que produziu a conclusão errada, como teste."""

    def test_o_contexto_padrao_nao_bastaria(self):
        """Entrada de 2227 + saída de 1869 = 4096: exatamente o padrão.

        O cálculo tem de pedir mais do que isso — foi o que faltou.
        """
        assert dimensionar(entrada=2227, saida_esperada=6000, folga=1.0) > 4096

    def test_a_folga_padrao_cobre_a_maior_saida_observada(self):
        """Maior saída medida: 5948 tokens, na rota de texto."""
        assert dimensionar(entrada=2233, saida_esperada=5948) >= 2233 + 5948
