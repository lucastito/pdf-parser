"""Ingestão em lote — o núcleo do produto.

O caso de uso é: alguém entrega uma pasta com muitos documentos heterogêneos, e o
sistema consolida numa saída única, sinalizando o que precisa de atenção humana.

O que estes testes protegem:

- **um arquivo com problema não interrompe o lote** — numa pasta de cem documentos,
  abortar no terceiro desperdiça o processamento dos outros noventa e sete;
- **um arquivo é lote de tamanho 1** — sem caminho especial, para o comportamento não
  divergir entre um e cem;
- **toda linha carrega origem** — sem isso o revisor não sabe onde conferir;
- **o que falta vira lista curta**, não planilha inteira para revisar.
"""

import json

import pytest

from parser.lote import Lote, ResultadoLote, ingerir


@pytest.fixture
def pasta_com_pdfs(tmp_path, pdf_exemplo):
    import shutil

    pasta = tmp_path / "entrada"
    pasta.mkdir()
    for nome in ("a.pdf", "b.pdf", "c.pdf"):
        shutil.copy(pdf_exemplo, pasta / nome)
    return pasta


class TestDescobertaDeArquivos:
    def test_encontra_pdfs_na_pasta(self, pasta_com_pdfs):
        lote = Lote(pasta_com_pdfs)
        assert len(lote.arquivos()) == 3

    def test_ignora_extensao_desconhecida(self, pasta_com_pdfs):
        (pasta_com_pdfs / "leiame.txt").write_text("nada", encoding="utf-8")
        assert len(Lote(pasta_com_pdfs).arquivos()) == 3

    def test_aceita_arquivo_unico(self, pdf_exemplo):
        """Um arquivo é lote de tamanho 1 — sem caminho especial."""
        assert len(Lote(pdf_exemplo).arquivos()) == 1

    def test_pasta_vazia_nao_falha(self, tmp_path):
        vazia = tmp_path / "vazia"
        vazia.mkdir()
        assert Lote(vazia).arquivos() == []

    def test_pasta_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Lote(tmp_path / "nao-existe").arquivos()

    def test_percorre_subpastas(self, pasta_com_pdfs, pdf_exemplo):
        import shutil

        sub = pasta_com_pdfs / "sub"
        sub.mkdir()
        shutil.copy(pdf_exemplo, sub / "d.pdf")
        assert len(Lote(pasta_com_pdfs).arquivos()) == 4


class TestResiliencia:
    """Um arquivo problemático não pode custar o lote inteiro."""

    def test_arquivo_corrompido_nao_interrompe(self, tmp_path, pdf_exemplo):
        """O critério central: **todos** os arquivos são visitados.

        Sem isto, um arquivo ruim no início custaria o processamento de todos os
        seguintes. O teste não exige que a extração tenha sucesso — exige que a
        falha de um não impeça a tentativa nos outros.
        """
        import shutil

        pasta = tmp_path / "mista"
        pasta.mkdir()
        for nome in ("a.pdf", "b.pdf", "c.pdf"):
            shutil.copy(pdf_exemplo, pasta / nome)
        (pasta / "corrompido.pdf").write_bytes(b"isto nao e um pdf")

        resultado = ingerir(pasta)

        assert resultado.arquivos_encontrados == 4
        # Todo arquivo aparece no log ou nas falhas — nenhum foi saltado.
        visitados = len(resultado.falhas) + resultado.processados
        assert visitados == 4, f"só {visitados} de 4 arquivos foram visitados"

    def test_registro_e_falha_somam_o_total(self, tmp_path, pdf_exemplo):
        import shutil

        pasta = tmp_path / "p"
        pasta.mkdir()
        for i in range(5):
            shutil.copy(pdf_exemplo, pasta / f"{i}.pdf")

        resultado = ingerir(pasta)
        assert resultado.processados + len(resultado.falhas) == 5

    def test_falha_registra_o_arquivo_e_o_motivo(self, pasta_com_pdfs):
        (pasta_com_pdfs / "corrompido.pdf").write_bytes(b"nao e pdf")

        resultado = ingerir(pasta_com_pdfs)
        falha = next(f for f in resultado.falhas if "corrompido" in f.arquivo)

        assert falha.motivo
        assert falha.acao, "falha sem ação recomendada é só reclamação"

    def test_lote_todo_falho_ainda_devolve_resultado(self, tmp_path):
        pasta = tmp_path / "ruins"
        pasta.mkdir()
        for nome in ("x.pdf", "y.pdf"):
            (pasta / nome).write_bytes(b"nao e pdf")

        resultado = ingerir(pasta)
        assert resultado.processados == 0
        assert len(resultado.falhas) == 2


class TestSaidasConsolidadas:
    def test_grava_csv_log_e_erros(self, pasta_com_pdfs, tmp_path):
        saida = tmp_path / "consolidado.csv"
        (pasta_com_pdfs / "ruim.pdf").write_bytes(b"nao e pdf")

        ingerir(pasta_com_pdfs, saida=saida)

        assert saida.exists()
        assert saida.with_suffix(".log").exists()
        assert saida.with_suffix(".erros.json").exists()

    def test_erros_em_json_legivel(self, pasta_com_pdfs, tmp_path):
        saida = tmp_path / "c.csv"
        (pasta_com_pdfs / "ruim.pdf").write_bytes(b"nao e pdf")

        ingerir(pasta_com_pdfs, saida=saida)
        erros = json.loads(saida.with_suffix(".erros.json").read_text(encoding="utf-8"))

        assert isinstance(erros, list)
        assert all("arquivo" in e and "motivo" in e and "acao" in e for e in erros)

    def test_log_registra_cada_arquivo(self, pasta_com_pdfs, tmp_path):
        saida = tmp_path / "c.csv"
        ingerir(pasta_com_pdfs, saida=saida)
        log = saida.with_suffix(".log").read_text(encoding="utf-8")

        for nome in ("a.pdf", "b.pdf", "c.pdf"):
            assert nome in log

    def test_sem_saida_nao_grava_arquivo(self, pasta_com_pdfs):
        """Útil para inspecionar antes de comprometer disco."""
        resultado = ingerir(pasta_com_pdfs)
        assert isinstance(resultado, ResultadoLote)


class TestRastreabilidade:
    def test_registro_sabe_de_qual_arquivo_veio(self, pasta_com_pdfs):
        resultado = ingerir(pasta_com_pdfs)
        for registro in resultado.registros:
            assert registro.fonte, "registro sem arquivo de origem"

    def test_resultado_relata_o_que_aconteceu(self, pasta_com_pdfs):
        resultado = ingerir(pasta_com_pdfs)
        assert resultado.arquivos_encontrados == 3
        assert resultado.segundos >= 0
        assert resultado.resumo()


class TestPendencias:
    """O que falta deve virar lista curta, não planilha para conferir."""

    def test_campo_ausente_entra_em_pendencias(self, pasta_com_pdfs):
        resultado = ingerir(pasta_com_pdfs, campos_esperados=["campo_inexistente"])
        assert resultado.pendencias

    def test_pendencia_diz_onde_procurar(self, pasta_com_pdfs):
        resultado = ingerir(pasta_com_pdfs, campos_esperados=["campo_inexistente"])
        for pendencia in resultado.pendencias:
            assert pendencia.campo
            assert pendencia.motivo

    def test_sem_campos_esperados_nao_gera_pendencia(self, pasta_com_pdfs):
        assert not ingerir(pasta_com_pdfs).pendencias


class TestUnidadeEEsquemaNoLote:
    """As duas etapas novas têm de rodar no caminho real, não só existir.

    Um módulo correto que ninguém chama é dívida disfarçada de trabalho pronto —
    foi exatamente o estado de `pint` e `pandera` antes disto: instalados, sem uso.
    """

    @pytest.fixture
    def pasta_tabular(self, tmp_path):
        """Um PDF cuja tabela o extrator posicional consegue reconstruir.

        Local a esta classe, e não em `conftest`, por duas razões: o layout
        precisa casar exatamente com o perfil declarado abaixo, e o espaço após
        cada palavra é significativo — sem ele o PyMuPDF funde nome e unidade
        (`"Energia(kcal)"`), a unidade nunca cai na própria faixa de X e a
        reconstrução devolve zero registro.
        """
        import fitz

        pasta = tmp_path / "entrada"
        pasta.mkdir()
        documento = fitz.open()
        pagina = documento.new_page(width=595, height=842)

        linhas = [
            ("Energia", "(kcal)", 400.0, ["124", "360", "128"]),
            ("Proteína", "(g)", 350.0, ["2,6", "7,3", "2,5"]),
            ("Lipídeos", "(g)", 300.0, ["1,0", "1,9", "Tr"]),
        ]
        for rotulo, unidade, y, valores in linhas:
            pagina.insert_text((112, y), rotulo + " ")
            pagina.insert_text((165, y), unidade + " ")
            for i, valor in enumerate(valores):
                pagina.insert_text((230 + i * 70, y), valor + " ")

        for i, nome in enumerate(["Um", "Dois", "Tres"]):
            pagina.insert_text((230 + i * 70, 600), nome + " ")

        documento.save(pasta / "a.pdf")
        documento.close()
        return pasta

    @pytest.fixture
    def perfil_tabular(self):
        """Perfil com layout explícito, para não depender da calibração.

        A calibração recusa este PDF sintético — pequeno demais para atingir o
        limiar de densidade numérica —, e recusar é o comportamento correto dela.
        Declarar o layout isola o que estes testes medem: as etapas de unidade e
        de esquema, não a descoberta de layout.
        """
        from parser.configuracao import Perfil, Rota

        return Perfil(
            nome="tabular",
            rotas={
                "posicional": Rota(
                    nome="posicional",
                    layout={
                        "x_rotulos": [110.0, 160.0],
                        "x_unidades": [160.0, 200.0],
                        "x_valores_min": 200.0,
                        "y_identificadores_min": 550.0,
                        "y_rotulo_max": 550.0,
                        "tolerancia_y": 6.0,
                        "tolerancia_x": 6.0,
                    },
                )
            },
            mapeamento={
                "energia_kcal": ["Energia (kcal)"],
                "proteina_g": ["Proteína (g)"],
                "lipideos_g": ["Lipídeos (g)"],
            },
        )

    def test_lote_converte_a_unidade_declarada(self, pasta_tabular, perfil_tabular):
        perfil_tabular.unidades = {"energia_kcal": {"de": "kcal", "para": "kJ"}}

        resultado = ingerir(pasta_tabular, perfil=perfil_tabular, calibrar_por_arquivo=False)

        valores = [
            r.campos["energia_kcal"].valor
            for r in resultado.registros
            if r.campos["energia_kcal"].valor is not None
        ]
        assert valores, "o lote não produziu energia para converter"
        # 124 kcal ≈ 519 kJ: a ordem de grandeza sozinha denuncia se não converteu.
        assert min(valores) > 400

    def test_campo_convertido_no_lote_sai_derivado(self, pasta_tabular, perfil_tabular):
        from parser.modelo import Origem

        perfil_tabular.unidades = {"energia_kcal": {"de": "kcal", "para": "kJ"}}
        resultado = ingerir(pasta_tabular, perfil=perfil_tabular, calibrar_por_arquivo=False)

        convertidos = [
            r.campos["energia_kcal"]
            for r in resultado.registros
            if r.campos["energia_kcal"].valor is not None
        ]
        assert convertidos
        assert all(c.origem is Origem.DERIVADO for c in convertidos)
        assert all(c.evidencia is not None for c in convertidos), "perdeu a auditoria"

    def test_campo_sem_regra_nao_e_tocado(self, pasta_tabular, perfil_tabular):
        """Converter energia não pode alterar proteína."""
        from parser.modelo import Origem

        perfil_tabular.unidades = {"energia_kcal": {"de": "kcal", "para": "kJ"}}
        resultado = ingerir(pasta_tabular, perfil=perfil_tabular, calibrar_por_arquivo=False)

        proteinas = [
            r.campos["proteina_g"]
            for r in resultado.registros
            if r.campos["proteina_g"].valor is not None
        ]
        assert proteinas
        assert all(c.origem is Origem.EXTRAIDO for c in proteinas)
        assert max(c.valor for c in proteinas) < 10

    def test_esquema_barra_a_gravacao_de_lote_invalido(
        self, pasta_tabular, perfil_tabular, tmp_path
    ):
        from parser.esquema import SaidaInvalida

        perfil_tabular.esquema = {"coluna_que_nao_existe": {"tipo": "numero"}}
        saida = tmp_path / "saida.csv"

        with pytest.raises(SaidaInvalida):
            ingerir(
                pasta_tabular,
                saida=saida,
                perfil=perfil_tabular,
                calibrar_por_arquivo=False,
            )
        assert not saida.exists(), "gravou apesar do esquema violado"

    def test_esquema_conforme_deixa_gravar(self, pasta_tabular, perfil_tabular, tmp_path):
        perfil_tabular.esquema = {
            "identificador": {"tipo": "texto"},
            "energia_kcal": {"tipo": "numero", "minimo": 0.0},
            "proteina_g": {"tipo": "numero"},
            "lipideos_g": {"tipo": "numero"},
        }
        saida = tmp_path / "saida.csv"

        ingerir(
            pasta_tabular,
            saida=saida,
            perfil=perfil_tabular,
            calibrar_por_arquivo=False,
        )
        assert saida.exists()

    def test_sem_declaracao_o_lote_nao_muda(self, pasta_tabular, perfil_tabular, tmp_path):
        """Nenhuma medição anterior pode mudar de valor por causa desta fatia."""
        from parser.modelo import Origem

        saida = tmp_path / "saida.csv"
        resultado = ingerir(
            pasta_tabular, saida=saida, perfil=perfil_tabular, calibrar_por_arquivo=False
        )

        assert saida.exists()
        assert resultado.registros
        origens = {
            c.origem for r in resultado.registros for c in r.campos.values() if c.preenchido
        }
        assert Origem.DERIVADO not in origens, "converteu sem regra declarada"


class TestFalhaDeConfiguracaoNaoEEngolida:
    """Perfil inconsistente tem de acusar, não degradar em silêncio.

    Os dois casos aqui vinham de `except Exception` largos que devolviam o valor
    de antes. A intenção era boa — não custar o lote inteiro por causa de um
    perfil ruim —, mas o efeito é pior que a falha: o sistema segue produzindo
    resultado plausível e errado, e o erro que o usuário vê aponta para o lugar
    errado.
    """

    def test_mapeamento_ambiguo_acusa_o_mapeamento(self):
        """O sintoma era 'coluna ausente' — que manda procurar no lugar errado.

        Sem mapeamento aplicado, os registros saem com os rótulos do documento;
        a validação de esquema então acusa coluna faltando. A causa real, um
        perfil com dois campos reivindicando o mesmo rótulo, fica escondida.
        """
        from parser.lote import _aplicar_mapeamento
        from parser.mapeamento import MapeamentoInvalido
        from parser.modelo import Campo, Evidencia, Registro

        ev = Evidencia(pagina=1, texto_bruto="124")
        registro = Registro(
            campos={"Energia (kcal)": Campo[float].extraido(valor=124.0, evidencia=ev)},
            fonte="a.pdf",
        )

        class PerfilAmbiguo:
            mapeamento = {
                "energia_kcal": ["Energia (kcal)"],
                "energia_duplicada": ["Energia (kcal)"],
            }

        with pytest.raises(MapeamentoInvalido) as erro:
            _aplicar_mapeamento([registro], PerfilAmbiguo())

        assert "Energia (kcal)" in str(erro.value)

    def test_paginas_invalidas_acusam_o_perfil(self):
        """Pedir 3 páginas e receber 164 sem aviso é pior que falhar."""
        from parser.configuracao import ConfiguracaoInvalida
        from parser.lote import _paginas_do_perfil

        class PerfilComPaginasRuins:
            nome = "ruim"
            paginas = [1, 2, 3, 4, 5]  # 'paginas' aceita 2 ou 3 valores, não 5

            def intervalo_de_paginas(self):
                raise ConfiguracaoInvalida("'paginas' deve ter 2 ou 3 valores")

        with pytest.raises(ConfiguracaoInvalida):
            _paginas_do_perfil(PerfilComPaginasRuins())

    def test_perfil_sem_paginas_continua_valendo_o_documento_todo(self):
        """Ausência de declaração não é erro — é o padrão."""
        from parser.lote import _paginas_do_perfil

        class PerfilSemPaginas:
            paginas = None

            def intervalo_de_paginas(self):
                return None

        assert _paginas_do_perfil(PerfilSemPaginas()) is None
        assert _paginas_do_perfil(None) is None

    def test_perfil_ruim_falha_uma_vez_e_nao_por_arquivo(self, pasta_com_pdfs):
        """Cem arquivos não devem render cem cópias do mesmo erro de perfil.

        Erro de configuração é igual para a pasta inteira. Verificar antes do
        laço troca cem falhas idênticas — e a extração gasta para produzi-las —
        por um erro no lugar certo.
        """
        from parser.mapeamento import MapeamentoInvalido

        class PerfilAmbiguo:
            mapeamento = {"a": ["Rótulo X"], "b": ["Rótulo X"]}

        with pytest.raises(MapeamentoInvalido):
            ingerir(pasta_com_pdfs, perfil=PerfilAmbiguo())

    def test_unidade_impossivel_no_perfil_falha_antes_do_lote(self, pasta_com_pdfs):
        from parser.unidades import ConversaoImpossivel

        class PerfilUnidadeRuim:
            mapeamento = {}
            unidades = {"proteina_g": {"de": "g", "para": "kcal"}}

        with pytest.raises(ConversaoImpossivel):
            ingerir(pasta_com_pdfs, perfil=PerfilUnidadeRuim())
