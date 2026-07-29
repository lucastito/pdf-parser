"""Orquestração: fonte → extrator → destinos.

Mantido deliberadamente magro. Toda variação — formato de entrada, estratégia de
extração, destino — vive nos adapters; o pipeline apenas os conecta e mede.

A medição não é acessório: sem tempo e contagem por execução, comparar
estratégias exigiria instrumentar cada uma separadamente, e o resultado
dependeria de quem instrumentou.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from parser.modelo import Registro
from parser.portas import Destino, DocumentoCanonico, Extrator, FonteDocumento
from parser.triagem import Classe, Triagem

__all__ = ["Pipeline", "Resultado"]


@dataclass
class Resultado:
    """O que aconteceu numa execução."""

    documento: str
    paginas: int
    registros: int
    segundos: float
    triagem: dict[Classe, int] | None = None
    extraidos: list[Registro] = field(default_factory=list, repr=False)

    @property
    def paginas_por_segundo(self) -> float:
        return self.paginas / self.segundos if self.segundos else 0.0

    def resumo(self) -> str:
        linhas = [
            f"documento : {self.documento}",
            f"páginas   : {self.paginas}",
            f"registros : {self.registros}",
            f"tempo     : {self.segundos:.2f}s ({self.paginas_por_segundo:.0f} pág/s)",
        ]
        if self.triagem:
            classes = "  ".join(
                f"{classe.value}={n}" for classe, n in self.triagem.items() if n
            )
            linhas.append(f"triagem   : {classes}")
        return "\n".join(linhas)


class Pipeline:
    """Conecta as três portas e mede a execução."""

    def __init__(
        self,
        fonte: FonteDocumento,
        extrator: Extrator,
        destinos: list[Destino],
        *,
        triar_paginas: bool = False,
        apenas_dados: bool = False,
    ) -> None:
        """
        Args:
            triar_paginas: classifica cada página e reporta a distribuição.
            apenas_dados: restringe a extração às páginas classificadas como
                dados. Exige ``triar_paginas``. Reduz o custo em documentos
                longos com muita página de texto corrido.
        """
        if apenas_dados and not triar_paginas:
            raise ValueError("apenas_dados exige triar_paginas=True")

        self.fonte = fonte
        self.extrator = extrator
        self.destinos = destinos
        self.triar_paginas = triar_paginas
        self.apenas_dados = apenas_dados

    def executar(self, caminho: str) -> Resultado:
        inicio = time.perf_counter()

        documento = self.fonte.carregar(caminho)
        total_paginas = len(documento.paginas)

        resumo_triagem = None
        if self.triar_paginas:
            triagem = Triagem.do_documento(documento)
            resumo_triagem = triagem.resumo()
            if self.apenas_dados:
                documento = DocumentoCanonico(
                    identificador=documento.identificador,
                    paginas=triagem.paginas_de(Classe.DADOS),
                )

        registros = self.extrator.extrair(documento)
        for destino in self.destinos:
            destino.gravar(registros)

        return Resultado(
            documento=documento.identificador,
            paginas=total_paginas,
            registros=len(registros),
            segundos=time.perf_counter() - inicio,
            triagem=resumo_triagem,
            extraidos=registros,
        )
