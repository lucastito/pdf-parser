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
                linhas.append(f"  [{d.item[:26]}] {d.campo}: {valores}  (isolada: {d.isolada})")
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

    Só itens presentes em **todas** as estratégias entram: comparar item ausente
    numa delas mediria cobertura, não concordância, e as duas coisas já são
    medidas separadamente.
    """
    indices = {nome: _indexar(dados, chave_item) for nome, dados in saidas.items()}
    estrategias = [n for n, i in indices.items() if i]

    resultado = ResultadoConcordancia(estrategias=estrategias)
    if len(estrategias) < 2:
        return resultado

    comuns = set.intersection(*(set(indices[n]) for n in estrategias))
    resultado.itens_comuns = len(comuns)
    if not comuns:
        return resultado

    acertos_par: dict[str, list[int]] = {}
    acertos_campo: dict[str, list[int]] = {}

    for item in sorted(comuns):
        campos = set()
        for nome in estrategias:
            campos |= set(indices[nome][item])

        for campo in sorted(campos):
            valores = {n: indices[n][item].get(campo) for n in estrategias}
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
                    Divergencia(item=item, campo=campo, valores=valores)
                )

    resultado.por_par = {
        par: sum(v) / len(v) for par, v in acertos_par.items() if v
    }
    resultado.por_campo = {
        campo: sum(v) / len(v) for campo, v in acertos_campo.items() if v
    }
    return resultado
