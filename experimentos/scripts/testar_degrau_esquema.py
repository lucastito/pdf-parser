"""Os modelos que zeraram falham por formato — o esquema como gramática resolve?

Na medição de seis modelos (2026-08-01), quatro pontuaram zero **sem falhar em
ler**: `glm-ocr` transcreveu a linha inteira corretamente e devolveu um objeto
solto; `minicpm-v4.6:1b` leu certo e inventou os nomes das chaves.

A causa é do desenho da medição, não dos modelos: aquele script enviou
`format: "json"`, que é o **degrau 2** — o servidor garante JSON válido e **não
impõe a estrutura**. Objeto solto com nomes do documento é JSON perfeitamente
válido.

O **degrau 1** envia o esquema como gramática de decodificação, e aí o servidor
fica *impossibilitado* de gerar fora dele. É o mecanismo que o projeto construiu
para exatamente este problema (SPEC §4.4, ADR-0015) e que a medição não usou.

Este script isola a variável: **mesmo modelo, mesma página, mesmo prompt, mesma
semente** — só o degrau muda.
"""

from __future__ import annotations

import base64
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

PAGINA = 29
CAMPOS = ["energia_kcal", "proteina_g", "lipideos_g", "carboidrato_g", "fibra_g"]

# Os que zeraram por formato, do menor ao maior.
CANDIDATOS = ["glm-ocr", "minicpm-v4.6:1b", "qwen3-vl:2b", "deepseek-ocr:3b"]


def _esquema() -> dict:
    campos = ["identificador", *CAMPOS]
    return {
        "type": "object",
        "properties": {
            "itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {c: {"type": ["string", "number", "null"]} for c in campos},
                    "required": campos,
                },
            }
        },
        "required": ["itens"],
    }


def _gabarito() -> dict:
    import csv

    tabela = {}
    with (RAIZ / "experimentos" / "golden" / "taco.csv").open(encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            chave = _chave_de_item(f"{linha['numero']} {linha['descricao']}")
            tabela[chave] = {c: float(linha[c]) for c in CAMPOS if linha.get(c)}
    return tabela


def _conferir(itens: list, gabarito: dict) -> dict:
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


def _descarregar(modelo: str) -> None:
    carga = {
        "model": modelo,
        "prompt": "x",
        "stream": False,
        "keep_alive": 0,
        "options": {"num_predict": 1},
    }
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
        try:
            with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=10) as r:
                if not (json.load(r).get("models") or []):
                    return
        except OSError:
            return
        time.sleep(5)


def main() -> int:
    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")
    rota = perfil.rotas["vlm"]
    prompt = carregar_prompt(RAIZ / rota.prompt)

    import pymupdf

    with pymupdf.open(RAIZ / perfil.documento) as pdf:
        imagem = base64.b64encode(
            pdf[PAGINA - 1].get_pixmap(dpi=rota.dpi).tobytes("png")
        ).decode("ascii")

    colunas = "\n".join(f"{i}. {n}" for i, n in enumerate(perfil.campos_na_ordem, 1))
    instrucao = (
        f"{prompt.texto()}\n\n"
        f"As colunas da tabela, nesta ordem:\n{colunas}\n\n"
        "Cada linha traz um valor para **cada** coluna acima, na sequência."
    )

    gabarito = _gabarito()
    saida = RAIZ / "experimentos" / "resultados" / "titoslaptop" / "degrau-esquema.json"
    registro = {
        "medicao": "os modelos que zeraram por formato, agora com esquema como gramática",
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "degrau": "esquema-completo (degrau 1)",
        "comparado_com": "format json (degrau 2), que produziu 0% nestes modelos",
        "resultados": [],
    }

    for modelo in CANDIDATOS:
        print(f"\n=== {modelo} ===", flush=True)
        carga = {
            "model": modelo,
            "prompt": instrucao,
            "images": [imagem],
            "stream": False,
            "think": False,
            "format": _esquema(),
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
        try:
            with urllib.request.urlopen(pedido, timeout=None) as resposta:
                dados = json.load(resposta)
        except Exception as erro:  # noqa: BLE001 — falha é dado
            resultado = {"modelo": modelo, "falhou": f"{type(erro).__name__}: {erro}"}
            print(f"  falhou: {resultado['falhou']}", flush=True)
        else:
            segundos = time.perf_counter() - inicio
            texto = dados.get("response", "")
            if not texto.strip() and (dados.get("thinking") or "").strip():
                texto = dados["thinking"]
            itens = []
            try:
                estrutura = json.loads(texto) if texto.strip() else {}
                if isinstance(estrutura, dict):
                    itens = estrutura.get("itens", [])
            except json.JSONDecodeError:
                pass
            # Sem os tokens não se distingue corte por contexto de corte por
            # teto de saída — foi a soma deles que revelou a causa no ADR-0018,
            # e este script os descartava. Mesmo erro, script novo.
            entrada = dados.get("prompt_eval_count") or 0
            saida_tok = dados.get("eval_count") or 0
            resultado = {
                "modelo": modelo,
                "minutos": round(segundos / 60, 1),
                "done_reason": dados.get("done_reason"),
                "uso": {
                    "entrada": entrada,
                    "saida": saida_tok,
                    "total": entrada + saida_tok,
                    "contexto_pedido": rota.extras["contexto"],
                    "bateu_no_contexto": entrada + saida_tok >= rota.extras["contexto"],
                },
                **_conferir(itens, gabarito),
                "resposta": texto[:2000],
            }
            print(
                f"  {resultado['minutos']} min | itens={resultado['itens']} "
                f"casaram={resultado['casaram']} | acurácia={resultado['acuracia']:.1%}",
                flush=True,
            )

        registro["resultados"].append(resultado)
        saida.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        _descarregar(modelo)

    print(f"\ngravado em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
