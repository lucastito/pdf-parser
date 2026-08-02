"""Remedição da rota de visão: página inteira, contexto correto, sem limite de tempo.

O que esta medição responde, e nenhuma anterior respondeu: **quanto tempo a
chamada realmente leva** quando nada a interrompe.

As três medições anteriores (`contexto-limite.json`) esbarraram em limite do
cliente: o caso com contexto de 4096 foi cortado pelo servidor em 21 min, e os de
16k e 32k passaram de 1 h ainda gerando, até o cliente desistir. O campo
`nao_medido` daquele arquivo registra exatamente esta lacuna.

Por que sem limite de tempo: um teto de cliente não mede o modelo, mede o teto.
Duas chamadas que estourariam em 1 h são indistinguíveis entre si — uma podendo
levar 70 min e outra 10 h. Para dimensionar a máquina de destino, a diferença é
tudo.

Contexto declarado, não herdado: 12271 para esta rota, valor que
`parser.contexto.dimensionar` devolve a partir da entrada medida (ADR-0018).
Herdar o padrão de 4096 do servidor foi a causa da conclusão errada que o projeto
publicou.

**Uma medição por vez.** O módulo `parser.medicao` tem a trava; este script a
respeita.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from parser.configuracao import carregar_perfil, carregar_prompt  # noqa: E402
from parser.contexto import aferir  # noqa: E402
from parser.degraus import Uso  # noqa: E402

PAGINA = 29
"""A mesma página de todas as medições anteriores.

Trocar de página tornaria esta rodada incomparável com as três de
`contexto-limite.json`, que é justamente com quem ela precisa ser comparada.
"""


def _verificar_pacote() -> None:
    """O pacote importado tem de ser o do repositório.

    Armadilha real, encontrada nesta máquina: um pacote instalado apontava para
    um clone antigo, e a medição rodaria código desatualizado sem nada denunciar.
    Falhar alto aqui é mais barato que descobrir depois de horas de execução.
    """
    import parser

    caminho = Path(parser.__file__).resolve()
    esperado = (RAIZ / "src" / "parser" / "__init__.py").resolve()
    if caminho != esperado:
        raise SystemExit(
            f"o pacote importado não é o do repositório:\n"
            f"  importado: {caminho}\n"
            f"  esperado : {esperado}\n"
            "Rode com PYTHONPATH apontando para src/, ou reinstale o pacote."
        )


def _renderizar(documento: Path, pagina: int, dpi: int) -> str:
    """Página como imagem, em base64 — a mesma entrada das medições anteriores."""
    import base64

    import pymupdf

    with pymupdf.open(documento) as pdf:
        alvo = pdf[pagina - 1]
        pixels = alvo.get_pixmap(dpi=dpi)
        return base64.b64encode(pixels.tobytes("png")).decode("ascii")


def _medir_entrada(modelo: str, prompt: str, imagens: list[str] | None) -> int:
    """Uma chamada de um token: quantos o modelo consome para ler esta entrada.

    O contexto passa a ser aferido **deste** modelo, não herdado da rota. Medido:
    na mesma imagem, um modelo consome 2159 tokens de entrada e outro 2791 — e o
    valor único cortou a geração no meio (ADR-0018).
    """
    import urllib.request

    carga: dict = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 1, "num_ctx": 4096},
    }
    if imagens:
        carga["images"] = imagens
    pedido = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(pedido, timeout=None) as resposta:
        return json.load(resposta).get("prompt_eval_count") or 0


def main() -> int:
    _verificar_pacote()

    perfil = carregar_perfil(RAIZ / "perfis" / "nutricional.json")
    rota = perfil.rotas["vlm"]
    contexto = rota.extras.get("contexto")
    if not contexto:
        raise SystemExit("a rota vlm não declara contexto — é o defeito do ADR-0018")

    documento = RAIZ / perfil.documento
    prompt = carregar_prompt(RAIZ / rota.prompt)
    imagem = _renderizar(documento, PAGINA, rota.dpi)

    destino = RAIZ / "experimentos" / "resultados" / "titoslaptop"
    destino.mkdir(parents=True, exist_ok=True)
    saida = destino / "vlm-pagina-inteira-sem-limite.json"

    registro: dict = {
        "proposito": (
            "Medir quanto tempo a rota de visão leva numa página inteira, com "
            "contexto correto e SEM limite de tempo do cliente."
        ),
        "pergunta": (
            "Com contexto suficiente, a rota preenche a planilha? E em quanto tempo?"
        ),
        "procedencia": {
            "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "maquina": platform.node(),
            "modelo": rota.modelo,
            "documento": f"página {PAGINA} do documento-caso, renderizada a {rota.dpi} dpi",
            "pedido": "extração COM VALORES — o caso de uso real",
            "contexto_declarado": contexto,
            "limite_de_tempo_do_cliente_s": None,
            "uma_medicao_por_vez": True,
            "prompt_impressao_digital": prompt.impressao_digital,
        },
        "estado": "em andamento",
    }
    saida.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"modelo   : {rota.modelo}")
    print(f"contexto : {contexto}")
    print(f"página   : {PAGINA} a {rota.dpi} dpi")
    print("limite   : nenhum — a chamada roda até o servidor terminar")
    print("iniciando; o resultado parcial já está em disco", flush=True)

    import urllib.request

    afericao = aferir(
        rota.modelo,
        medir=_medir_entrada,
        prompt=prompt.texto(),
        imagens=[imagem],
        saida_esperada=5948,
        nativo=32768,
    )
    print(f"contexto aferido: {afericao.contexto} (entrada {afericao.entrada})", flush=True)

    carga = {
        "model": rota.modelo,
        # `texto()` é método, não atributo: passar `prompt.texto` enviaria o
        # objeto-método e quebraria na serialização — aconteceu, e o ensaio não
        # pegou porque validava o carregamento do prompt, não o envio.
        "prompt": prompt.texto(),
        "images": [imagem],
        "stream": False,
        "think": False,
        # Degrau 2 deliberado: este script mede a rota como ela roda em
        # produção sem restrição de esquema, para comparar com o degrau 1.
        "format": "json",
        "options": {"num_ctx": afericao.contexto},
    }
    # Serializa antes de cronometrar: erro de carga tem de aparecer agora, não
    # depois de o servidor já estar ocupado.
    corpo = json.dumps(carga).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{rota.url}/api/generate",
        data=corpo,
        headers={"Content-Type": "application/json"},
    )

    inicio = time.perf_counter()
    try:
        # timeout=None é o ponto da medição: qualquer teto mediria o teto.
        with urllib.request.urlopen(requisicao, timeout=None) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except Exception as erro:  # noqa: BLE001 — falha é dado, não interrupção
        registro["estado"] = "falhou"
        registro["erro"] = f"{type(erro).__name__}: {erro}"
        registro["segundos"] = round(time.perf_counter() - inicio, 1)
        saida.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"falhou após {registro['segundos']}s: {registro['erro']}")
        return 1

    segundos = time.perf_counter() - inicio
    uso = Uso(
        entrada=dados.get("prompt_eval_count") or 0,
        saida=dados.get("eval_count") or 0,
        # O canal de raciocínio vem preenchido mesmo com think=false, e
        # descartá-lo foi o que tornou a primeira rodada desta medição
        # ininterpretável: 5684 tokens gerados e resposta vazia, sem saber onde
        # o conteúdo tinha ido parar.
        raciocinio_chars=len(dados.get("thinking") or ""),
        eval_ns=dados.get("eval_duration") or 0,
        load_ns=dados.get("load_duration") or 0,
        total_ns=dados.get("total_duration") or 0,
    )
    texto = dados.get("response", "")

    itens = None
    try:
        estrutura = json.loads(texto) if texto.strip() else {}
        if isinstance(estrutura, dict):
            itens = len(estrutura.get("itens", []))
    except json.JSONDecodeError:
        itens = None

    registro.update(
        {
            "estado": "concluído",
            "segundos": round(segundos, 1),
            "minutos": round(segundos / 60, 1),
            "done_reason": dados.get("done_reason"),
            # A soma é o que diagnostica: igual ao contexto é assinatura de corte.
            "uso": uso.como_dados(),
            "bateu_no_contexto": uso.bate_no_teto(contexto),
            "chars_resposta": len(texto),
            "chars_raciocinio": uso.raciocinio_chars,
            "itens_extraidos": itens,
            "resposta": texto,
            # Guardado na íntegra: se a resposta vier vazia de novo, é aqui que
            # se vê o que o modelo produziu, e o diagnóstico não depende de
            # refazer 77 minutos de medição.
            "raciocinio": dados.get("thinking") or "",
        }
    )
    saida.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"concluído em {registro['minutos']} min")
    print(f"tokens: entrada {uso.entrada} + saída {uso.saida} = {uso.total}")
    print(f"raciocínio: {uso.raciocinio_chars} chars  resposta: {len(texto)} chars")
    if uso.tokens_por_segundo is not None:
        print(f"velocidade: {uso.tokens_por_segundo:.2f} tokens/s")
    print(f"done_reason: {registro['done_reason']}  itens: {itens}")
    print(f"gravado em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
