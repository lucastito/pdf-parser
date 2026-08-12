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
    def __init__(self, caminho: str | Path, *, incluir_fonte: bool = False) -> None:
        """
        Args:
            incluir_fonte: acrescenta a coluna `_arquivo`, com `Registro.fonte`.
                Desligado por padrão — o formato original do destino é só os
                campos do registro; quem grava um lote de vários documentos e
                precisa rastrear a origem de cada linha liga isto.
        """
        self.caminho = Path(caminho)
        self.incluir_fonte = incluir_fonte

    def gravar(self, registros: list[Registro]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)

        if not registros:
            self.caminho.write_text("", encoding="utf-8")
            return

        # A união dos campos de **todos** os registros, na ordem em que aparecem.
        # Usar só o primeiro registro fazia um lote heterogêneo perder coluna sem
        # erro algum: o arquivo saía bem-formado e o dado não estava lá. Ordem de
        # aparição, e não alfabética, para que duas execuções iguais produzam
        # arquivos idênticos.
        colunas: list[str] = []
        for registro in registros:
            for nome in registro.campos:
                if nome not in colunas:
                    colunas.append(nome)

        campos_saida = ["_arquivo", *colunas] if self.incluir_fonte else colunas

        with self.caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=campos_saida)
            escritor.writeheader()
            for registro in registros:
                linha = {"_arquivo": registro.fonte} if self.incluir_fonte else {}
                linha.update({nome: _celula(registro, nome) for nome in colunas})
                escritor.writerow(linha)


def _celula(registro: Registro, nome: str) -> str:
    campo = registro.campos.get(nome)
    if campo is None or not campo.preenchido:
        return ""
    if campo.sentinela is not None:
        return campo.sentinela.value
    return "" if campo.valor is None else str(campo.valor)
