"""Modelo de dados do núcleo: proveniência, sentinelas e registros validados.

Independe de formato de entrada, de domínio e de destino. Um valor extraído nunca
viaja sozinho: carrega como foi obtido e de onde veio.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class Origem(StrEnum):
    """Como o valor de um campo foi obtido.

    A distinção existe para separar o que o documento afirma do que o sistema
    supôs. Sem ela não há como medir extração contra inferência.
    """

    EXTRAIDO = "extraido"
    """Lido diretamente do documento."""

    DERIVADO = "derivado"
    """Calculado a partir de campos extraídos (ex.: conversão de unidade)."""

    INFERIDO = "inferido"
    """Estimado por modelo, sem respaldo direto no documento."""

    AUSENTE = "ausente"
    """Não encontrado. Nada foi inventado para preencher."""


class Sentinela(StrEnum):
    """Marcadores que documentos usam no lugar de um número.

    Não são zero e não são nulo: `TRACO` afirma "presente em quantidade
    desprezível", enquanto `NAO_ANALISADO` afirma "não sabemos". Colapsar os dois
    em ``None`` — ou pior, em ``0`` — corrompe qualquer cálculo a jusante.
    """

    TRACO = "traco"
    NAO_ANALISADO = "nao_analisado"
    NAO_APLICAVEL = "nao_aplicavel"


class Evidencia(BaseModel):
    """Onde, no documento de origem, o valor foi encontrado."""

    model_config = ConfigDict(frozen=True)

    pagina: int | None = Field(default=None, ge=1)
    bbox: tuple[float, float, float, float] | None = None
    texto_bruto: str | None = None
    """Texto exatamente como aparecia, antes de qualquer normalização."""

    vizinhanca: str | None = None
    """Texto ao redor, para desambiguar o que o valor isolado não resolve.

    Um `"1,5"` sozinho não diz se é grama, porcentagem ou índice; a vizinhança
    preserva a pista que a normalização descartou. Serve à auditoria humana e,
    quando um extrator baseado em modelo entrar na comparação, é o contexto que
    ele precisa receber para julgar em vez de adivinhar.
    """


class Campo(BaseModel, Generic[T]):
    """Um valor com sua procedência.

    Invariantes (garantidas na validação, não por convenção):

    - ``AUSENTE`` implica ``valor is None`` e ``confianca == 0``.
    - Valor presente implica origem diferente de ``AUSENTE``.
    - ``sentinela`` e ``valor`` são mutuamente exclusivos.
    - ``EXTRAIDO`` e ``DERIVADO`` exigem evidência: sem ela não há auditoria.
    """

    model_config = ConfigDict(frozen=True)

    valor: T | None = None
    sentinela: Sentinela | None = None
    origem: Origem
    confianca: float = Field(default=1.0, ge=0.0, le=1.0)
    evidencia: Evidencia | None = None

    @model_validator(mode="after")
    def _coerencia(self) -> Campo[T]:
        if self.valor is not None and self.sentinela is not None:
            raise ValueError(
                "campo não pode ter valor e sentinela ao mesmo tempo: "
                f"valor={self.valor!r}, sentinela={self.sentinela!r}"
            )

        if self.origem is Origem.AUSENTE:
            if self.valor is not None:
                raise ValueError("campo AUSENTE não pode carregar valor")
            if self.confianca != 0.0:
                raise ValueError("campo AUSENTE deve ter confianca 0.0")
        elif self.valor is None and self.sentinela is None:
            raise ValueError(
                f"campo sem valor nem sentinela deve ter origem AUSENTE, não {self.origem}"
            )

        if self.origem in (Origem.EXTRAIDO, Origem.DERIVADO) and self.evidencia is None:
            raise ValueError(f"origem {self.origem} exige evidencia para auditoria")

        return self

    @property
    def preenchido(self) -> bool:
        """Verdadeiro se o campo afirma algo — inclusive uma sentinela."""
        return self.origem is not Origem.AUSENTE

    @classmethod
    def ausente(cls) -> Campo[T]:
        return cls(origem=Origem.AUSENTE, confianca=0.0)

    @classmethod
    def extraido(
        cls,
        valor: T | None = None,
        *,
        evidencia: Evidencia,
        sentinela: Sentinela | None = None,
        confianca: float = 1.0,
    ) -> Campo[T]:
        return cls(
            valor=valor,
            sentinela=sentinela,
            origem=Origem.EXTRAIDO,
            confianca=confianca,
            evidencia=evidencia,
        )


class Registro(BaseModel):
    """Um item extraído, com seus campos e a proveniência de cada um.

    O núcleo não conhece os nomes dos campos: o schema é parâmetro de quem usa.
    """

    model_config = ConfigDict(frozen=True)

    campos: dict[str, Campo[Any]]
    fonte: str
    """Identificador do documento de origem."""

    @property
    def taxa_inferencia(self) -> float:
        """Proporção de campos preenchidos que não foram extraídos diretamente.

        Mede quanto do registro o sistema supôs. Campos ausentes ficam fora do
        cálculo: eles não afirmam nada, e incluí-los faria um registro vazio
        parecer bem-fundamentado.
        """
        preenchidos = [c for c in self.campos.values() if c.preenchido]
        if not preenchidos:
            return 0.0
        nao_extraidos = sum(1 for c in preenchidos if c.origem is not Origem.EXTRAIDO)
        return nao_extraidos / len(preenchidos)

    @property
    def cobertura(self) -> float:
        """Proporção de campos que afirmam algo."""
        if not self.campos:
            return 0.0
        return sum(1 for c in self.campos.values() if c.preenchido) / len(self.campos)
