"""Apoio comum aos extratores que produzem tabelas como listas de células.

Concentra o que não varia entre pdfplumber, Camelot e OCR: transformar uma matriz
de texto em registros validados. Se cada um convertesse células à sua maneira, a
comparação entre eles mediria a conversão em vez da extração (ADR-0005).
"""

from __future__ import annotations

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, normalizar_texto, parse_numero

__all__ = ["campo_de_celula", "registros_de_matriz", "registros_por_posicao"]


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


def registros_por_posicao(
    matriz: list[list[str | None]],
    pagina: int,
    fonte: str,
    campos_ordenados: list[str],
) -> list[Registro]:
    """Converte uma matriz alinhando valores por **ordem de aparição**.

    Serve às tabelas em que a primeira linha não é um cabeçalho utilizável — caso
    comum quando o cabeçalho vem rotacionado, partido em várias linhas ou disperso
    em células vazias. Aí o cabeçalho detectado é lixo, mas as linhas de dados
    estão íntegras e na ordem certa.

    A linha é reconhecida como item quando começa por um número inteiro isolado
    (o identificador), e o nome do item é a junção das células de texto seguintes —
    que a detecção costuma fragmentar (``"Biscoito, s" | "ado, cream" | "cracker"``).

    Isto **não** é interpretar além do que a ferramenta entrega: os valores são
    exatamente os que ela devolveu, só reordenados pela posição em vez de por um
    cabeçalho inexistente.
    """
    registros = []

    for linha in matriz:
        celulas = [str(c).strip() for c in linha if c and str(c).strip()]
        if not celulas or not celulas[0].isdigit():
            continue

        identificador = celulas[0]
        nome_partes: list[str] = []
        valores: list[str] = []

        for celula in celulas[1:]:
            if _parece_numero(celula):
                valores.append(celula)
            elif not valores:
                # Texto antes do primeiro número faz parte do nome.
                nome_partes.append(celula)

        if not valores:
            continue

        campos: dict[str, Campo] = {
            "identificador": campo_de_celula(
                f"{identificador} {' '.join(nome_partes)}".strip(), pagina
            )
        }
        for nome, valor in zip(campos_ordenados, valores):
            campos[nome] = campo_de_celula(valor, pagina, vizinhanca=" | ".join(celulas))

        registros.append(Registro(campos=campos, fonte=fonte))

    return registros


def _parece_numero(texto: str) -> bool:
    """Célula que é valor, incluindo sentinelas do documento."""
    limpo = texto.strip()
    if limpo in ("Tr", "tr", "NA", "na", "*"):
        return True
    return bool(limpo) and all(c.isdigit() or c in ",.-" for c in limpo)
