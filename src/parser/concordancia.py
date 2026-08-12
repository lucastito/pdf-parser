"""Concordância entre estratégias, quando não há gabarito.

Serve a uma pergunta legítima e a um limite que precisa ficar explícito.

**O que mede:** quanto duas estratégias produzem o mesmo valor para o mesmo
campo do mesmo item. Concordância alta é sinal — se duas abordagens
independentes chegam ao mesmo número, provavelmente ambas leram certo.

**O que NÃO mede: acurácia.** Duas estratégias podem errar igual, sobretudo se
compartilharem a mesma fonte de erro (a camada de texto do documento, por
exemplo). Uma estratégia isolada que discorde das outras pode ser a única
correta. Concordância é evidência circunstancial, não veredito.

Só o gabarito conferido à mão responde "quem acertou mais". Este módulo existe
para extrair o máximo de informação **enquanto** o gabarito não existe — e para
apontar onde vale concentrar a conferência humana: os campos em que as
estratégias divergem são os mais informativos.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

__all__ = ["Divergencia", "ResultadoConcordancia", "comparar_estrategias"]

TOLERANCIA = 0.01


@dataclass
class Divergencia:
    """Um ponto em que as estratégias não concordam."""

    item: str
    campo: str
    valores: dict[str, Any]
    """Estratégia → valor produzido."""

    @property
    def isolada(self) -> str | None:
        """A estratégia que discorda de todas as outras, se houver uma só.

        É o caso mais informativo para conferência humana: ou ela é a única
        certa, ou é a única errada, e saber qual muda a conclusão.
        """
        contagem: dict[str, list[str]] = {}
        for estrategia, valor in self.valores.items():
            contagem.setdefault(_chave(valor), []).append(estrategia)
        if len(contagem) != 2:
            return None
        for _, estrategias in contagem.items():
            if len(estrategias) == 1:
                return estrategias[0]
        return None


@dataclass
class ResultadoConcordancia:
    estrategias: list[str]
    itens_comuns: int = 0
    comparacoes: int = 0
    concordantes: int = 0
    por_par: dict[str, float] = field(default_factory=dict)
    por_campo: dict[str, float] = field(default_factory=dict)
    divergencias: list[Divergencia] = field(default_factory=list)
    itens_exclusivos: dict[str, int] = field(default_factory=dict)
    """Quantos itens de cada estratégia **não** entraram em `itens_comuns`.

    Existe porque a interseção, sozinha, é cega a fabricação: uma estratégia
    que inventa linhas extras nunca teve essas linhas comparadas contra
    nada — elas caem fora da conta antes de qualquer campo ser olhado, e a
    taxa de concordância sai perfeita mesmo com a rota dobrando o número de
    itens da página (achado da auditoria de 2026-08-02, `concordancia.py:198`).
    Isto não decide sozinho que a diferença é invenção — sem gabarito, item
    exclusivo também pode ser cobertura genuína que as outras erraram —, mas
    deixa de ser invisível.
    """

    @property
    def taxa(self) -> float:
        return self.concordantes / self.comparacoes if self.comparacoes else 0.0

    def relatorio(self) -> str:
        if len(self.estrategias) < 2:
            return (
                "Sem base para comparar concordância: apenas "
                f"{len(self.estrategias)} estratégia produziu dados "
                f"({', '.join(self.estrategias) or 'nenhuma'})."
            )

        if not self.comparacoes:
            return (
                f"estratégias comparadas : {', '.join(self.estrategias)}\n"
                f"itens em comum         : {self.itens_comuns}\n\n"
                "Nenhum campo comparável. As estratégias produziram identificadores\n"
                "ou nomes de campo que não se alinham — o que é informação sobre elas,\n"
                "não concordância de 0%."
            )

        linhas = [
            f"estratégias comparadas : {', '.join(self.estrategias)}",
            f"itens em comum         : {self.itens_comuns}",
            f"concordância geral     : {self.taxa:.1%} "
            f"({self.concordantes}/{self.comparacoes})",
        ]
        exclusivos = {n: q for n, q in self.itens_exclusivos.items() if q}
        if exclusivos:
            linhas.append("\nitens fora da interseção (não entraram na concordância acima):")
            for nome, quantos in sorted(exclusivos.items(), key=lambda x: -x[1]):
                linhas.append(
                    f"  {nome:20s} {quantos} — sem gabarito, pode ser cobertura "
                    "genuína ou item fabricado; investigue antes de confiar"
                )
        if self.por_par:
            linhas.append("\nconcordância por par:")
            for par, taxa in sorted(self.por_par.items(), key=lambda x: -x[1]):
                linhas.append(f"  {par:44s} {taxa:6.1%}")
        if self.por_campo:
            linhas.append("\nconcordância por campo (menor primeiro — confira estes):")
            for campo, taxa in sorted(self.por_campo.items(), key=lambda x: x[1]):
                linhas.append(f"  {campo:30s} {taxa:6.1%}")
        if self.divergencias:
            linhas.append(
                f"\n{len(self.divergencias)} divergência(s). "
                "Onde uma estratégia se isola, a conferência humana rende mais:"
            )
            isoladas = [d for d in self.divergencias if d.isolada]
            for d in isoladas[:10]:
                valores = "  ".join(f"{e}={v}" for e, v in d.valores.items())
                linhas.append(
                    f"  [{d.item[:26]}] {d.campo}: {valores}  (isolada: {d.isolada})"
                )
        linhas.append(
            "\nConcordância NÃO é acurácia: estratégias podem errar igual, e uma "
            "\nestratégia isolada pode ser a única correta. Só o gabarito decide."
        )
        return "\n".join(linhas)


def _chave(valor: Any) -> str:
    """Normaliza para comparação: `42` e `42.0` são o mesmo valor."""
    if valor is None:
        return "\x00ausente"
    numero = _numero(valor)
    if numero is not None:
        return f"n:{round(numero, 4)}"
    return f"t:{str(valor).strip().casefold()}"


def _numero(valor: Any) -> float | None:
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


def _equivalentes(a: Any, b: Any) -> bool:
    na, nb = _numero(a), _numero(b)
    if na is not None and nb is not None:
        if na == 0:
            return abs(nb) <= TOLERANCIA
        return abs(na - nb) / abs(na) <= TOLERANCIA
    return _chave(a) == _chave(b)


def _valor(campo: dict) -> Any:
    """Extrai o valor comparável de um campo serializado."""
    if not isinstance(campo, dict):
        return None
    if campo.get("origem") == "ausente":
        return None
    if campo.get("sentinela"):
        return campo["sentinela"]
    return campo.get("valor")


def _chave_de_item(identificador: str) -> str:
    """Forma normalizada usada **só para casar** o mesmo item entre estratégias.

    Medido sobre saídas reais: apenas 81 de ~283 itens apareciam nas quatro
    rotas de um mesmo documento. A causa dominante não é acento — é **espaço
    espúrio no meio da palavra**, que um extrator de tabela insere ao atravessar
    a quebra de coluna num cabeçalho rotacionado: `Arroz, integra l` e
    `Arroz, integral` são o mesmo item, e viravam dois itens de um voto cada.

    Remover **todo** espaço é agressivo de propósito, e seguro aqui porque o
    identificador costuma carregar o número do item: `100 Brocolis, cozido` e
    `101 Brocolis, cru` continuam distintos. Fosse só o nome, colapsaria
    demais — misturar itens diferentes é pior que não alinhar.

    Compartilhado com `parser.consolidacao`, que decide a partir da mesma
    normalização — as duas contam o mesmo item da mesma forma, ou a
    concordância medida aqui e a votação decidida lá divergiriam sem motivo.
    """
    sem_acento = unicodedata.normalize("NFKD", identificador)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return "".join(sem_acento.split()).casefold()


def _mais_legivel(a: str, b: str) -> str:
    """Entre duas grafias do mesmo item, a que aparece nos relatórios.

    Critério: menos espaços vence — `Arroz, integral` sobre `Arroz, integra l`.
    Empatando, a que tem acento, forma correta em português. A chave
    normalizada serve para casar; ninguém quer lê-la.
    """
    if a.count(" ") != b.count(" "):
        return a if a.count(" ") < b.count(" ") else b
    acentos = sum(1 for c in unicodedata.normalize("NFKD", a) if unicodedata.combining(c))
    outros = sum(1 for c in unicodedata.normalize("NFKD", b) if unicodedata.combining(c))
    return a if acentos >= outros else b


def _indexar(dados: list[dict], chave_item: str) -> dict[str, dict[str, Any]]:
    """Indexa registros pelo identificador, com os valores achatados."""
    indice = {}
    for registro in dados:
        campos = registro.get("campos", {})
        identificador = _valor(campos.get(chave_item, {}))
        if identificador is None:
            continue
        indice[str(identificador).strip()] = {
            nome: _valor(campo) for nome, campo in campos.items() if nome != chave_item
        }
    return indice


def comparar_estrategias(
    saidas: dict[str, list[dict]], *, chave_item: str = "identificador"
) -> ResultadoConcordancia:
    """Compara as saídas de várias estratégias entre si.

    Args:
        saidas: estratégia → lista de registros serializados.
        chave_item: campo que identifica o item, para alinhar as saídas.

    Só itens presentes em **todas** as estratégias entram na conta de
    concordância por campo: comparar item ausente numa delas mediria cobertura,
    não concordância, e as duas coisas já são medidas separadamente. Itens que
    ficam de fora são contados em `itens_exclusivos` — nunca descartados em
    silêncio.
    """
    brutos = {nome: _indexar(dados, chave_item) for nome, dados in saidas.items()}

    # Reindexa pela forma normalizada, guardando à parte a grafia mais legível
    # para exibir. Sem isto, "Arroz, integra l" e "Arroz, integral" contam como
    # dois itens de um voto cada e nenhum dos dois entra na interseção — o
    # item deixa de ser "comum" por causa de um espaço espúrio, não por ter
    # sido lido só por uma rota (mesma normalização de `parser.consolidacao`).
    indices: dict[str, dict[str, dict[str, Any]]] = {}
    rotulos: dict[str, str] = {}
    for nome, indice in brutos.items():
        indices[nome] = {}
        for identificador, campos_lidos in indice.items():
            chave = _chave_de_item(identificador)
            indices[nome][chave] = campos_lidos
            anterior = rotulos.get(chave)
            rotulos[chave] = (
                identificador if anterior is None else _mais_legivel(anterior, identificador)
            )

    estrategias = [n for n, i in indices.items() if i]

    resultado = ResultadoConcordancia(estrategias=estrategias)
    if len(estrategias) < 2:
        return resultado

    comuns = set.intersection(*(set(indices[n]) for n in estrategias))
    resultado.itens_comuns = len(comuns)
    resultado.itens_exclusivos = {
        nome: len(set(indices[nome]) - comuns) for nome in estrategias
    }
    if not comuns:
        return resultado

    acertos_par: dict[str, list[int]] = {}
    acertos_campo: dict[str, list[int]] = {}

    for chave in sorted(comuns):
        campos = set()
        for nome in estrategias:
            campos |= set(indices[nome][chave])

        for campo in sorted(campos):
            valores = {n: indices[n][chave].get(campo) for n in estrategias}
            # Campo ausente em todas não informa nada sobre concordância.
            if all(v is None for v in valores.values()):
                continue

            houve_divergencia = False
            for a, b in combinations(estrategias, 2):
                par = f"{a} × {b}"
                iguais = _equivalentes(valores[a], valores[b])
                acertos_par.setdefault(par, []).append(1 if iguais else 0)
                acertos_campo.setdefault(campo, []).append(1 if iguais else 0)
                resultado.comparacoes += 1
                if iguais:
                    resultado.concordantes += 1
                else:
                    houve_divergencia = True

            if houve_divergencia:
                resultado.divergencias.append(
                    Divergencia(item=rotulos[chave], campo=campo, valores=valores)
                )

    resultado.por_par = {par: sum(v) / len(v) for par, v in acertos_par.items() if v}
    resultado.por_campo = {campo: sum(v) / len(v) for campo, v in acertos_campo.items() if v}
    return resultado
