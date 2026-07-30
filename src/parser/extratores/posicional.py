"""Extrator que reconstrói tabelas a partir das coordenadas das palavras.

Existe porque detectores de tabela baseados em linhas de grade não têm o que
detectar em documentos que separam colunas apenas por alinhamento visual — e
porque leitura linear embaralha tabelas rotacionadas, em que uma faixa de Y
percorre *um atributo de todos os itens* em vez de *todos os atributos de um item*.

A estratégia é indexar por posição: agrupar rótulos por faixa de Y, agrupar
valores por coluna de X, e cruzar os dois eixos. O resultado é uma transposição
explícita, com cada valor carregando página e bbox como evidência.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, normalizar_texto, parse_numero
from parser.portas import DocumentoCanonico, Pagina, Palavra

__all__ = ["ExtratorPosicional", "LayoutTabela"]


@dataclass(frozen=True)
class LayoutTabela:
    """Descreve onde, na página, cada parte da tabela se encontra.

    Isolar o layout do algoritmo mantém o extrator agnóstico: outro documento
    com a mesma patologia é atendido trocando estes números, sem tocar no código.

    Todos os valores estão em pontos tipográficos, no sistema de coordenadas do
    PDF (origem no topo-esquerda).
    """

    x_rotulos: tuple[float, float]
    """Faixa de X onde ficam os nomes dos atributos."""

    x_unidades: tuple[float, float]
    """Faixa de X onde ficam as unidades.

    A unidade — não o nome — é o que ancora verticalmente cada faixa de valores.
    Quando um atributo é publicado em duas unidades (por exemplo energia em kJ e
    em kcal), o nome aparece uma vez só, a meio caminho entre as duas linhas de
    valores, e usá-lo como âncora erra ambas.
    """

    x_valores_min: float
    """A partir de onde começam as colunas de valores."""

    y_identificadores_min: float
    """A partir de onde começam os nomes dos itens (área inferior da página)."""

    tolerancia_y: float = 6.0
    """Distância vertical máxima para considerar duas palavras na mesma faixa."""

    tolerancia_x: float = 6.0
    """Distância horizontal máxima para considerar duas palavras na mesma coluna."""

    y_rotulo_max: float | None = None
    """Limite inferior da área de rótulos, se houver texto abaixo a ignorar."""

    distancia_rotulo_max: float = 40.0
    """Quão longe uma unidade pode estar do nome do atributo a que pertence."""


@dataclass
class _Coluna:
    """Uma coluna de valores, ancorada num X."""

    x: float
    palavras: list[Palavra] = field(default_factory=list)


class ExtratorPosicional:
    """Reconstrói registros cruzando faixas de Y com colunas de X."""

    def __init__(self, layout: LayoutTabela) -> None:
        self.layout = layout

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        registros: list[Registro] = []
        for pagina in documento.paginas:
            registros.extend(self._extrair_pagina(pagina, documento.identificador))
        return registros

    def _extrair_pagina(self, pagina: Pagina, fonte: str) -> list[Registro]:
        rotulos = self._rotulos_por_faixa(pagina)
        if not rotulos:
            return []

        identificadores = self._identificadores_por_coluna(pagina)
        if not identificadores:
            return []

        valores = self._valores_por_faixa(pagina)

        registros = []
        for x, nome in sorted(identificadores.items()):
            campos = self._campos_do_item(x, rotulos, valores, pagina.numero)
            if not campos:
                continue
            campos["identificador"] = Campo[str].extraido(
                valor=nome,
                evidencia=Evidencia(pagina=pagina.numero, texto_bruto=nome),
            )
            registros.append(Registro(campos=campos, fonte=fonte))
        return registros

    def _rotulos_por_faixa(self, pagina: Pagina) -> dict[float, str]:
        """Mapeia cada faixa de valores ao nome do atributo correspondente.

        A âncora é a **unidade**, porque é ela que se alinha aos valores. O nome
        do atributo é então buscado como o mais próximo verticalmente. Isso
        resolve o caso de um atributo publicado em duas unidades: cada unidade
        recebe sua própria faixa, ambas remetendo ao mesmo nome, e o rótulo
        final desambigua com a unidade — `Energia (kJ)` e `Energia (kcal)`.
        """
        nomes = self._palavras_por_faixa(pagina, self.layout.x_rotulos)
        unidades = self._palavras_por_faixa(pagina, self.layout.x_unidades)

        rotulos: dict[float, str] = {}
        for y_unidade, palavras_unidade in unidades.items():
            unidade = normalizar_texto(" ".join(p.texto for p in palavras_unidade))
            nome = self._nome_mais_proximo(nomes, y_unidade)
            if not nome:
                continue
            rotulos[y_unidade] = f"{nome} {unidade}".strip()
        return rotulos

    def _palavras_por_faixa(
        self, pagina: Pagina, faixa_x: tuple[float, float]
    ) -> dict[float, list[Palavra]]:
        x_min, x_max = faixa_x
        faixas: dict[float, list[Palavra]] = defaultdict(list)
        for palavra in pagina.palavras:
            if not (x_min <= palavra.x0 <= x_max):
                continue
            if self.layout.y_rotulo_max is not None and palavra.y0 > self.layout.y_rotulo_max:
                continue
            chave = self._faixa_existente(faixas, palavra.centro_y, self.layout.tolerancia_y)
            faixas[chave].append(palavra)
        return faixas

    def _nome_mais_proximo(self, nomes: dict[float, list[Palavra]], y: float) -> str | None:
        candidatos = [
            (abs(y_nome - y), y_nome)
            for y_nome in nomes
            if abs(y_nome - y) <= self.layout.distancia_rotulo_max
        ]
        if not candidatos:
            return None
        _, y_nome = min(candidatos)
        palavras = sorted(nomes[y_nome], key=lambda p: p.y0)
        return normalizar_texto(" ".join(p.texto for p in palavras)) or None

    def _valores_por_faixa(self, pagina: Pagina) -> dict[float, list[Palavra]]:
        """Agrupa os valores numéricos por faixa de Y."""
        candidatas = [
            p
            for p in pagina.palavras
            if p.x0 >= self.layout.x_valores_min and p.y0 < self.layout.y_identificadores_min
        ]

        faixas: dict[float, list[Palavra]] = defaultdict(list)
        for palavra in candidatas:
            chave = self._faixa_existente(faixas, palavra.centro_y, self.layout.tolerancia_y)
            faixas[chave].append(palavra)
        return faixas

    def _identificadores_por_coluna(self, pagina: Pagina) -> dict[float, str]:
        """Reconstrói o nome de cada item a partir da sua coluna vertical.

        O texto é escrito de baixo para cima: ordenar por Y decrescente devolve
        a ordem de leitura.
        """
        candidatas = [
            p
            for p in pagina.palavras
            if p.y0 >= self.layout.y_identificadores_min and p.x0 >= self.layout.x_valores_min
        ]

        colunas: dict[float, list[Palavra]] = defaultdict(list)
        for palavra in candidatas:
            chave = self._faixa_existente(colunas, palavra.x0, self.layout.tolerancia_x)
            colunas[chave].append(palavra)

        identificadores = {}
        for x, palavras in colunas.items():
            ordenadas = sorted(palavras, key=lambda p: p.y0, reverse=True)
            texto = normalizar_texto(" ".join(p.texto for p in ordenadas))
            if texto:
                identificadores[x] = texto
        return identificadores

    def _campos_do_item(
        self,
        x_item: float,
        rotulos: dict[float, str],
        valores: dict[float, list[Palavra]],
        pagina: int,
    ) -> dict[str, Campo]:
        """Cruza a coluna do item com cada faixa de atributo."""
        campos: dict[str, Campo] = {}
        for y, rotulo in rotulos.items():
            faixa = self._faixa_proxima(valores, y)
            palavra = self._valor_na_coluna(faixa, x_item)
            campos[rotulo] = self._campo(palavra, pagina, faixa)
        return campos

    def _faixa_proxima(self, valores: dict[float, list[Palavra]], y: float) -> list[Palavra]:
        """Busca a faixa de valores correspondente a um Y de rótulo.

        Rótulo e valores são agrupados independentemente, então suas chaves de Y
        raramente coincidem ao decimal — casá-las por igualdade exata devolveria
        vazio para todas as faixas.
        """
        for y_valor, palavras in valores.items():
            if abs(y_valor - y) <= self.layout.tolerancia_y:
                return palavras
        return []

    def _valor_na_coluna(self, palavras: list[Palavra], x: float) -> Palavra | None:
        for palavra in palavras:
            if abs(palavra.x0 - x) <= self.layout.tolerancia_x:
                return palavra
        return None

    @staticmethod
    def _vizinhanca(palavra: Palavra, faixa: list[Palavra], janela: int = 2) -> str:
        """Texto imediatamente à esquerda e à direita, na mesma faixa.

        Guardar o entorno custa pouco agora e é impossível de recuperar depois:
        quando a saída já foi gravada, o documento original pode não estar mais
        à mão para quem precisa auditar um valor suspeito.
        """
        ordenadas = sorted(faixa, key=lambda p: p.x0)
        try:
            indice = ordenadas.index(palavra)
        except ValueError:
            return palavra.texto
        inicio = max(0, indice - janela)
        fim = min(len(ordenadas), indice + janela + 1)
        return " ".join(p.texto for p in ordenadas[inicio:fim])

    @staticmethod
    def _campo(
        palavra: Palavra | None, pagina: int, faixa: list[Palavra] | None = None
    ) -> Campo:
        if palavra is None:
            return Campo.ausente()

        evidencia = Evidencia(
            pagina=pagina,
            bbox=(palavra.x0, palavra.y0, palavra.x1, palavra.y1),
            texto_bruto=palavra.texto,
            vizinhanca=(ExtratorPosicional._vizinhanca(palavra, faixa) if faixa else None),
        )
        try:
            valor, sentinela = parse_numero(palavra.texto)
        except ValorNaoReconhecido:
            return Campo[str].extraido(valor=palavra.texto, evidencia=evidencia)
        return Campo[float].extraido(valor=valor, sentinela=sentinela, evidencia=evidencia)

    @staticmethod
    def _faixa_existente(faixas: dict, coordenada: float, tolerancia: float) -> float:
        for chave in faixas:
            if abs(chave - coordenada) <= tolerancia:
                return chave
        return coordenada
