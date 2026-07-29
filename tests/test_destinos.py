"""Destinos CSV e JSON — cobre S1 (round-trip) e S2 (destino é parâmetro).

O que estes testes protegem: a distinção entre sentinela, zero e ausente tem de
sobreviver à serialização. Se `Tr` e `0` ficam indistinguíveis no CSV, todo o
cuidado do modelo foi desperdiçado na última etapa.
"""

import csv
import json

import pytest

from parser.destinos.csv_ import DestinoCSV
from parser.destinos.json_ import DestinoJSON
from parser.modelo import Campo, Evidencia, Origem, Registro, Sentinela

EV = Evidencia(pagina=3, bbox=(1.0, 2.0, 3.0, 4.0), texto_bruto="3,86")


def _registros() -> list[Registro]:
    return [
        Registro(
            campos={
                "nome": Campo[str].extraido(valor="Arroz, integral, cozido", evidencia=EV),
                "energia": Campo[float].extraido(valor=124.0, evidencia=EV),
                "fibra": Campo[float].extraido(sentinela=Sentinela.TRACO, evidencia=EV),
                "colesterol": Campo[float].extraido(
                    sentinela=Sentinela.NAO_ANALISADO, evidencia=EV
                ),
                "zero_real": Campo[float].extraido(valor=0.0, evidencia=EV),
                "faltante": Campo[float].ausente(),
            },
            fonte="doc.pdf",
        ),
    ]


class TestDestinoCSV:
    def test_grava_arquivo_com_cabecalho(self, tmp_path):
        destino = DestinoCSV(tmp_path / "saida.csv")
        destino.gravar(_registros())

        linhas = list(csv.DictReader((tmp_path / "saida.csv").open(encoding="utf-8")))
        assert len(linhas) == 1
        assert "nome" in linhas[0]

    def test_valor_numerico_sobrevive(self, tmp_path):
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(_registros())
        linha = next(csv.DictReader((tmp_path / "s.csv").open(encoding="utf-8")))
        assert float(linha["energia"]) == pytest.approx(124.0)

    def test_texto_com_virgula_e_escapado(self, tmp_path):
        """O nome contém vírgulas; sem escape correto o CSV desalinha."""
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(_registros())
        linha = next(csv.DictReader((tmp_path / "s.csv").open(encoding="utf-8")))
        assert linha["nome"] == "Arroz, integral, cozido"

    def test_sentinela_nao_vira_zero(self, tmp_path):
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(_registros())
        linha = next(csv.DictReader((tmp_path / "s.csv").open(encoding="utf-8")))
        assert linha["fibra"] != "0"
        assert linha["fibra"] != "0.0"

    def test_sentinelas_diferentes_permanecem_distinguiveis(self, tmp_path):
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(_registros())
        linha = next(csv.DictReader((tmp_path / "s.csv").open(encoding="utf-8")))
        assert linha["fibra"] != linha["colesterol"]

    def test_sentinela_difere_de_ausente(self, tmp_path):
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(_registros())
        linha = next(csv.DictReader((tmp_path / "s.csv").open(encoding="utf-8")))
        assert linha["fibra"] != linha["faltante"]

    def test_zero_real_permanece_zero(self, tmp_path):
        """O oposto do teste da sentinela: um zero legítimo não pode virar vazio."""
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(_registros())
        linha = next(csv.DictReader((tmp_path / "s.csv").open(encoding="utf-8")))
        assert float(linha["zero_real"]) == 0.0

    def test_arquivo_e_utf8(self, tmp_path):
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar(
            [
                Registro(
                    campos={"n": Campo[str].extraido(valor="Açúcar", evidencia=EV)},
                    fonte="f",
                )
            ]
        )
        assert "Açúcar" in (tmp_path / "s.csv").read_text(encoding="utf-8")

    def test_lista_vazia_gera_arquivo_vazio_sem_erro(self, tmp_path):
        destino = DestinoCSV(tmp_path / "s.csv")
        destino.gravar([])
        assert (tmp_path / "s.csv").exists()


class TestDestinoJSON:
    def test_preserva_proveniencia(self, tmp_path):
        """A vantagem do JSON sobre o CSV: origem e evidência sobrevivem."""
        destino = DestinoJSON(tmp_path / "s.json")
        destino.gravar(_registros())

        dados = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
        campo = dados[0]["campos"]["energia"]
        assert campo["origem"] == Origem.EXTRAIDO.value
        assert campo["evidencia"]["pagina"] == 3

    def test_preserva_sentinela_nomeada(self, tmp_path):
        destino = DestinoJSON(tmp_path / "s.json")
        destino.gravar(_registros())
        dados = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
        assert dados[0]["campos"]["fibra"]["sentinela"] == Sentinela.TRACO.value
        assert dados[0]["campos"]["fibra"]["valor"] is None

    def test_round_trip_reconstroi_registro(self, tmp_path):
        """S1: o que saiu tem de voltar igual."""
        destino = DestinoJSON(tmp_path / "s.json")
        original = _registros()
        destino.gravar(original)

        dados = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
        recuperado = Registro.model_validate(dados[0])
        assert recuperado == original[0]

    def test_taxa_inferencia_sobrevive_ao_round_trip(self, tmp_path):
        destino = DestinoJSON(tmp_path / "s.json")
        original = _registros()
        destino.gravar(original)
        dados = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
        assert Registro.model_validate(dados[0]).taxa_inferencia == original[0].taxa_inferencia


class TestDestinoEParametro:
    """S2: trocar o destino não deve exigir mudança em mais nada."""

    def test_mesmos_registros_em_destinos_diferentes(self, tmp_path):
        registros = _registros()
        for destino in (
            DestinoCSV(tmp_path / "a.csv"),
            DestinoJSON(tmp_path / "a.json"),
        ):
            destino.gravar(registros)

        assert (tmp_path / "a.csv").exists()
        assert (tmp_path / "a.json").exists()

    def test_destinos_respeitam_a_porta(self, tmp_path):
        from parser.portas import Destino

        assert isinstance(DestinoCSV(tmp_path / "a.csv"), Destino)
        assert isinstance(DestinoJSON(tmp_path / "a.json"), Destino)
