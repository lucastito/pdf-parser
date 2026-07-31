"""Os documentos do experimento não podem trocar sem que se saiba.

Uma comparação entre máquinas só significa alguma coisa se todas leram o **mesmo
arquivo**. Sem verificação, um documento substituído ou corrompido produziria
diferenças que pareceriam de hardware ou de estratégia — e não haveria como
distinguir.

O custo de verificar é milissegundos; o custo de não verificar é uma bateria de
medições inválida que ninguém percebe.
"""

import hashlib
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parents[1] / "experimentos" / "documentos"

IMPRESSOES = {
    "TACO.pdf": "2002aec5615b5b1395aaa8fa675635bbb7f712c33f278af5e332f1cac8f108c8",
}
"""Documento → sha256 esperado.

Acrescentar documento aqui é parte do procedimento descrito no README da pasta.
"""


@pytest.mark.parametrize("nome, esperado", sorted(IMPRESSOES.items()))
class TestIntegridadeDosDocumentos:
    def test_o_documento_existe(self, nome: str, esperado: str):
        assert (PASTA / nome).exists(), (
            f"{nome} não está em experimentos/documentos/. As medições que dependem "
            "dele não são reproduzíveis sem o arquivo."
        )

    def test_a_impressao_digital_confere(self, nome: str, esperado: str):
        obtido = hashlib.sha256((PASTA / nome).read_bytes()).hexdigest()
        assert obtido == esperado, (
            f"{nome} mudou. Comparações entre máquinas que usem este arquivo "
            f"deixam de ser válidas.\n  esperado: {esperado}\n  obtido:   {obtido}"
        )


def test_todo_documento_versionado_tem_impressao_registrada():
    """Arquivo novo sem registro passaria sem verificação — e sem ninguém notar."""
    if not PASTA.exists():
        pytest.skip("pasta de documentos ausente")

    presentes = {p.name for p in PASTA.iterdir() if p.suffix.lower() == ".pdf"}
    sem_registro = presentes - set(IMPRESSOES)
    assert not sem_registro, (
        f"documento sem impressão digital registrada: {sorted(sem_registro)}. "
        "Ver o procedimento em experimentos/documentos/README.md"
    )


def test_a_licenca_esta_declarada():
    """Documento redistribuído sem licença declarada é risco, não descuido."""
    leiame = PASTA / "README.md"
    assert leiame.exists(), "experimentos/documentos/ sem README"

    texto = leiame.read_text(encoding="utf-8").lower()
    assert "licença" in texto or "licenca" in texto
    for nome in IMPRESSOES:
        assert nome.lower() in texto, f"{nome} versionado sem menção no README"
