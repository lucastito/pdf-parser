"""Execução e registro de um experimento comparativo.

Roda estratégias sobre o mesmo documento, no mesmo ambiente, e grava os
resultados com **procedência**: processador, memória, modelos e etiquetas,
resolução, páginas, data. Sem isso, duas execuções em máquinas diferentes não
podem ser confrontadas — e uma medição de tempo sem contexto é inútil semanas
depois.

Duas decisões de método valem explicitar:

**Cada máquina é uma rodada autocontida.** Comparar estratégias executadas em
hardwares diferentes mediria hardware, não estratégia. Entre máquinas, só a
dimensão de velocidade é comparável.

**Os dados brutos são gravados antes de qualquer conclusão.** Acurácia exige
gabarito conferido à mão; enquanto ele não existe, o experimento coleta o que
não depende dele (velocidade, cobertura, concordância entre estratégias) e a
acurácia é calculada **retroativamente** sobre os mesmos dados, sem reexecutar.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parser.pipeline import Pipeline
from parser.portas import Extrator, FonteDocumento

__all__ = ["Ambiente", "Execucao", "Experimento", "identificador_de_maquina"]


def identificador_de_maquina() -> str:
    """Rótulo curto e estável para nomear a pasta de resultados."""
    nome = platform.node() or "maquina"
    return re.sub(r"[^a-zA-Z0-9_-]", "-", nome).strip("-").lower() or "maquina"


def _processador() -> str:
    if platform.system() == "Windows":
        try:
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True, text=True, timeout=20,
            )
            if saida.stdout.strip():
                return saida.stdout.strip().splitlines()[0]
        except Exception:
            pass
    return platform.processor() or platform.machine()


def _nucleos() -> int | None:
    try:
        import os
        return os.cpu_count()
    except Exception:
        return None


def _ram() -> tuple[float | None, float | None]:
    try:
        if platform.system() == "Windows":
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "$c=Get-CimInstance Win32_ComputerSystem;"
                 "$o=Get-CimInstance Win32_OperatingSystem;"
                 "Write-Output \"$($c.TotalPhysicalMemory) $($o.FreePhysicalMemory)\""],
                capture_output=True, text=True, timeout=20,
            )
            partes = saida.stdout.split()
            if len(partes) == 2:
                return round(int(partes[0]) / 1024**3, 1), round(int(partes[1]) / 1024**2, 1)
        else:
            info = Path("/proc/meminfo").read_text()
            campos = {
                linha.split(":")[0]: int(linha.split()[1])
                for linha in info.splitlines() if ":" in linha
            }
            total = round(campos["MemTotal"] / 1024**2, 1)
            livre = round(campos.get("MemAvailable", campos["MemFree"]) / 1024**2, 1)
            return total, livre
    except Exception:
        pass
    return None, None


def _gpu() -> tuple[str | None, str | None]:
    import shutil
    if shutil.which("nvidia-smi"):
        try:
            saida = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=20,
            )
            linha = saida.stdout.strip().splitlines()[0]
            nome, memoria = (p.strip() for p in linha.split(","))
            return nome, memoria
        except Exception:
            pass
    if platform.system() == "Windows":
        try:
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name"],
                capture_output=True, text=True, timeout=20,
            )
            if saida.stdout.strip():
                return saida.stdout.strip().splitlines()[0], None
        except Exception:
            pass
    return None, None


def modelos_disponiveis(url: str = "http://localhost:11434") -> list[dict]:
    """Etiquetas exatas dos modelos no servidor.

    A etiqueta importa: `modelo` e `modelo:variante` podem ser modelos distintos,
    e comparar rodadas com etiquetas diferentes não é comparar o mesmo modelo.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=10) as r:
            dados = json.loads(r.read().decode("utf-8"))
        return [
            {"nome": m.get("name"), "digest": (m.get("digest") or "")[:12],
             "tamanho_gb": round(m.get("size", 0) / 1024**3, 2)}
            for m in dados.get("models", [])
        ]
    except Exception:
        return []


@dataclass
class Ambiente:
    """Procedência de uma rodada. É o que torna duas rodadas confrontáveis."""

    maquina: str
    sistema: str
    processador: str
    nucleos: int | None
    ram_total_gb: float | None
    ram_livre_gb: float | None
    gpu: str | None
    vram: str | None
    python: str
    data_utc: str
    modelos: list[dict] = field(default_factory=list)

    @classmethod
    def levantar(cls) -> Ambiente:
        total, livre = _ram()
        gpu, vram = _gpu()
        return cls(
            maquina=identificador_de_maquina(),
            sistema=f"{platform.system()} {platform.release()}",
            processador=_processador(),
            nucleos=_nucleos(),
            ram_total_gb=total,
            ram_livre_gb=livre,
            gpu=gpu,
            vram=vram,
            python=platform.python_version(),
            data_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            modelos=modelos_disponiveis(),
        )


@dataclass
class Execucao:
    """O resultado de uma estratégia sobre um documento."""

    estrategia: str
    parametros: dict[str, Any] = field(default_factory=dict)
    paginas: int = 0
    registros: int = 0
    campos: int = 0
    campos_preenchidos: int = 0
    segundos: float = 0.0
    erro: str | None = None
    dados: list[dict] = field(default_factory=list, repr=False)

    @property
    def cobertura(self) -> float:
        return self.campos_preenchidos / self.campos if self.campos else 0.0

    @property
    def segundos_por_pagina(self) -> float:
        return self.segundos / self.paginas if self.paginas else 0.0

    def resumo(self) -> dict:
        """Versão sem os dados brutos, para a tabela comparativa."""
        d = asdict(self)
        d.pop("dados", None)
        d["cobertura"] = round(self.cobertura, 4)
        d["segundos_por_pagina"] = round(self.segundos_por_pagina, 2)
        return d


class Experimento:
    """Executa estratégias e grava tudo em disco, com procedência."""

    def __init__(
        self, documento: str, destino: str | Path, ambiente: Ambiente | None = None
    ) -> None:
        self.documento = documento
        self.destino = Path(destino)
        self.ambiente = ambiente or Ambiente.levantar()
        self.execucoes: list[Execucao] = []

    def rodar(
        self,
        nome: str,
        fonte: FonteDocumento,
        extrator: Extrator,
        *,
        parametros: dict[str, Any] | None = None,
    ) -> Execucao:
        """Executa uma estratégia e registra o resultado.

        Uma estratégia que falhe **não interrompe** o experimento: a falha é
        registrada como resultado. "O modelo não conseguiu processar esta página
        no tempo disponível" é um achado, não um erro de execução a esconder.
        """
        execucao = Execucao(estrategia=nome, parametros=parametros or {})
        inicio = time.perf_counter()
        try:
            resultado = Pipeline(fonte, extrator, []).executar(self.documento)
            execucao.paginas = resultado.paginas
            execucao.registros = resultado.registros
            execucao.segundos = resultado.segundos
            execucao.campos = sum(len(r.campos) for r in resultado.extraidos)
            execucao.campos_preenchidos = sum(
                1 for r in resultado.extraidos for c in r.campos.values() if c.preenchido
            )
            execucao.dados = [r.model_dump(mode="json") for r in resultado.extraidos]
        except Exception as erro:  # noqa: BLE001 - a falha é dado do experimento
            execucao.segundos = time.perf_counter() - inicio
            execucao.erro = f"{type(erro).__name__}: {erro}"

        self.execucoes.append(execucao)
        return execucao

    def gravar(self) -> Path:
        """Grava ambiente, resumo e dados brutos.

        Os dados brutos vão em arquivo separado por estratégia: são grandes, e
        separá-los mantém o resumo legível e diffável.
        """
        pasta = self.destino / self.ambiente.maquina
        pasta.mkdir(parents=True, exist_ok=True)

        (pasta / "ambiente.json").write_text(
            json.dumps(asdict(self.ambiente), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resumo = {
            "documento": Path(self.documento).name,
            "maquina": self.ambiente.maquina,
            "data_utc": self.ambiente.data_utc,
            "execucoes": [e.resumo() for e in self.execucoes],
        }
        (pasta / "resumo.json").write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        brutos = pasta / "brutos"
        brutos.mkdir(exist_ok=True)
        for execucao in self.execucoes:
            if execucao.dados:
                nome = re.sub(r"[^a-z0-9]+", "-", execucao.estrategia.lower()).strip("-")
                (brutos / f"{nome}.json").write_text(
                    json.dumps(execucao.dados, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        return pasta

    def tabela(self) -> str:
        """Tabela comparativa em texto, para leitura imediata."""
        cabecalho = (
            f"{'estratégia':22s} {'registros':>10s} {'campos':>8s} "
            f"{'cobertura':>10s} {'tempo':>10s} {'s/página':>10s}"
        )
        linhas = [cabecalho, "-" * len(cabecalho)]
        for e in self.execucoes:
            if e.erro:
                linhas.append(f"{e.estrategia:22s} {'FALHOU':>10s}  {e.erro[:44]}")
                continue
            linhas.append(
                f"{e.estrategia:22s} {e.registros:10d} {e.campos:8d} "
                f"{e.cobertura:9.0%} {e.segundos:9.1f}s {e.segundos_por_pagina:9.1f}s"
            )
        return "\n".join(linhas)
