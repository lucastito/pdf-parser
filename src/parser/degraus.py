"""Degraus de saída do modelo: do mais restrito ao mais livre (SPEC §4.4).

Um modelo pequeno pode devolver **resposta vazia** sem erro algum. O que torna
esse modo de falha traiçoeiro é que **ele não se parece com falha**: não há
exceção, não há JSON malformado, não há tempo esgotado. O servidor responde `200`,
a resposta é `""` com `done_reason=stop`, e o extrator recebe zero item — como se
a página estivesse em branco. Numa execução em lote isso vira "processado, 0
registros" e segue adiante.

**A causa não é a restrição, e ainda não foi identificada.** A hipótese inicial
culpava o esquema restringido — a gramática de decodificação tornando o caminho
válido inalcançável. Medição de 2026-07-30 com `qwen3-vl:4b`, mesma imagem e mesma
instrução, variando só a restrição e o canal de raciocínio:

| Degrau | Raciocínio ligado | Raciocínio desligado |
|---|---|---|
| esquema completo | 306 s · 153 tokens · vazia | 77 s · 152 tokens · vazia |
| `format: "json"` | 82 s · 152 tokens · vazia | 79 s · 152 tokens · vazia |
| texto livre | 1055 s · 1844 tokens · vazia | 953 s · 1817 tokens · vazia |

Duas conclusões, ambas negativas:

**A restrição não é a culpada** — o texto livre, sem restrição alguma, também
devolve vazio.

**O raciocínio também não explica** — desligá-lo praticamente não muda os números
(152 contra 152; 1817 contra 1844). A contagem quase idêntica sugere que
`think: false` **não está sendo respeitado** por esta combinação de servidor e
modelo. Uma hipótese anterior dava esta causa como confirmada, a partir de um único
teste com prompt de descrição; a medição completa não sustentou.

A única pista firme é o **prompt**: um pedido de descrição responde (521 tokens),
o de extração não (152). Investigação em aberto.

`raciocinar` existe como parâmetro porque poder ligar e desligar é condição para
medir. O padrão é desligado por ser o caso mais simples, **não** por estar provado
que resolve.

Os degraus permanecem porque resolvem um problema **diferente e real** — impedir
que resposta vazia vire "página sem dados" em silêncio, e registrar sob qual
restrição cada resultado foi obtido. Eles não consertam o vazio.

A saída é, então, tentada em degraus:

1. **esquema completo** — gramática de decodificação; nada a validar depois;
2. **`format: "json"`** — sem gramática, com validação em Python;
3. **texto livre** — o JSON é recortado da prosa e validado.

Duas regras governam a descida, e ambas existem por causa da comparabilidade
(ADR-0005):

**O degrau usado é registrado com o resultado.** Sem isso, duas execuções não são
comparáveis — a matriz passaria a medir também a diferença de restrição, e não a
diferença entre estratégias.

**A descida é achado, não detalhe.** Cair de degrau diz algo sobre o modelo, e
essa informação tem de chegar a quem lê o resultado.

O que a descida **nunca** degrada é a validação: a estrutura é verificada nos três
degraus. Afrouxar a forma da restrição não afrouxa RF-7.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "Degrau",
    "RespostaVazia",
    "ResultadoDegrau",
    "SaidaEmDegraus",
    "Tentativa",
    "TodosOsDegrausFalharam",
]


class Degrau(Enum):
    """Como a saída do modelo é restringida, do mais estrito ao mais livre."""

    ESQUEMA_COMPLETO = "esquema-completo"
    """Esquema JSON como gramática de decodificação."""

    JSON_LIVRE = "json-livre"
    """`format: "json"` — o servidor garante JSON, não a estrutura."""

    TEXTO_COM_EXTRACAO = "texto-com-extracao"
    """Sem restrição: o JSON é recortado da resposta."""


ORDEM = (Degrau.ESQUEMA_COMPLETO, Degrau.JSON_LIVRE, Degrau.TEXTO_COM_EXTRACAO)


class RespostaVazia(ValueError):
    """O modelo respondeu, e a resposta não tem conteúdo.

    Distinta de `RespostaInvalida`: ali o modelo falou algo inaproveitável; aqui
    ele não falou nada. É a assinatura do colapso do esquema restringido, e
    tratá-la como "página sem dados" é o erro que este módulo existe para impedir.
    """


class TodosOsDegrausFalharam(RuntimeError):
    """Nenhum degrau produziu estrutura utilizável.

    A mensagem relata **cada** tentativa: sem isso, quem depura não sabe se o
    problema é o esquema, o modelo ou a página.
    """


@dataclass(frozen=True)
class Tentativa:
    """O que aconteceu num degrau."""

    degrau: Degrau
    sucesso: bool
    motivo: str = ""
    segundos: float = 0.0


@dataclass
class ResultadoDegrau:
    """A estrutura obtida, e como se chegou até ela."""

    dados: Any
    degrau: Degrau
    tentativas: list[Tentativa] = field(default_factory=list)

    @property
    def houve_descida(self) -> bool:
        """Verdadeiro se o degrau mais restrito não bastou."""
        return self.degrau is not ORDEM[0]

    def resumo(self) -> str:
        """Uma linha para o log, dizendo o que foi preciso para obter a saída."""
        if not self.houve_descida:
            return f"saída obtida no degrau {self.degrau.value}"

        falhos = ", ".join(
            f"{t.degrau.value} ({t.motivo})" for t in self.tentativas if not t.sucesso
        )
        return f"saída obtida em {self.degrau.value} — degraus que falharam: {falhos}"


class SaidaEmDegraus:
    """Obtém estrutura do modelo, afrouxando a restrição só quando preciso."""

    def __init__(
        self,
        cliente: Any,
        campos: list[str],
        *,
        chave: str = "itens",
        degrau_maximo: Degrau | None = None,
        raciocinar: bool = False,
    ) -> None:
        """
        Args:
            chave: a chave que a resposta precisa conter para valer como sucesso.
                JSON válido sem ela é JSON inútil, e aceitá-lo faria o degrau
                parecer bem-sucedido enquanto entrega nada.
            degrau_maximo: o degrau mais livre permitido. Fixá-lo é o que torna
                uma bateria de execuções comparável entre si: rodadas em degraus
                diferentes medem restrições diferentes, não estratégias.
            raciocinar: liga o canal de raciocínio do modelo. **Desligado por
                padrão, por medição** — ver o cabeçalho do módulo. Ligá-lo é
                escolha legítima para medir o efeito, não o comportamento padrão.
        """
        self.cliente = cliente
        self.campos = campos
        self.chave = chave
        self.degrau_maximo = degrau_maximo
        self.raciocinar = raciocinar

    def _permitidos(self) -> tuple[Degrau, ...]:
        if self.degrau_maximo is None:
            return ORDEM
        return ORDEM[: ORDEM.index(self.degrau_maximo) + 1]

    def obter(self, prompt: str, *, imagens: list[str] | None = None) -> ResultadoDegrau:
        """Tenta cada degrau permitido, do mais restrito ao mais livre.

        Levanta:
            TodosOsDegrausFalharam: se nenhum produzir a estrutura esperada.
        """
        tentativas: list[Tentativa] = []

        for degrau in self._permitidos():
            try:
                dados = self._tentar(degrau, prompt, imagens)
            except (RespostaVazia, ValueError) as erro:
                tentativas.append(
                    Tentativa(degrau=degrau, sucesso=False, motivo=str(erro)[:120])
                )
                continue

            tentativas.append(Tentativa(degrau=degrau, sucesso=True))
            return ResultadoDegrau(dados=dados, degrau=degrau, tentativas=tentativas)

        raise TodosOsDegrausFalharam(self._relatorio(tentativas))

    def _relatorio(self, tentativas: list[Tentativa]) -> str:
        linhas = [f"  {t.degrau.value}: {t.motivo}" for t in tentativas]
        relato = (
            f"nenhum dos {len(tentativas)} degraus produziu estrutura utilizável:\n"
            + "\n".join(linhas)
        )

        if all("vazia" in t.motivo for t in tentativas):
            relato += (
                "\n\nTodos os degraus vieram vazios — inclusive o menos restrito. "
                "Comportamento já medido neste projeto com modelo de visão pequeno: "
                "a restrição de formato não é a causa, e desligar o raciocínio "
                "também não resolveu. A pista é o prompt — um pedido de descrição "
                "responde onde o de extração não. Comece por um prompt curto que "
                "funcione e acrescente as regras uma a uma."
            )
        return relato

    def _tentar(self, degrau: Degrau, prompt: str, imagens: list[str] | None) -> Any:
        bruto = self._chamar(degrau, prompt, imagens)

        if not bruto or not bruto.strip():
            raise RespostaVazia(
                "resposta vazia — sinal típico de esquema restringido inalcançável "
                "para este modelo"
            )

        dados = self._estruturar(degrau, bruto)
        if not isinstance(dados, dict) or self.chave not in dados:
            raise ValueError(f"resposta sem a chave {self.chave!r}")
        return dados

    def _chamar(self, degrau: Degrau, prompt: str, imagens: list[str] | None) -> str:
        """Fala com o servidor no formato do degrau.

        Usa o transporte do cliente diretamente, em vez de `cliente.gerar`, porque
        aquele já decodifica JSON e levanta em resposta não conforme — e é
        exatamente a resposta não conforme que os degraus 2 e 3 precisam receber
        para tratar.
        """
        carga: dict[str, Any] = {
            "model": self.cliente.modelo,
            "prompt": self._prompt_do_degrau(degrau, prompt),
            "stream": False,
            # Vale igual nos três degraus: variar o raciocínio junto com a
            # restrição criaria variável escondida, e nenhuma comparação entre
            # degraus significaria mais nada.
            "think": self.raciocinar,
        }
        if degrau is Degrau.ESQUEMA_COMPLETO:
            carga["format"] = self._esquema()
        elif degrau is Degrau.JSON_LIVRE:
            carga["format"] = "json"
        if imagens:
            carga["images"] = imagens

        resposta = self.cliente.transporte.enviar(
            f"{self.cliente.url}/api/generate", carga, self.cliente.timeout
        )
        return resposta.get("response", "")

    def _prompt_do_degrau(self, degrau: Degrau, prompt: str) -> str:
        """Quanto menos a gramática restringe, mais a instrução precisa dizer.

        No primeiro degrau a forma é imposta na decodificação e descrevê-la seria
        redundante. Nos seguintes, a instrução é a única coisa que resta.
        """
        if degrau is Degrau.ESQUEMA_COMPLETO:
            return prompt

        exemplo = ", ".join(f'"{c}": ...' for c in self.campos)
        forma = f'{{"{self.chave}": [{{{exemplo}}}]}}'

        if degrau is Degrau.JSON_LIVRE:
            return f"{prompt}\n\nResponda apenas com JSON válido, no formato {forma}."

        return (
            f"{prompt}\n\nResponda com um bloco JSON no formato {forma}. "
            "O bloco pode vir acompanhado de texto, mas precisa estar presente."
        )

    def _estruturar(self, degrau: Degrau, bruto: str) -> Any:
        if degrau is Degrau.TEXTO_COM_EXTRACAO:
            return _extrair_json(bruto)
        try:
            return json.loads(bruto)
        except json.JSONDecodeError as erro:
            raise ValueError(f"resposta não é JSON: {bruto[:80]!r}") from erro

    def _esquema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                self.chave: {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            campo: {"type": ["string", "number", "null"]}
                            for campo in self.campos
                        },
                    },
                }
            },
            "required": [self.chave],
        }


_BLOCO_CERCADO = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _extrair_json(texto: str) -> Any:
    """Recorta o JSON de uma resposta que também contém prosa.

    Três formas, em ordem de confiabilidade: bloco cercado por crases, o texto
    inteiro, e por fim o maior trecho entre chaves equilibradas. A última existe
    porque modelo pequeno costuma emoldurar o JSON com cortesias — "Claro! Segue
    o resultado:" — que não são erro dele, e sim o comportamento esperado de quem
    não recebeu restrição alguma.
    """
    cercado = _BLOCO_CERCADO.search(texto)
    if cercado:
        try:
            return json.loads(cercado.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    trecho = _maior_objeto(texto)
    if trecho is None:
        raise ValueError(f"nenhum JSON encontrado na resposta: {texto[:80]!r}")
    try:
        return json.loads(trecho)
    except json.JSONDecodeError as erro:
        raise ValueError(f"trecho parecido com JSON não decodifica: {trecho[:80]!r}") from erro


def _maior_objeto(texto: str) -> str | None:
    """O primeiro objeto de chaves equilibradas, ignorando chaves dentro de string.

    Contar chaves ingenuamente quebra em qualquer valor que contenha `{` ou `}` —
    e valores de documento contêm de tudo.
    """
    inicio = texto.find("{")
    if inicio == -1:
        return None

    profundidade = 0
    em_string = False
    escapado = False

    for i in range(inicio, len(texto)):
        c = texto[i]

        if escapado:
            escapado = False
            continue
        if c == "\\":
            escapado = True
            continue
        if c == '"':
            em_string = not em_string
            continue
        if em_string:
            continue

        if c == "{":
            profundidade += 1
        elif c == "}":
            profundidade -= 1
            if profundidade == 0:
                return texto[inicio : i + 1]

    return None
