"""As três portas do núcleo e o formato canônico que trafega entre elas.

O núcleo conhece apenas estes contratos. Formato de entrada, estratégia de
extração e destino são implementações intercambiáveis — é isso que permite
comparar extratores sob condições idênticas.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from parser.modelo import Registro

__all__ = [
    "Destino",
    "DocumentoCanonico",
    "Extrator",
    "FonteDocumento",
    "FormatoNaoSuportado",
    "Pagina",
    "Palavra",
]


class FormatoNaoSuportado(NotImplementedError):
    """O formato é reconhecido mas não há implementação para ele.

    Existe para que um adapter ausente falhe alto. Devolver documento vazio
    faria o pipeline completar com sucesso aparente sem ter lido nada.
    """


class Palavra(BaseModel):
    """Uma palavra com sua posição na página.

    A posição não é metadado acessório: em documentos cuja tabela não tem linhas
    de grade, ela é a única informação que permite reconstruir a estrutura.
    """

    model_config = ConfigDict(frozen=True)

    texto: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def centro_y(self) -> float:
        return (self.y0 + self.y1) / 2


class Pagina(BaseModel):
    model_config = ConfigDict(frozen=True)

    numero: int = Field(ge=1)
    palavras: list[Palavra]

    @property
    def texto(self) -> str:
        """Concatenação simples, na ordem em que as palavras chegaram.

        Deliberadamente ingênua: preserva a ordem de leitura do documento sem
        tentar inferir estrutura. Quem precisa de estrutura usa as coordenadas.
        """
        return " ".join(p.texto for p in self.palavras)


class DocumentoCanonico(BaseModel):
    """Representação neutra de um documento, independente do formato de origem."""

    model_config = ConfigDict(frozen=True)

    identificador: str
    paginas: list[Pagina]


@runtime_checkable
class FonteDocumento(Protocol):
    """Lê um arquivo e devolve o formato canônico."""

    def carregar(self, caminho: str) -> DocumentoCanonico: ...


@runtime_checkable
class Extrator(Protocol):
    """Transforma documento canônico em registros validados.

    A porta que torna a comparação possível: determinístico, baseado em
    biblioteca e baseado em modelo são implementações desta mesma interface,
    medidas pela mesma régua sobre o mesmo golden set.
    """

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]: ...


@runtime_checkable
class Destino(Protocol):
    """Grava registros validados onde quer que seja."""

    def gravar(self, registros: list[Registro]) -> None: ...
