"""Configuração declarativa: perfis e prompts fora do código (ADR-0008).

Existe para responder a uma pergunta prática: quando alguém precisar mudar a
resolução do reconhecedor, apontar o parser para outro documento ou trocar de
modelo, **onde essa pessoa olha?** A resposta tem de ser um arquivo, não um
módulo Python — porque a equipe que herdar isto não vai ter um assistente de
programação ao lado.

O código conserva apenas *defaults de segurança*, e cada um aponta para a decisão
que o mediu. Um número sem procedência é um número que ninguém pode questionar
nem revisar.

Três eixos de extensibilidade orientam o formato:

- **modelo novo** — nome e endereço no perfil, sem tocar em código;
- **documento novo** — novo arquivo de perfil, com seu layout e resolução;
- **formato novo** — o perfil declara o tipo; só o adapter é código.

O risco oposto — configuração virar depósito de opções acopladas — é contido
organizando o perfil por **rota**, cada uma independente das demais.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULTS",
    "ConfiguracaoInvalida",
    "Perfil",
    "Prompt",
    "Rota",
    "carregar_perfil",
    "carregar_prompt",
]


class ConfiguracaoInvalida(ValueError):
    """A configuração não descreve uma execução válida."""


ROTAS_CONHECIDAS = ("posicional", "linear", "biblioteca", "pdfplumber", "camelot", "ocr", "vlm", "llm")
"""Rotas que o projeto sabe executar.

Nome fora desta lista é erro de digitação, e falhar na carga é melhor que ignorar
em silêncio uma rota que o autor pretendia executar.
"""

DEFAULTS: dict[str, dict[str, Any]] = {
    "ocr.dpi": {
        "valor": 350,
        "origem": "ADR-0007",
        "porque": "ótimo medido; abaixo perde a vírgula decimal, acima quebra o alinhamento",
    },
    "vlm.dpi": {
        "valor": 150,
        "origem": "ADR-0003",
        "porque": "compromisso entre legibilidade da tabela e custo em processador",
    },
    "llm.dpi": {"valor": 0, "origem": "—", "porque": "rota de texto não renderiza imagem"},
    "modelo.timeout": {
        "valor": 3600.0,
        "origem": "medição em CPU de baixo consumo",
        "porque": "uma página pode levar minutos; limite curto viraria falha artificial",
    },
    "modelo.url": {
        "valor": "http://localhost:11434",
        "origem": "convenção do servidor de inferência",
        "porque": "servidor local por padrão; remoto é configuração",
    },
    "tolerancia": {
        "valor": 0.01,
        "origem": "ADR-0005",
        "porque": "erro relativo aceito na comparação numérica; '42' e '42.0' são iguais",
    },
}


def _default(chave: str) -> Any:
    return DEFAULTS[chave]["valor"]


@dataclass
class Rota:
    """Parâmetros de uma estratégia de extração.

    Cada rota é independente: configurar uma não afeta as outras.
    """

    nome: str
    dpi: int = 0
    modelo: str | None = None
    url: str = field(default_factory=lambda: _default("modelo.url"))
    timeout: float = field(default_factory=lambda: _default("modelo.timeout"))
    prompt: str | None = None
    layout: dict[str, Any] = field(default_factory=dict)
    campos_na_ordem: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def de_dados(cls, nome: str, dados: dict[str, Any]) -> Rota:
        conhecidos = {
            "dpi", "modelo", "url", "timeout", "prompt", "layout", "campos_na_ordem"
        }
        chave_dpi = f"{nome}.dpi"
        return cls(
            nome=nome,
            dpi=dados.get("dpi", _default(chave_dpi) if chave_dpi in DEFAULTS else 0),
            modelo=dados.get("modelo"),
            url=dados.get("url", _default("modelo.url")),
            timeout=dados.get("timeout", _default("modelo.timeout")),
            prompt=dados.get("prompt"),
            layout=dados.get("layout", {}),
            campos_na_ordem=dados.get("campos_na_ordem", []),
            extras={k: v for k, v in dados.items() if k not in conhecidos},
        )


@dataclass
class Perfil:
    """Tudo que muda quando o documento muda."""

    nome: str
    documento: str | None = None
    rotas: dict[str, Rota] = field(default_factory=dict)
    mapeamento: dict[str, list[str]] = field(default_factory=dict)
    unidades: dict[str, dict[str, str]] = field(default_factory=dict)
    """Campo canônico → ``{"de": unidade de origem, "para": unidade alvo}``.

    Vazio por padrão: sem declaração, a etapa de conversão executa e não converte
    nada, e nenhuma medição anterior muda de valor (SPEC §4.3).
    """

    esquema: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Coluna → declaração (``tipo``, ``minimo``, ``maximo``, ``obrigatorio``).

    Vazio por padrão: sem declaração, a saída não é verificada como conjunto e o
    comportamento anterior fica intacto (SPEC §4.5).
    """

    campos_na_ordem: list[str] = field(default_factory=list)
    paginas: list[int] | None = None
    tolerancia: float = field(default_factory=lambda: _default("tolerancia"))
    gabarito: str | None = None
    holdout: str | None = None
    caminho: Path | None = None

    def rota(self, nome: str) -> Rota:
        if nome not in self.rotas:
            disponiveis = ", ".join(sorted(self.rotas)) or "nenhuma"
            raise ConfiguracaoInvalida(
                f"perfil {self.nome!r} não define a rota {nome!r} (tem: {disponiveis})"
            )
        return self.rotas[nome]

    def intervalo_de_paginas(self) -> range | None:
        """`[inicio, fim]` ou `[inicio, fim, passo]`, base 0."""
        if not self.paginas:
            return None
        if len(self.paginas) not in (2, 3):
            raise ConfiguracaoInvalida(
                f"perfil {self.nome!r}: 'paginas' deve ser [inicio, fim] ou "
                f"[inicio, fim, passo], recebido {self.paginas!r}"
            )
        return range(*self.paginas)


def carregar_perfil(caminho: str | Path) -> Perfil:
    """Lê e valida um perfil.

    Valida na carga, falhando alto: um perfil inconsistente descoberto no meio de
    uma execução longa custa muito mais que um erro imediato.
    """
    arquivo = Path(caminho)
    if not arquivo.exists():
        raise ConfiguracaoInvalida(f"perfil não encontrado: {arquivo}")

    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ConfiguracaoInvalida(f"perfil {arquivo.name} não é JSON válido: {erro}") from erro

    if not dados.get("nome"):
        raise ConfiguracaoInvalida(f"perfil {arquivo.name} sem 'nome'")
    if "rotas" not in dados:
        raise ConfiguracaoInvalida(f"perfil {arquivo.name} sem 'rotas'")

    rotas = {}
    for nome, config in (dados.get("rotas") or {}).items():
        if nome not in ROTAS_CONHECIDAS:
            raise ConfiguracaoInvalida(
                f"perfil {arquivo.name}: rota desconhecida {nome!r}. "
                f"Conhecidas: {', '.join(ROTAS_CONHECIDAS)}"
            )
        rotas[nome] = Rota.de_dados(nome, config or {})

    perfil = Perfil(
        nome=dados["nome"],
        documento=dados.get("documento"),
        rotas=rotas,
        mapeamento=dados.get("mapeamento", {}),
        unidades=dados.get("unidades", {}),
        esquema=dados.get("esquema", {}),
        campos_na_ordem=dados.get("campos_na_ordem", []),
        paginas=dados.get("paginas"),
        tolerancia=dados.get("tolerancia", _default("tolerancia")),
        gabarito=dados.get("gabarito"),
        holdout=dados.get("holdout"),
        caminho=arquivo,
    )
    perfil.intervalo_de_paginas()  # valida cedo
    _validar_declaracoes(perfil, arquivo.name)
    return perfil


def _validar_declaracoes(perfil: Perfil, nome_arquivo: str) -> None:
    """Constrói conversor e esquema na carga, só para falhar cedo.

    Ambos validam a própria declaração ao serem construídos. Fazê-lo aqui troca
    um erro no meio de um lote de 164 páginas por um erro imediato, com o nome do
    arquivo de perfil na mensagem.

    O import é local para não impor `pint` e `pandera` a quem apenas lê um perfil.
    """
    from parser.esquema import Esquema, EsquemaInvalido
    from parser.unidades import Conversor, UnidadeInvalida

    try:
        Conversor.de_perfil(perfil)
    except UnidadeInvalida as erro:
        raise ConfiguracaoInvalida(f"perfil {nome_arquivo}: {erro}") from erro

    try:
        Esquema.de_perfil(perfil)
    except EsquemaInvalido as erro:
        raise ConfiguracaoInvalida(f"perfil {nome_arquivo}: {erro}") from erro


@dataclass
class Prompt:
    """Instrução ao modelo, com os guardrails que a acompanham.

    Instrução e guardrails viajam juntos por decisão: separá-los na hora do envio
    anularia o propósito de tê-los escrito, e a próxima pessoa não teria como saber
    que uma regra foi omitida.
    """

    nome: str
    instrucao: str
    guardrails: str = ""
    historico: str = ""
    caminho: Path | None = None

    def texto(self) -> str:
        """O que efetivamente vai ao modelo."""
        if not self.guardrails:
            return self.instrucao
        return f"{self.instrucao}\n\nRegras obrigatórias:\n{self.guardrails}"

    @property
    def impressao_digital(self) -> str:
        """Identifica esta versão do prompt.

        Necessário para distinguir, numa comparação, o efeito de mudar o prompt do
        efeito de mudar o modelo. Sem isso as duas causas ficam indistinguíveis.
        """
        return hashlib.sha256(self.texto().encode("utf-8")).hexdigest()[:12]


_SECAO = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def carregar_prompt(caminho: str | Path) -> Prompt:
    """Lê um prompt de arquivo Markdown com seções nomeadas."""
    arquivo = Path(caminho)
    if not arquivo.exists():
        raise ConfiguracaoInvalida(f"prompt não encontrado: {arquivo}")

    texto = arquivo.read_text(encoding="utf-8")
    secoes: dict[str, str] = {}
    marcas = list(_SECAO.finditer(texto))
    for i, marca in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        secoes[_normalizar(marca.group(1))] = texto[marca.end():fim].strip()

    if "instrucao" not in secoes or not secoes["instrucao"]:
        raise ConfiguracaoInvalida(
            f"prompt {arquivo.name} precisa de uma seção '## Instrução' não vazia"
        )

    return Prompt(
        nome=arquivo.stem,
        instrucao=secoes["instrucao"],
        guardrails=secoes.get("guardrails", ""),
        historico=secoes.get("historico", ""),
        caminho=arquivo,
    )


def _normalizar(titulo: str) -> str:
    import unicodedata

    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", titulo) if unicodedata.category(c) != "Mn"
    )
    return sem_acento.strip().lower()
