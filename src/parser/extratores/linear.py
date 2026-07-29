"""Extrator de controle: leitura linear, sem reconstrução posicional.

Não é uma tentativa de extrair bem. É o **piso** da comparação: representa o que
se obtém tratando a página como sequência de palavras na ordem em que o PDF as
emite, que é o comportamento padrão de quem chama `get_text()` e itera.

Existe para responder a uma pergunta que só faz sentido com número: *quanto a
reconstrução posicional realmente ganha?* Sem esse piso, dizer que o extrator
posicional é bom seria afirmação sem régua.

Em tabela rotacionada espera-se que ele erre de forma característica: uma faixa
de Y percorre um atributo de todos os itens, então a leitura linear associa ao
primeiro item os valores que pertencem a todos.
"""

from __future__ import annotations

import re

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, parse_numero
from parser.portas import DocumentoCanonico, Pagina

__all__ = ["ExtratorLinear"]

_ROTULO = re.compile(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{2,})\s*\(([^)]+)\)\s*$")


class ExtratorLinear:
    """Lê a página como sequência e associa rótulo ao valor seguinte."""

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        return [
            registro
            for pagina in documento.paginas
            if (registro := self._extrair_pagina(pagina, documento.identificador))
        ]

    def _extrair_pagina(self, pagina: Pagina, fonte: str) -> Registro | None:
        palavras = pagina.palavras
        if not palavras:
            return None

        campos: dict[str, Campo] = {}
        for i, palavra in enumerate(palavras):
            rotulo = self._como_rotulo(palavra.texto)
            if rotulo is None:
                continue
            proxima = palavras[i + 1] if i + 1 < len(palavras) else None
            campos[rotulo] = self._campo(proxima, pagina.numero)

        if not campos:
            return None
        return Registro(campos=campos, fonte=fonte)

    @staticmethod
    def _como_rotulo(texto: str) -> str | None:
        match = _ROTULO.match(texto.strip())
        return match.group(0).strip() if match else None

    @staticmethod
    def _campo(palavra, pagina: int) -> Campo:
        if palavra is None:
            return Campo.ausente()
        evidencia = Evidencia(
            pagina=pagina,
            bbox=(palavra.x0, palavra.y0, palavra.x1, palavra.y1),
            texto_bruto=palavra.texto,
        )
        try:
            valor, sentinela = parse_numero(palavra.texto)
        except ValorNaoReconhecido:
            return Campo[str].extraido(valor=palavra.texto, evidencia=evidencia)
        return Campo[float].extraido(valor=valor, sentinela=sentinela, evidencia=evidencia)
