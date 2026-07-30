"""Validação da saída tabular, antes da gravação.

O modelo já valida **campo a campo**, na construção do `Registro`. O que faltava
era o **conjunto**: coluna ausente, tipo divergente entre registros, lote
heterogêneo.

O caso concreto que motivou o módulo está no destino CSV, que monta o cabeçalho a
partir do primeiro registro. Um lote em que o segundo registro traga um campo a
mais perde a coluna **sem erro algum** — o pipeline completa, o arquivo parece
bom, e o dado não está lá. É a falha muda que a spec repudia: um extrator que roda
sem erro e grava lixo é pior que um que falha alto.

Como toda configuração deste projeto, o esquema é declarativo e vem do perfil: o
núcleo não conhece nome de campo nem domínio. Sem esquema declarado, o validador
é inerte e o comportamento anterior fica intacto.

A validação é delegada a `pandera`, e não escrita à mão, para que as restrições do
perfil (tipo, mínimo, obrigatoriedade) sejam declaradas uma vez e verificadas por
código que já trata os casos de borda — e para que a mensagem de erro venha
pronta, apontando coluna e motivo.
"""

from __future__ import annotations

from typing import Any

from parser.modelo import Registro

__all__ = ["Esquema", "EsquemaInvalido", "SaidaInvalida"]

TIPOS = {"numero": "float64", "texto": "object", "inteiro": "Int64"}
"""Tipos declaráveis no perfil.

Vocabulário deliberadamente pequeno e neutro: o perfil descreve a **forma** da
saída, não o domínio. Nome fora desta tabela é erro de digitação e falha na carga.
"""


class EsquemaInvalido(ValueError):
    """A declaração de esquema no perfil não é utilizável."""


class SaidaInvalida(ValueError):
    """Os registros não satisfazem o esquema declarado.

    Levantada **antes** da gravação: dado inválido que chegou ao destino já
    contaminou o consumidor, e nenhum erro posterior desfaz isso.
    """


class Esquema:
    """Valida um lote de registros contra as colunas que o perfil declarar."""

    def __init__(self, colunas: dict[str, dict[str, Any]]) -> None:
        """
        Args:
            colunas: nome canônico → declaração. A declaração aceita ``tipo``
                (ver `TIPOS`), ``minimo``, ``maximo`` e ``obrigatorio``.

        Levanta:
            EsquemaInvalido: se alguma declaração citar tipo desconhecido.
        """
        for nome, regra in colunas.items():
            tipo = regra.get("tipo", "numero")
            if tipo not in TIPOS:
                raise EsquemaInvalido(
                    f"coluna {nome!r}: tipo {tipo!r} desconhecido. "
                    f"Conhecidos: {', '.join(sorted(TIPOS))}"
                )
        self.colunas = colunas

    @classmethod
    def de_perfil(cls, perfil: Any) -> Esquema:
        """Constrói a partir do perfil. Sem `esquema` declarado, sai inerte."""
        return cls(getattr(perfil, "esquema", None) or {})

    def validar(self, registros: list[Registro]) -> None:
        """Verifica o lote inteiro. Não devolve nada: ou passa, ou levanta.

        O esquema descreve os **campos** do registro. Colunas de proveniência que
        o destino acrescenta na gravação — como `_arquivo`, derivada de
        ``Registro.fonte`` — ficam fora de propósito: não são dado extraído, e
        exigi-las no perfil obrigaria cada usuário a declarar detalhe de destino.

        Lote vazio passa — zero registro é resultado legítimo de um documento sem
        dados, não violação de esquema.

        Levanta:
            SaidaInvalida: nomeando coluna, motivo e o índice do registro. Sem o
                índice, uma falha em lote longo é impossível de localizar.
        """
        if not self.colunas or not registros:
            return

        self._verificar_colunas(registros)
        self._verificar_valores(registros)

    def _verificar_colunas(self, registros: list[Registro]) -> None:
        """Presença e ausência de coluna, registro a registro.

        Feito fora do `pandera` de propósito: montar o quadro a partir dos
        registros faria a coluna faltante *desaparecer* em vez de acusar — o
        mesmo defeito do destino CSV que este módulo existe para pegar.
        """
        declaradas = set(self.colunas)

        for indice, registro in enumerate(registros):
            presentes = set(registro.campos)

            faltando = declaradas - presentes
            if faltando:
                raise SaidaInvalida(
                    f"registro {indice} ({registro.fonte}): coluna declarada ausente "
                    f"na saída: {', '.join(sorted(faltando))}"
                )

            sobrando = presentes - declaradas
            if sobrando:
                raise SaidaInvalida(
                    f"registro {indice} ({registro.fonte}): campo fora do esquema: "
                    f"{', '.join(sorted(sobrando))}. Em lote heterogêneo a coluna "
                    f"sumiria em silêncio na gravação"
                )

    def _verificar_valores(self, registros: list[Registro]) -> None:
        import pandas
        import pandera.pandas as pandera

        # O dtype é imposto coluna a coluna, não inferido: uma coluna numérica
        # inteiramente vazia (todos os registros com sentinela ou ausente) seria
        # inferida como `object` e acusaria tipo divergente onde não há nenhum.
        # A imposição é o que *revela* o tipo errado — texto onde se esperava
        # número não converte, e o erro sai nomeando a coluna.
        bruto = {
            nome: [_valor_bruto(registro, nome) for registro in registros]
            for nome in self.colunas
        }
        quadro = pandas.DataFrame(
            {
                nome: _coluna_tipada(
                    valores, self.colunas[nome].get("tipo", "numero"), pandas
                )
                for nome, valores in bruto.items()
            }
        )

        colunas = {
            nome: pandera.Column(
                TIPOS[regra.get("tipo", "numero")],
                checks=_restricoes(regra, pandera),
                nullable=True,
                coerce=False,
                required=True,
            )
            for nome, regra in self.colunas.items()
        }

        try:
            pandera.DataFrameSchema(colunas, strict=True).validate(quadro, lazy=True)
        except pandera.errors.SchemaErrors as erro:
            raise SaidaInvalida(_mensagem(erro)) from erro

        self._verificar_obrigatorios(registros)

    def _verificar_obrigatorios(self, registros: list[Registro]) -> None:
        """Coluna obrigatória não pode sair vazia.

        Separado do `pandera` porque "vazio" aqui é a ausência de proveniência —
        um campo `AUSENTE` —, não `NaN` no quadro. Uma sentinela também produz
        célula sem número, e essa **afirma** algo: colapsar as duas seria repetir,
        na validação, o erro que o modelo evita na extração.
        """
        for nome, regra in self.colunas.items():
            if not regra.get("obrigatorio"):
                continue
            for indice, registro in enumerate(registros):
                campo = registro.campos.get(nome)
                if campo is None or not campo.preenchido:
                    raise SaidaInvalida(
                        f"registro {indice} ({registro.fonte}): coluna {nome!r} é "
                        f"obrigatória e saiu sem valor"
                    )


def _valor_bruto(registro: Registro, nome: str) -> Any:
    """O valor como o destino o gravaria — sentinela e ausente viram vazio.

    Uma sentinela **satisfaz** uma coluna numérica: `Tr` é valor válido do
    documento, não tipo divergente. Quem precisa distingui-la de um vazio usa a
    proveniência, que o destino JSON preserva.
    """
    campo = registro.campos.get(nome)
    if campo is None or not campo.preenchido or campo.valor is None:
        return None
    return campo.valor


def _coluna_tipada(valores: list[Any], tipo: str, pandas: Any) -> Any:
    """Impõe o dtype declarado, deixando o valor incompatível denunciar-se.

    Uma coluna numérica que receba texto não converte; em vez de deixar o
    `pandas` inferir `object` e o erro sair como "dtype divergente" — mensagem
    que não diz qual valor é o culpado —, a série vira `object` e o `pandera`
    acusa a coluna pelo nome.
    """
    serie = pandas.Series(valores, dtype="object")
    if tipo == "texto":
        return serie

    convertida = pandas.to_numeric(serie, errors="coerce")
    # `coerce` transforma o texto inválido em `NaN`, que é indistinguível de um
    # campo legitimamente vazio. Só se aceita a conversão quando nada se perdeu.
    perdeu = convertida.isna() & serie.notna()
    if perdeu.any():
        return serie

    return convertida.astype(TIPOS[tipo])


def _restricoes(regra: dict[str, Any], pandera: Any) -> list[Any]:
    checks = []
    if (minimo := regra.get("minimo")) is not None:
        checks.append(pandera.Check.ge(minimo))
    if (maximo := regra.get("maximo")) is not None:
        checks.append(pandera.Check.le(maximo))
    return checks


def _mensagem(erro: Any) -> str:
    """Reescreve o relatório do `pandera` na forma que este projeto usa.

    O padrão é um quadro com dezenas de colunas; o que quem depura precisa é
    coluna, motivo e **índice do registro**.
    """
    linhas = []
    for falha in erro.failure_cases.itertuples():
        coluna = getattr(falha, "column", None) or "?"
        indice = getattr(falha, "index", None)
        caso = getattr(falha, "failure_case", None)
        onde = f"registro {indice}: " if indice is not None else ""
        linhas.append(f"{onde}coluna {coluna!r} — {getattr(falha, 'check', '?')} "
                      f"(valor {caso!r})")

    return "saída não satisfaz o esquema declarado:\n  " + "\n  ".join(
        dict.fromkeys(linhas)
    )
