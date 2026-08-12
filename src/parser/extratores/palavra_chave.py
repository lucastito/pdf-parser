"""Extração por palavra-chave: acha valor em texto corrido, sem tabela.

Existe para o degrau que faltava entre "nada a tentar" e "manda pro modelo".
Uma página classificada como `Classe.CONTEXTO` (texto real, mas não é tabela
densa) pode conter exatamente o valor que o schema de destino pede — só não
em forma de tabela. Regex e proximidade de rótulo acham isso sem depender de
LLM, sempre que o nome do campo (ou um sinônimo declarado) aparecer perto de
algo que pareça um valor.

**O que isto não faz:** entender a frase. É casamento de string com distância
em caracteres, não compreensão — quando o rótulo não aparece perto de nada
que pareça valor, o campo simplesmente não é encontrado. Falha por omissão,
nunca por invenção: é o mesmo princípio dos demais extratores determinísticos
do projeto.

Depende de um vocabulário declarado (`parser.vocabulario.CampoEsperado`) —
sem ele não há o que procurar. É por isso que esta rota só existe para quem
declara um schema de destino; um núcleo agnóstico, sem vocabulário nenhum,
não tem como usá-la.
"""

from __future__ import annotations

import re

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, normalizar_texto, parse_numero
from parser.portas import DocumentoCanonico
from parser.vocabulario import CampoEsperado

__all__ = ["ExtratorPorPalavraChave"]

CONFIANCA_PALAVRA_CHAVE = 0.6
"""Menor que a extração geométrica (1.0, implícita) e que a de modelo (0.8,
marcador): é casamento de string com vizinhança, sem entender a frase — erra
o valor mais vezes que as outras duas quando há mais de um número por perto.
Ponto de partida declarado, não medido; calibrar quando houver gabarito de
página de texto corrido.
"""

JANELA_DE_CARACTERES = 120
"""Distância máxima, em caracteres, entre o fim do rótulo e o valor
candidato. Maior que isso, a chance de casar o número de outra frase cresce
mais do que o alcance ajuda. Ponto de partida declarado, a calibrar contra
documento real — não medido ainda."""

_PADRAO_VALOR = re.compile(r"[-+]?\d+(?:[.,]\d{3})*(?:[.,]\d+)?")
"""Só o número — nunca a unidade junto. `parser.normalizacao.parse_numero`
(o mesmo que todo extrator do projeto usa) exige a string **inteira**
numérica; devolver "1850 m" a faria falhar e o campo cairia como texto em vez
de número. A unidade permanece legível na vizinhança (o trecho ao redor),
só não faz parte do valor casado.
"""


class ExtratorPorPalavraChave:
    """Procura, em texto corrido, o valor mencionado perto do rótulo de cada
    campo esperado — nome ou sinônimo, sem diferenciar caixa nem posição
    exata. Um `Registro` por página com achado, reunindo todos os campos
    encontrados nela; página sem achado nenhum não produz registro.

    **Limite declarado:** busca só **depois** da ocorrência do rótulo no
    texto. Frases em que o valor vem antes do rótulo ("1850 metros de lâmina
    d'água") não são cobertas nesta versão — não foi medido o quanto isso
    importa em documento real.
    """

    def __init__(self, campos: list[CampoEsperado]) -> None:
        self.campos = campos

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        registros: list[Registro] = []
        for pagina in documento.paginas:
            achados = self._achar_na_pagina(pagina.texto, pagina.numero)
            if not achados:
                continue
            achados["identificador"] = Campo[str].extraido(
                valor=f"{documento.identificador} p.{pagina.numero}",
                evidencia=Evidencia(pagina=pagina.numero, texto_bruto=""),
            )
            registros.append(Registro(campos=achados, fonte=documento.identificador))
        return registros

    def _achar_na_pagina(self, texto: str, pagina: int) -> dict[str, Campo]:
        minusculo = texto.lower()
        achados: dict[str, Campo] = {}

        for campo in self.campos:
            posicao = self._posicao_do_rotulo(minusculo, campo)
            if posicao is None:
                continue

            fim_do_rotulo = posicao + max(len(r) for r in campo.rotulos())
            trecho = texto[fim_do_rotulo : fim_do_rotulo + JANELA_DE_CARACTERES]
            valor_bruto = self._primeiro_valor(trecho)
            if valor_bruto is None:
                continue

            achados[campo.nome] = self._campo(valor_bruto, pagina, trecho)

        return achados

    @staticmethod
    def _posicao_do_rotulo(minusculo: str, campo: CampoEsperado) -> int | None:
        posicoes = [
            minusculo.find(rotulo.lower())
            for rotulo in campo.rotulos()
            if rotulo and minusculo.find(rotulo.lower()) != -1
        ]
        return min(posicoes) if posicoes else None

    @staticmethod
    def _primeiro_valor(trecho: str) -> str | None:
        casado = _PADRAO_VALOR.search(trecho)
        if not casado or not casado.group(0).strip():
            return None
        return casado.group(0).strip()

    @staticmethod
    def _campo(valor_bruto: str, pagina: int, trecho: str) -> Campo:
        evidencia = Evidencia(
            pagina=pagina, texto_bruto=valor_bruto, vizinhanca=trecho.strip()
        )
        try:
            valor, sentinela = parse_numero(valor_bruto)
        except ValorNaoReconhecido:
            return Campo[str].extraido(
                valor=normalizar_texto(valor_bruto),
                evidencia=evidencia,
                confianca=CONFIANCA_PALAVRA_CHAVE,
            )
        return Campo[float].extraido(
            valor=valor,
            sentinela=sentinela,
            evidencia=evidencia,
            confianca=CONFIANCA_PALAVRA_CHAVE,
        )
