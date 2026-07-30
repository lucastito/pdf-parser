"""Ingestão em lote: uma pasta de documentos, uma saída consolidada.

É o núcleo do produto. O caso de uso real não é um arquivo por vez — é alguém
entregando um diretório com dezenas de documentos heterogêneos e esperando a
planilha preenchida, com o mínimo de intervenção manual.

Três princípios estruturam o módulo:

**Um arquivo é lote de tamanho 1.** Não há caminho especial para o caso único, o
que impede o comportamento de divergir entre um e cem documentos.

**Uma falha não custa o lote.** Numa pasta de cem arquivos, abortar no terceiro
desperdiça o processamento dos outros noventa e sete. Cada falha é registrada com o
motivo e a ação recomendada, e o lote segue.

**Tudo é rastreável.** Cada linha da saída carrega o arquivo de origem, a página, a
estratégia usada e a confiança. Quem revisar precisa saber onde conferir; sem isso,
a alternativa é reconferir tudo.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from parser.modelo import Registro

__all__ = ["Falha", "Lote", "Pendencia", "ResultadoLote", "ingerir"]

EXTENSOES_SUPORTADAS = {".pdf"}
"""Formatos com adapter implementado.

Outros formatos são declaráveis no perfil e falham alto ao serem usados — ver
`fontes/stub.py`. Ignorá-los silenciosamente aqui evita que um arquivo de texto
solto na pasta do cliente vire falha ruidosa.
"""

CONFIANCA_MINIMA_DE_CALIBRACAO = 0.75
"""Abaixo disto, o layout descoberto não é usado — recorre-se ao perfil informado."""


@dataclass
class Falha:
    """Um arquivo que não pôde ser processado."""

    arquivo: str
    motivo: str
    acao: str

    def __str__(self) -> str:
        return f"{self.arquivo}: {self.motivo}"


@dataclass
class Pendencia:
    """Um campo esperado que nenhum documento do lote trouxe.

    Existe para o revisor humano receber uma lista curta do que falta, em vez da
    planilha inteira para conferir.
    """

    item: str
    campo: str
    motivo: str
    procurar_em: list[str] = field(default_factory=list)


@dataclass
class ResultadoLote:
    """O que aconteceu na ingestão."""

    pasta: str
    arquivos_encontrados: int = 0
    processados: int = 0
    segundos: float = 0.0
    registros: list[Registro] = field(default_factory=list, repr=False)
    falhas: list[Falha] = field(default_factory=list)
    pendencias: list[Pendencia] = field(default_factory=list)
    log: list[str] = field(default_factory=list, repr=False)

    def resumo(self) -> str:
        linhas = [
            f"entrada    : {self.pasta}",
            f"arquivos   : {self.arquivos_encontrados} encontrados, "
            f"{self.processados} processados, {len(self.falhas)} com falha",
            f"registros  : {len(self.registros)}",
            f"tempo      : {self.segundos:.1f}s",
        ]
        if self.pendencias:
            linhas.append(f"pendências : {len(self.pendencias)} campo(s) sem dado no lote")
        if self.falhas:
            linhas.append("")
            linhas.append("Arquivos com falha:")
            for falha in self.falhas[:10]:
                linhas.append(f"  {falha.arquivo}")
                linhas.append(f"    {falha.motivo}")
                linhas.append(f"    → {falha.acao}")
            if len(self.falhas) > 10:
                linhas.append(f"  ... e mais {len(self.falhas) - 10}")
        return "\n".join(linhas)


class Lote:
    """Um conjunto de documentos a processar."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)

    def arquivos(self) -> list[Path]:
        """Documentos com formato suportado, em ordem estável.

        Ordem estável importa: duas execuções sobre a mesma pasta devem produzir a
        mesma saída, na mesma ordem, para que a comparação seja possível.
        """
        if not self.caminho.exists():
            raise FileNotFoundError(f"caminho não encontrado: {self.caminho}")

        if self.caminho.is_file():
            return (
                [self.caminho] if self.caminho.suffix.lower() in EXTENSOES_SUPORTADAS else []
            )

        return sorted(
            p
            for p in self.caminho.rglob("*")
            if p.is_file() and p.suffix.lower() in EXTENSOES_SUPORTADAS
        )


def ingerir(
    entrada: str | Path,
    *,
    saida: str | Path | None = None,
    perfil: Any = None,
    campos_esperados: list[str] | None = None,
    calibrar_por_arquivo: bool = True,
) -> ResultadoLote:
    """Processa todos os documentos de uma pasta e consolida o resultado.

    Args:
        saida: caminho do CSV. Grava também `.log` e `.erros.json` ao lado.
            Omitido, nada é escrito em disco.
        perfil: configuração a usar quando a calibração automática não tiver
            confiança suficiente.
        campos_esperados: campos que o destino exige. Os que faltarem entram como
            pendência, para revisão humana dirigida.
        calibrar_por_arquivo: descobre o layout de cada documento. Desligar força o
            uso do perfil para todos — útil quando a pasta é homogênea e o perfil
            já está validado.

    A ordem de decisão por arquivo é: layout descoberto (se confiável) → perfil
    informado → falha registrada com diagnóstico. O cliente não garante que a pasta
    seja homogênea, então decidir por arquivo é o comportamento correto.
    """
    inicio = time.perf_counter()
    lote = Lote(entrada)
    arquivos = lote.arquivos()

    # Erro de perfil é igual para todos os arquivos: verificar uma vez, antes do
    # laço, troca cem falhas idênticas por um erro no lugar certo. Sem isto, uma
    # pasta de cem documentos gastaria a extração inteira para repetir a mesma
    # mensagem cem vezes.
    _validar_perfil(perfil)

    resultado = ResultadoLote(pasta=str(entrada), arquivos_encontrados=len(arquivos))

    for arquivo in arquivos:
        try:
            registros, nota = _processar(arquivo, perfil, calibrar_por_arquivo)
            resultado.registros.extend(registros)
            resultado.processados += 1
            resultado.log.append(f"{arquivo.name}: {len(registros)} registro(s) — {nota}")
        except Exception as erro:  # noqa: BLE001 — a falha é dado, não interrupção
            falha = _classificar(arquivo, erro)
            resultado.falhas.append(falha)
            resultado.log.append(f"{arquivo.name}: FALHA — {falha.motivo}")

    if campos_esperados:
        resultado.pendencias = _levantar_pendencias(
            resultado.registros, campos_esperados, arquivos
        )

    resultado.segundos = time.perf_counter() - inicio

    if saida:
        # Verifica o lote **inteiro** antes de gravar: coluna faltante e lote
        # heterogêneo só aparecem no conjunto, e o destino CSV monta o cabeçalho
        # a partir do primeiro registro — a coluna sumiria calada (SPEC §4.5).
        _validar_saida(resultado.registros, perfil)
        _gravar(resultado, Path(saida))

    return resultado


def _validar_saida(registros: list[Registro], perfil: Any) -> None:
    """Valida contra o esquema declarado. Sem esquema no perfil, não faz nada."""
    if perfil is None:
        return

    from parser.esquema import Esquema

    Esquema.de_perfil(perfil).validar(registros)


def _processar(
    arquivo: Path, perfil: Any, calibrar_por_arquivo: bool
) -> tuple[list[Registro], str]:
    """Extrai de um documento, escolhendo o layout mais adequado.

    Devolve os registros e uma nota sobre como o layout foi decidido — a nota vai
    para o log, de modo que a origem de um valor suspeito seja rastreável.
    """
    from parser.extratores.posicional import ExtratorPosicional
    from parser.fontes.pdf import FontePDF

    layout, nota = _decidir_layout(arquivo, perfil, calibrar_por_arquivo)
    paginas = _paginas_do_perfil(perfil)

    documento = FontePDF(paginas=paginas).carregar(str(arquivo))
    registros = ExtratorPosicional(layout).extrair(documento)

    if not registros:
        raise ValueError("nenhum registro extraído")

    # Traduz os rótulos do documento para os nomes que o destino espera. Sem isto,
    # um campo extraído com sucesso apareceria como pendência só porque o documento
    # o chama de outro jeito.
    registros = _aplicar_mapeamento(registros, perfil)

    # Depois do mapeamento, nunca antes: as regras de unidade são declaradas sobre
    # os nomes canônicos, que só existem a partir daqui.
    registros = _converter_unidades(registros, perfil)

    return registros, nota


def _converter_unidades(registros: list[Registro], perfil: Any) -> list[Registro]:
    """Converte para a unidade que o perfil declarar (SPEC §4.3).

    Diferente do mapeamento, uma falha aqui **não** é engolida: unidade errada
    produz número plausível e errado, que ninguém audita a jusante. Sem regras
    declaradas o conversor é inerte e os registros passam intactos.
    """
    if perfil is None:
        return registros

    from parser.unidades import Conversor

    return Conversor.de_perfil(perfil).aplicar_todos(registros)


def _validar_perfil(perfil: Any) -> None:
    """Verifica o que não depende de documento algum, antes de processar.

    Mapeamento, unidades e esquema são iguais para a pasta inteira. Um erro em
    qualquer um deles falha em todos os arquivos com a mesma mensagem, e
    descobri-lo depois de extrair cem documentos é desperdício puro.

    Levanta o erro original — `MapeamentoInvalido`, `UnidadeInvalida` ou
    `EsquemaInvalido` —, que já nomeia campo e causa.
    """
    if perfil is None:
        return

    if getattr(perfil, "mapeamento", None):
        from parser.mapeamento import Mapeamento

        Mapeamento(perfil.mapeamento)

    from parser.esquema import Esquema
    from parser.unidades import Conversor

    Conversor.de_perfil(perfil)
    Esquema.de_perfil(perfil)


def _aplicar_mapeamento(registros: list[Registro], perfil: Any) -> list[Registro]:
    if perfil is None or not getattr(perfil, "mapeamento", None):
        return registros

    from parser.mapeamento import Mapeamento

    # Mapeamento inválido **falha alto**, e a razão é o efeito a jusante: sem
    # tradução, os registros seguem com os rótulos do documento e a validação de
    # esquema acusa "coluna ausente". O usuário então procura por que a coluna
    # sumiu, quando a causa é um perfil com dois campos reivindicando o mesmo
    # rótulo. Engolir aqui não protege o lote — só troca um erro localizável por
    # um erro que aponta para o lugar errado.
    return Mapeamento(perfil.mapeamento).aplicar_todos(registros)


def _decidir_layout(arquivo: Path, perfil: Any, calibrar_por_arquivo: bool):
    """Layout descoberto, se confiável; senão o do perfil."""
    if calibrar_por_arquivo:
        try:
            from parser.calibracao import calibrar

            candidato = calibrar(str(arquivo))
            if candidato.confianca >= CONFIANCA_MINIMA_DE_CALIBRACAO:
                return _layout_de_dados(candidato.layout), (
                    f"layout descoberto (confiança {candidato.confianca:.0%})"
                )
        except Exception:
            pass  # cai no perfil; a razão aparece se o perfil também falhar

    if perfil is not None:
        rota = perfil.rotas.get("posicional") if hasattr(perfil, "rotas") else None
        if rota and rota.layout:
            return _layout_de_dados(rota.layout), "layout do perfil"

    raise ValueError(
        "não foi possível determinar o layout: a calibração não teve confiança "
        "suficiente e nenhum perfil com layout foi informado"
    )


def _layout_de_dados(dados: dict):
    from parser.extratores.posicional import LayoutTabela

    return LayoutTabela(
        x_rotulos=tuple(dados["x_rotulos"]),
        x_unidades=tuple(dados["x_unidades"]),
        x_valores_min=dados["x_valores_min"],
        y_identificadores_min=dados["y_identificadores_min"],
        tolerancia_y=dados.get("tolerancia_y", 6.0),
        tolerancia_x=dados.get("tolerancia_x", 6.0),
        y_rotulo_max=dados.get("y_rotulo_max"),
        distancia_rotulo_max=dados.get("distancia_rotulo_max", 40.0),
    )


def _paginas_do_perfil(perfil: Any) -> range | None:
    if perfil is None or not hasattr(perfil, "intervalo_de_paginas"):
        return None

    # Sem captura: um 'paginas' malformado devolvia None em silêncio, e o lote
    # processava o documento inteiro. Quem pediu três páginas recebia cento e
    # sessenta e quatro, sem nenhum sinal de que o pedido foi ignorado.
    return perfil.intervalo_de_paginas()


def _classificar(arquivo: Path, erro: Exception) -> Falha:
    """Traduz a exceção em motivo e ação, consultando o diagnóstico do documento.

    Uma falha sem ação recomendada é só reclamação: quem opera o sistema precisa
    saber o que fazer, não apenas que algo deu errado.
    """
    motivo = f"{type(erro).__name__}: {erro}"

    try:
        from parser.diagnostico import Severidade, diagnosticar

        graves = [a for a in diagnosticar(str(arquivo)) if a.severidade is Severidade.BLOQUEIA]
        if graves:
            return Falha(
                arquivo=str(arquivo),
                motivo=f"{motivo} — diagnóstico: {graves[0].detalhe}",
                acao=graves[0].acao,
            )
    except Exception:
        pass

    return Falha(
        arquivo=str(arquivo),
        motivo=motivo,
        acao=(
            "Rode 'parser diagnosticar' neste arquivo para ver o que impede a "
            "leitura, e 'parser calibrar' para descobrir o layout."
        ),
    )


def _levantar_pendencias(
    registros: list[Registro], esperados: list[str], arquivos: list[Path]
) -> list[Pendencia]:
    """Campos que o destino exige e o lote não trouxe."""
    if not registros:
        return [
            Pendencia(
                item="(lote)",
                campo=campo,
                motivo="nenhum registro foi extraído do lote",
                procurar_em=[a.name for a in arquivos[:5]],
            )
            for campo in esperados
        ]

    presentes = {nome for r in registros for nome, c in r.campos.items() if c.preenchido}
    ausentes = [c for c in esperados if c not in presentes]

    return [
        Pendencia(
            item="(todos)",
            campo=campo,
            motivo="nenhum documento do lote traz este campo",
            procurar_em=[a.name for a in arquivos[:5]],
        )
        for campo in ausentes
    ]


def _gravar(resultado: ResultadoLote, saida: Path) -> None:
    """Grava CSV, log e erros.

    Três arquivos porque servem a três leitores: o CSV vai para o sistema de
    destino, o log para quem acompanha a execução, e os erros para quem precisa
    corrigir a entrada.
    """
    saida.parent.mkdir(parents=True, exist_ok=True)

    colunas: list[str] = []
    for registro in resultado.registros:
        for nome in registro.campos:
            if nome not in colunas:
                colunas.append(nome)

    with saida.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["_arquivo", *colunas])
        escritor.writeheader()
        for registro in resultado.registros:
            linha = {"_arquivo": registro.fonte}
            for nome in colunas:
                campo = registro.campos.get(nome)
                if campo is None or not campo.preenchido:
                    linha[nome] = ""
                elif campo.sentinela is not None:
                    linha[nome] = campo.sentinela.value
                else:
                    linha[nome] = "" if campo.valor is None else str(campo.valor)
            escritor.writerow(linha)

    saida.with_suffix(".log").write_text(
        "\n".join([resultado.resumo(), "", "Por arquivo:", *resultado.log]),
        encoding="utf-8",
    )

    saida.with_suffix(".erros.json").write_text(
        json.dumps([asdict(f) for f in resultado.falhas], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if resultado.pendencias:
        saida.with_suffix(".pendencias.json").write_text(
            json.dumps(
                [asdict(p) for p in resultado.pendencias], ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
