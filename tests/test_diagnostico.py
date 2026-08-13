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
    escolher_paginas_de_referencia,
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


class TestEscolherPaginasDeReferencia:
    """1 página representante por combinação distinta de características —
    não 1 por característica isolada, que duplicaria coleta quando páginas
    diferentes repetem a mesma combinação exata (ADR-0021: "a unidade de
    análise é a combinação")."""

    def _documento_com_combinacoes(self, tmp_path):
        """5 páginas, 3 combinações distintas:

        1: {pagina-rotacionada}                       — combinação A
        2: {pagina-rotacionada}                       — combinação A de novo
        3: {pagina-rotacionada, sem-camada-de-texto}  — combinação B
        4: {pagina-em-paisagem}                       — combinação C
        5: nenhuma característica
        """
        import fitz

        documento = fitz.open()

        p1 = documento.new_page()
        p1.insert_text((72, 72), "texto")
        p1.set_rotation(90)

        p2 = documento.new_page()
        p2.insert_text((72, 72), "texto")
        p2.set_rotation(90)

        p3 = documento.new_page()
        p3.set_rotation(90)  # sem inserir texto: também sem-camada-de-texto

        p4 = documento.new_page(width=800, height=600)  # página 4, paisagem
        p4.insert_text((72, 72), "texto")  # senão também ganharia sem-camada-de-texto

        p5 = documento.new_page()
        p5.insert_text((72, 72), "texto sem nenhuma característica")

        caminho = tmp_path / "combinacoes.pdf"
        documento.save(str(caminho))
        documento.close()
        return caminho

    def test_uma_pagina_por_combinacao_distinta(self, tmp_path):
        caminho = self._documento_com_combinacoes(tmp_path)

        resultado = escolher_paginas_de_referencia(str(caminho))

        # Combinação A (só rotação): página 1 é a primeira ocorrência —
        # página 2, mesma combinação exata, não deveria acrescentar mais
        # uma referência.
        assert resultado["pagina-rotacionada"] == [1, 3]

    def test_combinacao_diferente_ganha_pagina_propria(self, tmp_path):
        caminho = self._documento_com_combinacoes(tmp_path)

        resultado = escolher_paginas_de_referencia(str(caminho))

        assert resultado["sem-camada-de-texto"] == [3]
        assert resultado["pagina-em-paisagem"] == [4]

    def test_pagina_repetindo_combinacao_nao_vira_referencia_extra(self, tmp_path):
        """A página 2 repete exatamente a combinação da página 1 — não deve
        aparecer em lugar nenhum do resultado."""
        caminho = self._documento_com_combinacoes(tmp_path)

        resultado = escolher_paginas_de_referencia(str(caminho))

        todas_as_paginas = {p for paginas in resultado.values() for p in paginas}
        assert 2 not in todas_as_paginas

    def test_pagina_sem_caracteristica_nao_entra_no_resultado(self, tmp_path):
        caminho = self._documento_com_combinacoes(tmp_path)

        resultado = escolher_paginas_de_referencia(str(caminho))

        todas_as_paginas = {p for paginas in resultado.values() for p in paginas}
        assert 5 not in todas_as_paginas

    def test_documento_sem_nenhuma_caracteristica_devolve_dicionario_vazio(self, pdf_exemplo):
        assert escolher_paginas_de_referencia(str(pdf_exemplo)) == {}

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            escolher_paginas_de_referencia(str(tmp_path / "nao-existe.pdf"))


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


class TestPaginaEmPaisagem:
    """Característica geometricamente trivial (sem calibração), observada de
    verdade em documento real de um cenário corporativo (2026-08-13) — um
    documento inteiro em slides, todas as páginas em paisagem."""

    def _pdf_com_pagina(self, tmp_path, *, largura, altura):
        import fitz

        documento = fitz.open()
        documento.new_page(width=largura, height=altura)
        caminho = tmp_path / "pagina.pdf"
        documento.save(caminho)
        documento.close()
        return caminho

    def test_pagina_mais_larga_que_alta_gera_achado(self, tmp_path):
        import fitz

        caminho = self._pdf_com_pagina(tmp_path, largura=800, altura=600)
        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        (achado,) = [a for a in achados if a.codigo == "pagina-em-paisagem"]
        assert achado.metodo is MetodoDeDeteccao.METADADO_NATIVO

    def test_pagina_retrato_nao_gera_achado(self, tmp_path):
        import fitz

        caminho = self._pdf_com_pagina(tmp_path, largura=595, altura=842)
        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "pagina-em-paisagem" not in {a.codigo for a in achados}

    def test_pagina_quadrada_nao_gera_achado(self, tmp_path):
        """Empate (largura == altura) não é paisagem."""
        import fitz

        caminho = self._pdf_com_pagina(tmp_path, largura=600, altura=600)
        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "pagina-em-paisagem" not in {a.codigo for a in achados}


class TestMultiplasColunasDeTexto:
    """Observado de verdade em dois documentos reais de um cenário
    corporativo (2026-08-13): prosa em coluna dupla (slide) e coluna de
    comentário lateral reservada à parte do corpo (documento revisado) — as
    duas são a mesma característica geométrica: texto relevante em faixas
    de X que não se sobrepõem."""

    def _inserir_bloco(self, pagina, x, y0, palavras):
        texto = " ".join(f"palavra{i}" for i in range(palavras))
        for i, linha in enumerate(_dividir(texto, 3)):
            pagina.insert_text((x, y0 + i * 14), linha)

    def test_duas_colunas_com_bastante_texto_geram_achado(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        self._inserir_bloco(pagina, 72, 100, 18)
        self._inserir_bloco(pagina, 340, 100, 18)
        caminho = tmp_path / "duas-colunas.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        (achado,) = [a for a in achados if a.codigo == "multiplas-colunas-de-texto"]
        assert achado.severidade is Severidade.ALERTA

    def test_uma_coluna_so_nao_gera_achado(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        self._inserir_bloco(pagina, 72, 100, 30)
        caminho = tmp_path / "uma-coluna.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "multiplas-colunas-de-texto" not in {a.codigo for a in achados}

    def test_elemento_lateral_pequeno_abaixo_do_piso_nao_gera_achado(self, tmp_path):
        """Um número de página ou carimbo curto ao lado do corpo do texto não
        é uma segunda coluna — é o cabeçalho/rodapé que qualquer documento
        paginado tem. Sem o piso de palavras, isso disparia em toda página."""
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        self._inserir_bloco(pagina, 72, 100, 30)
        pagina.insert_text((500, 800), "pág 1 de 22")
        caminho = tmp_path / "com-rodape.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "multiplas-colunas-de-texto" not in {a.codigo for a in achados}


def _dividir(texto: str, palavras_por_linha: int) -> list[str]:
    palavras = texto.split()
    return [
        " ".join(palavras[i : i + palavras_por_linha])
        for i in range(0, len(palavras), palavras_por_linha)
    ]


class TestTabelaComFundoColorido:
    """Observado de verdade em documento real de um cenário corporativo
    (2026-08-13): tabela cujo agrupamento visual vem de cor de fundo
    (cabeçalho colorido + faixas alternadas), sem nenhuma linha de grade —
    detector de linha reta não teria o que reconhecer."""

    def _inserir_tabela_colorida(self, pagina, *, linhas, colunas=3, cores=None):
        import fitz

        cores = cores or [(0.15, 0.38, 0.33), (0.80, 0.83, 0.82), (0.91, 0.92, 0.91)]
        largura_coluna = 150
        altura_linha = 20
        for i in range(linhas):
            cor = cores[i % len(cores)]
            for j in range(colunas):
                x0 = 50 + j * largura_coluna
                y0 = 80 + i * altura_linha
                pagina.draw_rect(
                    fitz.Rect(x0, y0, x0 + largura_coluna, y0 + altura_linha),
                    color=None,
                    fill=cor,
                )

    def test_tabela_com_varias_linhas_e_cores_gera_achado(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        self._inserir_tabela_colorida(pagina, linhas=5)
        caminho = tmp_path / "tabela-colorida.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        (achado,) = [a for a in achados if a.codigo == "tabela-com-fundo-colorido"]
        assert achado.metodo is MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA

    def test_pagina_sem_retangulo_preenchido_nao_gera_achado(self, tmp_path):
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        pagina.insert_text((72, 72), "texto corrido sem tabela nenhuma")
        caminho = tmp_path / "sem-tabela.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "tabela-com-fundo-colorido" not in {a.codigo for a in achados}

    def test_banner_isolado_de_uma_linha_nao_gera_achado(self, tmp_path):
        """Uma única caixa colorida (destaque, banner) não é tabela — falta
        o mínimo de linhas que distingue "tabela" de "elemento de destaque"."""
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        self._inserir_tabela_colorida(pagina, linhas=1, cores=[(0.2, 0.4, 0.3)])
        caminho = tmp_path / "banner.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "tabela-com-fundo-colorido" not in {a.codigo for a in achados}

    def test_todas_as_linhas_da_mesma_cor_nao_gera_achado(self, tmp_path):
        """Sem alternância de cor entre linhas não há "listra" — pode ser só
        uma caixa grande com bordas internas, não uma tabela zebrada."""
        import fitz

        documento = fitz.open()
        pagina = documento.new_page()
        self._inserir_tabela_colorida(pagina, linhas=4, cores=[(0.5, 0.5, 0.5)])
        caminho = tmp_path / "mesma-cor.pdf"
        documento.save(caminho)
        documento.close()

        aberto = fitz.open(str(caminho))
        try:
            achados = caracterizar_pagina(aberto, 1)
        finally:
            aberto.close()
        assert "tabela-com-fundo-colorido" not in {a.codigo for a in achados}


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
