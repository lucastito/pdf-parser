"""Destino CSV — formato achatado, para consumo por planilha.

O CSV não tem tipos: tudo é texto. Isso cria o risco central deste módulo — se
`Tr`, `0` e "campo ausente" virarem a mesma célula vazia, a distinção que o
modelo preserva com cuidado morre na última etapa do pipeline.

A convenção adotada é explícita:

===============  =========================================
Situação         Célula
===============  =========================================
valor numérico   o número (`124.0`, `0.0`)
sentinela        o nome da sentinela (`traco`, `nao_analisado`)
campo ausente    vazio
===============  =========================================

Um zero legítimo aparece como `0.0` e nunca como vazio; uma sentinela aparece
nomeada e nunca como `0`. A proveniência completa não cabe aqui — quem precisa
dela usa o destino JSON.
"""

from __future__ import annotations

import csv
from pathlib import Path

from parser.modelo import Registro

__all__ = ["DestinoCSV"]


class DestinoCSV:
    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)

    def gravar(self, registros: list[Registro]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)

        if not registros:
            self.caminho.write_text("", encoding="utf-8")
            return

        colunas = list(registros[0].campos)
        with self.caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=colunas)
            escritor.writeheader()
            for registro in registros:
                escritor.writerow({nome: _celula(registro, nome) for nome in colunas})


def _celula(registro: Registro, nome: str) -> str:
    campo = registro.campos.get(nome)
    if campo is None or not campo.preenchido:
        return ""
    if campo.sentinela is not None:
        return campo.sentinela.value
    return "" if campo.valor is None else str(campo.valor)
