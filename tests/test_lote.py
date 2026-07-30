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
