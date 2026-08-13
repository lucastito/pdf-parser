"""Conhecimento operacional: o que sabota a extração, e como detectar.

Este módulo existe porque o aprendizado mais caro do projeto estava enterrado
dentro de extratores individuais. A rotação de página derrubava **quatro
ferramentas a zero de acurácia**, e o tratamento vivia duplicado em dois arquivos,
com implementações diferentes — a terceira ferramenta nem tratava. Quem escrevesse
a próxima cairia na mesma armadilha.

São duas famílias de verificação, com propósitos distintos:

**Diagnóstico de documento** — roda *antes* da extração e detecta características
que sabotam ferramentas. Cada achado vem com a ação recomendada; diagnóstico sem
ação é só reclamação.

**Validação de saída** — roda *depois* e pega resultado plausível mas errado. É o
modo de falha que mais custa: passa por validação de tipo, parece dado e chega ao
consumidor. Cobertura alta com valores errados é pior que cobertura baixa.

Nenhuma verificação aqui depende de conhecer o domínio do documento. As faixas de
valor, quando usadas, são parâmetro do perfil.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from parser.modelo import Registro

__all__ = [
    "Achado",
    "MetodoDeDeteccao",
    "Severidade",
    "caracteristicas_do_documento",
    "caracterizar_documento",
    "caracterizar_pagina",
    "contagem_por_caracteristica",
    "diagnosticar",
    "escolher_paginas_de_referencia",
    "paginas_por_caracteristica",
    "relatorio",
    "validar_registros",
]

MINIMO_PARA_ESTATISTICA = 5
"""Abaixo disto, coincidência é explicação mais provável que erro sistemático."""

COBERTURA_MINIMA = 0.30
"""Abaixo disto a extração provavelmente falhou, ainda que sem erro."""


class Severidade(Enum):
    BLOQUEIA = "bloqueia"
    """O resultado não deve ser usado sem investigar."""

    ALERTA = "alerta"
    """Merece atenção, mas pode ser legítimo."""

    NOTA = "nota"
    """Informação para a leitura do resultado."""

    @property
    def grave(self) -> bool:
        return self is Severidade.BLOQUEIA


class MetodoDeDeteccao(Enum):
    """Como uma característica foi descoberta — do mais barato ao mais caro.

    A pergunta não é "esta página tem tabela? tem rotação?" (verificar item a
    item de um catálogo fechado) — é "que método de descoberta achou o quê,
    nesta página?". A característica é a **resposta**, não uma pergunta fixa
    que o código já sabe fazer. O catálogo de características conhecidas
    (ADR-0021) cresce por decisão de quem desenvolve, ao encontrar algo novo
    num documento real — não em tempo de execução, no servidor do cliente.
    """

    METADADO_NATIVO = "metadado-nativo"
    """Propriedade que o PDF já expõe, lida direto da estrutura do arquivo —
    sem calcular nada (ex.: atributo de rotação da página, contagem de
    marcadores `/BaseFont`/`/ToUnicode`)."""

    FERRAMENTA_DETERMINISTICA = "ferramenta-deterministica"
    """Heurística ou cálculo sobre o conteúdo — determinístico (mesmo PDF,
    mesmo resultado sempre), sem chamar rede nem modelo (ex.: tentativa de
    extração de texto, geometria de linha, área de imagem embutida)."""

    LLM_SIMPLES = "llm-simples"
    """Classificação por um modelo pequeno/rápido, para o que geometria e
    heurística não alcançam — ex. domínio do documento ("é relatório
    financeiro ou manual técnico?"), impossível de responder só com
    coordenada. **Nenhum achado usa este método ainda** — é o que falta pro
    eixo C da taxonomia (ADR-0021)."""


@dataclass(frozen=True)
class Achado:
    """Uma característica detectada, com o que fazer a respeito.

    `metodo` é `None` só para os achados de `validar_registros` (validação
    de saída, não característica de página) — todo achado de característica
    declara o método que o descobriu.
    """

    codigo: str
    severidade: Severidade
    detalhe: str
    acao: str
    metodo: MetodoDeDeteccao | None = None


def diagnosticar(caminho: str | Path) -> list[Achado]:
    """Examina o documento antes da extração.

    Levanta:
        FileNotFoundError: arquivo inexistente.
    """
    import fitz

    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

    documento = fitz.open(arquivo)
    try:
        achados: list[Achado] = []
        achados += _checar_rotacao(documento)
        achados += _checar_camada_de_texto(documento)
        achados += _checar_orientacao_do_texto(documento)
        achados += _checar_fontes(documento)
        achados += _checar_imagem_embutida(documento)
        return achados
    finally:
        documento.close()


def caracterizar_documento(caminho: str | Path) -> dict[int, list[Achado]]:
    """`caracterizar_pagina`, para todas as páginas do documento — a forma
    consultável que faltava (−1.4, PLANO.md).

    `diagnosticar` agrega achados no nível do documento, com o número de
    página só citado dentro da string `detalhe` (ex.: "páginas 1, 2, 3…") —
    útil para leitura humana, inútil para perguntar em código "que
    características a página 7 tem". `caracterizar_pagina` responde isso,
    mas uma página de cada vez, exigindo um laço manual de quem quiser o
    documento inteiro. Esta função é esse laço, feito uma vez.

    Levanta:
        FileNotFoundError: arquivo inexistente.
    """
    import fitz

    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")

    documento = fitz.open(arquivo)
    try:
        return {
            numero: caracterizar_pagina(documento, numero)
            for numero in range(1, documento.page_count + 1)
        }
    finally:
        documento.close()


def paginas_por_caracteristica(
    caracterizacao: dict[int, list[Achado]],
) -> dict[str, list[int]]:
    """Inverte `caracterizar_documento`: de "página → achados" para
    "código de característica → páginas que a têm".

    É a forma que a escolha de página de triagem por característica precisa
    (ADR-0021: "uma página por combinação relevante") — sem isso, achar
    "quais páginas têm característica X" exigiria varrer o dicionário na
    mão toda vez. Uma página com várias características aparece em várias
    listas — de propósito: o ADR valoriza exatamente esse caso ("um
    documento pode marcar várias características de uma vez, e esses são os
    melhores").
    """
    paginas: dict[str, list[int]] = {}
    for numero, achados in sorted(caracterizacao.items()):
        for achado in achados:
            paginas.setdefault(achado.codigo, []).append(numero)
    return paginas


def caracteristicas_do_documento(caminho: str | Path) -> set[str]:
    """A característica do documento é a **soma** das características das
    páginas — só se apareceu em alguma, sem dizer onde nem quantas vezes.

    Levanta:
        FileNotFoundError: arquivo inexistente.
    """
    return set(paginas_por_caracteristica(caracterizar_documento(caminho)))


def contagem_por_caracteristica(caminho: str | Path) -> dict[str, int]:
    """Quantas páginas do documento têm cada característica — "quais são as
    maiores características de um PDF", da mais frequente pra menos.

    Levanta:
        FileNotFoundError: arquivo inexistente.
    """
    por_pagina = paginas_por_caracteristica(caracterizar_documento(caminho))
    return dict(
        sorted(
            ((codigo, len(paginas)) for codigo, paginas in por_pagina.items()),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def escolher_paginas_de_referencia(caminho: str | Path) -> dict[str, list[int]]:
    """Escolhe 1 página representante por **combinação distinta** de
    características do documento — nunca uma página por característica
    isolada, o que duplicaria coleta quando páginas diferentes exercitam
    exatamente a mesma combinação (ADR-0021: "a unidade de análise é a
    combinação... a triagem roda uma página por combinação relevante, e
    não uma por eixo").

    A primeira página (em ordem) de cada combinação nova é a escolhida —
    critério simples e determinístico; não há razão para preferir a
    página com mais achados dentro do **mesmo** conjunto exato de códigos,
    já que por definição elas são equivalentes para este propósito.

    Devolve no formato que `Perfil.paginas_de_referencia_por_caracteristica`
    já aceita — mas cada página escolhida entra na lista de **todas** as
    características que ela exibe, não numa lista isolada por
    característica: uma página com 3 características vale como referência
    das 3 ao mesmo tempo, em vez de 3 páginas escolhidas às cegas, uma por
    característica, sem checar se já havia página cobrindo mais de uma.

    Página sem nenhuma característica não entra — não há o que
    referenciar.

    Levanta:
        FileNotFoundError: arquivo inexistente.
    """
    caracterizacao = caracterizar_documento(caminho)

    representante_por_combinacao: dict[frozenset[str], int] = {}
    for numero, achados in sorted(caracterizacao.items()):
        if not achados:
            continue
        combinacao = frozenset(a.codigo for a in achados)
        representante_por_combinacao.setdefault(combinacao, numero)

    paginas_por_codigo: dict[str, list[int]] = {}
    for combinacao, pagina in representante_por_combinacao.items():
        for codigo in combinacao:
            paginas_por_codigo.setdefault(codigo, []).append(pagina)

    return {codigo: sorted(paginas) for codigo, paginas in paginas_por_codigo.items()}


_SONDAS: list[Callable[[Any, int], Achado | None]] = []
"""Registro de sondas de característica — cada uma roda e reporta o que
achar, ou `None`. Adicionar característica nova é registrar uma sonda nova
com `@_sonda`; `caracterizar_pagina` nunca precisa mudar. É a diferença
entre "verificar item a item de um catálogo fechado" e "descobrir o que
houver, do jeito mais barato ao mais caro" — a pergunta é "que
característica tem aqui", a resposta (rotação? imagem? o que for) vem da
sonda, não da pergunta.
"""


def _sonda(fn: Callable[[Any, int], Achado | None]) -> Callable[[Any, int], Achado | None]:
    _SONDAS.append(fn)
    return fn


def caracterizar_pagina(documento, numero: int) -> list[Achado]:
    """Os mesmos achados de `diagnosticar`, restritos a **uma** página.

    Existe para quem precisa decidir por página (o roteador de extração,
    `parser.planejador`) sem duplicar a lógica de detecção. `documento` é um
    `fitz.Document` já aberto — quem chama isto em laço sobre várias páginas do
    mesmo arquivo deve abrir uma vez só e reaproveitar, não reabrir por página.

    Não inclui `_checar_fontes`: mapa de caracteres é propriedade do dicionário
    de fontes do PDF, não de uma página isolada.
    """
    return [achado for sonda in _SONDAS if (achado := sonda(documento, numero)) is not None]


@_sonda
def _sonda_rotacao(documento, numero: int) -> Achado | None:
    if not _pagina_rotacionada(documento, numero):
        return None
    return _achado_rotacao(paginas=[numero], total=documento.page_count)


@_sonda
def _sonda_sem_camada_de_texto(documento, numero: int) -> Achado | None:
    if _pagina_tem_texto(documento, numero):
        return None
    return Achado(
        codigo="sem-camada-de-texto",
        severidade=Severidade.BLOQUEIA,
        detalhe=f"página {numero} não tem texto extraível",
        acao=(
            "Documento digitalizado: use a rota por reconhecimento óptico. "
            "As rotas que dependem da camada de texto não têm o que ler."
        ),
        metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
    )


@_sonda
def _sonda_texto_vertical(documento, numero: int) -> Achado | None:
    verticais, horizontais = _orientacao_da_pagina(documento, numero)
    total_linhas = verticais + horizontais
    if not total_linhas or verticais / total_linhas < 0.30:
        return None
    return Achado(
        codigo="texto-vertical",
        severidade=Severidade.ALERTA,
        detalhe=f"página {numero}: {verticais} de {total_linhas} linhas verticais",
        acao=(
            "Provável tabela rotacionada, em que cada faixa horizontal traz um "
            "atributo de todos os itens em vez de todos os atributos de um item. "
            "Alinhar por posição, não por cabeçalho: o cabeçalho detectado será "
            "lixo, mas as linhas de dados costumam estar íntegras."
        ),
        metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
    )


@_sonda
def _sonda_imagem_embutida(documento, numero: int) -> Achado | None:
    if not _pagina_tem_imagem(documento, numero):
        return None
    return _achado_imagem_embutida(numero)


@_sonda
def _sonda_pagina_em_paisagem(documento, numero: int) -> Achado | None:
    # `mediabox`, não `rect`: `rect` troca largura por altura sob rotação de
    # 90/270° (é o retângulo *renderizado*), o que faria uma página retrato
    # rotacionada contar como paisagem — característica diferente da que
    # `pagina-rotacionada` já cobre, não deveriam se sobrepor.
    caixa = documento[numero - 1].mediabox
    if caixa.width <= caixa.height:
        return None
    return Achado(
        codigo="pagina-em-paisagem",
        severidade=Severidade.NOTA,
        detalhe=f"página {numero}: {caixa.width:.0f}×{caixa.height:.0f}",
        acao=(
            "Geometria de referência (coordenadas de rótulo/valor calibradas noutro "
            "documento) não se transfere direto — orientação diferente muda onde o "
            "conteúdo cai na página."
        ),
        metodo=MetodoDeDeteccao.METADADO_NATIVO,
    )


@_sonda
def _sonda_multiplas_colunas_de_texto(documento, numero: int) -> Achado | None:
    grupos = _colunas_de_texto(documento, numero)
    if len(grupos) < 2:
        return None
    return Achado(
        codigo="multiplas-colunas-de-texto",
        severidade=Severidade.ALERTA,
        detalhe=f"página {numero}: {len(grupos)} colunas de texto distintas",
        acao=(
            "Leitura de texto corrido em ordem de coordenada concatenaria colunas "
            "diferentes numa frase só. Trate cada faixa de X como um fluxo "
            "separado, ou restrinja a extração à coluna de interesse."
        ),
        metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
    )


PALAVRAS_MINIMAS_POR_COLUNA = 15
"""Piso para uma faixa de X contar como coluna de texto, não um elemento
pequeno lateral (célula de cabeçalho de página, número de página, carimbo).

Ponto de partida declarado sobre dois documentos reais de um cenário
corporativo (2026-08-13), mesmo espírito de `AREA_MINIMA_DE_IMAGEM_RELEVANTE`
— não é calibração fina. Sem o piso, um cabeçalho repetido de poucas
palavras (comum a toda página de um documento com cabeçalho/rodapé
tabular) dispararia "múltiplas colunas" em todo documento com esse layout,
mesmo sem nenhuma coluna de texto de verdade."""


def _colunas_de_texto(documento, numero: int) -> list[tuple[float, float, int]]:
    """Agrupa os blocos de texto da página por faixa de X que não se
    sobrepõe — cada grupo é uma "coluna" candidata (x0, x1, palavras).

    Detecta tanto prosa em coluna dupla quanto uma coluna de comentário/nota
    lateral reservada à parte do corpo do texto — geometricamente as duas
    são a mesma coisa: conteúdo textual relevante em faixas de X distintas
    na mesma página. Grupos abaixo de `PALAVRAS_MINIMAS_POR_COLUNA` são
    descartados antes de contar.
    """
    blocos = []
    for bloco in documento[numero - 1].get_text("dict").get("blocks", []):
        if "lines" not in bloco:
            continue
        palavras = sum(
            len(span["text"].split()) for linha in bloco["lines"] for span in linha["spans"]
        )
        if palavras == 0:
            continue
        x0, _, x1, _ = bloco["bbox"]
        blocos.append((x0, x1, palavras))

    grupos: list[list[float | int]] = []
    for x0, x1, palavras in sorted(blocos):
        if grupos and x0 <= grupos[-1][1]:
            grupos[-1][1] = max(grupos[-1][1], x1)
            grupos[-1][2] += palavras
        else:
            grupos.append([x0, x1, palavras])

    return [(g[0], g[1], g[2]) for g in grupos if g[2] >= PALAVRAS_MINIMAS_POR_COLUNA]


LARGURA_MINIMA_DE_LINHA_COLORIDA = 0.35
"""Fração mínima da largura da página que as células preenchidas de uma
linha precisam somar para contar como candidata a linha de tabela.

Descarta preenchimento pequeno (ícone, marcador, sublinhado colorido) que
não é célula de tabela. Ponto de partida declarado sobre dois documentos
reais (2026-08-13), mesmo espírito de `AREA_MINIMA_DE_IMAGEM_RELEVANTE`."""

LINHAS_MINIMAS_TABELA_COLORIDA = 3
"""Abaixo disto (ex.: 1-2 linhas) é mais provável banner/caixa de destaque
do que tabela — uma tabela de verdade tem cabeçalho e ao menos duas linhas
de dado."""


@_sonda
def _sonda_tabela_com_fundo_colorido(documento, numero: int) -> Achado | None:
    linhas = _linhas_de_celulas_coloridas(documento[numero - 1])
    if len(linhas) < LINHAS_MINIMAS_TABELA_COLORIDA:
        return None

    cores = {cor for _, cor in linhas}
    if len(cores) < 2:
        return None

    return Achado(
        codigo="tabela-com-fundo-colorido",
        severidade=Severidade.NOTA,
        detalhe=(
            f"página {numero}: {len(linhas)} linhas de célula colorida, {len(cores)} cores"
        ),
        acao=(
            "Tabela sem linha de grade — o agrupamento visual vem da cor de fundo "
            "(cabeçalho e faixas alternadas), não de borda. Detectores de tabela "
            "que procuram linha reta não têm o que reconhecer aqui; alinhamento "
            "por posição de texto continua funcionando."
        ),
        metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
    )


LIMIAR_QUASE_PRETO = 0.15
"""Preenchimento com os três canais abaixo disto é tratado como linha de
borda, não como cor de tabela — descoberto validando contra documento real
(2026-08-13): tabela com bordas desenhadas como retângulos finos preenchidos
de preto (em vez de traço) produzia dezenas de "linhas", todas pretas;
somada a **uma única** célula de destaque colorida (não relacionada, ex.
texto realçado) em outro ponto da mesma página, isso passava no piso de
"2+ cores distintas" por acidente — a tabela com borda e o destaque isolado
não têm nenhuma relação entre si. Preto é o sinal de "grade desenhada por
preenchimento", que é `tabela com grade`, não `tabela com fundo colorido` —
características diferentes, não implementada a primeira ainda."""


def _linhas_de_celulas_coloridas(pagina) -> list[tuple[float, tuple]]:
    """Agrupa retângulos preenchidos (exceto quase-pretos — ver
    `LIMIAR_QUASE_PRETO`) por Y (arredondado) — cada grupo com 2+ células
    cobrindo uma fração relevante da largura da página é uma linha
    candidata de tabela com fundo colorido, não com borda."""
    area_pagina = pagina.rect.width * pagina.rect.height
    if area_pagina <= 0:
        return []

    tolerancia_y = 2.0
    por_y: dict[float, list[tuple[float, float, tuple]]] = {}
    for desenho in pagina.get_drawings():
        cor = desenho.get("fill")
        if cor is None or all(canal < LIMIAR_QUASE_PRETO for canal in cor):
            continue
        r = desenho["rect"]
        area = r.width * r.height
        if area <= 0 or area / area_pagina > 0.5:
            continue  # maior que meia página: provável fundo, não célula
        y = round(r.y0 / tolerancia_y) * tolerancia_y
        por_y.setdefault(y, []).append((r.x0, r.x1, cor))

    linhas = []
    for y, celulas in por_y.items():
        if len(celulas) < 2:
            continue
        largura_total = sum(x1 - x0 for x0, x1, _ in celulas)
        if largura_total / pagina.rect.width < LARGURA_MINIMA_DE_LINHA_COLORIDA:
            continue
        # Uma linha pode ter mais de uma cor (ex. coluna de destaque numa
        # linha de dado); representá-la pela cor mais comum é suficiente
        # para o que importa aqui — se a *linha* varia em relação às outras.
        cor_da_linha = Counter(c for _, _, c in celulas).most_common(1)[0][0]
        linhas.append((y, cor_da_linha))
    return linhas


def _pagina_rotacionada(documento, numero: int) -> bool:
    return bool(documento[numero - 1].rotation)


def _pagina_tem_texto(documento, numero: int) -> bool:
    return bool(documento[numero - 1].get_text("words"))


def _orientacao_da_pagina(documento, numero: int) -> tuple[int, int]:
    """Linhas (verticais, horizontais) da página, por direção do texto."""
    verticais = horizontais = 0
    for bloco in documento[numero - 1].get_text("dict").get("blocks", []):
        for linha in bloco.get("lines", []):
            direcao = linha.get("dir", (1, 0))
            if abs(direcao[0]) > 0.9:
                horizontais += 1
            else:
                verticais += 1
    return verticais, horizontais


AREA_MINIMA_DE_IMAGEM_RELEVANTE = 0.02
"""Fração mínima da área da página que uma imagem precisa ocupar para contar
como achado.

Sem este piso, `imagem-embutida` disparava em **toda** página de dois
documentos reais de um cenário corporativo usados para testar isto — o
"conteúdo visual" era sempre o mesmo logotipo de cabeçalho, repetido.
Medido nos dois: o logotipo ocupa entre 0,1% e 0,6% da página, sempre na
mesma razão página após página;
o conteúdo real (diagrama, gráfico, mapa) começa a partir de ~2%, com margem
folgada entre as duas faixas — nenhuma imagem caiu no meio.

Ponto de partida declarado sobre **dois** documentos só, não uma calibração.
O risco fica registrado, não escondido: uma imagem pequena mas informativa
(um ícone com valor, por exemplo) ficaria de fora. Entre esse risco e
disparar visão computacional (custo medido de dezenas de minutos por página)
em toda página de todo documento por causa de um logotipo, o piso é a
escolha melhor sustentada pelos dois documentos que existem — revisar
quando houver mais variedade."""


def _pagina_tem_imagem(documento, numero: int) -> bool:
    """Imagem grande o bastante para valer uma leitura por visão — não
    qualquer imagem embutida (ver `AREA_MINIMA_DE_IMAGEM_RELEVANTE`)."""
    pagina = documento[numero - 1]
    area_pagina = pagina.rect.width * pagina.rect.height
    if area_pagina <= 0:
        return False
    for info in pagina.get_image_info():
        bbox = info["bbox"]
        area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        if area / area_pagina >= AREA_MINIMA_DE_IMAGEM_RELEVANTE:
            return True
    return False


def _achado_imagem_embutida(numero: int) -> Achado:
    return Achado(
        codigo="imagem-embutida",
        severidade=Severidade.NOTA,
        detalhe=f"página {numero} contém ao menos uma imagem embutida",
        acao=(
            "Conteúdo visual que a extração de texto não alcança. Se a página "
            "também tiver texto ou tabela reconhecida por outra rota, considere "
            "uma leitura complementar por visão (VLM) — texto e imagem podem "
            "trazer informação diferente na mesma página, e uma rota não "
            "substitui a outra aqui."
        ),
        metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
    )


def _checar_imagem_embutida(documento) -> list[Achado]:
    """Imagem embutida é conteúdo que nenhuma rota de texto alcança.

    ADR-0021 já cataloga esta característica como "pronta" na taxonomia de
    estrutura — mas o código para detectá-la nunca foi escrito. Sem ele, uma
    página com tabela boa e uma figura ao lado tem a figura simplesmente
    nunca olhada, e isso não aparece em lugar nenhum do diagnóstico.
    """
    paginas = [
        i + 1 for i in range(documento.page_count) if _pagina_tem_imagem(documento, i + 1)
    ]
    if not paginas:
        return []

    amostra = ", ".join(str(p) for p in paginas[:5])
    reticencia = "…" if len(paginas) > 5 else ""
    return [
        Achado(
            codigo="imagem-embutida",
            severidade=Severidade.NOTA,
            detalhe=(
                f"{len(paginas)} de {documento.page_count} páginas têm imagem "
                f"embutida (páginas {amostra}{reticencia})"
            ),
            acao=(
                "Conteúdo visual que a extração de texto não alcança. Considere "
                "uma leitura complementar por visão (VLM) nessas páginas, mesmo "
                "quando o texto já foi extraído por outra rota."
            ),
            metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
        )
    ]


def _achado_rotacao(*, paginas: list[int], total: int) -> Achado:
    amostra = ", ".join(str(p) for p in paginas[:5])
    reticencia = "…" if len(paginas) > 5 else ""
    return Achado(
        codigo="pagina-rotacionada",
        severidade=Severidade.BLOQUEIA,
        detalhe=(
            f"{len(paginas)} de {total} páginas declaram rotação "
            f"(páginas {amostra}{reticencia})"
        ),
        acao=(
            "Desrotacione antes de detectar tabela: com a rotação ativa, os "
            "detectores encontram zero tabelas. Se renderizar para imagem, "
            "converta as coordenadas de volta ao espaço não rotacionado — a "
            "renderização aplica a rotação, a extração de texto não."
        ),
        metodo=MetodoDeDeteccao.METADADO_NATIVO,
    )


def _checar_rotacao(documento) -> list[Achado]:
    """Rotação declarada é a armadilha mais custosa já encontrada.

    Com `rotation=90` ativa, detectores de tabela encontram **zero** tabelas.
    Desrotacionada, a mesma página rende extração correta. Além disso, a
    renderização aplica a rotação enquanto a extração de texto não — os dois
    sistemas de coordenadas divergem em silêncio.
    """
    rotacionadas = [
        i + 1 for i in range(documento.page_count) if _pagina_rotacionada(documento, i + 1)
    ]
    if not rotacionadas:
        return []

    return [_achado_rotacao(paginas=rotacionadas, total=documento.page_count)]


def _checar_camada_de_texto(documento) -> list[Achado]:
    """Sem texto nativo, só a rota por reconhecimento óptico é possível."""
    amostra = range(min(10, documento.page_count))
    com_texto = sum(1 for i in amostra if _pagina_tem_texto(documento, i + 1))

    if com_texto == 0:
        return [
            Achado(
                codigo="sem-camada-de-texto",
                severidade=Severidade.BLOQUEIA,
                detalhe="nenhuma das páginas amostradas tem texto extraível",
                acao=(
                    "Documento digitalizado: use a rota por reconhecimento óptico. "
                    "As rotas que dependem da camada de texto não têm o que ler."
                ),
                metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
            )
        ]
    if com_texto < len(list(amostra)):
        return [
            Achado(
                codigo="camada-de-texto-parcial",
                severidade=Severidade.ALERTA,
                detalhe=f"{com_texto} de {len(list(amostra))} páginas amostradas têm texto",
                acao=(
                    "Documento misto. Triar por página e rotear cada uma para a "
                    "estratégia adequada, em vez de aplicar uma só ao documento todo."
                ),
                metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
            )
        ]
    return []


def _checar_orientacao_do_texto(documento) -> list[Achado]:
    """Texto vertical indica tabela rotacionada — o layout que quebra o
    pressuposto de que uma linha corresponde a um registro."""
    verticais = horizontais = 0
    for i in range(min(5, documento.page_count)):
        v, h = _orientacao_da_pagina(documento, i + 1)
        verticais += v
        horizontais += h

    total = verticais + horizontais
    if not total or verticais / total < 0.30:
        return []

    return [
        Achado(
            codigo="texto-vertical",
            severidade=Severidade.ALERTA,
            detalhe=f"{verticais} de {total} linhas de texto amostradas são verticais",
            acao=(
                "Provável tabela rotacionada, em que cada faixa horizontal traz um "
                "atributo de todos os itens em vez de todos os atributos de um item. "
                "Alinhar por posição, não por cabeçalho: o cabeçalho detectado será "
                "lixo, mas as linhas de dados costumam estar íntegras."
            ),
            metodo=MetodoDeDeteccao.FERRAMENTA_DETERMINISTICA,
        )
    ]


def _checar_fontes(documento) -> list[Achado]:
    """Fonte CID com mapa de caracteres incompleto corrompe extração ingênua.

    Medido no documento-caso: 5 mapas para 31 fontes, e leitura direta do fluxo
    rendeu 89 palavras reais em 534 mil caracteres.
    """
    bruto = documento.write() if documento.page_count < 50 else b""
    if not bruto:
        return []

    fontes = bruto.count(b"/BaseFont")
    mapas = bruto.count(b"/ToUnicode")
    if fontes and mapas < fontes / 2:
        return [
            Achado(
                codigo="mapa-de-caracteres-incompleto",
                severidade=Severidade.ALERTA,
                detalhe=f"{mapas} mapas ToUnicode para {fontes} fontes declaradas",
                acao=(
                    "Não leia o fluxo de conteúdo diretamente: sem o mapa, os bytes "
                    "não são o texto. Use biblioteca que aplique ToUnicode."
                ),
                metodo=MetodoDeDeteccao.METADADO_NATIVO,
            )
        ]
    return []


def validar_registros(
    registros: list[Registro],
    *,
    faixas: dict[str, tuple[float, float]] | None = None,
) -> list[Achado]:
    """Examina o resultado da extração.

    Args:
        faixas: por campo, o intervalo plausível. Parâmetro do perfil — este
            módulo não conhece domínio nenhum.
    """
    if not registros:
        return [
            Achado(
                codigo="nenhum-registro",
                severidade=Severidade.BLOQUEIA,
                detalhe="a extração não produziu registro algum",
                acao=(
                    "Verifique o diagnóstico do documento antes de concluir que a "
                    "estratégia falhou. Rotação de página e ausência de camada de "
                    "texto produzem esse sintoma."
                ),
            )
        ]

    achados: list[Achado] = []
    achados += _checar_identificadores(registros)
    achados += _checar_cobertura(registros)
    achados += _checar_valores_constantes(registros)
    if faixas:
        achados += _checar_faixas(registros, faixas)
    return achados


def _checar_identificadores(registros: list[Registro]) -> list[Achado]:
    """Identificador sem número indica cabeçalho lido como item.

    Sintoma observado: `{'Carbo-': 'idrato'}` — a ferramenta tomou o cabeçalho
    partido em duas linhas por dados, e produziu volume que parece registro.
    """
    com_identificador = [
        r for r in registros if (c := r.campos.get("identificador")) and c.preenchido
    ]
    if not com_identificador:
        return [
            Achado(
                codigo="sem-identificador",
                severidade=Severidade.BLOQUEIA,
                detalhe=f"nenhum dos {len(registros)} registros tem identificador",
                acao=(
                    "Sem identificador não há como alinhar com gabarito nem com outra "
                    "estratégia. Verifique se o cabeçalho está sendo lido como dado."
                ),
            )
        ]

    sem_numero = [
        r
        for r in com_identificador
        if not str(r.campos["identificador"].valor or "").strip()[:1].isdigit()
    ]
    if len(sem_numero) > len(com_identificador) / 2:
        exemplo = str(sem_numero[0].campos["identificador"].valor)[:40]
        return [
            Achado(
                codigo="identificador-sem-numero",
                severidade=Severidade.BLOQUEIA,
                detalhe=(
                    f"{len(sem_numero)} de {len(com_identificador)} identificadores não "
                    f"começam por número (ex.: {exemplo!r})"
                ),
                acao=(
                    "Provável cabeçalho lido como item. Alinhe por posição em vez de "
                    "cabeçalho, e descarte linhas que não comecem por identificador."
                ),
            )
        ]
    return []


def _checar_cobertura(registros: list[Registro]) -> list[Achado]:
    total = sum(len(r.campos) for r in registros)
    preenchidos = sum(1 for r in registros for c in r.campos.values() if c.preenchido)
    if not total:
        return []

    cobertura = preenchidos / total
    if cobertura >= COBERTURA_MINIMA:
        return []
    return [
        Achado(
            codigo="cobertura-baixa",
            severidade=Severidade.ALERTA,
            detalhe=f"{cobertura:.0%} dos campos preenchidos ({preenchidos}/{total})",
            acao=(
                "Verifique o alinhamento de colunas e a tolerância de coordenadas. "
                "Resolução alta demais também reduz cobertura, ao dessincronizar a "
                "tolerância expressa em pontos tipográficos."
            ),
        )
    ]


def _checar_valores_constantes(registros: list[Registro]) -> list[Achado]:
    """Mesmo valor em todo item sugere coluna lida errado.

    Com poucos itens é coincidência plausível; com muitos, não.
    """
    if len(registros) < MINIMO_PARA_ESTATISTICA:
        return []

    achados = []
    nomes = {n for r in registros for n in r.campos if n != "identificador"}
    for nome in sorted(nomes):
        valores = [
            r.campos[nome].valor
            for r in registros
            if nome in r.campos
            and r.campos[nome].preenchido
            and r.campos[nome].valor is not None
        ]
        if len(valores) < MINIMO_PARA_ESTATISTICA:
            continue
        contagem = Counter(valores)
        valor, ocorrencias = contagem.most_common(1)[0]
        if ocorrencias == len(valores):
            achados.append(
                Achado(
                    codigo="valor-constante",
                    severidade=Severidade.ALERTA,
                    detalhe=(
                        f"campo {nome!r}: valor {valor!r} em todos os " f"{len(valores)} itens"
                    ),
                    acao=(
                        "Improvável em dado real. Verifique se a coluna correta está "
                        "sendo lida — um deslocamento produz valores plausíveis e "
                        "todos errados."
                    ),
                )
            )
    return achados


def _checar_faixas(
    registros: list[Registro], faixas: dict[str, tuple[float, float]]
) -> list[Achado]:
    """Valor fora da faixa plausível.

    Pega o erro característico do reconhecimento óptico: a vírgula decimal perdida
    multiplica o valor por dez, produzindo um número que passa por validação de
    tipo e chega ao consumidor.
    """
    achados = []
    for nome, (minimo, maximo) in faixas.items():
        fora = []
        for registro in registros:
            campo = registro.campos.get(nome)
            if not campo or not campo.preenchido or campo.sentinela is not None:
                continue
            valor = campo.valor
            if isinstance(valor, (int, float)) and not minimo <= valor <= maximo:
                fora.append(valor)
        if fora:
            achados.append(
                Achado(
                    codigo="fora-da-faixa",
                    severidade=Severidade.ALERTA,
                    detalhe=(
                        f"campo {nome!r}: {len(fora)} valor(es) fora de "
                        f"[{minimo}, {maximo}] (ex.: {fora[:3]})"
                    ),
                    acao=(
                        "Verifique perda de separador decimal — é o erro típico do "
                        "reconhecimento óptico, e produz valores dez vezes maiores "
                        "que passam por validação de tipo."
                    ),
                )
            )
    return achados


def relatorio(achados: list[Achado]) -> str:
    """Formata os achados, mais graves primeiro."""
    if not achados:
        return "nenhum achado"

    ordem = {Severidade.BLOQUEIA: 0, Severidade.ALERTA: 1, Severidade.NOTA: 2}
    linhas = []
    for achado in sorted(achados, key=lambda a: ordem[a.severidade]):
        linhas.append(f"[{achado.severidade.value.upper()}] {achado.codigo}")
        linhas.append(f"  {achado.detalhe}")
        linhas.append(f"  → {achado.acao}")
        linhas.append("")
    return "\n".join(linhas).rstrip()
