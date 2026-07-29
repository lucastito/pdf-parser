"""Apoio comum aos extratores que produzem tabelas como listas de células.

Concentra o que não varia entre pdfplumber, Camelot e OCR: transformar uma matriz
de texto em registros validados. Se cada um convertesse células à sua maneira, a
comparação entre eles mediria a conversão em vez da extração (ADR-0005).
"""

from __future__ import annotations

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, normalizar_texto, parse_numero

__all__ = ["campo_de_celula", "registros_de_matriz"]


def campo_de_celula(celula: str | None, pagina: int, vizinhanca: str | None = None) -> Campo:
    """Converte uma célula de texto num campo com proveniência."""
    texto = (celula or "").strip()
    if not texto:
        return Campo.ausente()

    evidencia = Evidencia(pagina=pagina, texto_bruto=texto, vizinhanca=vizinhanca)
    try:
        valor, sentinela = parse_numero(texto)
    except ValorNaoReconhecido:
        return Campo[str].extraido(valor=normalizar_texto(texto), evidencia=evidencia)
    return Campo[float].extraido(valor=valor, sentinela=sentinela, evidencia=evidencia)


def registros_de_matriz(
    matriz: list[list[str | None]], pagina: int, fonte: str
) -> list[Registro]:
    """Converte uma matriz em registros, usando a primeira linha como cabeçalho.

    Deliberadamente ingênuo: é assim que estas ferramentas devolvem tabela, e
    interpretar além disso mascararia o que elas de fato entregam. Se a matriz não
    corresponder à estrutura real do documento, o resultado ruim **é** o achado.
    """
    if len(matriz) < 2:
        return []

    cabecalho = [normalizar_texto(c or "") for c in matriz[0]]
    linha_bruta = " | ".join(c or "" for c in matriz[0])

    registros = []
    for linha in matriz[1:]:
        campos = {
            nome: campo_de_celula(celula, pagina, vizinhanca=linha_bruta)
            for nome, celula in zip(cabecalho, linha)
            if nome
        }
        if campos:
            registros.append(Registro(campos=campos, fonte=fonte))
    return registros
