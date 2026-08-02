"""Os documentos do experimento não podem trocar sem que se saiba.

Uma comparação entre máquinas só significa alguma coisa se todas leram o **mesmo
arquivo**. Sem verificação, um documento substituído ou corrompido produziria
diferenças que pareceriam de hardware ou de estratégia — e não haveria como
distinguir.

O custo de verificar é milissegundos; o custo de não verificar é uma bateria de
medições inválida que ninguém percebe.

**A fonte é o manifesto, e só ele.** Os hashes já ficavam repetidos aqui, e duas
listas do mesmo fato divergem — foi o que aconteceu com a escada de modelos, que
existia em PowerShell e em Python e passou a instalar um conjunto enquanto a
bateria esperava outro. Aqui o teste lê `manifest.yaml`; acrescentar documento em
um lugar só passa a ser suficiente, e impossível de esquecer no outro.
"""

import hashlib
from pathlib import Path

import pytest
import yaml

PASTA = Path(__file__).resolve().parents[1] / "experimentos" / "pdf"
MANIFESTO = PASTA / "manifest.yaml"


def _manifesto() -> dict:
    return yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))


def _impressoes() -> dict[str, str]:
    """Documento → sha256 declarado no manifesto."""
    if not MANIFESTO.exists():
        return {}
    return {
        doc["file"]: str(doc["sha256"]).lower()
        for doc in _manifesto().get("documents", [])
        if doc.get("sha256")
    }


IMPRESSOES = _impressoes()


def test_o_manifesto_declara_documentos():
    """Guarda contra a suíte passar por ler um manifesto vazio ou movido."""
    assert MANIFESTO.exists(), f"{MANIFESTO} não existe"
    assert IMPRESSOES, "manifesto sem nenhum documento com sha256"


@pytest.mark.parametrize("nome, esperado", sorted(IMPRESSOES.items()))
class TestIntegridadeDosDocumentos:
    def test_o_documento_existe(self, nome: str, esperado: str):
        assert (PASTA / nome).exists(), (
            f"{nome} está no manifesto e não está em experimentos/pdf/. "
            "As medições que dependem dele não são reproduzíveis sem o arquivo."
        )

    def test_a_impressao_digital_confere(self, nome: str, esperado: str):
        obtido = hashlib.sha256((PASTA / nome).read_bytes()).hexdigest()
        assert obtido == esperado, (
            f"{nome} mudou. Comparações entre máquinas que usem este arquivo "
            f"deixam de ser válidas.\n  esperado: {esperado}\n  obtido:   {obtido}"
        )


def test_todo_documento_presente_esta_no_manifesto():
    """Arquivo novo sem registro passaria sem verificação — e sem ninguém notar."""
    presentes = {p.name for p in PASTA.iterdir() if p.suffix.lower() == ".pdf"}
    sem_registro = presentes - set(IMPRESSOES)
    assert not sem_registro, (
        f"documento sem entrada no manifesto: {sorted(sem_registro)}. "
        "Ver o procedimento em experimentos/pdf/README.md"
    )


def test_todo_documento_declara_proveniencia():
    """Documento sem origem não é reproduzível por quem não o tem."""
    sem_origem = [
        doc["file"]
        for doc in _manifesto()["documents"]
        if not str(doc.get("source", "")).strip()
    ]
    assert not sem_origem, f"documento sem `source` no manifesto: {sem_origem}"


def test_a_situacao_de_redistribuicao_cobre_todo_documento():
    """Publicar o corpus exige saber, por documento, o que foi confirmado.

    O campo não bloqueia nada: os arquivos estão versionados por decisão
    explícita. Ele responde à pergunta que aparece depois — *este documento pode
    sair daqui?* — sem obrigar ninguém a refazer o levantamento de licença.

    Documento novo que entre sem classificação faria a resposta virar silêncio,
    que é o pior desfecho: parece confirmado e não é.
    """
    manifesto = _manifesto()
    grupos = manifesto.get("redistribuicao")
    assert grupos, "manifesto sem a seção `redistribuicao`"

    classificados: list[str] = []
    for nome, grupo in grupos.items():
        assert grupo.get("base"), f"grupo `{nome}` sem justificativa em `base`"
        classificados += grupo.get("documentos", [])

    declarados = set(IMPRESSOES)
    faltando = declarados - set(classificados)
    assert (
        not faltando
    ), f"documento sem situação de redistribuição declarada: {sorted(faltando)}"

    inexistentes = set(classificados) - declarados
    assert not inexistentes, (
        f"`redistribuicao` cita documento que não está no manifesto: "
        f"{sorted(inexistentes)}"
    )

    repetidos = {n for n in classificados if classificados.count(n) > 1}
    assert not repetidos, (
        f"documento em mais de um grupo de redistribuição: {sorted(repetidos)}. "
        "A situação de cada um tem de ser única para poder ser consultada."
    )


def test_toda_caracteristica_tem_ao_menos_um_caso():
    """A cobertura é o requisito do corpus — sem ela, a triagem tem buraco."""
    cobertura = _manifesto().get("coverage") or {}
    assert cobertura, "manifesto sem a seção `coverage`"

    vazias = [codigo for codigo, arquivos in cobertura.items() if not arquivos]
    assert not vazias, f"característica sem nenhum documento: {sorted(vazias)}"

    declarados = set(IMPRESSOES)
    for codigo, arquivos in cobertura.items():
        ausentes = set(arquivos) - declarados
        assert not ausentes, (
            f"característica {codigo} cita documento que não está no manifesto: "
            f"{sorted(ausentes)}"
        )
