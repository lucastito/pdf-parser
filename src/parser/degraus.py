"""Degraus de saída do modelo: do mais restrito ao mais livre (SPEC §4.4).

Um modelo pequeno pode devolver **resposta vazia** sem erro algum: o servidor
responde `200`, a resposta é `""`, e o extrator recebe zero item — como se a
página estivesse em branco. Numa execução em lote isso vira "processado, 0
registros" e segue adiante.

**A causa foi medida: corte pelo limite de tokens.** Três hipóteses foram
levantadas neste projeto e duas foram refutadas; o registro das três fica porque
hipótese invalidada também é resultado, e sem ele a próxima pessoa refaz a busca.

*Refutada — o esquema restringido.* A suspeita era que a gramática de
decodificação tornasse o caminho válido inalcançável. Mas o texto livre, **sem
restrição alguma**, também devolvia vazio.

*Refutada como causa isolada — o canal de raciocínio.* Desligá-lo não mudou os
números (152 contra 152 tokens; 1817 contra 1844).

*Confirmada — o limite de saída.* Cinco prompts na mesma página real, medidos um
por vez:

| prompt | `done_reason` | tokens | resposta |
|---|---|---|---|
| descreva a imagem | `stop` | 689 | 794 chars |
| leia a tabela | `length` | 1927 | vazia |
| leia com campos | `length` | 1923 | vazia |
| leia em JSON | `length` | 1912 | vazia |
| leia com guardrails | `length` | 1887 | vazia |

O sinal está no motivo do encerramento: `stop` é o modelo terminando, `length` é
a geração sendo cortada. Descrever uma página cabe em 689 tokens; enumerar
dezenas de itens não cabe em ~1900, e o corte vem antes de a resposta fechar.

Elevando o teto para 8192, a mesma chamada que devolvia vazio passou a devolver a
lista dos alimentos — corretos e na ordem do documento. Mas a geração **ainda foi
cortada**, e é aí que as duas hipóteses se encontram: o modelo gasta a maior parte
do orçamento no canal de raciocínio e só o restante vira resposta. O raciocínio
não era a causa; é o que **consome** o orçamento que o limite restringe.

Consequência prática: pedir a página inteira de uma vez a um modelo pequeno não é
viável. Ou se eleva muito o teto, ou se pede menos itens por chamada — e as duas
escolhas são variáveis de experimento, não padrões a adivinhar.

Os degraus permanecem porque resolvem um problema **diferente e real**: impedir
que resposta vazia vire "página sem dados" em silêncio, e registrar sob qual
restrição cada resultado foi obtido.

A saída é tentada em degraus:

1. **esquema completo** — gramática de decodificação; nada a validar depois;
2. **`format: "json"`** — sem gramática, com validação em Python;
3. **texto livre** — o JSON é recortado da prosa e validado.

Duas regras governam a descida, ambas por causa da comparabilidade (ADR-0005):

**O degrau usado é registrado com o resultado.** Sem isso, duas execuções não são
comparáveis — a matriz mediria também a diferença de restrição.

**A descida é achado, não detalhe.** Cair de degrau diz algo sobre o modelo, e
essa informação tem de chegar a quem lê o resultado.

O que a descida **nunca** degrada é a validação: a estrutura é verificada nos três
degraus. Afrouxar a forma da restrição não afrouxa RF-7.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "Degrau",
    "Varredura",
    "RespostaCortada",
    "RespostaVazia",
    "ResultadoDegrau",
    "SaidaEmDegraus",
    "Tentativa",
    "TodosOsDegrausFalharam",
    "Uso",
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


class RespostaCortada(ValueError):
    """A geração foi interrompida pelo limite de tokens, antes de terminar.

    Distinta de `RespostaVazia`: ali o modelo não produziu nada; aqui produziu e
    foi cortado no meio, e o que chega é o pedaço — ou nada, se o corte veio
    antes de qualquer conteúdo utilizável.

    A distinção decide onde procurar. Vazio manda investigar modelo ou prompt;
    corte manda aumentar o limite. Confundir os dois custou uma sessão inteira
    de investigação neste projeto.
    """


class TodosOsDegrausFalharam(RuntimeError):
    """Nenhum degrau produziu estrutura utilizável.

    A mensagem relata **cada** tentativa: sem isso, quem depura não sabe se o
    problema é o esquema, o modelo ou a página.
    """


@dataclass(frozen=True)
class Uso:
    """Quantos tokens a chamada consumiu, de cada lado.

    Existe porque a **soma** é o que diagnostica: o limite de contexto vale para
    entrada e saída juntas, e soma igual ao contexto configurado é assinatura de
    corte, não de o modelo ter terminado.

    Estes dois números vinham em toda resposta do servidor e eram descartados.
    Durante uma sessão inteira, o projeto culpou o parâmetro errado por não
    olhá-los (ADR-0018).
    """

    entrada: int = 0
    saida: int = 0

    raciocinio_chars: int = 0
    """Tamanho do canal de raciocínio.

    Registrado **mesmo quando o raciocínio é pedido desligado**, porque o
    servidor o devolve preenchido de qualquer forma. Custou uma medição de 77
    minutos: a chamada terminou sozinha, sobrou contexto, gerou 5684 tokens — e a
    resposta veio vazia, porque o conteúdo tinha ido para cá.

    Sem este número, "resposta vazia" é indistinguível de incapacidade do modelo.
    """

    eval_ns: int = 0
    """Nanossegundos gerando. Separado do total, que inclui carregar o modelo."""

    load_ns: int = 0
    """Nanossegundos carregando o modelo.

    A primeira execução paga isto e as seguintes não. Sem separar, a primeira
    pareceria mais lenta e a diferença viraria "resultado" na comparação entre
    máquinas.
    """

    total_ns: int = 0

    @property
    def total(self) -> int:
        return self.entrada + self.saida

    @property
    def tokens_por_segundo(self) -> float | None:
        """Velocidade de geração, ou `None` se o servidor não informou a duração.

        É o que torna máquinas de capacidade diferente comparáveis: tempo
        absoluto por página mistura tamanho da tarefa com velocidade do
        hardware.

        Devolve `None` em vez de zero ou de uma estimativa: número inventado aqui
        entraria na comparação entre máquinas sem nada denunciar.
        """
        if not self.eval_ns or not self.saida:
            return None
        return self.saida / (self.eval_ns / 1_000_000_000)

    def bate_no_teto(self, contexto: int | None) -> bool:
        """A soma atingiu exatamente o contexto configurado?

        Prompts de tamanhos diferentes parando no mesmo total é assinatura de
        teto atingido — foi assim que a causa apareceu.
        """
        return bool(contexto) and self.total >= (contexto or 0)

    def como_dados(self) -> dict[str, Any]:
        dados: dict[str, Any] = {
            "entrada": self.entrada,
            "saida": self.saida,
            "total": self.total,
            "raciocinio_chars": self.raciocinio_chars,
        }
        if self.eval_ns:
            dados["eval_s"] = round(self.eval_ns / 1_000_000_000, 3)
        if self.load_ns:
            dados["load_s"] = round(self.load_ns / 1_000_000_000, 3)
        if self.total_ns:
            dados["total_s"] = round(self.total_ns / 1_000_000_000, 3)
        if self.tokens_por_segundo is not None:
            dados["tokens_por_s"] = round(self.tokens_por_segundo, 2)
        return dados


@dataclass(frozen=True)
class Tentativa:
    """O que aconteceu num degrau."""

    degrau: Degrau
    sucesso: bool
    motivo: str = ""
    segundos: float = 0.0
    tipo_de_falha: str | None = None
    """Categoria da falha, para agrupar resultados entre máquinas.

    `resposta-vazia` e `sem-estrutura` são achados diferentes: o primeiro sugere
    problema de modelo, o segundo de formato. Colapsar os dois em "falhou"
    perderia a distinção justamente na comparação em que ela importa.
    """

    uso: Uso | None = None
    """Tokens consumidos. Registrado sempre, inclusive em sucesso.

    Em falha, diagnostica; em sucesso, alimenta a curva de memória por contexto
    que dimensiona a máquina de destino (ADR-0018).
    """

    def como_dados(self) -> dict[str, Any]:
        dados: dict[str, Any] = {
            "degrau": self.degrau.value,
            "sucesso": self.sucesso,
            "segundos": round(self.segundos, 2),
            "tipo_de_falha": self.tipo_de_falha,
            "motivo": self.motivo,
        }
        if self.uso is not None:
            dados["uso"] = self.uso.como_dados()
        return dados


@dataclass
class Varredura:
    """O resultado de rodar **todos** os degraus, para comparação entre máquinas."""

    tentativas: list[Tentativa] = field(default_factory=list)

    @property
    def primeiro_sucesso(self) -> Degrau | None:
        for tentativa in self.tentativas:
            if tentativa.sucesso:
                return tentativa.degrau
        return None

    def como_dados(self) -> dict[str, Any]:
        """Forma serializável, para gravar em `experimentos/resultados/`."""
        primeiro = self.primeiro_sucesso
        return {
            "primeiro_sucesso": primeiro.value if primeiro else None,
            "tentativas": [t.como_dados() for t in self.tentativas],
        }

    def resumo(self) -> str:
        linhas = []
        for tentativa in self.tentativas:
            marca = "ok    " if tentativa.sucesso else "falhou"
            detalhe = "" if tentativa.sucesso else f" ({tentativa.tipo_de_falha})"
            linhas.append(
                f"  {tentativa.degrau.value:20s} {marca} {tentativa.segundos:7.1f}s{detalhe}"
            )
        return "\n".join(linhas)


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
        tokens_maximos: int | None = None,
        contexto: int | None = None,
        semente: int | None = None,
        temperatura: float = 0.0,
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
            tokens_maximos: teto de tokens da **resposta**. Necessário, mas
                **não suficiente**: sozinho não impede o corte, porque o limite
                que corta é o contexto. Ver `contexto`.
            contexto: teto de tokens de **entrada mais saída, somadas**. É o
                limite que de fato corta, e o padrão do servidor (4096) foi a
                causa medida das respostas vazias — uma página renderizada
                consome ~2200 só de entrada, e sobra pouco para a resposta.

                Elevar `tokens_maximos` sem declarar isto **não resolve**: foi
                exatamente o que se tentou, e o corte continuou na mesma soma
                (ADR-0018).

                Nenhum valor é inventado aqui. Um teto arbitrário viraria número
                mágico sem procedência (ADR-0008) — e o valor certo depende de
                quanto a entrada consome, que precisa ser medido.
            semente: fixa a amostragem, tornando a geração repetível. Sem ela,
                duas execuções da mesma configuração podem divergir — e entre
                máquinas a diferença viraria indistinguível de ruído (ADR-0020).
            temperatura: **zero por padrão**. Extração de tabela não tem
                criatividade a exercitar; amostragem aleatória só acrescenta
                variância. Declarável para quem quiser medir o efeito dela, que é
                hipótese legítima — só não é o comportamento padrão.
        """
        self.cliente = cliente
        self.campos = campos
        self.chave = chave
        self.degrau_maximo = degrau_maximo
        self.raciocinar = raciocinar
        self.tokens_maximos = tokens_maximos
        self.contexto = contexto
        self.semente = semente
        self.temperatura = temperatura
        self._ultimo_uso: Uso | None = None
        """Tokens da chamada mais recente. Alimenta diagnóstico e registro."""

    def _permitidos(self) -> tuple[Degrau, ...]:
        if self.degrau_maximo is None:
            return ORDEM
        return ORDEM[: ORDEM.index(self.degrau_maximo) + 1]

    def varrer(self, prompt: str, *, imagens: list[str] | None = None) -> Varredura:
        """Roda **todos** os degraus, em ordem, mesmo os que vêm depois de um sucesso.

        É o modo de experimento, e o contrário de `obter`. A diferença é de
        propósito, não de implementação:

        - `obter` para no primeiro sucesso, porque em produção os degraus
          seguintes custariam tempo sem acrescentar nada;
        - `varrer` executa todos, porque **comparar máquinas exige que todas
          tenham tentado as mesmas coisas**. Se a máquina A responde no degrau 1
          e para, não há como saber se ela também responderia no 3 — e a
          comparação com uma máquina B que só responde no 3 fica sem base.

        Nunca levanta: falha é o dado que se quer medir. Cada tentativa registra
        degrau, sucesso, tipo da falha e tempo.

        `degrau_maximo` é ignorado de propósito: limitar degraus é decisão de
        produção, e o experimento mede todos.
        """
        tentativas: list[Tentativa] = []

        for degrau in ORDEM:
            inicio = time.perf_counter()
            try:
                self._tentar(degrau, prompt, imagens)
            except (RespostaVazia, ValueError) as erro:
                tentativas.append(
                    Tentativa(
                        degrau=degrau,
                        sucesso=False,
                        # Sem corte: o diagnóstico de contexto traz os números
                        # que apontam o parâmetro culpado, e truncá-los devolve
                        # o problema a quem depura.
                        motivo=str(erro),
                        segundos=time.perf_counter() - inicio,
                        tipo_de_falha=_classificar_falha(erro),
                        uso=self._ultimo_uso,
                    )
                )
                continue

            tentativas.append(
                Tentativa(
                    degrau=degrau,
                    sucesso=True,
                    segundos=time.perf_counter() - inicio,
                    uso=self._ultimo_uso,
                )
            )

        return Varredura(tentativas=tentativas)

    def obter(self, prompt: str, *, imagens: list[str] | None = None) -> ResultadoDegrau:
        """Tenta cada degrau permitido, parando no primeiro que funcionar.

        É o modo de produção. Para medir e comparar máquinas, use `varrer`.

        Levanta:
            TodosOsDegrausFalharam: se nenhum produzir a estrutura esperada.
        """
        tentativas: list[Tentativa] = []

        for degrau in self._permitidos():
            inicio = time.perf_counter()
            try:
                dados = self._tentar(degrau, prompt, imagens)
            except (RespostaVazia, ValueError) as erro:
                tentativas.append(
                    Tentativa(
                        degrau=degrau,
                        sucesso=False,
                        motivo=str(erro),
                        segundos=time.perf_counter() - inicio,
                        tipo_de_falha=_classificar_falha(erro),
                        uso=self._ultimo_uso,
                    )
                )
                continue

            tentativas.append(
                Tentativa(
                    degrau=degrau,
                    sucesso=True,
                    segundos=time.perf_counter() - inicio,
                    uso=self._ultimo_uso,
                )
            )
            return ResultadoDegrau(dados=dados, degrau=degrau, tentativas=tentativas)

        raise TodosOsDegrausFalharam(self._relatorio(tentativas))

    def _relatorio(self, tentativas: list[Tentativa]) -> str:
        linhas = [f"  {t.degrau.value}: {t.motivo}" for t in tentativas]
        relato = (
            f"nenhum dos {len(tentativas)} degraus produziu estrutura utilizável:\n"
            + "\n".join(linhas)
        )

        if all("limite" in t.motivo for t in tentativas):
            relato += (
                "\n\nTodos os degraus foram cortados. É a causa medida das "
                "respostas vazias neste projeto, e o parâmetro culpado não é o "
                "óbvio: o **contexto** limita entrada MAIS saída, e o padrão do "
                "servidor é 4096. Uma página como imagem consome ~2200 só de "
                "entrada.\n"
                "Some entrada e saída acima: se a soma bate no contexto, declare "
                "num_ctx maior. Elevar apenas tokens_maximos não resolve — foi o "
                "que se tentou, e o corte continuou (ADR-0018)."
            )
            return relato

        if all("vazia" in t.motivo for t in tentativas):
            relato += (
                "\n\nTodos os degraus vieram vazios — inclusive o menos restrito. "
                "Três hipóteses já foram medidas e refutadas neste projeto: a "
                "restrição de formato não é a causa, desligar o raciocínio não "
                "resolveu, e elevar só o teto de saída também não.\n"
                "Confira primeiro os tokens: se houver corte, some entrada e "
                "saída e compare com o contexto — foi essa a causa real, e o "
                "sintoma é idêntico ao de resposta vazia (ADR-0018). Se não "
                "houver corte, aí sim a pista é o prompt: um pedido de descrição "
                "responde onde o de extração não."
            )
        return relato

    def _tentar(self, degrau: Degrau, prompt: str, imagens: list[str] | None) -> Any:
        bruto, motivo = self._chamar(degrau, prompt, imagens)

        if not bruto or not bruto.strip():
            if motivo == "length":
                raise RespostaCortada(self._diagnostico_de_corte())
            raise RespostaVazia("resposta vazia — o modelo encerrou sem emitir conteúdo")

        dados = self._estruturar(degrau, bruto)
        if not isinstance(dados, dict) or self.chave not in dados:
            raise ValueError(f"resposta sem a chave {self.chave!r}")
        return dados

    def _diagnostico_de_corte(self) -> str:
        """A mensagem aponta o parâmetro que de fato corta.

        A versão anterior mandava elevar `tokens_maximos`, e foi o conselho
        seguido por uma sessão inteira: o teto foi elevado, o corte continuou na
        mesma soma, e a contradição passou despercebida (ADR-0018).
        """
        uso = self._ultimo_uso
        partes = ["geração interrompida pelo limite antes de terminar."]

        if uso and uso.total:
            partes.append(f"Tokens: entrada {uso.entrada} + saída {uso.saida} = {uso.total}.")

        if uso and uso.bate_no_teto(self.contexto):
            partes.append(
                f"A soma bateu no contexto configurado ({self.contexto}) — é ele "
                "que corta, e não o teto de saída. Declare num_ctx maior."
            )
        else:
            partes.append(
                "Compare a soma com o contexto do servidor: ele limita entrada "
                "MAIS saída, e o padrão é 4096. Uma página como imagem consome "
                "~2200 só de entrada. Declare contexto (num_ctx) com folga — "
                "elevar apenas tokens_maximos não resolve."
            )
        return " ".join(partes)

    def _chamar(
        self, degrau: Degrau, prompt: str, imagens: list[str] | None
    ) -> tuple[str, str | None]:
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

        # Sempre declarada: o padrão do servidor é amostragem aleatória, e
        # geração irrepetível impede atribuir diferença a modelo, configuração
        # ou máquina — que é o propósito do experimento (ADR-0020).
        opcoes: dict[str, Any] = {"temperature": self.temperatura}
        if self.semente is not None:
            opcoes["seed"] = self.semente
        if self.tokens_maximos:
            opcoes["num_predict"] = self.tokens_maximos
        if self.contexto:
            # Sem isto vale o padrão do servidor, que limita entrada + saída
            # juntas e foi a causa medida das respostas vazias (ADR-0018).
            opcoes["num_ctx"] = self.contexto
        carga["options"] = opcoes

        resposta = self.cliente.transporte.enviar(
            f"{self.cliente.url}/api/generate", carga, self.cliente.timeout
        )
        # O motivo do encerramento distingue "não respondeu" de "foi cortado";
        # a soma dos tokens distingue **qual limite** cortou; e o raciocínio
        # distingue "não gerou nada" de "gerou no canal errado" (ADR-0018).
        # Todos já vinham na resposta e eram descartados.
        self._ultimo_uso = Uso(
            entrada=resposta.get("prompt_eval_count") or 0,
            saida=resposta.get("eval_count") or 0,
            raciocinio_chars=len(resposta.get("thinking") or ""),
            eval_ns=resposta.get("eval_duration") or 0,
            load_ns=resposta.get("load_duration") or 0,
            total_ns=resposta.get("total_duration") or 0,
        )
        return resposta.get("response", ""), resposta.get("done_reason")

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


def _classificar_falha(erro: Exception) -> str:
    """Agrupa a falha num tipo comparável entre máquinas.

    A distinção que importa: `resposta-vazia` sugere problema de modelo — ele
    gerou tokens e nada chegou ao campo de resposta —, enquanto `sem-estrutura`
    sugere problema de formato: o modelo falou, mas não no formato pedido.
    Colapsar os dois em "falhou" perderia justamente a informação que separa uma
    causa da outra.
    """
    if isinstance(erro, RespostaCortada):
        return "resposta-cortada"
    if isinstance(erro, RespostaVazia):
        return "resposta-vazia"
    return "sem-estrutura"
