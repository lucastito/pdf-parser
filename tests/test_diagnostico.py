"""Diagnóstico de documento e validação de saída.

Este módulo carrega o **conhecimento operacional** aprendido na prática: as
características de documento que sabotam a extração, e as verificações que pegam
saída plausível mas errada.

O que estes testes protegem: que esse conhecimento não volte a ficar enterrado
dentro de um extrator específico. A rotação de página derrubava quatro ferramentas
a 0% de acurácia, e o tratamento vivia duplicado em dois arquivos com
implementações diferentes — a terceira ferramenta não tratava.
"""

import pytest

from parser.diagnostico import (
    Achado,
    MetodoDeDeteccao,
    Severidade,
    caracteristicas_do_documento,
    caracterizar_documento,
    caracterizar_pagina,
    contagem_por_caracteristica,
    diagnosticar,
    paginas_por_caracteristica,
    validar_registros,
)
from parser.modelo import Campo, Evidencia, Registro, Sentinela

EV = Evidencia(pagina=1, texto_bruto="x")


def _registro(**valores) -> Registro:
    campos = {}
    for nome, valor in valores.items():
        if valor is None:
            campos[nome] = Campo.ausente()
        elif isinstance(valor, Sentinela):
            campos[nome] = Campo[float].extraido(sentinela=valor, evidencia=EV)
        elif isinstance(valor, str):
            campos[nome] = Campo[str].extraido(valor=valor, evidencia=EV)
        else:
            campos[nome] = Campo[float].extraido(valor=valor, evidencia=EV)
    return Registro(campos=campos, fonte="d.pdf")


class TestDiagnosticoDeDocumento:
    def test_detecta_documento_sem_problema(self, pdf_exemplo):
        achados = diagnosticar(str(pdf_exemplo))
        assert all(a.severidade is not Severidade.BLOQUEIA for a in achados)

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            diagnosticar(str(tmp_path / "nao-existe.pdf"))

    def test_achado_tem_acao_recomendada(self, pdf_exemplo):
        """Diagnóstico sem ação é só reclamação."""
        for achado in diagnosticar(str(pdf_exemplo)):
            assert achado.acao, f"achado {achado.codigo} sem ação recomendada"

    def test_achado_cita_a_evidencia(self, pdf_exemplo):
        for achado in diagnosticar(str(pdf_exemplo)):
            assert achado.detalhe, f"achado {achado.codigo} sem detalhe medido"


class TestRotacaoDetectada:
    """A verificação que faltava: rotação derrubou quatro ferramentas a 0%."""

    def test_detecta_pagina_rotacionada(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        pagina.insert_text((72, 72), "texto")
        pagina.set_rotation(90)
        caminho = tmp_path / "rot.pdf"
        documento.save(str(caminho))
        documento.close()

        achados = diagnosticar(str(caminho))
        codigos = {a.codigo for a in achados}
        assert "pagina-rotacionada" in codigos

    def test_pagina_sem_rotacao_nao_gera_achado(self, pdf_exemplo):
        codigos = {a.codigo for a in diagnosticar(str(pdf_exemplo))}
        assert "pagina-rotacionada" not in codigos


class TestCaracterizarPagina:
    """Os mesmos achados de `diagnosticar`, mas isolados por página — é o que o
    roteador de extração (`parser.planejador`) precisa para decidir página a
    página, em vez de por documento inteiro."""

    def test_so_a_pagina_rotacionada_recebe_o_achado(self, tmp_path):
        import fitz

        documento = fitz.open()
        normal = documento.new_page()
        normal.insert_text((72, 72), "texto")
        rotacionada = documento.new_page()
        rotacionada.insert_text((72, 72), "texto")
        rotacionada.set_rotation(90)
        caminho = tmp_path / "mista.pdf"
        documento.save(str(caminho))
        documento.close()

        aberto = fitz.open(caminho)
        try:
            assert "pagina-rotacionada" not in {
                a.codigo for a in caracterizar_pagina(aberto, 1)
            }
            assert "pagina-rotacionada" in {a.codigo for a in caracterizar_pagina(aberto, 2)}
        finally:
            aberto.close()

    def test_so_a_pagina_sem_texto_recebe_o_achado(self, tmp_path):
        import fitz

        documento = fitz.open()
        com_texto = documento.new_page()
        com_texto.insert_text((72, 72), "texto")
        documento.new_page()  # sem inserir texto algum
        caminho = tmp_path / "mista-texto.pdf"
        documento.save(str(caminho))
        documento.close()

        aberto = fitz.open(caminho)
        try:
            assert "sem-camada-de-texto" not in {
                a.codigo for a in caracterizar_pagina(aberto, 1)
            }
            assert "sem-camada-de-texto" in {a.codigo for a in caracterizar_pagina(aberto, 2)}
        finally:
            aberto.close()

    def test_pagina_sem_problema_nao_gera_achado_grave(self, pdf_exemplo):
        import fitz

        aberto = fitz.open(pdf_exemplo)
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert all(a.severidade is not Severidade.BLOQUEIA for a in achados)

    def test_detalhe_cita_o_numero_da_pagina(self, tmp_path):
        import fitz

        documento = fitz.open()
        documento.new_page()  # página 1, sem texto
        caminho = tmp_path / "sem-texto.pdf"
        documento.save(str(caminho))
        documento.close()

        aberto = fitz.open(caminho)
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        (achado,) = [a for a in achados if a.codigo == "sem-camada-de-texto"]
        assert "1" in achado.detalhe


class TestMetodoDeDeteccao:
    """Todo achado de característica declara **como** foi descoberto — a
    mesma disciplina que o projeto já aplica ao valor extraído (proveniência
    por campo, CLAUDE.md), aplicada agora à própria detecção da
    característica.
    """

    def test_rotacao_e_metadado_nativo(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        pagina.insert_text((72, 72), "texto")
        pagina.set_rotation(90)
        caminho = tmp_path / "rot.pdf"
        documento.save(str(caminho))
        documento.close()

        aberto = fitz.open(caminho)
        try:
            (achado,) = [
                a for a in caracterizar_pagina(aberto, 1) if a.codigo == "pagina-rotacionada"
            ]
        finally:
            aberto.close()
        assert achado.metodo is MetodoDeDeteccao.METADADO_NATIVO

    def test_sem_camada_de_texto_e_ferramenta_deterministica(self, tmp_path):
        import fitz

        documento = fitz.open()
        documento.new_page()
        caminho = tmp_path / "sem-texto.pdf"
        documento.save(str(caminho))
        documento.close()

        aberto = fitz.open(caminho)
        try:
            (achado,) = [
                a for a in caracterizar_pagina(aberto, 1) if a.codigo == "sem-camada-de-texto"
            ]
        finally:
            aberto.close()
        assert achado.metodo is MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA

    def test_achado_de_validacao_de_saida_nao_declara_metodo(self):
        """`validar_registros` examina resultado de extração, não
        característica de página — `metodo` não se aplica."""
        (achado,) = validar_registros([])
        assert achado.metodo is None

    def test_nenhum_achado_usa_llm_simples_ainda(self, pdf_exemplo):
        """Gap real, declarado: nenhum detector de característica hoje usa
        método 3. É o que falta pro eixo de domínio da taxonomia (ADR-0021)."""
        achados = diagnosticar(str(pdf_exemplo))
        assert not any(a.metodo is MetodoDeDeteccao.LLM_SIMPLES for a in achados)


class TestRegistroDeSondas:
    """`caracterizar_pagina` não verifica um catálogo fechado item a item —
    roda um registro de sondas e reporta o que cada uma achar. Adicionar
    característica nova é registrar uma sonda nova; esta suíte prova que
    isso não exige tocar em `caracterizar_pagina`.
    """

    def test_registrar_uma_sonda_nova_aparece_sem_tocar_a_funcao(
        self, pdf_exemplo, monkeypatch
    ):
        import parser.diagnostico as modulo

        def _sonda_de_teste(documento, numero):
            return Achado(
                codigo="caracteristica-de-teste",
                severidade=Severidade.NOTA,
                detalhe="sonda de teste sempre dispara",
                acao="nenhuma",
                metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
            )

        monkeypatch.setattr(modulo, "_SONDAS", modulo._SONDAS + [_sonda_de_teste])

        import fitz

        aberto = fitz.open(pdf_exemplo)
        try:
            codigos = {a.codigo for a in modulo.caracterizar_pagina(aberto, 1)}
        finally:
            aberto.close()
        assert "caracteristica-de-teste" in codigos

    def test_sonda_que_devolve_none_nao_produz_achado(self, pdf_exemplo, monkeypatch):
        import fitz

        import parser.diagnostico as modulo

        aberto = fitz.open(pdf_exemplo)
        try:
            antes = len(modulo.caracterizar_pagina(aberto, 1))

            monkeypatch.setattr(
                modulo, "_SONDAS", modulo._SONDAS + [lambda documento, numero: None]
            )
            depois = len(modulo.caracterizar_pagina(aberto, 1))
        finally:
            aberto.close()
        assert depois == antes


class TestCaracterizarDocumento:
    """`caracterizar_pagina` já existe página a página, mas só serve a quem
    já sabe qual página perguntar (o roteador, um número por vez). Falta a
    forma consultável do documento inteiro — "que características cada
    página tem" — que é o que descobrir característica por característica
    no corpus (−1.4, PLANO.md) precisa: sem isso, a única saída é chamar
    `caracterizar_pagina` em laço manual, ou ler número de página de dentro
    da string `detalhe` de `diagnosticar`.
    """

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            caracterizar_documento(str(tmp_path / "nao-existe.pdf"))

    def test_devolve_um_conjunto_de_achados_por_pagina(self, tmp_path):
        import fitz

        documento = fitz.open()
        normal = documento.new_page()
        normal.insert_text((72, 72), "texto")
        rotacionada = documento.new_page()
        rotacionada.insert_text((72, 72), "texto")
        rotacionada.set_rotation(90)
        caminho = tmp_path / "mista.pdf"
        documento.save(str(caminho))
        documento.close()

        resultado = caracterizar_documento(str(caminho))

        assert set(resultado) == {1, 2}
        assert "pagina-rotacionada" not in {a.codigo for a in resultado[1]}
        assert "pagina-rotacionada" in {a.codigo for a in resultado[2]}

    def test_bate_com_caracterizar_pagina_chamada_a_mao(self, pdf_exemplo):
        import fitz

        aberto = fitz.open(pdf_exemplo)
        try:
            esperado = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()

        resultado = caracterizar_documento(str(pdf_exemplo))
        assert resultado[1] == esperado


class TestPaginasPorCaracteristica:
    """A relação que a escolha de página de triagem por característica
    precisa (ADR-0021): não "que características esta página tem", mas
    "quais páginas têm esta característica" — o inverso."""

    def test_inverte_pagina_para_caracteristica_em_caracteristica_para_paginas(self, tmp_path):
        import fitz

        documento = fitz.open()
        normal = documento.new_page()
        normal.insert_text((72, 72), "texto")
        rotacionada = documento.new_page()
        rotacionada.insert_text((72, 72), "texto")
        rotacionada.set_rotation(90)
        caminho = tmp_path / "mista.pdf"
        documento.save(str(caminho))
        documento.close()

        caracterizacao = caracterizar_documento(str(caminho))
        por_caracteristica = paginas_por_caracteristica(caracterizacao)

        assert por_caracteristica["pagina-rotacionada"] == [2]

    def test_pagina_com_varias_caracteristicas_aparece_em_varias_listas(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        pagina.insert_text((72, 72), "texto")
        pagina.set_rotation(90)
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4))
        pixmap.set_rect(pixmap.irect, (255, 0, 0))
        pagina.insert_image(
            fitz.Rect(0, 0, pagina.rect.width, pagina.rect.height * 0.5), pixmap=pixmap
        )
        caminho = tmp_path / "dupla.pdf"
        documento.save(str(caminho))
        documento.close()

        por_caracteristica = paginas_por_caracteristica(caracterizar_documento(str(caminho)))

        assert 1 in por_caracteristica.get("pagina-rotacionada", [])
        assert 1 in por_caracteristica.get("imagem-embutida", [])

    def test_documento_sem_nenhum_achado_devolve_dicionario_vazio(self, pdf_exemplo):
        # pdf_exemplo não tem rotação, imagem, nem página sem texto.
        por_caracteristica = paginas_por_caracteristica(
            caracterizar_documento(str(pdf_exemplo))
        )
        assert por_caracteristica == {}


class TestCaracteristicasDoDocumento:
    """A característica do PDF é a **soma** das características das
    páginas — pedido direto: "o pdf tem uma ou mais características que é a
    soma das características das páginas"."""

    def test_soma_das_paginas_e_um_conjunto(self, tmp_path):
        import fitz

        documento = fitz.open()
        normal = documento.new_page()
        normal.insert_text((72, 72), "texto")
        rotacionada = documento.new_page()
        rotacionada.insert_text((72, 72), "texto")
        rotacionada.set_rotation(90)
        caminho = tmp_path / "mista.pdf"
        documento.save(str(caminho))
        documento.close()

        assert caracteristicas_do_documento(str(caminho)) == {"pagina-rotacionada"}

    def test_documento_sem_nenhuma_caracteristica_devolve_conjunto_vazio(self, pdf_exemplo):
        assert caracteristicas_do_documento(str(pdf_exemplo)) == set()

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            caracteristicas_do_documento(str(tmp_path / "nao-existe.pdf"))


class TestContagemPorCaracteristica:
    """ "Quais são as maiores características de um PDF" — quantas páginas
    cada uma tem, da maior pra menor."""

    def _documento_com_tres_rotacionadas_e_uma_imagem(self, tmp_path):
        import fitz

        documento = fitz.open()
        for _ in range(3):
            pagina = documento.new_page()
            pagina.insert_text((72, 72), "texto")
            pagina.set_rotation(90)

        pagina = documento.new_page()
        pagina.insert_text((72, 72), "texto")
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4))
        pixmap.set_rect(pixmap.irect, (255, 0, 0))
        pagina.insert_image(
            fitz.Rect(0, 0, pagina.rect.width, pagina.rect.height * 0.5), pixmap=pixmap
        )

        caminho = tmp_path / "documento.pdf"
        documento.save(str(caminho))
        documento.close()
        return caminho

    def test_conta_paginas_por_caracteristica(self, tmp_path):
        caminho = self._documento_com_tres_rotacionadas_e_uma_imagem(tmp_path)

        contagem = contagem_por_caracteristica(str(caminho))

        assert contagem["pagina-rotacionada"] == 3
        assert contagem["imagem-embutida"] == 1

    def test_ordena_da_maior_para_a_menor(self, tmp_path):
        caminho = self._documento_com_tres_rotacionadas_e_uma_imagem(tmp_path)

        contagem = contagem_por_caracteristica(str(caminho))

        assert list(contagem.keys())[0] == "pagina-rotacionada"

    def test_documento_sem_nenhuma_caracteristica_devolve_dicionario_vazio(self, pdf_exemplo):
        assert contagem_por_caracteristica(str(pdf_exemplo)) == {}

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            contagem_por_caracteristica(str(tmp_path / "nao-existe.pdf"))


class TestImagemEmbutida:
    """Achado que faltava apesar de o ADR-0021 declará-lo "pronto" — e que
    precisa de um piso de área, medido contra dois documentos reais: sem
    ele, o logotipo de cabeçalho de toda página disparava o achado em toda
    página, escondendo justamente as páginas com conteúdo visual real."""

    def _pdf_com_imagem(self, tmp_path, *, bbox):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4))
        pixmap.set_rect(pixmap.irect, (255, 0, 0))
        pagina.insert_image(fitz.Rect(*bbox), pixmap=pixmap)
        caminho = tmp_path / "com-imagem.pdf"
        documento.save(caminho)
        documento.close()
        return caminho

    def test_imagem_pequena_tipo_logo_nao_gera_achado(self, tmp_path):
        """~0,3% da página — a ordem de grandeza do logotipo medido nos
        documentos reais que motivaram este piso."""
        caminho = self._pdf_com_imagem(tmp_path, bbox=(500, 10, 550, 40))

        import fitz

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "imagem-embutida" not in {a.codigo for a in achados}

    def test_imagem_grande_gera_achado(self, tmp_path):
        """~24% da página — a ordem de grandeza de um diagrama real."""
        caminho = self._pdf_com_imagem(tmp_path, bbox=(100, 300, 400, 500))

        import fitz

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "imagem-embutida" in {a.codigo for a in achados}


class TestValidacaoDeSaida:
    """Pega saída plausível mas errada — o modo de falha que passa por validação
    de tipo e chega ao consumidor."""

    def test_registro_correto_nao_gera_achado(self):
        achados = validar_registros(
            [_registro(identificador="1 Arroz", energia_kcal=124.0, proteina_g=2.6)]
        )
        assert not [a for a in achados if a.severidade is Severidade.BLOQUEIA]

    def test_detecta_cabecalho_virando_dado(self):
        """`{'Carbo-': 'idrato'}` — o sintoma de cabeçalho partido lido como item."""
        achados = validar_registros([_registro(identificador="Carbo-", energia_kcal="idrato")])
        assert "identificador-sem-numero" in {a.codigo for a in achados}

    def test_detecta_ausencia_total_de_registros(self):
        achados = validar_registros([])
        assert "nenhum-registro" in {a.codigo for a in achados}

    def test_detecta_cobertura_muito_baixa(self):
        """Identificador presente e nenhum valor: 1 campo de 6 = 17%, abaixo do piso."""
        vazios = [
            _registro(
                identificador=f"{i} X",
                energia_kcal=None,
                proteina_g=None,
                lipideos_g=None,
                carboidrato_g=None,
                fibra_g=None,
            )
            for i in range(10)
        ]
        assert "cobertura-baixa" in {a.codigo for a in validar_registros(vazios)}

    def test_detecta_valor_repetido_em_todos_os_itens(self):
        """Mesmo valor em todo item sugere coluna lida errado, não coincidência."""
        iguais = [_registro(identificador=f"{i} X", energia_kcal=42.0) for i in range(10)]
        assert "valor-constante" in {a.codigo for a in validar_registros(iguais)}

    def test_valores_legitimamente_iguais_em_poucos_itens_nao_alarmam(self):
        poucos = [_registro(identificador=f"{i} X", energia_kcal=42.0) for i in range(2)]
        assert "valor-constante" not in {a.codigo for a in validar_registros(poucos)}

    def test_detecta_ordem_de_magnitude_suspeita(self):
        """O erro do reconhecedor óptico: vírgula perdida multiplica por dez."""
        registros = [_registro(identificador="1 X", proteina_g=v) for v in (2.6, 3.1, 48.0)]
        achados = validar_registros(registros, faixas={"proteina_g": (0.0, 40.0)})
        assert "fora-da-faixa" in {a.codigo for a in achados}

    def test_faixa_respeitada_nao_alarma(self):
        registros = [_registro(identificador="1 X", proteina_g=v) for v in (2.6, 3.1, 8.5)]
        achados = validar_registros(registros, faixas={"proteina_g": (0.0, 40.0)})
        assert "fora-da-faixa" not in {a.codigo for a in achados}

    def test_sentinela_nao_e_tratada_como_numero_fora_de_faixa(self):
        registros = [_registro(identificador="1 X", proteina_g=Sentinela.TRACO)]
        achados = validar_registros(registros, faixas={"proteina_g": (0.0, 40.0)})
        assert "fora-da-faixa" not in {a.codigo for a in achados}


class TestSeveridade:
    def test_bloqueia_e_mais_grave_que_alerta(self):
        assert Severidade.BLOQUEIA.grave
        assert not Severidade.ALERTA.grave

    def test_relatorio_lista_por_severidade(self):
        from parser.diagnostico import relatorio

        achados = [
            Achado("a", Severidade.ALERTA, "detalhe a", "ação a"),
            Achado("b", Severidade.BLOQUEIA, "detalhe b", "ação b"),
        ]
        texto = relatorio(achados)
        assert texto.index("detalhe b") < texto.index("detalhe a")
