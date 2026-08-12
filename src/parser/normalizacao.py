"""Normalização de texto e número, compartilhada por todos os extratores.

Vive no núcleo, **depois** do extrator e igual para todos: se cada extrator
normalizasse à sua maneira, a diferença medida entre eles seria artefato do
pipeline, não do extrator. Aqui a normalização é variável controlada.

É também a camada que mais corrompe em silêncio — um `Tr` virando `0.0` não
levanta exceção, só produz um número errado que ninguém audita. Daí a opção
consistente por falhar alto.
"""

from __future__ import annotations

import re
import unicodedata

from parser.modelo import Sentinela

__all__ = ["ValorNaoReconhecido", "normalizar_texto", "parse_numero"]


class ValorNaoReconhecido(ValueError):
    """O texto não é número nem sentinela conhecida.

    Levantada em vez de devolver ``None``: um valor ininteligível gravado como
    nulo é indistinguível de um campo legitimamente ausente.
    """


_SENTINELAS: dict[str, Sentinela] = {
    "tr": Sentinela.TRACO,
    "traço": Sentinela.TRACO,
    "traco": Sentinela.TRACO,
    "na": Sentinela.NAO_ANALISADO,
    "n/a": Sentinela.NAO_ANALISADO,
    "*": Sentinela.NAO_APLICAVEL,
}

# Aceita 1.405,5 · 1,405.5 · 3,86 · 3.86 · 124 · -2,5
_NUMERO = re.compile(r"^[+-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?$|^[+-]?\d+(?:[.,]\d+)?$")

# 4+ letras isoladas consecutivas: limiar deliberadamente conservador.
_ESPACADO = re.compile(r"(?:(?<=\s)|^)((?:[^\W\d_]\s+){3,}[^\W\d_])(?=\s|$)")

_MIN_LETRAS_ISOLADAS = 4


def parse_numero(bruto: str) -> tuple[float | None, Sentinela | None]:
    """Converte texto em número ou sentinela.

    Devolve o par ``(valor, sentinela)``, sempre mutuamente exclusivos. Devolver
    apenas ``float | None`` obrigaria o chamador a adivinhar se ``None`` significa
    "ausente" ou "traço" — distinção que altera qualquer soma a jusante.

    Levanta:
        ValorNaoReconhecido: se o texto não for número nem sentinela conhecida.
    """
    texto = bruto.strip()
    if not texto:
        raise ValorNaoReconhecido("valor vazio")

    sentinela = _SENTINELAS.get(texto.casefold())
    if sentinela is not None:
        return None, sentinela

    if not _NUMERO.match(texto):
        raise ValorNaoReconhecido(f"não é número nem sentinela: {bruto!r}")

    try:
        return _para_float(texto), None
    except ValueError as erro:
        # O contrato desta função é levantar só `ValorNaoReconhecido` — um
        # `ValueError` bruto escapando derruba o registro (ou o arquivo)
        # inteiro por causa de um valor isolado, quando o comportamento
        # correto é tratá-lo como campo não reconhecido, igual a qualquer
        # outro texto que não é número.
        raise ValorNaoReconhecido(f"não é número nem sentinela: {bruto!r}") from erro


def _para_float(texto: str) -> float:
    """Resolve vírgula e ponto sem presumir a locale do documento.

    O separador decimal é o **último** separador presente; os anteriores são de
    milhar. Isso trata `1.405,5` e `1,405.5` sem configuração externa.
    """
    ultima_virgula = texto.rfind(",")
    ultimo_ponto = texto.rfind(".")

    if ultima_virgula == -1 and ultimo_ponto == -1:
        return float(texto)

    if ultima_virgula > ultimo_ponto:
        decimal, milhar = ",", "."
    else:
        decimal, milhar = ".", ","

    posicao = max(ultima_virgula, ultimo_ponto)

    # O separador "decimal" aparece mais de uma vez, e o outro nenhuma: um
    # número real só tem **um** ponto decimal, então repetição do mesmo
    # símbolo só pode ser milhar. Sem este caso, "112.797.661" (dois pontos,
    # nenhuma vírgula) caía direto no `float()` final sem separador algum
    # removido — `float("112.797.661")` — e explodia com `ValueError` bruto
    # em vez de `ValorNaoReconhecido`. Achado ao rodar sobre PDF real de um
    # cenário corporativo, com coordenada UTM citada em prosa.
    if texto.count(decimal) > 1 and texto.count(milhar) == 0:
        return float(texto.replace(decimal, ""))

    # Um separador único com exatamente 3 dígitos à direita é ambíguo
    # ("1.405" pode ser mil e quatrocentos e cinco ou 1,405). Neste corpus,
    # milhar é a leitura correta.
    if texto.count(decimal) == 1 and texto.count(milhar) == 0:
        if len(texto) - posicao - 1 == 3:
            return float(texto.replace(decimal, ""))

    return float(texto.replace(milhar, "").replace(decimal, "."))


def normalizar_texto(bruto: str) -> str:
    """Limpa texto extraído, preservando acentuação.

    Trata duas patologias comuns em PDF: hifenização de quebra de linha
    (``"Carbo-\\nidrato"``) e texto emitido letra a letra
    (``"A L I M E N T O"``).

    A junção de letras isoladas é **heurística** e exige 4+ letras consecutivas,
    para que texto legítimo — ``"vitamina A e C"`` — sobreviva intacto. Quem
    chama deve preservar o texto original em ``Evidencia.texto_bruto``, de modo
    que um erro aqui permaneça auditável.
    """
    texto = unicodedata.normalize("NFC", bruto)
    # Hifenização de quebra: o hífen final cola na continuação, com ou sem \n
    # entre as partes — no PDF a quebra pode chegar como espaço.
    texto = re.sub(r"(\w)-\s+(\w)", r"\1\2", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    if not texto:
        return ""

    return _juntar_espacado(texto)


def _juntar_espacado(texto: str) -> str:
    def junta(m: re.Match[str]) -> str:
        trecho = m.group(1)
        letras = trecho.split()
        if len(letras) < _MIN_LETRAS_ISOLADAS:
            return trecho
        return "".join(letras)

    return _ESPACADO.sub(junta, texto)
