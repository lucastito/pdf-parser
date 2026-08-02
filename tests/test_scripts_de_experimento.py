"""Os scripts de medição têm de medir o que a produção faz.

Um script que monta a chamada ao servidor à mão mede **o script**, não o
pipeline. E a diferença não é teórica: em 2026-08-01 a medição de seis modelos
enviou `format: "json"` diretamente — o degrau 2, que garante JSON válido e
**não impõe a estrutura**.

O resultado foi quatro modelos com 0%, e o diagnóstico apontava para eles.
Investigando as respostas brutas, três haviam **lido a tabela corretamente** e
devolvido um objeto solto com os nomes do documento. A produção nunca teria esse
problema: ela começa no degrau 1, com o esquema como gramática de decodificação,
e só desce se falhar.

Estes testes leem o código-fonte dos scripts em vez de executá-los. Não é
elegante, e é o que pega o defeito: executar exigiria servidor e horas, e a
falha está na **montagem** da chamada, não no resultado.
"""

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "experimentos" / "scripts"


def _fontes_python() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if not p.name.startswith("_"))


def test_ha_scripts_para_verificar():
    """Guarda contra o teste passar por não encontrar nada."""
    assert _fontes_python(), f"nenhum script em {SCRIPTS}"


@pytest.mark.parametrize("script", _fontes_python(), ids=lambda p: p.name)
def test_nenhum_script_pede_json_livre_sem_dizer_por_que(script: Path):
    """`format: "json"` é o degrau 2, e usá-lo por engano custou uma bateria.

    O degrau 1 — esquema como gramática — impede o servidor de gerar fora da
    estrutura. O degrau 2 só garante que a saída é JSON, e um objeto solto com
    os nomes do documento é JSON perfeitamente válido.

    Se um script precisar mesmo do degrau 2 (para medir o efeito dele, por
    exemplo), que declare no comentário adjacente. O que este teste barra é o uso
    **silencioso**, que foi como o defeito entrou.
    """
    fonte = script.read_text(encoding="utf-8")
    linhas = fonte.splitlines()

    for numero, linha in enumerate(linhas, 1):
        if '"format": "json"' not in linha:
            continue
        contexto = "\n".join(linhas[max(0, numero - 4) : numero + 1]).lower()
        assert "degrau" in contexto, (
            f"{script.name}:{numero} envia `format: json` (degrau 2) sem "
            "justificar. O degrau 1 usa o esquema como gramática e evita que o "
            "modelo invente a estrutura — foi o que custou a bateria de "
            "2026-08-01. Se o degrau 2 for intencional, diga isso num "
            "comentário adjacente."
        )


@pytest.mark.parametrize("script", _fontes_python(), ids=lambda p: p.name)
def test_nenhum_script_impoe_teto_de_tempo_ao_servidor(script: Path):
    """Teto de cliente mede o teto, não o modelo.

    Duas medições foram abortadas assim: uma rota de visão foi cortada em 6350 s
    contra um limite de 3600, e depois um `timeout` de shell matou um teste aos
    600 s. Nos dois casos o modelo estava trabalhando.

    No pacote que vai para outras máquinas o teto volta — travar para sempre é
    pior que abortar. Mas aqui, onde o número **é** o resultado, ele não entra.
    """
    fonte = script.read_text(encoding="utf-8")
    linhas = fonte.splitlines()

    for numero, linha in enumerate(linhas, 1):
        if "urlopen(" not in linha or "timeout=None" in linha:
            continue
        # Consulta de estado e descarga têm teto legítimo: não é a geração que
        # está sendo cronometrada, e travar ali só atrasaria a bateria. A janela
        # é generosa porque a carga costuma ser montada bem acima da chamada.
        contexto = "\n".join(linhas[max(0, numero - 20) : numero + 2])
        if "/api/ps" in contexto or "keep_alive" in contexto:
            continue
        assert "timeout=None" in linha, (
            f"{script.name}:{numero} impõe limite de tempo numa chamada de "
            "geração. Um teto mede o teto: já abortou duas medições em que o "
            "modelo estava trabalhando — 6350 s contra um limite de 3600, e um "
            "teste morto aos 600 s."
        )
