"""Gatilho automático para o achado −1.2 (PLANO.md): as auditorias de 02/08
relataram testes que passam isolados e falham na suíte completa, sem causa
raiz identificada. Investigação manual (2026-08-12) — três rodadas em ordem
fixa e quatro com ordem embaralhada (`pytest-randomly`), 784/784 nas sete —
não reproduziu nada, mas "não reproduzido hoje" não é "não existe".

Este módulo existe pra não depender de alguém notar e lembrar os detalhes na
próxima vez que isso acontecer. Quando um teste falha rodando a suíte
completa (não um arquivo isolado — TDD normal não deve disparar isto), ele:

1. grava a ordem exata dos testes que rodaram antes dele, nesta sessão —
   é a pista que falta pra achar qual teste vaza estado pro outro;
2. grava a semente do `pytest-randomly` desta rodada — reproduz com
   `--randomly-seed=<semente>` ou `--randomly-seed=last`;
3. roda o mesmo teste sozinho, num processo novo, pra confirmar (ou não) o
   padrão "passa isolado, falha no conjunto" que as auditorias relataram;
4. grava tudo num JSON em `diagnostico-instabilidade/`, fora do git.

Ativa só quando muitos testes foram coletados (suíte completa) — o limiar é
configurável via `PARSER_LIMIAR_DIAGNOSTICO` (padrão 100) pra que este
próprio mecanismo seja testável sem precisar rodar a suíte real inteira
(ver `tests/test_gatilho_instabilidade.py`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ENV_LIMIAR = "PARSER_LIMIAR_DIAGNOSTICO"
ENV_REEXECUCAO = "_PARSER_REEXECUCAO_DIAGNOSTICO"
LIMIAR_PADRAO = 100

_ordem_da_sessao: list[str] = []
_total_coletado = 0
_config_da_sessao: Any = None


def pytest_configure(config):
    global _config_da_sessao
    _config_da_sessao = config


def pytest_collection_modifyitems(session, config, items):
    global _total_coletado
    _total_coletado = len(items)


def pytest_runtest_logstart(nodeid, location):
    _ordem_da_sessao.append(nodeid)


def pytest_runtest_logreport(report):
    """Só age numa falha real de execução (`when == "call"`), na suíte
    completa, e nunca na própria reexecução de diagnóstico — senão ela
    dispararia a si mesma."""
    if report.when != "call" or not report.failed:
        return
    if os.environ.get(ENV_REEXECUCAO):
        return

    limiar = int(os.environ.get(ENV_LIMIAR, LIMIAR_PADRAO))
    if _total_coletado < limiar:
        return

    _capturar(report)


def _raiz() -> Path:
    if _config_da_sessao is not None:
        return Path(_config_da_sessao.rootpath)
    return Path.cwd()


def _capturar(report) -> None:
    nodeid = report.nodeid
    momento = time.strftime("%Y%m%dT%H%M%S")
    raiz = _raiz()

    env = dict(os.environ)
    env[ENV_REEXECUCAO] = "1"
    try:
        isolado = subprocess.run(
            [sys.executable, "-m", "pytest", nodeid, "-q"],
            cwd=str(raiz),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        passou_isolado = isolado.returncode == 0
        saida_isolada = isolado.stdout[-4000:]
    except Exception as erro:  # noqa: BLE001 — diagnóstico não pode derrubar a suíte
        passou_isolado = None
        saida_isolada = f"reexecução isolada falhou: {type(erro).__name__}: {erro}"

    seed = (
        _config_da_sessao.getoption("randomly_seed", None)
        if _config_da_sessao is not None
        else None
    )

    dados = {
        "quando": momento,
        "teste_que_falhou": nodeid,
        "semente_pytest_randomly": seed,
        "ordem_dos_testes_ate_aqui": list(_ordem_da_sessao),
        "passou_isolado": passou_isolado,
        "saida_da_reexecucao_isolada": saida_isolada,
        "traceback_no_conjunto": str(report.longrepr)[:8000],
    }

    pasta = raiz / "diagnostico-instabilidade"
    pasta.mkdir(exist_ok=True)
    nome = nodeid.replace("/", "_").replace("::", "-").replace(":", "-")
    caminho = pasta / f"{momento}-{nome}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"\n\n⚠ INSTABILIDADE CAPTURADA (−1.2, PLANO.md) — evidência em {caminho}",
        file=sys.stderr,
    )
    if passou_isolado:
        print(
            "  Confirma o padrão das auditorias: passou sozinho, falhou no conjunto.",
            file=sys.stderr,
        )
