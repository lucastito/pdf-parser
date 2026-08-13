"""Ensaio prévio: exercita o caminho inteiro em minutos, antes de gastar horas.

Este script não mede nada. Ele **falha cedo** — e é essa a função.

## Por que existe

A bateria completa custa horas, e todo defeito que ela encontrou nesta sessão
poderia ter sido encontrado nos primeiros minutos: contexto fixado para um modelo
e usado por seis, página lida com índice trocado, modelo ausente da máquina,
servidor no ar mas ocupado. Cada um desses custou uma rodada inteira descartada.

Na máquina de outra pessoa o custo é pior. Ela roda à noite, encontra o erro pela
manhã, e refazer é um pedido que não se pode fazer duas vezes.

## O que ele exercita, e por que basta

O caminho crítico é **a montagem da chamada**, não a geração. Um modelo que afere
sua entrada corretamente e responde a um pedido mínimo vai responder ao pedido
inteiro — mais devagar, e é só isso que a bateria acrescenta.

Então, para cada modelo da escada:

1. **está instalado?** — ausência aqui é minutos; na bateria seria horas;
2. **a entrada cabe?** — `aferir` mede o modelo real e calcula o contexto dele.
   Se nem a entrada couber, falha com o número na mensagem;
3. **ele gera?** — um pedido de poucos tokens, só para ver a chamada completar.

O que **não** é exercitado: qualidade, tempo comparável, acurácia. Nada aqui vira
resultado, e o script não grava em `resultados/` de propósito — número medido sob
condição de ensaio contaminaria a comparação se alguém o lesse depois.

## Falha é dado, e a varredura não para

Um modelo quebrado não aborta os outros: o relatório final lista quem passou e
quem não, com o motivo. Abortar no primeiro esconderia os demais problemas e
exigiria uma rodada por defeito.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from parser.cli import MODELOS_DO_EXPERIMENTO  # noqa: E402
from parser.configuracao import carregar_perfil, carregar_prompt  # noqa: E402
from parser.contexto import aferir  # noqa: E402

SERVIDOR = "http://localhost:11434"

TOKENS_DO_ENSAIO = 32
"""Saída mínima só para ver a chamada completar.

Não é amostra de qualidade: 32 tokens não cabe um item inteiro. O que se verifica
é que a chamada vai e volta com a configuração aferida.
"""

SAIDA_ESPERADA = 2607
"""O mesmo valor da bateria — o contexto aferido tem de ser o que ela vai usar.

Se o ensaio dimensionasse com folga menor, ele passaria e a bateria falharia,
que é exatamente o oposto do propósito.
"""

NATIVO_MINIMO = 32768


def _modelo_e_de_visao(nome: str) -> bool:
    """Modelo de visão recebe imagem; modelo de texto, o texto da página.

    A distinção importa aqui porque a entrada de um modelo de visão é dominada
    pela imagem, e aferir sem ela mediria outra coisa.
    """
    return "-vl" in nome or "ocr" in nome or "minicpm-v" in nome


def _requisicao(carga: dict) -> urllib.request.Request:
    return urllib.request.Request(
        f"{SERVIDOR}/api/generate",
        data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def _gerar(carga: dict) -> dict:
    """Chamada de geração, **sem teto de tempo** — e escrito por extenso.

    Um teto mede o teto: já abortou duas medições em que o modelo estava
    trabalhando. Aqui a espera pode ser longa de verdade, porque a primeira
    chamada de cada modelo inclui carregá-lo do disco.

    O `timeout=None` fica literal nesta linha de propósito. Escondê-lo atrás de
    um parâmetro deixaria o leitor — e a guarda que lê o código dos scripts —
    sem saber se há limite. Uma variável seria mais enxuta e menos verificável.
    """
    with urllib.request.urlopen(_requisicao(carga), timeout=None) as resposta:
        return json.load(resposta)


def _medir_entrada(modelo: str, prompt: str, imagens: list[str] | None) -> int:
    """Uma chamada de um token: o servidor relata quanto a entrada ocupou."""
    carga: dict = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 1},
    }
    if imagens:
        carga["images"] = imagens
    return _gerar(carga).get("prompt_eval_count") or 0


def _instalados() -> set[str]:
    with urllib.request.urlopen(f"{SERVIDOR}/api/tags", timeout=30) as r:
        nomes = {m["name"] for m in (json.load(r).get("models") or [])}
    # O servidor devolve "glm-ocr:latest" para quem foi baixado como "glm-ocr".
    return nomes | {n.split(":")[0] for n in nomes if n.endswith(":latest")}


def _descarregar(modelo: str) -> None:
    """Libera a memória antes do modelo seguinte.

    Teto legítimo, e por um motivo diferente do da geração: aqui não há número
    sendo cronometrado. Descarga que trava seguraria a bateria inteira, e o pior
    desfecho de desistir é o modelo seguinte carregar mais devagar.
    """
    carga = {
        "model": modelo,
        "prompt": "x",
        "stream": False,
        "keep_alive": 0,
        "options": {"num_predict": 1},
    }
    try:
        with urllib.request.urlopen(_requisicao(carga), timeout=120):
            pass
    except OSError:
        pass


def _texto_da_pagina(documento: Path, pagina: int) -> str:
    import pymupdf

    with pymupdf.open(documento) as pdf:
        return pdf[pagina - 1].get_text()


def _imagem_da_pagina(documento: Path, pagina: int, dpi: int) -> str:
    import base64

    import pymupdf

    with pymupdf.open(documento) as pdf:
        pixels = pdf[pagina - 1].get_pixmap(dpi=dpi)
        return base64.b64encode(pixels.tobytes("png")).decode("ascii")


def _entrada_do_ensaio(perfil, de_visao: bool) -> tuple[str, list[str] | None]:
    """A entrada é a **mesma** da bateria — ensaiar outra coisa não ensaia nada.

    Vale para os dois lados. A rota de visão manda a página renderizada; a de
    texto **anexa o texto extraído**, e é ele que domina o tamanho da entrada.
    Aferir o modelo de texto só com a instrução mediria uma fração do real, e o
    ensaio passaria exatamente onde a bateria falharia — o oposto do propósito.
    """
    rota = perfil.rotas["vlm" if de_visao else "llm"]
    documento = RAIZ / perfil.documento
    pagina = perfil.paginas_de_referencia("pagina-rotacionada")[0]

    prompt = carregar_prompt(RAIZ / rota.prompt).texto()
    colunas = "\n".join(f"{i}. {n}" for i, n in enumerate(perfil.campos_na_ordem, 1))
    instrucao = f"{prompt}\n\nAs colunas da tabela, nesta ordem:\n{colunas}"

    if de_visao:
        return instrucao, [_imagem_da_pagina(documento, pagina, rota.dpi)]
    return f"{instrucao}\n\n{_texto_da_pagina(documento, pagina)}", None


def ensaiar(modelo: str, perfil, instalados: set[str]) -> dict:
    if modelo not in instalados:
        return {
            "modelo": modelo,
            "ok": False,
            "onde": "instalação",
            "motivo": f"não está instalado — rode `ollama pull {modelo}`",
        }

    de_visao = _modelo_e_de_visao(modelo)
    instrucao, imagens = _entrada_do_ensaio(perfil, de_visao)

    inicio = time.perf_counter()
    try:
        afericao = aferir(
            modelo,
            medir=_medir_entrada,
            prompt=instrucao,
            imagens=imagens,
            saida_esperada=SAIDA_ESPERADA,
            nativo=NATIVO_MINIMO,
        )
    except (ValueError, OSError) as erro:
        return {"modelo": modelo, "ok": False, "onde": "aferição", "motivo": str(erro)}

    try:
        resposta = _gerar(
            {
                "model": modelo,
                "prompt": instrucao,
                **({"images": imagens} if imagens else {}),
                "stream": False,
                "think": False,
                "options": {
                    "num_ctx": afericao.contexto,
                    "num_predict": TOKENS_DO_ENSAIO,
                    "temperature": 0,
                },
            }
        )
    except OSError as erro:
        return {"modelo": modelo, "ok": False, "onde": "geração", "motivo": str(erro)}
    finally:
        _descarregar(modelo)

    gerou = (resposta.get("eval_count") or 0) > 0
    return {
        "modelo": modelo,
        "ok": gerou,
        "onde": None if gerou else "geração",
        "motivo": None if gerou else "respondeu sem gerar nenhum token",
        "entrada": afericao.entrada,
        "contexto": afericao.contexto,
        "segundos": round(time.perf_counter() - inicio, 1),
    }


def main() -> int:
    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")

    print(
        f"ensaio previo - pagina {perfil.paginas_de_referencia('pagina-rotacionada')[0]}",
        flush=True,
    )
    print(f"{len(MODELOS_DO_EXPERIMENTO)} modelos, saida de {TOKENS_DO_ENSAIO} tokens")
    print("nada aqui e resultado: o proposito e falhar cedo\n", flush=True)

    try:
        instalados = _instalados()
    except OSError as erro:
        print(f"servidor fora do ar em {SERVIDOR}: {erro}")
        print("inicie com `ollama serve` e rode de novo.")
        return 2

    relatos = []
    for numero, modelo in enumerate(MODELOS_DO_EXPERIMENTO, 1):
        print(f"[{numero}/{len(MODELOS_DO_EXPERIMENTO)}] {modelo}", flush=True)
        relato = ensaiar(modelo, perfil, instalados)
        relatos.append(relato)
        if relato["ok"]:
            print(
                f"      ok   entrada {relato['entrada']} tokens, "
                f"contexto {relato['contexto']}, {relato['segundos']}s",
                flush=True,
            )
        else:
            print(f"      X    {relato['onde']}: {relato['motivo']}", flush=True)

    falhos = [r for r in relatos if not r["ok"]]
    print(f"\n{len(relatos) - len(falhos)} de {len(relatos)} passaram")
    if falhos:
        print("\nnao rode a bateria antes de resolver:")
        for relato in falhos:
            print(f"  - {relato['modelo']}: {relato['motivo']}")
        return 1

    print("caminho livre — a bateria pode rodar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
