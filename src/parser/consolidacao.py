"""Consolidação por campo: votar por célula, não escolher planilha (ADR-0017).

Cada estratégia produz uma planilha do mesmo documento. Escolher "a melhor"
desperdiça informação: três rotas empatam em 100% contra o conjunto de reserva, e
nenhuma acerta tudo em todas as páginas.

A saída é votar **por célula**. Onde as rotas concordam, a concordância vira
confiança — "confirmado por três leituras independentes" é afirmação que nenhuma
rota sozinha sustenta. Onde divergem, o valor entra marcado. Onde empatam ou
ninguém leu, **vira pendência para revisão humana**.

Este módulo **decide**; `concordancia.py` **mede**. A distinção não é acadêmica:
medir não compromete, decidir coloca valor na planilha que alguém vai usar.

## O que fica parametrizado, e por quê

O **peso** de cada rota é parâmetro, com padrão uniforme declarado provisório.
Rotas que compartilham fonte de erro erram juntas — três leitores da mesma camada
de texto podem confirmar o mesmo erro com confiança alta. Calibrar isso exige a
matriz de correlação de erros, que só existe depois das medições. Embutir peso
agora seria decidir por suposição o que a medição vai responder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from parser.concordancia import _equivalentes, _indexar

__all__ = [
    "Celula",
    "Desfecho",
    "PendenciaDeCampo",
    "Placar",
    "ResultadoConsolidacao",
    "consolidar",
]


class Desfecho(StrEnum):
    """O que a votação decidiu para uma célula."""

    CONCORDANCIA = "concordancia"
    """Todas as rotas que leram disseram o mesmo. Confiança alta."""

    MAIORIA = "maioria"
    """A maioria concordou; a divergência fica registrada junto do valor."""

    VOTO_UNICO = "voto-unico"
    """Uma só rota leu. O valor é aproveitado, mas ninguém o confirmou.

    Distinto de `CONCORDANCIA` de propósito: dar a uma leitura solitária a mesma
    marca de três leituras concordantes inflaria a confiança exatamente onde ela
    é menor.
    """

    PENDENCIA = "pendencia"
    """Empate, ou ninguém leu. **Não preenche** — vai para revisão humana."""


@dataclass(frozen=True)
class Celula:
    """Uma decisão sobre um par (item, campo)."""

    item: str
    campo: str
    valor: Any
    desfecho: Desfecho
    concordaram: int = 0
    rotas_a_favor: tuple[str, ...] = ()
    rotas_divergentes: list[str] = field(default_factory=list)

    @property
    def preenche(self) -> bool:
        return self.desfecho is not Desfecho.PENDENCIA

    def como_dados(self) -> dict[str, Any]:
        return {
            "item": self.item,
            "campo": self.campo,
            "valor": self.valor,
            "desfecho": self.desfecho.value,
            "concordaram": self.concordaram,
            "rotas_a_favor": list(self.rotas_a_favor),
            "rotas_divergentes": self.rotas_divergentes,
        }


@dataclass(frozen=True)
class PendenciaDeCampo:
    """Um campo que a consolidação não preencheu, e o motivo."""

    item: str
    campo: str
    motivo: str


@dataclass(frozen=True)
class Placar:
    """Acertos, erros e omissões contados **separado**.

    A separação é a decisão central da métrica. Omitir vira pendência: custa
    trabalho humano, mas a planilha não fica errada. Errar entra na planilha como
    dado bom, e ninguém revisa.

    Um extrator que omite 20% e nunca erra é melhor para este caso de uso que um
    que erra 10% — e a taxa de acerto simples diria o contrário.
    """

    acertos: int = 0
    erros: int = 0
    omissoes: int = 0

    @property
    def preenchidos(self) -> int:
        return self.acertos + self.erros

    @property
    def taxa_de_erro(self) -> float:
        """Erros **entre o que foi preenchido**.

        Não inclui omissões no denominador de propósito: misturá-las esconderia
        um extrator conservador, que preenche pouco e acerta tudo que preenche.
        """
        return self.erros / self.preenchidos if self.preenchidos else 0.0

    def como_dados(self) -> dict[str, Any]:
        return {
            "acertos": self.acertos,
            "erros": self.erros,
            "omissoes": self.omissoes,
            "taxa_de_erro": round(self.taxa_de_erro, 4),
        }


@dataclass
class ResultadoConsolidacao:
    """A planilha consolidada, com a proveniência de cada célula."""

    celulas: list[Celula] = field(default_factory=list)
    rotas: list[str] = field(default_factory=list)
    valores_divergentes: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    """(item, campo) → rota → o valor que ela leu, quando houve divergência.

    Guardado à parte para que o relatório mostre **o que** cada rota leu, e não
    só quem discordou: sem o valor, quem confere precisa abrir as planilhas de
    origem para saber o que estava em jogo.
    """

    def celula(self, item: str, campo: str) -> Celula:
        for c in self.celulas:
            if c.item == item and c.campo == campo:
                return c
        raise KeyError(f"sem célula para ({item!r}, {campo!r})")

    @property
    def pendencias(self) -> list[PendenciaDeCampo]:
        return [
            PendenciaDeCampo(
                item=c.item,
                campo=c.campo,
                motivo=("ninguém leu" if c.concordaram == 0 else "empate entre rotas"),
            )
            for c in self.celulas
            if c.desfecho is Desfecho.PENDENCIA
        ]

    def contra_gabarito(self, gabarito: dict[str, dict[str, Any]]) -> Placar:
        """Confere a planilha consolidada contra valores conferidos à mão."""
        acertos = erros = omissoes = 0
        for celula in self.celulas:
            esperado = gabarito.get(celula.item, {})
            if celula.campo not in esperado:
                continue
            if not celula.preenche:
                omissoes += 1
            elif _equivalentes(celula.valor, esperado[celula.campo]):
                acertos += 1
            else:
                erros += 1
        return Placar(acertos=acertos, erros=erros, omissoes=omissoes)

    def relatorio(self) -> str:
        linhas = [f"consolidação de {len(self.rotas)} rota(s): {', '.join(self.rotas)}"]
        for celula in self.celulas:
            if celula.desfecho is Desfecho.CONCORDANCIA:
                continue
            detalhe = f"  {celula.item} / {celula.campo}: {celula.desfecho.value}"
            if celula.preenche:
                detalhe += f" = {celula.valor}"
            if celula.rotas_divergentes:
                # O valor lido vai junto do nome da rota: sem ele, quem confere
                # precisa abrir as planilhas de origem para saber o que estava
                # em jogo.
                lidos = self.valores_divergentes.get((celula.item, celula.campo), {})
                divergentes = ", ".join(
                    f"{rota}={lidos[rota]}" if rota in lidos else rota
                    for rota in celula.rotas_divergentes
                )
                detalhe += f" — divergiram: {divergentes}"
            linhas.append(detalhe)
        return "\n".join(linhas)

    def como_dados(self) -> dict[str, Any]:
        return {
            "rotas": self.rotas,
            "celulas": [
                {
                    **c.como_dados(),
                    # Junto da célula, e não numa seção à parte: quem lê o JSON
                    # para conferir uma divergência precisa dos dois no mesmo
                    # lugar.
                    "valores_divergentes": self.valores_divergentes.get((c.item, c.campo), {}),
                }
                for c in self.celulas
            ],
            "pendencias": [
                {"item": p.item, "campo": p.campo, "motivo": p.motivo} for p in self.pendencias
            ],
        }


def _agrupar_votos(valores: dict[str, Any]) -> list[list[str]]:
    """Agrupa rotas que disseram a mesma coisa.

    Usa equivalência numérica com tolerância, e não igualdade exata: '124' e
    '124.0' são o mesmo número, e tratá-los como divergentes produziria pendência
    onde não há dúvida.
    """
    grupos: list[list[str]] = []
    for rota, valor in valores.items():
        for grupo in grupos:
            if _equivalentes(valores[grupo[0]], valor):
                grupo.append(rota)
                break
        else:
            grupos.append([rota])
    return grupos


def _canonizar(
    indice: dict[str, dict[str, Any]], mapeamento: dict[str, list[str]]
) -> dict[str, dict[str, Any]]:
    """Traduz os nomes lidos para os canônicos declarados no perfil.

    Sem isto, cada variante de nome vira uma coluna própria com **um voto**.
    Medido sobre as saídas reais das quatro rotas determinísticas: 56% das
    células saíam como voto único porque `Fibra Alimentar (g)` e `Alimentar
    Fibra (g)` — o mesmo campo, com o cabeçalho rotacionado — não se
    encontravam.

    Campo fora do mapeamento mantém o nome lido: mapear é opcional, e sumir com
    coluna não declarada seria pior que não alinhar.
    """
    if not mapeamento:
        return indice

    de_para = {
        variante: canonico
        for canonico, variantes in mapeamento.items()
        for variante in variantes
    }
    return {
        item: {de_para.get(nome, nome): valor for nome, valor in campos.items()}
        for item, campos in indice.items()
    }


def consolidar(
    saidas: dict[str, list[dict]],
    *,
    chave_item: str = "identificador",
    pesos: dict[str, float] | None = None,
    mapeamento: dict[str, list[str]] | None = None,
) -> ResultadoConsolidacao:
    """Vota célula a célula entre as saídas das estratégias.

    Args:
        saidas: rota → lista de registros serializados.
        chave_item: campo que identifica o item, para alinhar as planilhas.
        pesos: rota → peso do voto. Padrão uniforme, **declarado provisório**:
            o peso definitivo depende da matriz de correlação de erros, que só
            existe depois das medições (ADR-0017).
        mapeamento: campo canônico → nomes que as rotas usam para ele. É o mesmo
            `mapeamento` do perfil. Sem ele, variantes do mesmo campo não votam
            juntas e a concordância se perde.

    Raises:
        ValueError: se `pesos` citar rota que não está em `saidas` — nome errado
            passaria despercebido e aquela rota votaria com peso 1 sem aviso.

    Rota ausente **não** conta como discordância: ela não votou. Máquinas
    diferentes rodam conjuntos diferentes de modelos, e contar ausência como voto
    contrário faria o resultado depender de quem rodou o quê.
    """
    if pesos:
        desconhecidas = set(pesos) - set(saidas)
        if desconhecidas:
            raise ValueError(
                f"pesos citam rota inexistente: {', '.join(sorted(desconhecidas))}"
            )

    indices = {
        nome: _canonizar(_indexar(dados, chave_item), mapeamento or {})
        for nome, dados in saidas.items()
    }
    # Rota sem nenhum registro não rodou; mantê-la na lista de votantes faria
    # cada célula parecer ter mais discordância do que teve.
    ativas = [nome for nome, indice in indices.items() if indice]

    resultado = ResultadoConsolidacao(rotas=ativas)
    if not ativas:
        return resultado

    itens = sorted(set().union(*(set(indices[n]) for n in ativas)))

    for item in itens:
        campos: set[str] = set()
        for nome in ativas:
            campos |= set(indices[nome].get(item, {}))

        for campo in sorted(campos):
            # Só quem leu vota. `None` é ausência de leitura, não voto em branco.
            votos = {
                nome: indices[nome][item][campo]
                for nome in ativas
                if item in indices[nome] and indices[nome][item].get(campo) is not None
            }
            celula = _decidir(item, campo, votos, pesos or {})
            resultado.celulas.append(celula)
            if celula.rotas_divergentes:
                resultado.valores_divergentes[(item, campo)] = {
                    rota: votos[rota] for rota in celula.rotas_divergentes
                }

    return resultado


def _decidir(item: str, campo: str, votos: dict[str, Any], pesos: dict[str, float]) -> Celula:
    if not votos:
        return Celula(item=item, campo=campo, valor=None, desfecho=Desfecho.PENDENCIA)

    def peso(rotas: list[str]) -> float:
        return sum(pesos.get(rota, 1.0) for rota in rotas)

    grupos = _agrupar_votos(votos)
    grupos.sort(key=peso, reverse=True)

    vencedor = grupos[0]
    divergentes = sorted(r for grupo in grupos[1:] for r in grupo)

    if len(grupos) == 1:
        desfecho = Desfecho.VOTO_UNICO if len(vencedor) == 1 else Desfecho.CONCORDANCIA
    elif peso(vencedor) > peso(grupos[1]):
        desfecho = Desfecho.MAIORIA
    else:
        # Empate. Desempatar por ordem ou por "rota preferida" produziria valor
        # plausível sem base — o modo de falha mais perigoso deste módulo.
        return Celula(
            item=item,
            campo=campo,
            valor=None,
            desfecho=Desfecho.PENDENCIA,
            concordaram=len(vencedor),
            rotas_divergentes=divergentes,
        )

    return Celula(
        item=item,
        campo=campo,
        valor=votos[vencedor[0]],
        desfecho=desfecho,
        concordaram=len(vencedor),
        rotas_a_favor=tuple(sorted(vencedor)),
        rotas_divergentes=divergentes,
    )
