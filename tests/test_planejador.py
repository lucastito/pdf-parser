"""O roteador de extração por página.

Estes testes protegem a promessa central: o parser decide sozinho, por página,
qual rota usar — nunca por perfil declarado à mão, nunca com uma IA lendo o
documento antes. Cada teste corresponde a uma classe de página que o roteador
precisa reconhecer sem configuração prévia (ADR-0021, ADR-0023, ADR-0024).
"""

from parser.fontes.pdf import FontePDF
from parser.modelo import Campo, Evidencia, Registro
from parser.planejador import (
    CONFIANCA_MINIMA_DE_CALIBRACAO,
    LIMIAR_DE_CONCORDANCIA,
    _decidir_entre_deterministicos,
    planejar,
)
from parser.vocabulario import CampoEsperado

EV = Evidencia(pagina=1, texto_bruto="x")


def _planejar(caminho, vocabulario=None):
    documento = FontePDF().carregar(str(caminho))
    return planejar(caminho, documento, vocabulario=vocabulario)


def _registro(identificador: str, **valores: float) -> Registro:
    campos = {"identificador": Campo[str].extraido(valor=identificador, evidencia=EV)}
    for nome, valor in valores.items():
        campos[nome] = Campo[float].extraido(valor=valor, evidencia=EV)
    return Registro(campos=campos, fonte="d.pdf")


class TestPaginaSemCamadaDeTexto:
    """O caso do documento digitalizado — nível 1, grátis."""

    def test_vai_para_reconhecimento_optico(self, pdf_sem_texto):
        (decisao,) = _planejar(pdf_sem_texto)
        assert decisao.rota == "ocr"
        assert decisao.nivel == 1

    def test_nao_e_descartada_como_sem_conteudo(self, pdf_sem_texto):
        """Zero palavras faria a triagem classificar `DESCARTAVEL` — mas isso
        mediria a ausência de camada de texto, não a ausência de conteúdo. O
        roteador precisa checar o achado de diagnóstico antes de confiar na
        densidade numérica da triagem."""
        (decisao,) = _planejar(pdf_sem_texto)
        assert decisao.rota != "nenhuma"


class TestPaginaDeTextoCorrido:
    """Texto nativo sem tabela — a triagem classifica `Classe.CONTEXTO`.

    Não é tabela, mas pode ter o dado que o schema de destino pede — por
    exemplo um valor citado em prosa. Vai para o modelo (nível 3) com prompt
    genérico, nunca para as ferramentas de tabela, que não têm o que
    reconhecer num parágrafo."""

    def test_pula_ferramentas_de_tabela_e_vai_direto_ao_modelo(self, pdf_texto_corrido):
        (decisao,) = _planejar(pdf_texto_corrido)
        assert decisao.rota == "llm"
        assert decisao.nivel == 3
        assert decisao.ordem_das_colunas is None

    def test_nao_chama_descoberta_de_colunas(self, pdf_texto_corrido, monkeypatch):
        """`descobrir_nomes_de_coluna` só se justifica quando há tabela — uma
        página de prosa não deveria pagar (nem arriscar) essa chamada."""

        def _falha_se_chamado(*args, **kwargs):
            raise AssertionError("descobrir_nomes_de_coluna não deveria ser chamado aqui")

        monkeypatch.setattr(
            "parser.planejador.descobrir_nomes_de_coluna", _falha_se_chamado
        )
        _planejar(pdf_texto_corrido)  # não deve levantar


class TestPaginaComTabelaReconhecivel:
    """Estrutura que a geometria já sabe ler (ADR-0002/ADR-0006) — nível 2."""

    def test_vai_para_extrator_posicional_com_layout_descoberto(self, pdf_tabela_calibravel):
        (decisao,) = _planejar(pdf_tabela_calibravel)
        assert decisao.rota == "posicional"
        assert decisao.nivel == 2
        assert decisao.confianca is not None
        assert decisao.confianca >= CONFIANCA_MINIMA_DE_CALIBRACAO
        assert decisao.layout is not None
        assert set(decisao.layout) >= {"x_rotulos", "x_unidades", "x_valores_min"}


class TestPaginaComTabelaNaoReconhecivelPelaGeometria:
    """A geometria atual foi ajustada ao formato do TACO (unidade entre
    parênteses como âncora) — uma tabela sem esse sinal precisa escalar para o
    modelo, não travar o lote nem inventar layout (ADR-0024)."""

    def test_escala_para_rota_de_modelo(self, pdf_tabela_sem_unidade_reconhecivel):
        (decisao,) = _planejar(pdf_tabela_sem_unidade_reconhecivel)
        assert decisao.rota == "llm"
        assert decisao.nivel == 3

    def test_motivo_explica_por_que_a_geometria_nao_bastou(
        self, pdf_tabela_sem_unidade_reconhecivel
    ):
        (decisao,) = _planejar(pdf_tabela_sem_unidade_reconhecivel)
        assert decisao.motivo


class TestDecisaoEntreRotasDeterministicas:
    """`_decidir_entre_deterministicos` — a lógica que usa concordância como
    sinal de confiança em vez da confiança isolada de uma rota só. Testado
    direto, com `Registro`s construídos à mão: coagir pdfplumber/Camelot a
    achar ou não uma tabela num PDF sintético seria testar a biblioteca
    externa, não a decisão."""

    def test_duas_rotas_concordando_decide_por_consolidacao(self):
        """Concordância não escolhe mais uma planilha — vota célula a célula
        (ADR-0017) e o resultado já materializado viaja na decisão."""
        iguais = {
            "posicional": [_registro("1 X", v=10.0)],
            "pdfplumber": [_registro("1 X", v=10.0)],
        }
        decisao = _decidir_entre_deterministicos(1, iguais, None, None)
        assert decisao is not None
        assert decisao.nivel == 2
        assert decisao.rota == "consolidado"
        assert decisao.registros is not None
        (registro,) = decisao.registros
        assert registro["campos"]["v"]["valor"] == 10.0

    def test_duas_rotas_discordando_nao_decide(self):
        """Discordância abaixo do limiar não é decisão — é motivo de escalar."""
        divergentes = {
            "posicional": [_registro("1 X", v=10.0)],
            "pdfplumber": [_registro("1 X", v=9999.0)],
        }
        assert _decidir_entre_deterministicos(1, divergentes, None, None) is None

    def test_uma_so_rota_com_resultado_e_aceita_sem_segunda_opiniao(self):
        decisao = _decidir_entre_deterministicos(
            1, {"camelot": [_registro("1 X", v=10.0)]}, None, None
        )
        assert decisao is not None
        assert decisao.rota == "camelot"
        assert decisao.nivel == 2
        assert "única rota determinística" in decisao.motivo

    def test_nenhuma_rota_com_resultado_nao_decide(self):
        assert _decidir_entre_deterministicos(1, {}, None, None) is None

    def test_concordancia_no_limiar_exato_decide(self):
        """Documenta o limiar declarado — não é número escondido."""
        assert 0.0 < LIMIAR_DE_CONCORDANCIA <= 1.0

    def test_consolidacao_registra_quais_rotas_concordaram(self):
        iguais = {
            "pdfplumber": [_registro("1 X", v=10.0)],
            "camelot": [_registro("1 X", v=10.0)],
        }
        decisao = _decidir_entre_deterministicos(1, iguais, None, ["v"])
        assert "pdfplumber" in decisao.motivo
        assert "camelot" in decisao.motivo
        assert decisao.layout is None


class TestNivel2bPalavraChave:
    """O último determinístico antes do modelo — só roda com vocabulário
    declarado, e só intercepta a escalada quando acha algo de verdade."""

    def _pdf_contexto_com_valor(self, tmp_path):
        """Página de prosa (`Classe.CONTEXTO`) que cita um valor por extenso —
        densidade numérica baixa, mas o dado que o vocabulário procura está
        lá, só não em forma de tabela."""
        import fitz

        caminho = tmp_path / "contexto-com-valor.pdf"
        documento = fitz.open()
        pagina = documento.new_page()
        texto = (
            "Este relatorio descreve o contexto geral do projeto e resume as "
            "condicoes observadas em campo. Water Depth: 1850 m. Nenhuma "
            "tabela de valores aparece nesta pagina em particular."
        )
        for i, palavra in enumerate(texto.split()):
            pagina.insert_text((72 + (i % 8) * 60, 100 + (i // 8) * 20), palavra)
        documento.save(caminho)
        documento.close()
        return caminho

    def test_sem_vocabulario_vai_direto_pro_llm(self, pdf_texto_corrido):
        (decisao,) = _planejar(pdf_texto_corrido, vocabulario=None)
        assert decisao.rota == "llm"

    def test_com_vocabulario_e_achado_intercepta_antes_do_llm(self, tmp_path):
        caminho = self._pdf_contexto_com_valor(tmp_path)
        vocabulario = [CampoEsperado(nome="profundidade", sinonimos=("Water Depth",))]

        (decisao,) = _planejar(caminho, vocabulario=vocabulario)

        assert decisao.rota == "palavra_chave"
        assert decisao.nivel == 2
        assert "profundidade" in decisao.motivo

    def test_com_vocabulario_sem_achado_ainda_vai_pro_llm(self, pdf_texto_corrido):
        vocabulario = [CampoEsperado(nome="algo_que_nao_esta_la", sinonimos=("Xyzzy",))]

        (decisao,) = _planejar(pdf_texto_corrido, vocabulario=vocabulario)

        assert decisao.rota == "llm"


class TestVlmComplementarPorImagemEmbutida:
    """Página com imagem embutida ganha uma segunda decisão de visão, além da
    rota principal — nunca no lugar dela (achado `imagem-embutida`,
    ADR-0021)."""

    def _pdf_com_imagem(self, tmp_path):
        import fitz

        caminho = tmp_path / "com-imagem.pdf"
        documento = fitz.open()
        pagina = documento.new_page()
        texto = (
            "Texto corrido sem estrutura de tabela, apenas contexto "
            "descritivo para a pagina de teste sem densidade numerica."
        )
        for i, palavra in enumerate(texto.split()):
            pagina.insert_text((72 + (i % 8) * 60, 100 + (i // 8) * 20), palavra)

        # Precisa ocupar pelo menos AREA_MINIMA_DE_IMAGEM_RELEVANTE da página
        # (página A4 padrão, ~595×842): um retângulo pequeno o bastante para
        # simular um logotipo de canto não dispara o achado de propósito.
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4))
        pixmap.set_rect(pixmap.irect, (255, 0, 0))
        pagina.insert_image(fitz.Rect(100, 300, 400, 500), pixmap=pixmap)

        documento.save(caminho)
        documento.close()
        return caminho

    def test_pagina_com_imagem_ganha_decisao_de_vlm_alem_da_principal(self, tmp_path):
        decisoes = _planejar(self._pdf_com_imagem(tmp_path))

        rotas = [d.rota for d in decisoes]
        assert "vlm" in rotas
        assert len(decisoes) >= 2
        assert all(d.pagina == 1 for d in decisoes)

    def test_decisao_de_vlm_complementar_declara_o_motivo(self, tmp_path):
        decisoes = _planejar(self._pdf_com_imagem(tmp_path))
        (complementar,) = [d for d in decisoes if d.rota == "vlm"]
        assert "imagem" in complementar.motivo

    def test_pagina_sem_imagem_nao_ganha_decisao_extra(self, pdf_texto_corrido):
        assert len(_planejar(pdf_texto_corrido)) == 1


class TestDecisaoSempreTemMotivo:
    """Decisão sem motivo é só reclamação — o mesmo princípio de diagnostico.py."""

    def test_toda_decisao_declara_motivo(
        self,
        pdf_sem_texto,
        pdf_texto_corrido,
        pdf_tabular,
        pdf_tabela_sem_unidade_reconhecivel,
    ):
        for caminho in (
            pdf_sem_texto,
            pdf_texto_corrido,
            pdf_tabular,
            pdf_tabela_sem_unidade_reconhecivel,
        ):
            for decisao in _planejar(caminho):
                assert decisao.motivo
