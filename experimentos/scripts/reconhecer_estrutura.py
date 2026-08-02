"""Um modelo consegue **descrever a estrutura** da página, em vez de extraí-la?

A pergunta que este script responde decide uma arquitetura inteira.

Hoje o parser precisa que alguém configure a estrutura de cada documento — quais
colunas, em que ordem, com que rotação. Isso funciona para um documento conhecido
e **não escala**: o cliente sempre manda o que não está na coleção, e coletar
mais exemplos nunca fecha o problema.

A saída é o parser **descobrir** com o que está lidando. E há três fontes de
sinal, em ordem de custo:

1. **estrutura nativa do PDF** — rotação, blocos, linhas de grade, gerador do
   arquivo. Grátis e instantâneo, e discrimina mais do que parece;
2. **inspeção determinística** — densidade numérica por faixa, contagem de
   linhas. Barata;
3. **modelo descrevendo o layout** — caro, e é o que este script mede.

A terceira só é necessária quando as duas primeiras não bastam: escaneado sem
camada de texto, manuscrito, layout exótico.

**Por que pode ser barato:** descrever estrutura pede dezenas de tokens de
resposta; extrair uma página inteira pede milhares. Se a descrição custar uma
fração da extração, ela cabe como etapa de reconhecimento por página.
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

ESQUEMA = {
    "type": "object",
    "properties": {
        "tem_tabela": {"type": "boolean"},
        "orientacao": {"type": "string"},
        "colunas": {"type": "array", "items": {"type": "string"}},
        "tem_grade": {"type": "boolean"},
        "dificuldade": {"type": "string"},
    },
    "required": ["tem_tabela", "colunas"],
}

INSTRUCAO = """Descreva a ESTRUTURA desta página. NÃO extraia os dados.

- tem_tabela: existe uma tabela de dados?
- orientacao: o texto está na horizontal ou girado?
- colunas: os NOMES dos cabeçalhos, na ordem em que aparecem
- tem_grade: há linhas separando as células?
- dificuldade: o que dificultaria a leitura automática desta página"""


def _sinais_nativos(caminho: Path, pagina: int) -> dict:
    """O que o PDF entrega sem modelo nenhum — grátis e instantâneo."""
    import pymupdf

    with pymupdf.open(caminho) as pdf:
        p = pdf[pagina - 1]
        palavras = p.get_text("words")
        desenhos = p.get_drawings()
        numericas = sum(1 for w in palavras if any(c.isdigit() for c in w[4]))
        return {
            "rotacao": p.rotation,
            "palavras": len(palavras),
            "densidade_numerica": round(numericas / len(palavras), 2) if palavras else 0.0,
            "blocos": len(p.get_text("blocks")),
            "imagens": len(p.get_images()),
            "linhas_horizontais": sum(
                1 for d in desenhos if d["rect"].height < 2 and d["rect"].width > 50
            ),
            "linhas_verticais": sum(
                1 for d in desenhos if d["rect"].width < 2 and d["rect"].height > 50
            ),
            "gerador": (pdf.metadata or {}).get("creator", ""),
            "tem_camada_de_texto": bool(palavras),
        }


def main() -> int:
    documento = RAIZ / "experimentos" / "pdf" / "TACO.pdf"
    pagina = 29
    modelo = sys.argv[1] if len(sys.argv) > 1 else "qwen3-vl:2b"

    nativos = _sinais_nativos(documento, pagina)
    print("SINAIS NATIVOS (custo zero):")
    for chave, valor in nativos.items():
        print(f"  {chave:22s} {valor}")

    import pymupdf

    with pymupdf.open(documento) as pdf:
        imagem = base64.b64encode(pdf[pagina - 1].get_pixmap(dpi=150).tobytes("png")).decode()

    carga = {
        "model": modelo,
        "prompt": INSTRUCAO,
        "images": [imagem],
        "stream": False,
        "think": False,
        "format": ESQUEMA,
        "options": {"num_ctx": 6000, "seed": 20260801, "temperature": 0},
    }
    pedido = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    print(f"\nRECONHECIMENTO POR MODELO ({modelo}) — descrever, não extrair...", flush=True)
    inicio = time.perf_counter()
    with urllib.request.urlopen(pedido, timeout=None) as resposta:
        dados = json.load(resposta)
    segundos = time.perf_counter() - inicio

    texto = dados.get("response", "") or dados.get("thinking", "")
    try:
        descricao = json.loads(texto)
    except json.JSONDecodeError:
        descricao = {"bruto": texto[:600]}

    print(f"  {segundos / 60:.1f} min | saída: {dados.get('eval_count')} tokens")
    print(json.dumps(descricao, ensure_ascii=False, indent=2)[:1200])

    saida = (
        RAIZ / "experimentos" / "resultados" / "titoslaptop" / "reconhecimento-estrutura.json"
    )
    saida.write_text(
        json.dumps(
            {
                "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "modelo": modelo,
                "pagina": pagina,
                "sinais_nativos": nativos,
                "segundos": round(segundos, 1),
                "tokens_saida": dados.get("eval_count"),
                "descricao": descricao,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\ngravado em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
