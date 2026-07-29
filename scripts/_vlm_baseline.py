"""Roda o VLM nas paginas do gabarito, sem limite apertado."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, "src")
from parser.experimento import Experimento
from parser.extratores.vlm import ExtratorVLM
from parser.fontes.pdf import FontePDF
from parser.ollama import ClienteOllama

PDF = r"c:\Users\Lucas Tito\projetos\nutriflow\data\rag\sources\taco\raw\TACO.pdf"
CAMPOS = ["identificador","energia_kcal","proteina_g","lipideos_g","carboidrato_g","fibra_g"]
PAGINAS = range(28, 31, 2)   # indices 28 e 30 -> paginas 29 e 31 (as do gabarito)

exp = Experimento(PDF, Path("resultados"))
print(f"maquina: {exp.ambiente.maquina}", flush=True)
print(f"paginas: {list(PAGINAS)} (PDF {[i+1 for i in PAGINAS]})", flush=True)
print("iniciando VLM dpi=150, limite 3600s por chamada...", flush=True)

t0 = time.perf_counter()
ex = exp.rodar(
    "vlm",
    FontePDF(paginas=PAGINAS),
    ExtratorVLM(
        ClienteOllama(modelo="qwen3-vl:4b", timeout=3600.0),
        CAMPOS, PDF, dpi=150,
    ),
    parametros={"tipo":"vlm","modelo":"qwen3-vl:4b","dpi":150},
)
print(f"\nconcluido em {time.perf_counter()-t0:.0f}s", flush=True)
print(f"  registros: {ex.registros}", flush=True)
print(f"  campos   : {ex.campos}", flush=True)
print(f"  erro     : {ex.erro}", flush=True)
pasta = exp.gravar()
print(f"gravado em {pasta}", flush=True)
