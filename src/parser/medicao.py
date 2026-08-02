"""Arnês de medição: o que faz um número medido ser confiável.

Este módulo existe por causa de uma falha concreta. Duas medições foram deixadas
rodando ao mesmo tempo, na mesma máquina. Elas disputaram o mesmo processador, cada
uma inflou o tempo da outra, e **nada no resultado denunciava isso**. Quem lesse os
segundos depois não teria como saber que eram lixo.

O projeto inteiro se apoia em comparar tempos (ADR-0005). Uma medição que não pode
ser confrontada com outra não vale o custo de tê-la feito — e, pior, uma medição
contaminada que *parece* válida leva a conclusão errada.

Três garantias, cada uma respondendo a um jeito de perder a comparabilidade:

**Exclusão mútua.** Duas medições não rodam ao mesmo tempo na mesma máquina. A
segunda falha alto, em vez de contaminar as duas em silêncio.

**Procedência junto do número.** Máquina, parâmetros e data saem no mesmo arquivo
do resultado. Número sem contexto é inútil semanas depois, e a tentação de comparar
duas rodadas com parâmetros diferentes é grande justamente quando não se lembra
mais quais eram.

**Condição declarada.** A memória livre no início vai gravada. Tempo medido com a
máquina ocupada não é comparável com tempo medido em máquina ociosa, e essa
diferença precisa ser visível a quem lê.

O que este módulo **não** faz: julgar se um número é bom. Ele só garante que o
número seja interpretável.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "Medicao",
    "MedicaoEmAndamento",
    "travar",
]

NOME_DA_TRAVA = ".medicao-em-andamento"


class MedicaoEmAndamento(RuntimeError):
    """Já existe uma medição rodando nesta máquina.

    Levantada em vez de esperar ou seguir: esperar esconderia a disputa por
    processador dentro do tempo medido, e seguir contaminaria as duas rodadas.
    """


def _processo_vive(pid: Any) -> bool:
    """O dono da trava ainda está rodando?

    Sem esta pergunta, uma medição interrompida deixava a máquina bloqueada para
    sempre — o processo morria, o arquivo ficava, e a execução seguinte era
    recusada. O PID já era gravado; só nunca era conferido.

    **Na dúvida, responde que vive.** Se não dá para saber, o certo é manter a
    trava: recusar uma medição custa um aviso, e atropelar outra em curso custa
    as duas.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False

    try:
        # Sinal 0 não envia nada — só verifica se o processo existe e é
        # acessível.
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Existe, e é de outro usuário. Vive.
        return True
    except OSError as erro:
        # No Windows, PID inexistente não vira ProcessLookupError: vem um
        # OSError com "parâmetro incorreto" (winerror 87). Medido — sem este
        # caso, toda trava órfã continuava bloqueando.
        if getattr(erro, "winerror", None) == 87:
            return False
        return True
    return True


@contextmanager
def travar(caminho: str | Path, *, descricao: str = "") -> Iterator[Path]:
    """Impede que duas medições rodem ao mesmo tempo.

    Args:
        caminho: arquivo de trava. Criado ao entrar, removido ao sair.
        descricao: o que está sendo medido. Aparece na mensagem de erro de quem
            tentar rodar em paralelo — sem isso a pessoa sabe que está bloqueada
            e não sabe pelo quê.

    Levanta:
        MedicaoEmAndamento: se a trava já existir.
    """
    trava = Path(caminho)
    trava.parent.mkdir(parents=True, exist_ok=True)

    if trava.exists():
        try:
            dono = json.loads(trava.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            dono = {}

        if _processo_vive(dono.get("pid")):
            raise MedicaoEmAndamento(
                f"já há uma medição em andamento nesta máquina: "
                f"{dono.get('descricao') or 'sem descrição'} "
                f"(iniciada em {dono.get('quando', '?')}, processo {dono.get('pid', '?')}).\n"
                f"Rodar duas ao mesmo tempo infla o tempo das duas e invalida a "
                f"comparação. Espere terminar, ou apague {trava} se souber que a "
                f"anterior morreu."
            )
        # Trava órfã: o dono morreu sem liberar. Aconteceu duas vezes ao
        # interromper uma bateria — o processo pai morria, o filho ficava
        # segurando o arquivo, e a execução seguinte era recusada. Na máquina de
        # outra pessoa isso é pior: ela não sabe que arquivo apagar.
        trava.unlink(missing_ok=True)

    trava.write_text(
        json.dumps(
            {
                "descricao": descricao,
                "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "pid": os.getpid(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    try:
        yield trava
    finally:
        # Remove mesmo se a medição falhar: trava órfã deixaria a máquina
        # bloqueada para sempre, e a pessoa seguinte não saberia por quê.
        trava.unlink(missing_ok=True)


@dataclass
class Medicao:
    """Uma rodada de medição, com procedência e exclusão mútua.

    Uso::

        medicao = Medicao(nome="degraus-visao", raiz=Path("resultados"),
                          parametros={"modelo": "m:4b", "dpi": 150})
        with medicao:
            medicao.registrar("esquema-completo", {"segundos": 77.4, "tokens": 152})

    O arquivo é gravado ao sair do bloco, **inclusive quando a medição falha no
    meio** — o que já foi medido não se perde por causa do que faltou, e a rodada
    fica marcada como interrompida.
    """

    nome: str
    raiz: Path
    parametros: dict[str, Any] = field(default_factory=dict)
    casos: list[dict[str, Any]] = field(default_factory=list)
    interrompida: bool = False
    amostrar_cpu: bool = False
    """Amostra a carga de processador por meio segundo antes de começar.

    Desligado por padrão porque custa meio segundo por rodada — desprezível numa
    medição de minutos, mas somado em centenas de testes deixaria a suíte lenta, e
    suíte lenta deixa de ser rodada. **Ligue numa medição de verdade:** saber que a
    máquina estava com 90% de carga é o que distingue um número comparável de um
    número inútil.
    """

    _inicio: float = field(default=0.0, repr=False)
    _trava: Any = field(default=None, repr=False)

    def __enter__(self) -> Medicao:
        self.raiz = Path(self.raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self._trava = travar(self.raiz / NOME_DA_TRAVA, descricao=self.nome)
        self._trava.__enter__()
        self._inicio = time.perf_counter()
        self._condicao = _condicao_da_maquina(amostrar_cpu=self.amostrar_cpu)
        return self

    def __exit__(self, tipo, valor, tb) -> bool:
        self.interrompida = tipo is not None
        try:
            self._gravar()
        finally:
            self._trava.__exit__(None, None, None)
        return False  # nunca engole a exceção: a falha é resultado

    def registrar(self, nome: str, dados: dict[str, Any]) -> None:
        """Anota um caso medido. `dados` é livre — cada medição mede o que precisa."""
        self.casos.append({"nome": nome, **dados})

    def _gravar(self) -> None:
        from parser.procedencia import Ambiente

        # Sem consultar o servidor: o modelo usado já vai em `parametros`, e o
        # inventário do servidor não descreve *esta* rodada. A consulta custaria
        # segundos e, com o servidor fora do ar, uma espera inútil.
        ambiente = Ambiente.levantar(consultar_modelos=False)
        conteudo = {
            "nome": self.nome,
            "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "segundos_totais": round(time.perf_counter() - self._inicio, 1),
            "interrompida": self.interrompida,
            "parametros": self.parametros,
            "condicao": self._condicao,
            "ambiente": {
                "maquina": ambiente.maquina,
                "sistema": ambiente.sistema,
                "processador": ambiente.processador,
                "nucleos": ambiente.nucleos,
                "ram_total_gb": ambiente.ram_total_gb,
                "gpu": ambiente.gpu,
                "python": ambiente.python,
            },
            "casos": self.casos,
        }

        destino = self.raiz / f"{self.nome}.json"
        # Rodada anterior é preservada com sufixo de data: sobrescrever apagaria a
        # evidência de que o resultado mudou — que é exatamente o que se quer ver.
        if destino.exists():
            carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            destino.replace(self.raiz / f"{self.nome}.{carimbo}.json")

        destino.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _condicao_da_maquina(*, amostrar_cpu: bool = False) -> dict[str, Any]:
    """Estado da máquina no início da rodada.

    Serve para responder, depois, à pergunta "esta medição é comparável com
    aquela?" — se uma rodou com a memória cheia e outra não, os tempos não são.
    """
    condicao: dict[str, Any] = {"ram_livre_gb": None}
    try:
        import psutil  # type: ignore

        condicao["ram_livre_gb"] = round(psutil.virtual_memory().available / 1024**3, 1)
        # Com `interval`, a leitura é confiável mas custa meio segundo; sem ele é
        # instantânea e relativa à chamada anterior. Ver `Medicao.amostrar_cpu`.
        condicao["carga_cpu_pct"] = psutil.cpu_percent(interval=0.5 if amostrar_cpu else None)
    except Exception:  # noqa: BLE001 — ausência de psutil não impede medir
        pass
    return condicao
