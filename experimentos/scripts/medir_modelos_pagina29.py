"""Mede cada modelo na página de referência, um de cada vez.

Fecha o conjunto da máquina de referência: cada modelo instalado lê a **mesma
página**, com o **mesmo prompt**, a **mesma semente** e **sem limite de tempo**.

## O que garante o rigor

**Um por vez, e a máquina livre.** Duas medições em paralelo inflam o tempo das
duas, e nada no resultado denuncia — já aconteceu neste projeto e os números
tiveram de ser refeitos. Aqui a sequência é estrita: um modelo termina, é
descarregado, e só então o seguinte começa.

**Descarga entre modelos.** Sem isso o segundo mediria com o primeiro ainda
ocupando memória, e a carga do segundo não entraria na conta. O tempo relatado
inclui carregar o modelo, porque é o que a máquina de destino também vai pagar.

**Ordem crescente de tamanho.** Se a memória apertar, aperta no fim — e os
resultados dos menores já estão gravados.

**Grava a cada modelo.** Interrupção no meio preserva o que já foi medido.

**Falha é dado.** Modelo que não roda tem o motivo registrado e a bateria segue;
abortar tudo por causa de um perderia os demais.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from parser.concordancia import _equivalentes, _indexar  # noqa: E402
from parser.configuracao import carregar_perfil, carregar_prompt  # noqa: E402
from parser.consolidacao import _chave_de_item  # noqa: E402
from parser.degraus import Uso  # noqa: E402

PAGINA = 29
"""Índice 28 no documento. A mesma de todas as medições comparáveis."""

CAMPOS = ["energia_kcal", "proteina_g", "lipideos_g", "carboidrato_g", "fibra_g"]

# Ordem crescente de tamanho: se a memória apertar, aperta no fim.
MODELOS_VISAO = [
    ("minicpm-v4.6:1b", 1.6),
    ("glm-ocr", 2.2),
    ("qwen3-vl:2b", 1.9),
    ("qwen3-vl:4b", 3.3),
    ("deepseek-ocr:3b", 6.7),
    ("minicpm-v4.5:8b", 6.1),
]


def _servidor_ocioso() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=10) as r:
            return not (json.load(r).get("models") or [])
    except OSError:
        return False


def _descarregar(modelo: str) -> None:
    """Pede ao servidor que libere o modelo, e espera de fato.

    Sem esperar, o modelo seguinte começaria a carregar com o anterior ainda na
    memória — e o tempo do seguinte incluiria a disputa.
    """
    carga = {"model": modelo, "prompt": "x", "stream": False, "keep_alive": 0}
    carga["options"] = {"num_predict": 1}
    pedido = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=300) as r:
            r.read()
    except OSError:
        pass

    for _ in range(60):
        if _servidor_ocioso():
            return
        time.sleep(5)


def _ocupacao_de_placa(modelo: str) -> dict:
    """Quanto do modelo foi para a placa, segundo o próprio servidor.

    Registrado porque é a diferença entre "esta máquina é lenta" e "esta máquina
    não usa a placa" — e nesta as duas coisas se confundem sem o número.
    """
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=10) as r:
            for m in json.load(r).get("models") or []:
                if m.get("name", "").startswith(modelo.split(":")[0]):
                    total = m.get("size", 0)
                    vram = m.get("size_vram", 0)
                    return {
                        "total_gb": round(total / 1e9, 2),
                        "placa_gb": round(vram / 1e9, 2),
                        "placa_pct": round(100 * vram / total, 1) if total else 0.0,
                    }
    except OSError:
        pass
    return {}


def _esquema_de_saida(campos: list[str]) -> dict:
    """O esquema como **gramática de decodificação** — o degrau 1 (SPEC §4.4).

    Difere de pedir `format: "json"`, que é o degrau 2: aquele garante JSON
    válido e não impõe a estrutura, e um objeto solto com os nomes do documento é
    JSON perfeitamente válido. Medido: com o degrau 2, três modelos leram a
    tabela certo e pontuaram zero por devolverem forma diferente da pedida.
    """
    todos = ["identificador", *campos]
    return {
        "type": "object",
        "properties": {
            "itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {c: {"type": ["string", "number", "null"]} for c in todos},
                    "required": todos,
                },
            }
        },
        "required": ["itens"],
    }


def _gabarito() -> dict[str, dict[str, float]]:
    import csv

    tabela: dict[str, dict[str, float]] = {}
    with (RAIZ / "experimentos" / "golden" / "taco.csv").open(encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            chave = _chave_de_item(f"{linha['numero']} {linha['descricao']}")
            tabela[chave] = {c: float(linha[c]) for c in CAMPOS if linha.get(c)}
    return tabela


def _conferir(itens: list, gabarito: dict) -> dict:
    # Modelo pequeno às vezes devolve lista de strings em vez de lista de
    # objetos. Descartar o que não é dicionário evita que a conferência quebre e
    # perca o resultado dos itens bem formados.
    itens = [it for it in itens if isinstance(it, dict)]
    registros = [{"campos": {k: {"valor": v} for k, v in it.items()}} for it in itens]
    indice = _indexar(registros, "identificador")
    acertos = erros = omissoes = 0
    for item, campos in indice.items():
        esperado = gabarito.get(_chave_de_item(item))
        if not esperado:
            continue
        for campo, valor in esperado.items():
            lido = campos.get(campo)
            if lido is None:
                omissoes += 1
            elif _equivalentes(lido, valor):
                acertos += 1
            else:
                erros += 1
    total = acertos + erros + omissoes
    return {
        "itens": len(itens),
        "casaram": sum(1 for i in indice if _chave_de_item(i) in gabarito),
        "acertos": acertos,
        "erros": erros,
        "omissoes": omissoes,
        "acuracia": round(acertos / total, 4) if total else 0.0,
    }


def _imagem(dpi: int) -> str:
    import base64

    import pymupdf

    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")
    with pymupdf.open(RAIZ / perfil.documento) as pdf:
        pixels = pdf[PAGINA - 1].get_pixmap(dpi=dpi)
        return base64.b64encode(pixels.tobytes("png")).decode("ascii")


def medir(modelo: str, imagem: str, gabarito: dict) -> dict:
    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")
    rota = perfil.rotas["vlm"]
    prompt = carregar_prompt(RAIZ / rota.prompt)

    colunas = "\n".join(f"{i}. {n}" for i, n in enumerate(perfil.campos_na_ordem, 1))
    instrucao = (
        f"{prompt.texto()}\n\n"
        f"As colunas da tabela, nesta ordem:\n{colunas}\n\n"
        "Cada linha traz um valor para **cada** coluna acima, na sequência.\n\n"
        f"Campos: identificador, {', '.join(CAMPOS)}\n\n"
        'Responda {"itens": [...]} com todos os itens da página.'
    )

    carga = {
        "model": modelo,
        "prompt": instrucao,
        "images": [imagem],
        "stream": False,
        "think": False,
        "format": _esquema_de_saida(CAMPOS),
        "options": {
            "num_ctx": rota.extras["contexto"],
            "seed": rota.extras["semente"],
            "temperature": 0,
        },
    }
    pedido = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    inicio = time.perf_counter()
    # Sem teto: um limite mediria o limite, não o modelo.
    with urllib.request.urlopen(pedido, timeout=None) as resposta:
        dados = json.load(resposta)
    segundos = time.perf_counter() - inicio

    uso = Uso(
        entrada=dados.get("prompt_eval_count") or 0,
        saida=dados.get("eval_count") or 0,
        raciocinio_chars=len(dados.get("thinking") or ""),
        eval_ns=dados.get("eval_duration") or 0,
        load_ns=dados.get("load_duration") or 0,
        total_ns=dados.get("total_duration") or 0,
    )

    texto = dados.get("response", "")
    # O servidor às vezes entrega a estrutura pelo canal de raciocínio e deixa a
    # resposta vazia — medido, e já custou o descarte de uma extração perfeita.
    veio_do_raciocinio = False
    if not texto.strip() and (dados.get("thinking") or "").strip():
        texto = dados["thinking"]
        veio_do_raciocinio = True

    itens: list[dict] = []
    erro_de_forma = None
    try:
        estrutura = json.loads(texto) if texto.strip() else {}
        if isinstance(estrutura, dict):
            itens = estrutura.get("itens", [])
    except json.JSONDecodeError as erro:
        erro_de_forma = str(erro)

    return {
        "modelo": modelo,
        "segundos": round(segundos, 1),
        "minutos": round(segundos / 60, 1),
        "done_reason": dados.get("done_reason"),
        "uso": uso.como_dados(),
        "placa": _ocupacao_de_placa(modelo),
        "veio_do_raciocinio": veio_do_raciocinio,
        "erro_de_forma": erro_de_forma,
        **_conferir(itens, gabarito),
        "resposta": texto[:4000],
    }


def main() -> int:
    import parser as pacote

    caminho = Path(pacote.__file__).resolve()
    if caminho != (RAIZ / "src" / "parser" / "__init__.py").resolve():
        raise SystemExit(f"pacote errado: {caminho}")

    if not _servidor_ocioso():
        print("servidor ocupado — descarregando antes de começar", flush=True)
        for modelo, _ in MODELOS_VISAO:
            _descarregar(modelo)

    gabarito = _gabarito()
    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")
    imagem = _imagem(perfil.rotas["vlm"].dpi)

    destino = RAIZ / "experimentos" / "resultados" / "titoslaptop"
    saida = destino / "modelos-pagina29.json"
    registro = {
        "medicao": "cada modelo de visão na página 29, um de cada vez",
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "maquina": "titoslaptop",
        "pagina": PAGINA,
        "condicao": (
            "sequencial, máquina ociosa, modelo descarregado entre execuções, "
            "semente fixa, temperatura zero, sem limite de tempo"
        ),
        "resultados": [],
    }

    for modelo, tamanho in MODELOS_VISAO:
        print(f"\n=== {modelo} ({tamanho} GB) ===", flush=True)
        try:
            resultado = medir(modelo, imagem, gabarito)
        except Exception as erro:  # noqa: BLE001 — falha é dado, não interrupção
            resultado = {"modelo": modelo, "falhou": f"{type(erro).__name__}: {erro}"}
            print(f"  falhou: {resultado['falhou']}", flush=True)
        else:
            placa = resultado.get("placa", {})
            print(
                f"  {resultado['minutos']} min | itens={resultado['itens']} "
                f"casaram={resultado['casaram']} | acurácia={resultado['acuracia']:.1%}",
                flush=True,
            )
            if placa:
                print(f"  placa: {placa.get('placa_pct')}%", flush=True)
            if resultado.get("veio_do_raciocinio"):
                print("  (conteúdo veio do canal de raciocínio)", flush=True)

        registro["resultados"].append(resultado)
        # Grava a cada modelo: interrupção preserva o que já foi medido.
        saida.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        _descarregar(modelo)

    print(f"\ngravado em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
