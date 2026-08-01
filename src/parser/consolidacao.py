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

import unicodedata
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

_ITENS_PARA_CONCLUIR_COLUNA_VAZIA = 10
"""Quantos itens é preciso ter para chamar uma coluna quase vazia de artefato.

Abaixo disto, coluna sem valor é campo não lido — pendência legítima. A ausência
sistemática só vira evidência de cabeçalho corrompido quando há itens suficientes
para que "sistemática" queira dizer algo.
"""

_PREENCHIMENTO_MINIMO_DA_COLUNA = 0.05
"""Fração dos itens que uma coluna precisa preencher para contar como dado.

Não é vazio absoluto, e a diferença veio de um caso real: a coluna `Energia —`,
inventada pelo OCR a partir de um cabeçalho corrompido, aparece em 159 itens e
tem **um** valor não nulo — o resíduo `'='`. Exigir vazio absoluto deixaria essa
coluna passar por causa de um caractere, e as 158 pendências continuariam
afogando as verdadeiras.

O limiar é baixo de propósito: campo legitimamente esparso (presente em poucos
alimentos) precisa sobreviver. O que ele corta é a coluna preenchida em fração
ínfima, que é assinatura de artefato e não de dado raro.
"""


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

    campos_vazios: list[str] = field(default_factory=list)
    """Colunas preenchidas em fração ínfima dos itens — artefato, não dado.

    Descartadas da planilha, e listadas aqui em vez de sumirem em silêncio:
    coluna assim costuma ser cabeçalho corrompido na extração, e escondê-la
    esconderia o defeito que a produziu.
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
        """Confere a planilha consolidada contra valores conferidos à mão.

        Casa por identificador **normalizado**: o gabarito é transcrito à mão e
        pode trazer outra grafia do mesmo item. Sem isso o item não casaria e
        sumiria do placar — nem acerto, nem erro, nem omissão. Zero silencioso é
        pior que erro, porque a acurácia continua parecendo boa sobre uma amostra
        menor do que se pensa.
        """
        por_chave = {_chave_de_item(item): campos for item, campos in gabarito.items()}
        # Reserva: o número do item, quando ele existe e é único.
        #
        # Modelo pequeno devolve `"1"` onde as demais rotas dão `"1 Arroz…"` —
        # medido, e a conferência acusava 0% em modelo que acertava 92,9% dos
        # campos. Zero por chave que não casa é o pior erro de medição: parece
        # incapacidade e é defeito do instrumento.
        por_numero: dict[str, dict[str, Any]] = {}
        for item, campos in gabarito.items():
            numero = _numero_de_item(item)
            if numero and numero not in por_numero:
                por_numero[numero] = campos

        acertos = erros = omissoes = 0
        for celula in self.celulas:
            esperado = por_chave.get(_chave_de_item(celula.item))
            if esperado is None:
                esperado = por_numero.get(_numero_de_item(celula.item), {})
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


def _chave_de_item(identificador: str) -> str:
    """Forma normalizada usada **só para casar** o mesmo item entre rotas.

    Medido sobre as saídas reais: apenas 81 de ~283 itens apareciam nas quatro
    rotas. A causa dominante não é acento — é **espaço espúrio no meio da
    palavra**, que o extrator de tabela insere ao atravessar a quebra de coluna
    num cabeçalho rotacionado: `Arroz, integra l` e `Arroz, integral` são o
    mesmo alimento, e viravam dois itens de um voto cada.

    Remover **todo** espaço é agressivo de propósito, e seguro aqui porque o
    identificador carrega o número do item: `100 Brocolis, cozido` e
    `101 Brocolis, cru` continuam distintos. Fosse só o nome, colapsaria
    demais — e colapsar itens diferentes é pior que não alinhar, porque
    misturaria valores de alimentos distintos na mesma linha.
    """
    sem_acento = unicodedata.normalize("NFKD", identificador)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return "".join(sem_acento.split()).casefold()


def _numero_de_item(identificador: str) -> str:
    """O número que abre o identificador, se houver.

    Serve de chave reserva quando o modelo devolve só `"1"` e o gabarito traz
    `"1 Arroz, integral, cozido"`. Devolve vazio quando não começa por número —
    aí não há reserva, e o casamento continua sendo pela forma normalizada.
    """
    texto = str(identificador).strip()
    if not texto:
        return ""
    primeiro = texto.split()[0].rstrip(".,)")
    return primeiro if primeiro.isdigit() else ""


def _mais_legivel(a: str, b: str) -> str:
    """Entre duas grafias do mesmo item, a que vai para a planilha.

    Critério: menos espaços vence — `Arroz, integral` sobre `Arroz, integra l`.
    Empatando, a que tem acento, que é a forma correta em português. A chave
    normalizada serve para casar; ninguém quer lê-la.
    """
    if a.count(" ") != b.count(" "):
        return a if a.count(" ") < b.count(" ") else b
    acentos = sum(1 for c in unicodedata.normalize("NFKD", a) if unicodedata.combining(c))
    outros = sum(1 for c in unicodedata.normalize("NFKD", b) if unicodedata.combining(c))
    return a if acentos >= outros else b


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

    lidos = {
        nome: _canonizar(_indexar(dados, chave_item), mapeamento or {})
        for nome, dados in saidas.items()
    }

    # Reindexa pela forma normalizada, guardando à parte a grafia que vai para a
    # planilha: sem isso, `Arroz, integra l` e `Arroz, integral` seriam dois
    # itens de um voto cada — a causa de 204 dos 283 itens ficarem sem votação.
    indices: dict[str, dict[str, dict[str, Any]]] = {}
    rotulos: dict[str, str] = {}
    for nome, indice in lidos.items():
        indices[nome] = {}
        for identificador, campos_lidos in indice.items():
            chave = _chave_de_item(identificador)
            indices[nome][chave] = campos_lidos
            anterior = rotulos.get(chave)
            rotulos[chave] = (
                identificador if anterior is None else _mais_legivel(anterior, identificador)
            )

    # Rota sem nenhum registro não rodou; mantê-la na lista de votantes faria
    # cada célula parecer ter mais discordância do que teve.
    ativas = [nome for nome, indice in indices.items() if indice]

    resultado = ResultadoConsolidacao(rotas=ativas)
    if not ativas:
        return resultado

    itens = sorted(set().union(*(set(indices[n]) for n in ativas)))

    # Coluna que nenhuma rota preencheu em item algum é artefato de extração —
    # cabeçalho corrompido que virou coluna. Medido: 158 das 251 pendências
    # vinham de uma dessas, afogando as 3 pendências verdadeiras. Pendência é
    # pedido de trabalho humano, e não se pede revisão de coluna inexistente.
    #
    # Exige **vários itens** para concluir. Num documento de um item só, campo
    # vazio é campo não lido daquele item — que é pendência legítima — e não há
    # evidência de coluna fantasma. Sem esta condição, a regra descartaria a
    # única pendência de uma extração pequena.
    if len(itens) >= _ITENS_PARA_CONCLUIR_COLUNA_VAZIA:
        declarados: set[str] = set()
        itens_com_valor: dict[str, set[str]] = {}
        for nome in ativas:
            for item, campos_lidos in indices[nome].items():
                declarados |= set(campos_lidos)
                for campo, valor in campos_lidos.items():
                    if valor is not None:
                        itens_com_valor.setdefault(campo, set()).add(item)

        minimo = len(itens) * _PREENCHIMENTO_MINIMO_DA_COLUNA
        resultado.campos_vazios = sorted(
            campo for campo in declarados if len(itens_com_valor.get(campo, set())) < minimo
        )

    for item in itens:
        campos: set[str] = set()
        for nome in ativas:
            campos |= set(indices[nome].get(item, {}))
        campos -= set(resultado.campos_vazios)

        # A chave normalizada casa as rotas; o rótulo é o que a planilha mostra.
        rotulo = rotulos[item]

        for campo in sorted(campos):
            # Só quem leu vota. `None` é ausência de leitura, não voto em branco.
            votos = {
                nome: indices[nome][item][campo]
                for nome in ativas
                if item in indices[nome] and indices[nome][item].get(campo) is not None
            }
            celula = _decidir(rotulo, campo, votos, pesos or {})
            resultado.celulas.append(celula)
            if celula.rotas_divergentes:
                resultado.valores_divergentes[(rotulo, campo)] = {
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
