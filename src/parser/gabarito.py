"""Carrega o gabarito conferido à mão e mede acurácia contra ele.

O gabarito é a única fonte que responde *quem acertou mais*. Cobertura, volume e
concordância entre estratégias são sinais úteis, mas nenhum deles distingue um
extrator que lê certo de um que preenche tudo errado com convicção.

Uma limitação precisa acompanhar qualquer número produzido aqui: se o gabarito foi
gerado por uma das estratégias e apenas confirmado, a acurácia **dessa** estratégia
é tautológica — ela acerta por construção. As demais têm medição legítima. O
relatório declara isso; esconder seria vender rigor que não existe.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parser.avaliacao import ResultadoExtrator, avaliar
from parser.modelo import Registro

__all__ = ["Gabarito", "GabaritoInvalido", "medir_acuracia"]

MACROS = ["energia_kcal", "proteina_g", "lipideos_g", "carboidrato_g", "fibra_g"]

MARCAS_DE_CONFERIDO = {"ok", "x", "sim", "v", "true"}
"""Marcações que significam "confere". Qualquer outro texto é o valor corrigido."""


class GabaritoInvalido(ValueError):
    """O arquivo não descreve um gabarito utilizável."""


@dataclass
class Gabarito:
    """Valores corretos, indexados pelo identificador do item."""

    caminho: Path
    itens: dict[str, dict[str, Any]] = field(default_factory=dict)
    campos: list[str] = field(default_factory=list)
    conferidos: int = 0
    total: int = 0
    correcoes: int = 0
    gerado_por: str | None = None
    """Estratégia que gerou o material conferido, se conhecida.

    Marca a tautologia: a acurácia desta estratégia não é medição independente.
    """

    @property
    def completo(self) -> bool:
        return self.total > 0 and self.conferidos == self.total

    @classmethod
    def de_arquivo(
        cls, caminho: str | Path, *, campos: list[str] | None = None, gerado_por: str | None = None
    ) -> Gabarito:
        """Lê o gabarito de um CSV.

        Aceita o formato de conferência (colunas `campo` + `campo_ok`) e o formato
        simples (só `campo`). No primeiro, uma marcação diferente de "ok" é lida
        como **o valor correto** — o revisor escreveu a correção ali.

        `utf-8-sig` porque planilhas costumam gravar BOM, e o BOM entraria no nome
        da primeira coluna.
        """
        arquivo = Path(caminho)
        if not arquivo.exists():
            raise GabaritoInvalido(f"gabarito não encontrado: {arquivo}")

        with arquivo.open(encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f))

        if not linhas:
            raise GabaritoInvalido(f"gabarito vazio: {arquivo}")

        colunas = set(linhas[0])
        if "numero" not in colunas or "descricao" not in colunas:
            raise GabaritoInvalido(
                f"gabarito {arquivo.name} precisa das colunas 'numero' e 'descricao'"
            )

        alvos = campos or [c for c in MACROS if c in colunas]
        if not alvos:
            raise GabaritoInvalido(f"gabarito {arquivo.name} não tem nenhum campo de valor")

        gabarito = cls(caminho=arquivo, campos=alvos, gerado_por=gerado_por)

        for linha in linhas:
            chave = _identificador(linha)
            valores: dict[str, Any] = {}
            for campo in alvos:
                bruto = (linha.get(campo) or "").strip()
                marca = (linha.get(f"{campo}_ok") or "").strip()

                if f"{campo}_ok" in colunas:
                    gabarito.total += 1
                    if marca:
                        gabarito.conferidos += 1
                        if marca.casefold() not in MARCAS_DE_CONFERIDO:
                            # O revisor escreveu o valor correto no lugar da marca.
                            bruto = marca
                            gabarito.correcoes += 1
                elif bruto:
                    gabarito.total += 1
                    gabarito.conferidos += 1

                valores[campo] = bruto or None
            gabarito.itens[chave] = valores

        return gabarito

    def medir(self, registros: list[Registro], *, tolerancia: float = 0.01) -> ResultadoExtrator:
        """Compara os registros de uma estratégia com o gabarito."""
        return medir_acuracia("", registros, self, tolerancia=tolerancia)


def _identificador(linha: dict) -> str:
    """`"1 Arroz, integral, cozido"` — mesmo formato que o extrator produz."""
    return f"{(linha.get('numero') or '').strip()} {(linha.get('descricao') or '').strip()}".strip()


def _indexar(registros: list[Registro]) -> dict[str, Registro]:
    indice = {}
    for registro in registros:
        campo = registro.campos.get("identificador")
        if campo and campo.valor:
            indice[str(campo.valor).strip()] = registro
    return indice


def medir_acuracia(
    estrategia: str,
    registros: list[Registro],
    gabarito: Gabarito,
    *,
    tolerancia: float = 0.01,
) -> ResultadoExtrator:
    """Mede a acurácia de uma estratégia contra o gabarito.

    O alinhamento é pelo identificador do item. Um item do gabarito ausente nos
    registros conta como campo faltante — o que é correto: o extrator deveria
    tê-lo encontrado.
    """
    obtidos = _indexar(registros)
    esperados = {
        chave: {campo: valor for campo, valor in valores.items()}
        for chave, valores in gabarito.itens.items()
    }
    return avaliar(estrategia, obtidos, esperados, tolerancia=tolerancia)
