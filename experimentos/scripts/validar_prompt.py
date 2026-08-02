"""Valida o prompt em escopo pequeno, antes de qualquer bateria.

**Não é medição comparativa.** É acerto de configuração, e a distinção decide o
desenho: aqui nenhuma hipótese varia. Variá-las agora mediria configuração sob um
prompt ainda não confirmado, e o trabalho teria de ser refeito depois que o
prompt mudasse.

A ordem é: prompt validado → prompt congelado (ADR-0022) → hipóteses variam na
triagem, em todas as máquinas.

## Por que poucos itens

A bateria completa custou 8071 s para revelar dois defeitos que meia dúzia de
itens mostraria em minutos: colunas deslocadas por uma posição e identificador
sem descrição. Medir grande para descobrir pequeno foi erro de método, e este
script existe para não repeti-lo.

O que se confere aqui:

1. a saída é JSON bem-formado, com a chave esperada;
2. o identificador traz número **e** descrição;
3. os valores caem na coluna certa — conferidos contra o gabarito.

O item 3 é o que pega o defeito silencioso: valores reais, da linha certa, no
campo errado.

## Sem limite de tempo

`timeout=None`, por decisão registrada no perfil. Um teto não mede o modelo, mede
o teto: foi ele que abortou a rota de visão em 6350 s, quando a medição sem
limite mostrou que ela termina.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from parser.configuracao import carregar_perfil, carregar_prompt  # noqa: E402
from parser.degraus import Uso  # noqa: E402

PAGINA = 29
"""A mesma de todas as medições anteriores — trocar tornaria incomparável."""

CAMPOS_CONFERIDOS = ["energia_kcal", "proteina_g", "lipideos_g", "carboidrato_g", "fibra_g"]


def _verificar_pacote() -> None:
    """O pacote importado tem de ser o do repositório.

    Armadilha real desta máquina: um pacote instalado apontava para clone antigo,
    e a validação rodaria código desatualizado sem nada denunciar.
    """
    import parser

    caminho = Path(parser.__file__).resolve()
    esperado = (RAIZ / "src" / "parser" / "__init__.py").resolve()
    if caminho != esperado:
        raise SystemExit(
            f"o pacote importado não é o do repositório:\n"
            f"  importado: {caminho}\n  esperado : {esperado}"
        )


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
    """Valores conferidos à mão, indexados pelo número do item."""
    fonte = RAIZ / "experimentos" / "golden" / "taco.csv"
    tabela: dict[str, dict[str, float]] = {}
    with fonte.open(encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            tabela[linha["numero"]] = {
                campo: float(linha[campo]) for campo in CAMPOS_CONFERIDOS if linha.get(campo)
            }
    return tabela


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


def _como_numero(valor: object) -> float | None:
    """Converte o valor lido para número, aceitando vírgula decimal.

    O prompt manda **preservar a vírgula** como está no documento (a conversão é
    etapa posterior, igual para todas as estratégias). Um conferidor que compara
    texto marcaria `"2,6"` como diferente de `2.6` — o mesmo número — e
    reportaria erro onde a extração acertou.

    Aconteceu: a primeira rodada desta validação acusou 20 erros, dos quais 8
    eram vírgula contra ponto.
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _numero_de(identificador: object) -> str:
    """Extrai o número do item, seja ele `12` ou `12 Farinha, de mandioca`."""
    if identificador is None:
        return ""
    texto = str(identificador).strip()
    if not texto:
        return ""
    if isinstance(identificador, float) and identificador.is_integer():
        return str(int(identificador))
    return texto.split()[0].rstrip(".,")


def _conferir(itens: list[dict], gabarito: dict[str, dict[str, float]]) -> dict:
    """Confere os itens extraídos contra o gabarito, campo a campo.

    Devolve também **em qual campo** cada erro aconteceu: se os erros se
    concentram num campo só, ou se todos os campos após um certo ponto erram, a
    assinatura é de deslocamento de coluna — não de leitura ruim.
    """
    acertos = erros = omissoes = 0
    por_campo: dict[str, dict[str, int]] = {c: {"ok": 0, "erro": 0} for c in CAMPOS_CONFERIDOS}
    exemplos: list[dict] = []
    sem_descricao = 0
    conferidos = 0

    for item in itens:
        bruto = item.get("identificador")
        numero = _numero_de(bruto)
        # Identificador sem descrição é defeito por si: sem ele nenhum item casa
        # na consolidação nem contra o gabarito. A marca é não haver espaço —
        # `12` contra `12 Farinha, de mandioca`.
        if bruto is not None and " " not in str(bruto).strip():
            sem_descricao += 1
        if numero not in gabarito:
            continue
        conferidos += 1
        for campo, esperado in gabarito[numero].items():
            lido = item.get(campo)
            if lido is None:
                omissoes += 1
                continue
            numero = _como_numero(lido)
            certo = (
                numero is not None
                and bool(esperado)
                and abs(numero - esperado) / abs(esperado) <= 0.01
            )
            if certo:
                acertos += 1
                por_campo[campo]["ok"] += 1
            else:
                erros += 1
                por_campo[campo]["erro"] += 1
                if len(exemplos) < 6:
                    exemplos.append(
                        {"item": numero, "campo": campo, "lido": lido, "esperado": esperado}
                    )

    total = acertos + erros + omissoes
    return {
        "itens_extraidos": len(itens),
        "itens_conferidos": conferidos,
        "identificadores_sem_descricao": sem_descricao,
        "acertos": acertos,
        "erros": erros,
        "omissoes": omissoes,
        "acuracia": round(acertos / total, 4) if total else 0.0,
        "por_campo": por_campo,
        "exemplos_de_erro": exemplos,
    }


def _chamar(rota, prompt_texto: str, imagem: str | None) -> tuple[dict, float]:
    import urllib.request

    carga: dict = {
        "model": rota.modelo,
        "prompt": prompt_texto,
        "stream": False,
        "think": False,
        "format": _esquema_de_saida(CAMPOS_CONFERIDOS),
        "options": {
            "num_ctx": rota.extras["contexto"],
            "seed": rota.extras["semente"],
            "temperature": 0,
        },
    }
    if imagem:
        carga["images"] = [imagem]

    corpo = json.dumps(carga).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{rota.url}/api/generate", data=corpo, headers={"Content-Type": "application/json"}
    )
    inicio = time.perf_counter()
    # Sem teto: um limite mediria o limite, não o modelo.
    with urllib.request.urlopen(requisicao, timeout=None) as resposta:
        dados = json.load(resposta)
    return dados, time.perf_counter() - inicio


def validar(nome_rota: str, limite_de_itens: int) -> dict:
    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")
    rota = perfil.rotas[nome_rota]
    prompt = carregar_prompt(RAIZ / rota.prompt)
    documento = RAIZ / perfil.documento

    forma = ", ".join(f'"{campo}": ...' for campo in ["identificador", *CAMPOS_CONFERIDOS])
    instrucao = (
        f"{prompt.texto()}\n\n"
        f"Extraia apenas os **{limite_de_itens} primeiros** itens da tabela.\n"
        f'Responda no formato {{"itens": [{{{forma}}}]}}'
    )

    imagem = None
    if nome_rota == "vlm":
        imagem = _imagem_da_pagina(documento, PAGINA, rota.dpi)
    else:
        instrucao = f"{instrucao}\n\n{_texto_da_pagina(documento, PAGINA)}"

    print(f"  modelo   : {rota.modelo}")
    print(f"  contexto : {rota.extras['contexto']}   semente: {rota.extras['semente']}")
    print(f"  prompt   : {prompt.impressao_digital[:12]}")
    print("  sem limite de tempo; aguardando o servidor...", flush=True)

    dados, segundos = _chamar(rota, instrucao, imagem)
    uso = Uso(
        entrada=dados.get("prompt_eval_count") or 0,
        saida=dados.get("eval_count") or 0,
        raciocinio_chars=len(dados.get("thinking") or ""),
        eval_ns=dados.get("eval_duration") or 0,
        load_ns=dados.get("load_duration") or 0,
        total_ns=dados.get("total_duration") or 0,
    )

    texto = dados.get("response", "")
    itens: list[dict] = []
    erro_de_forma = None
    try:
        estrutura = json.loads(texto) if texto.strip() else {}
        itens = estrutura.get("itens", []) if isinstance(estrutura, dict) else []
    except json.JSONDecodeError as erro:
        erro_de_forma = f"JSON inválido: {erro}"

    conferencia = _conferir(itens, _gabarito()) if itens else {}

    return {
        "rota": nome_rota,
        "modelo": rota.modelo,
        "prompt": prompt.impressao_digital,
        "itens_pedidos": limite_de_itens,
        "segundos": round(segundos, 1),
        "done_reason": dados.get("done_reason"),
        "uso": uso.como_dados(),
        "bateu_no_contexto": uso.bate_no_teto(rota.extras["contexto"]),
        "erro_de_forma": erro_de_forma,
        "chars_resposta": len(texto),
        **conferencia,
        "resposta": texto,
        "raciocinio": dados.get("thinking") or "",
    }


def main(argv: list[str] | None = None) -> int:
    parser_args = argparse.ArgumentParser(description=__doc__)
    parser_args.add_argument("--rotas", nargs="+", default=["llm", "vlm"])
    parser_args.add_argument("--itens", type=int, default=5)
    opcoes = parser_args.parse_args(argv)

    _verificar_pacote()

    destino = RAIZ / "experimentos" / "resultados" / "titoslaptop"
    destino.mkdir(parents=True, exist_ok=True)
    saida = destino / "validacao-de-prompt.json"

    registro = {
        "proposito": (
            "Validar o prompt corrigido em escopo pequeno. NÃO é medição "
            "comparativa: nenhuma hipótese varia, e o tempo não deve ser usado "
            "para comparar máquinas."
        ),
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pagina": PAGINA,
        "resultados": [],
    }

    for nome in opcoes.rotas:
        print(f"\n{nome} — {opcoes.itens} itens")
        try:
            resultado = validar(nome, opcoes.itens)
        except Exception as erro:  # noqa: BLE001 — falha é dado
            resultado = {"rota": nome, "falhou": f"{type(erro).__name__}: {erro}"}
            print(f"  falhou: {resultado['falhou']}")
        else:
            print(f"  {resultado['segundos']}s  itens: {resultado.get('itens_extraidos', 0)}")
            if resultado.get("erro_de_forma"):
                print(f"  FORMA: {resultado['erro_de_forma']}")
            if resultado.get("itens_conferidos"):
                print(
                    f"  conferidos: {resultado['itens_conferidos']}  "
                    f"acertos: {resultado['acertos']}  erros: {resultado['erros']}  "
                    f"omissões: {resultado['omissoes']}  "
                    f"acurácia: {resultado['acuracia']:.1%}"
                )
                if resultado["exemplos_de_erro"]:
                    print("  erros:")
                    for e in resultado["exemplos_de_erro"]:
                        print(
                            f"    item {e['item']} {e['campo']}: "
                            f"leu {e['lido']}, esperado {e['esperado']}"
                        )
            if resultado.get("identificadores_sem_descricao"):
                print(
                    f"  ATENÇÃO: {resultado['identificadores_sem_descricao']} "
                    "identificador(es) sem descrição"
                )

        registro["resultados"].append(resultado)
        saida.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\ngravado em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
