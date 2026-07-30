"""Extração por modelo de linguagem, atrás da mesma porta dos demais extratores.

Existe para responder a uma pergunta mensurável: *um modelo lê este documento
melhor que as regras determinísticas?* A resposta pode ser não — e isso é
resultado, não fracasso do experimento.

Dois cuidados estruturam o módulo:

**A saída é validada, não confiada.** O schema é enviado ao servidor, que
restringe a decodificação a JSON conforme — mas a resposta ainda é verificada
aqui. Modelo pequeno às vezes devolve prosa, e prosa não pode virar dado.

**A confiança é menor que a da extração determinística.** Um valor lido por
coordenada tem respaldo verificável; um valor produzido por modelo, não. Tratar
os dois como equivalentes falsearia a métrica que compara justamente os dois.

O transporte é injetável para que os testes exercitem o contrato sem servidor,
sem rede e sem tempo de inferência.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from parser.modelo import Campo, Evidencia, Registro
from parser.normalizacao import ValorNaoReconhecido, parse_numero
from parser.portas import DocumentoCanonico

__all__ = [
    "INSTRUCAO_PADRAO",
    "ClienteOllama",
    "ExtratorBaseadoEmModelo",
    "ExtratorModelo",
    "RespostaInvalida",
    "ServidorIndisponivel",
    "Transporte",
]

URL_PADRAO = "http://localhost:11434"
CONFIANCA_MODELO = 0.8
"""Confiança atribuída a valor produzido por modelo.

Não é medida — é um marcador que impede tratar saída de modelo como equivalente
a leitura determinística. O número real só sai da avaliação contra o gabarito.
"""


class ServidorIndisponivel(RuntimeError):
    """Não foi possível falar com o servidor de inferência."""


class RespostaInvalida(ValueError):
    """O modelo respondeu algo que não é a estrutura pedida."""


class Transporte(Protocol):
    def enviar(self, url: str, carga: dict, timeout: float) -> dict: ...


class _TransporteHTTP:
    """Transporte real, sobre a biblioteca padrão — sem dependência extra."""

    def enviar(self, url: str, carga: dict, timeout: float) -> dict:
        import urllib.error
        import urllib.request

        requisicao = urllib.request.Request(
            url,
            data=json.dumps(carga).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.URLError as erro:
            raise OSError(str(erro)) from erro


class ClienteOllama:
    """Fala com um servidor de inferência compatível com a API do Ollama.

    O servidor pode ser local ou remoto: o cliente só faz HTTP, e toda a carga
    de modelo fica do lado do servidor.
    """

    def __init__(
        self,
        modelo: str,
        *,
        url: str = URL_PADRAO,
        transporte: Transporte | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.modelo = modelo
        self.url = url.rstrip("/")
        self.transporte = transporte or _TransporteHTTP()
        self.timeout = timeout

    def gerar(self, prompt: str, *, schema: dict, imagens: list[str] | None = None) -> Any:
        """Pede uma resposta conforme o schema.

        Args:
            imagens: imagens em base64, para modelos com visão. Uma página
                renderizada entra por aqui.

        Levanta:
            ServidorIndisponivel: sem comunicação com o servidor.
            RespostaInvalida: resposta que não é JSON conforme.
        """
        carga: dict[str, Any] = {
            "model": self.modelo,
            # Repetir a instrução no prompt não é redundante: sem ela a
            # amostragem degrada mesmo com a decodificação restringida.
            "prompt": f"{prompt}\n\nResponda apenas com JSON válido.",
            "format": schema,
            "stream": False,
        }
        if imagens:
            carga["images"] = imagens

        try:
            resposta = self.transporte.enviar(f"{self.url}/api/generate", carga, self.timeout)
        except OSError as erro:
            raise ServidorIndisponivel(
                f"sem resposta de {self.url} — o servidor está no ar e acessível? ({erro})"
            ) from erro

        bruto = resposta.get("response", "")
        try:
            return json.loads(bruto)
        except (json.JSONDecodeError, TypeError) as erro:
            trecho = str(bruto)[:120]
            raise RespostaInvalida(
                f"modelo {self.modelo!r} não devolveu JSON: {trecho!r}"
            ) from erro


INSTRUCAO_PADRAO = (
    "Extraia os itens da tabela. Para cada item, informe os campos pedidos. "
    "Use exatamente o texto do documento; não calcule nem estime. "
    "Se um valor não aparecer, omita o campo."
)


class ExtratorBaseadoEmModelo:
    """Base comum às estratégias que delegam a extração a um modelo.

    Concentra o que não varia entre elas — schema, validação da resposta e
    construção dos campos — para que a diferença entre enviar texto e enviar
    imagem seja **só** essa. Se cada uma tratasse a resposta à sua maneira, a
    comparação entre as duas mediria também a diferença de tratamento.

    Subclasses implementam apenas `_consultar`.
    """

    def __init__(
        self,
        cliente: ClienteOllama,
        campos: list[str],
        *,
        instrucao: str | None = None,
    ) -> None:
        self.cliente = cliente
        self.campos = campos
        self.instrucao = instrucao or INSTRUCAO_PADRAO

    def extrair(self, documento: DocumentoCanonico) -> list[Registro]:
        registros: list[Registro] = []
        for pagina in documento.paginas:
            resposta = self._consultar(pagina)
            registros.extend(
                self._registro(item, pagina.numero, documento.identificador)
                for item in self._itens(resposta)
            )
        return registros

    def _consultar(self, pagina) -> Any:
        raise NotImplementedError

    def _prompt(self) -> str:
        return f"{self.instrucao}\n\nCampos: {', '.join(self.campos)}"

    def _schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {campo: {"type": ["string", "number", "null"]} for campo in self.campos},
                    },
                }
            },
            "required": ["itens"],
        }

    @staticmethod
    def _itens(resposta: Any) -> list[dict]:
        if isinstance(resposta, dict):
            itens = resposta.get("itens", [])
            return [i for i in itens if isinstance(i, dict)]
        return []

    def _registro(self, item: dict, pagina: int, fonte: str) -> Registro:
        # Só os campos do schema entram: o que o modelo acrescentar por conta
        # própria é descartado, não promovido a dado.
        campos = {campo: self._campo(item.get(campo), pagina) for campo in self.campos}
        return Registro(campos=campos, fonte=fonte)

    @staticmethod
    def _campo(valor: Any, pagina: int) -> Campo:
        if valor is None or valor == "":
            return Campo.ausente()

        evidencia = Evidencia(pagina=pagina, texto_bruto=str(valor))
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return Campo[float].extraido(
                valor=float(valor), evidencia=evidencia, confianca=CONFIANCA_MODELO
            )

        try:
            numero, sentinela = parse_numero(str(valor))
        except ValorNaoReconhecido:
            return Campo[str].extraido(
                valor=str(valor), evidencia=evidencia, confianca=CONFIANCA_MODELO
            )
        return Campo[float].extraido(
            valor=numero, sentinela=sentinela, evidencia=evidencia, confianca=CONFIANCA_MODELO
        )


class ExtratorModelo(ExtratorBaseadoEmModelo):
    """Envia o **texto** da página a um modelo de linguagem.

    Uma página por chamada: enviar o documento inteiro estouraria o contexto e
    trocaria recuperação seletiva por "empurrar tudo e esperar que o modelo se
    vire".

    Depende da camada de texto do documento e, portanto, herda dela a ordem de
    leitura — inclusive quando essa ordem não corresponde à estrutura visual. É
    exatamente essa dependência que a rota por visão não tem, e é o que as duas
    estratégias existem para comparar.

    Usa os mesmos degraus de saída da rota por visão (SPEC §4.4). Não porque o
    colapso do esquema tenha sido observado aqui, mas porque tratar as duas rotas
    de modo diferente introduziria, na comparação entre elas, uma diferença que
    não é a que se quer medir (ADR-0005).
    """

    def __init__(
        self,
        cliente: ClienteOllama,
        campos: list[str],
        *,
        instrucao: str | None = None,
        degrau_maximo: Any = None,
    ) -> None:
        from parser.degraus import SaidaEmDegraus

        super().__init__(cliente, campos, instrucao=instrucao)
        self.saida = SaidaEmDegraus(cliente, campos, degrau_maximo=degrau_maximo)
        self.degraus_usados: list[Any] = []
        """O degrau que produziu cada página, na ordem."""

    def _consultar(self, pagina) -> Any:
        resultado = self.saida.obter(f"{self._prompt()}\n\n{pagina.texto}")
        self.degraus_usados.append(resultado.degrau)
        return resultado.dados
