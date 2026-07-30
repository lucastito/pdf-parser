"""Conversão de unidade de medida (RF-7).

RF-7 pede saída com tipo **e unidade**. Antes deste módulo a unidade era texto
inerte dentro do rótulo — `"Energia (kcal)"` servia para desambiguar o mapeamento
e nunca para converter. O sintoma era `Origem.DERIVADO`: definido e validado no
modelo, com "conversão de unidade" no próprio docstring, e sem nada que o
produzisse.

A etapa é **permanente no pipeline; a tabela de conversão vem do perfil**. É essa
separação que preserva o núcleo agnóstico: aqui se sabe *converter*, e não se sabe
que "kcal" ou "g" existem. Sem regra declarada, a etapa executa e devolve o
registro intacto — não por estar desligada, mas por não haver o que converter.
Mesmo contrato de `Mapeamento`, que também é sempre aplicado com regras de fora.

A aritmética é delegada a `pint`, e não escrita à mão, por uma razão específica:
uma tabela de fatores caseira aceita `g → kcal` e devolve um número plausível.
`pint` conhece **dimensão**, então recusa. O que este projeto mais evita é
justamente a conversão errada e silenciosa.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from parser.modelo import Campo, Origem, Registro

__all__ = [
    "ConversaoImpossivel",
    "Conversor",
    "UnidadeDesconhecida",
    "UnidadeInvalida",
]


class UnidadeInvalida(ValueError):
    """Base das falhas de conversão de unidade."""


class UnidadeDesconhecida(UnidadeInvalida):
    """A regra cita uma unidade que o registro de unidades não reconhece.

    Levantada na **construção**, não na aplicação: um perfil com unidade
    inexistente é erro de configuração, e descobri-lo no meio de um lote longo
    custa muito mais que descobri-lo na carga.
    """


class ConversaoImpossivel(UnidadeInvalida):
    """As duas unidades existem, mas não medem a mesma grandeza.

    `g → kcal` cai aqui. Uma tabela de fatores caseira responderia um número;
    este erro é o que impede esse número de chegar ao consumidor.
    """


@lru_cache(maxsize=1)
def _registro_de_unidades() -> Any:
    """O registro do `pint`, carregado uma vez.

    A carga custa centenas de milissegundos e não depende de perfil; repeti-la por
    documento apareceria como custo do extrator na matriz de comparação, que é
    exatamente o tipo de artefato de instrumentação que a medição aqui evita.
    """
    import pint

    return pint.UnitRegistry()


class Conversor:
    """Converte campos numéricos para a unidade que o perfil declarar."""

    def __init__(self, regras: dict[str, dict[str, str]]) -> None:
        """
        Args:
            regras: nome canônico do campo → ``{"de": origem, "para": alvo}``.
                Ambas as unidades são declaradas: a de origem porque o documento
                não a informa de modo confiável, e o rótulo já foi consumido pelo
                mapeamento antes de chegar aqui.

        Levanta:
            UnidadeDesconhecida: se uma regra estiver incompleta ou citar unidade
                que o registro não reconhece.
        """
        self.regras = regras
        self._fatores: dict[str, tuple[float, str]] = {}

        for campo, regra in regras.items():
            origem, alvo = self._ler(campo, regra)
            self._fatores[campo] = (self._fator(campo, origem, alvo), alvo)

    @classmethod
    def de_perfil(cls, perfil: Any) -> Conversor:
        """Constrói a partir do perfil. Sem `unidades` declaradas, sai inerte."""
        return cls(getattr(perfil, "unidades", None) or {})

    @staticmethod
    def _ler(campo: str, regra: dict[str, str]) -> tuple[str, str]:
        origem, alvo = regra.get("de"), regra.get("para")
        if not origem or not alvo:
            raise UnidadeDesconhecida(
                f"campo {campo!r}: regra de unidade exige 'de' e 'para', recebido {regra!r}"
            )
        return origem, alvo

    @staticmethod
    def _fator(campo: str, origem: str, alvo: str) -> float:
        """Resolve a conversão uma única vez, na construção.

        Guardar o fator — e não as unidades — mantém o custo do `pint` fora do
        laço por registro, onde ele pesaria em documento de 164 páginas.
        """
        import pint

        registro = _registro_de_unidades()
        try:
            quantidade = registro.Quantity(1.0, origem)
        except (pint.UndefinedUnitError, TypeError, AttributeError) as erro:
            raise UnidadeDesconhecida(
                f"campo {campo!r}: unidade de origem {origem!r} não reconhecida"
            ) from erro

        try:
            return float(quantidade.to(alvo).magnitude)
        except pint.UndefinedUnitError as erro:
            raise UnidadeDesconhecida(
                f"campo {campo!r}: unidade de destino {alvo!r} não reconhecida"
            ) from erro
        except pint.DimensionalityError as erro:
            raise ConversaoImpossivel(
                f"campo {campo!r}: {origem!r} e {alvo!r} não medem a mesma grandeza "
                f"— conversão recusada em vez de produzir número plausível e errado"
            ) from erro

    def aplicar(self, registro: Registro) -> Registro:
        """Converte o que houver regra para converter.

        Campo sem regra, sentinela e campo ausente atravessam intactos: não há
        número a multiplicar, e inventar um seria pior que não converter.
        """
        if not self._fatores:
            return registro

        convertidos: dict[str, Campo] = {}
        for nome, campo in registro.campos.items():
            fator = self._fatores.get(nome)
            if fator is None or campo.valor is None or not campo.preenchido:
                convertidos[nome] = campo
                continue
            convertidos[nome] = self._converter(nome, campo, *fator)

        return Registro(campos=convertidos, fonte=registro.fonte)

    def aplicar_todos(self, registros: list[Registro]) -> list[Registro]:
        return [self.aplicar(r) for r in registros]

    @staticmethod
    def _converter(nome: str, campo: Campo, fator: float, alvo: str) -> Campo:
        """Produz o campo derivado.

        Três invariantes, todas verificadas em teste: origem vira `DERIVADO`, a
        evidência do valor original é preservada (a auditoria tem de chegar ao
        texto bruto no documento) e a confiança é propagada sem ser elevada —
        converter não acrescenta conhecimento.
        """
        if not isinstance(campo.valor, (int, float)) or isinstance(campo.valor, bool):
            raise ConversaoImpossivel(
                f"campo {nome!r}: valor {campo.valor!r} não é número, "
                f"não há como convertê-lo para {alvo!r}"
            )

        return Campo(
            valor=campo.valor * fator,
            origem=Origem.DERIVADO,
            confianca=campo.confianca,
            evidencia=campo.evidencia,
        )
