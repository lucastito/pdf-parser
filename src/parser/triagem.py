"""Classificação de páginas por tipo de conteúdo.

Um documento real não é uniforme: tem capa, sumário, metodologia, tabelas
auxiliares e as páginas de dados propriamente ditas. Tratar tudo igual
desperdiça o que é aproveitável e polui o que é estruturado.

A regra que orienta este módulo: **descartar não é ignorar**. Toda página
recebe uma classe e um motivo, inclusive as descartáveis, de forma que a
contagem final feche com o total. Uma página que some sem registro é um erro
que só aparece quando alguém nota a informação faltando muito depois.

A classificação é heurística e determinística — por densidade numérica e volume
de texto. É deliberadamente simples: serve de **baseline** para a comparação
contra uma triagem feita por modelo, que é uma decisão semântica ("esta página
fala sobre o quê?") e pode muito bem se sair melhor. Essa é uma hipótese a
medir, não uma conclusão a assumir.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from parser.portas import DocumentoCanonico, Pagina

__all__ = ["Classe", "ResultadoTriagem", "Triagem", "triar"]

PALAVRAS_MINIMAS = 20
"""Abaixo disto a página não carrega conteúdo aproveitável (capa, folha de rosto)."""

PROPORCAO_NUMERICA_MINIMA = 0.45
"""A partir desta fração de tokens numéricos a página é tratada como tabela."""


class Classe(StrEnum):
    DADOS = "dados"
    """Tabela: vai para o extrator estruturado."""

    CONTEXTO = "contexto"
    """Texto aproveitável — metodologia, glossário, tabelas auxiliares."""

    DESCARTAVEL = "descartavel"
    """Sem conteúdo útil. Registrado mesmo assim."""


@dataclass(frozen=True)
class ResultadoTriagem:
    """A decisão sobre uma página, com o que a fundamentou.

    As métricas ficam junto do veredito de propósito: sem elas seria impossível
    auditar por que uma página foi para uma rota e não para outra, ou ajustar os
    limiares com base em evidência.
    """

    pagina: int
    classe: Classe
    motivo: str
    total_palavras: int
    proporcao_numerica: float


def triar(
    pagina: Pagina,
    *,
    palavras_minimas: int = PALAVRAS_MINIMAS,
    proporcao_numerica_minima: float = PROPORCAO_NUMERICA_MINIMA,
) -> ResultadoTriagem:
    """Classifica uma página pelo perfil do seu conteúdo."""
    if palavras_minimas < 0:
        raise ValueError(f"palavras_minimas não pode ser negativo: {palavras_minimas}")

    total = len(pagina.palavras)
    numericas = sum(1 for p in pagina.palavras if any(c.isdigit() for c in p.texto))
    proporcao = numericas / total if total else 0.0

    if total < palavras_minimas:
        classe = Classe.DESCARTAVEL
        motivo = f"apenas {total} palavras (mínimo {palavras_minimas})"
    elif proporcao >= proporcao_numerica_minima:
        classe = Classe.DADOS
        motivo = f"{proporcao:.0%} de tokens numéricos em {total} palavras"
    else:
        classe = Classe.CONTEXTO
        motivo = f"texto predominante ({proporcao:.0%} numérico em {total} palavras)"

    return ResultadoTriagem(
        pagina=pagina.numero,
        classe=classe,
        motivo=motivo,
        total_palavras=total,
        proporcao_numerica=proporcao,
    )


@dataclass
class Triagem:
    """Resultado da triagem de um documento inteiro."""

    documento: DocumentoCanonico
    resultados: list[ResultadoTriagem]

    @classmethod
    def do_documento(cls, documento: DocumentoCanonico, **limiares) -> Triagem:
        return cls(
            documento=documento,
            resultados=[triar(p, **limiares) for p in documento.paginas],
        )

    def paginas_de(self, classe: Classe) -> list[Pagina]:
        numeros = {r.pagina for r in self.resultados if r.classe is classe}
        return [p for p in self.documento.paginas if p.numero in numeros]

    def resumo(self) -> dict[Classe, int]:
        """Contagem por classe.

        A soma tem de bater com o total de páginas: é a verificação de que
        nenhuma sumiu pelo caminho.
        """
        contagem = Counter(r.classe for r in self.resultados)
        return {classe: contagem.get(classe, 0) for classe in Classe}

    def descartadas(self) -> list[ResultadoTriagem]:
        """As páginas descartadas, com o motivo — para auditoria."""
        return [r for r in self.resultados if r.classe is Classe.DESCARTAVEL]
