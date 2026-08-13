"""Tradução de rótulo do documento para nome canônico de campo.

O documento e o consumidor falam línguas diferentes: o PDF diz `"Proteína (g)"`,
o esquema de destino diz `proteina_g`. Sem essa tradução, uma extração perfeita
mede zero de acurácia — foi literalmente o que aconteceu antes deste módulo
existir, e o sintoma (0% em todas as estratégias, inclusive na que gerou o
gabarito) é o que denunciou a falta.

O mapeamento é **declarativo e por documento**. O núcleo continua sem saber nada
sobre o domínio; outro contexto entra trocando o arquivo de perfil.

Casar rótulos exige tolerância deliberada: acentuação vinda de PDF é instável, a
caixa varia, e o extrator monta o rótulo a partir do layout — então a ordem das
palavras pode sair invertida (`"Alimentar Fibra"` em vez de `"Fibra Alimentar"`).
A comparação é feita sobre o **conjunto de palavras normalizadas**, não sobre a
string literal.
"""

from __future__ import annotations

import re
import unicodedata

from parser.modelo import Campo, Registro

__all__ = ["Mapeamento", "MapeamentoInvalido"]


class MapeamentoInvalido(ValueError):
    """As regras de mapeamento não são utilizáveis."""


def _chave(rotulo: str) -> frozenset[str]:
    """Reduz um rótulo ao conjunto de palavras que o identifica.

    `"Proteína (g)"`, `"proteina (g)"` e `"(g) PROTEINA"` produzem a mesma chave.
    A unidade entra no conjunto de propósito: é ela que distingue
    `"Energia (kcal)"` de `"Energia (kJ)"`, e confundi-las erraria por fator ~4.
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", rotulo) if unicodedata.category(c) != "Mn"
    )
    return frozenset(p for p in re.findall(r"[a-z0-9]+", sem_acento.lower()) if p)


class Mapeamento:
    """Traduz os rótulos de um registro para os nomes canônicos do esquema."""

    def __init__(
        self,
        regras: dict[str, list[str]],
        *,
        descartar_nao_mapeados: bool = True,
    ) -> None:
        """
        Args:
            regras: nome canônico → rótulos aceitos, como aparecem no documento.
            descartar_nao_mapeados: por padrão, campo sem regra não entra na saída —
                o esquema de destino manda, e sobra do documento não vira dado.
        """
        if not regras:
            raise MapeamentoInvalido("nenhuma regra de mapeamento")

        self.regras = regras
        self.descartar_nao_mapeados = descartar_nao_mapeados
        self._indice: dict[frozenset[str], str] = {}

        for canonico, rotulos in regras.items():
            if not rotulos:
                raise MapeamentoInvalido(f"campo {canonico!r} sem rótulo correspondente")
            for rotulo in rotulos:
                chave = _chave(rotulo)
                if not chave:
                    raise MapeamentoInvalido(f"rótulo {rotulo!r} não tem palavra utilizável")
                ja_usado = self._indice.get(chave)
                if ja_usado and ja_usado != canonico:
                    raise MapeamentoInvalido(
                        f"rótulo ambíguo {rotulo!r}: reivindicado por "
                        f"{ja_usado!r} e {canonico!r}"
                    )
                self._indice[chave] = canonico

    def canonico_de(self, rotulo: str) -> str | None:
        return self._indice.get(_chave(rotulo))

    def aplicar(self, registro: Registro) -> Registro:
        """Traduz um registro, preservando proveniência.

        Campos do esquema sem correspondente no documento saem **ausentes**, não
        omitidos: o consumidor espera a coluna, e entregá-la vazia é mais honesto
        que fazê-la desaparecer.
        """
        traduzidos: dict[str, Campo] = {}

        for rotulo, campo in registro.campos.items():
            if rotulo == "identificador":
                traduzidos[rotulo] = campo
                continue

            canonico = self.canonico_de(rotulo)
            if canonico is not None:
                traduzidos[canonico] = campo
            elif not self.descartar_nao_mapeados:
                traduzidos[rotulo] = campo

        for canonico in self.regras:
            traduzidos.setdefault(canonico, Campo.ausente())

        return Registro(campos=traduzidos, fonte=registro.fonte)

    def aplicar_todos(self, registros: list[Registro]) -> list[Registro]:
        return [self.aplicar(r) for r in registros]
