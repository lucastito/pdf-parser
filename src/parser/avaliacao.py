"""Comparação de extratores contra um gabarito conferido à mão.

Mede **por campo**, não só no agregado: uma taxa global alta esconde um campo
sistematicamente errado, que é justamente o modo de falha que mais custa caro a
jusante. Cada campo do gabarito produz um veredito próprio, e o agregado é
derivado deles — nunca o contrário.

Números numéricos são comparados com tolerância relativa: `"42"` e `"42.0"` são
o mesmo valor, e tratá-los como divergentes produziria um relatório que grita
sem motivo. Sentinelas e texto são comparados por igualdade exata, porque ali
qualquer diferença é diferença de verdade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from parser.modelo import Campo, Registro, Sentinela

__all__ = ["Comparacao", "ResultadoCampo", "ResultadoExtrator", "Veredito", "avaliar"]


class Veredito(StrEnum):
    ACERTO = "acerto"
    ERRO = "erro"
    FALTOU = "faltou"
    """O gabarito afirma um valor que o extrator não produziu."""

    SOBROU = "sobrou"
    """O extrator produziu um valor que o gabarito diz não existir."""


@dataclass(frozen=True)
class ResultadoCampo:
    campo: str
    veredito: Veredito
    esperado: object = None
    obtido: object = None


@dataclass
class Comparacao:
    """Resultado da comparação de um registro contra seu gabarito."""

    identificador: str
    resultados: list[ResultadoCampo] = field(default_factory=list)

    @property
    def acertos(self) -> int:
        return sum(1 for r in self.resultados if r.veredito is Veredito.ACERTO)

    @property
    def acuracia(self) -> float:
        return self.acertos / len(self.resultados) if self.resultados else 0.0


@dataclass
class ResultadoExtrator:
    """Agregado de um extrator sobre todo o golden set."""

    extrator: str
    comparacoes: list[Comparacao] = field(default_factory=list)
    segundos: float = 0.0

    @property
    def acuracia(self) -> float:
        total = sum(len(c.resultados) for c in self.comparacoes)
        if not total:
            return 0.0
        return sum(c.acertos for c in self.comparacoes) / total

    def por_campo(self) -> dict[str, float]:
        """Acurácia de cada campo isoladamente.

        É esta visão — não a agregada — que revela um campo sistematicamente
        errado escondido atrás de uma média alta.
        """
        acertos: dict[str, int] = {}
        totais: dict[str, int] = {}
        for comparacao in self.comparacoes:
            for resultado in comparacao.resultados:
                totais[resultado.campo] = totais.get(resultado.campo, 0) + 1
                if resultado.veredito is Veredito.ACERTO:
                    acertos[resultado.campo] = acertos.get(resultado.campo, 0) + 1
        return {campo: acertos.get(campo, 0) / n for campo, n in totais.items()}

    def piores_campos(self, limite: int = 5) -> list[tuple[str, float]]:
        return sorted(self.por_campo().items(), key=lambda item: item[1])[:limite]


def avaliar(
    extrator: str,
    obtidos: dict[str, Registro],
    gabarito: dict[str, dict[str, object]],
    *,
    tolerancia: float = 0.01,
    segundos: float = 0.0,
) -> ResultadoExtrator:
    """Compara os registros de um extrator contra o gabarito.

    Args:
        obtidos: registros produzidos, indexados pelo identificador do item.
        gabarito: valores corretos, na mesma indexação. Um valor ``None``
            significa "este campo deve estar ausente" — o que permite penalizar
            um extrator que inventa dado.
        tolerancia: erro relativo aceito em comparação numérica.
    """
    comparacoes = []
    for identificador, esperados in gabarito.items():
        registro = obtidos.get(identificador)
        resultados = [
            _comparar(
                campo, esperado, registro.campos.get(campo) if registro else None, tolerancia
            )
            for campo, esperado in esperados.items()
        ]
        comparacoes.append(Comparacao(identificador=identificador, resultados=resultados))

    return ResultadoExtrator(extrator=extrator, comparacoes=comparacoes, segundos=segundos)


def _comparar(
    nome: str, esperado: object, campo: Campo | None, tolerancia: float
) -> ResultadoCampo:
    obtido = _valor_de(campo)

    if esperado is None:
        veredito = Veredito.ACERTO if obtido is None else Veredito.SOBROU
        return ResultadoCampo(nome, veredito, esperado, obtido)

    if obtido is None:
        return ResultadoCampo(nome, Veredito.FALTOU, esperado, None)

    igual = _equivalentes(esperado, obtido, tolerancia)
    return ResultadoCampo(nome, Veredito.ACERTO if igual else Veredito.ERRO, esperado, obtido)


def _valor_de(campo: Campo | None) -> object:
    if campo is None or not campo.preenchido:
        return None
    if campo.sentinela is not None:
        return campo.sentinela.value
    return campo.valor


_CANONICAS = frozenset(s.value for s in Sentinela)
"""Nomes canônicos das sentinelas, para reconhecer o que o extrator devolve."""


def _sentinela_de(valor: object) -> str | None:
    """O nome canônico da sentinela, se o texto for uma.

    O gabarito escreve a sentinela como ela aparece **no documento** (`Tr`, `NA`,
    `*`); o extrator devolve o nome canônico do modelo (`traco`,
    `nao_analisado`). São o mesmo valor, e compará-los como texto os tratava como
    erro — penalizando extração perfeita por diferença de grafia, justamente nos
    campos que mais têm sentinela.

    A tabela vem da normalização, e não é reescrita aqui: duas listas de
    sentinelas divergiriam, e a divergência apareceria como erro de extração.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None

    from parser.normalizacao import _SENTINELAS

    sentinela = _SENTINELAS.get(texto.casefold())
    if sentinela is not None:
        return sentinela.value
    # Já pode vir no formato canônico, vindo do extrator.
    return texto.casefold() if texto.casefold() in _CANONICAS else None


def _equivalentes(esperado: object, obtido: object, tolerancia: float) -> bool:
    esperado_num = _como_numero(esperado)
    obtido_num = _como_numero(obtido)

    if esperado_num is not None and obtido_num is not None:
        if esperado_num == 0:
            return abs(obtido_num) <= tolerancia
        return abs(esperado_num - obtido_num) / abs(esperado_num) <= tolerancia

    # Sentinelas se comparam pelo que **afirmam**, não pela grafia. Mas uma
    # sentinela nunca equivale a outra: `Tr` diz "quantidade desprezível" e `NA`
    # diz "não sabemos" (ADR-0004). Nem equivale a número: `Tr` não é zero.
    sentinela_esperada = _sentinela_de(esperado)
    sentinela_obtida = _sentinela_de(obtido)
    if sentinela_esperada is not None or sentinela_obtida is not None:
        return sentinela_esperada is not None and sentinela_esperada == sentinela_obtida

    return str(esperado).strip().casefold() == str(obtido).strip().casefold()


def _como_numero(valor: object) -> float | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        try:
            return float(valor.replace(",", "."))
        except ValueError:
            return None
    return None
