"""Extração por modelo de visão: a página vai como imagem, não como texto.

É a estratégia que testa a hipótese mais interessante do projeto. As rotas
determinística e por modelo de texto dependem da camada de texto do documento —
herdando dela toda ordem de leitura embaralhada e toda estrutura perdida. Um
modelo de visão enxerga a página como um leitor humano: alinhamento, proximidade,
rotação.

Em documento cuja tabela não tem linhas de grade e está rotacionada, essa
diferença pode ser decisiva. **Pode.** É hipótese a medir contra o gabarito, não
conclusão a assumir — e o custo em processamento é parte do que se mede.

Herda de `ExtratorBaseadoEmModelo` para que a única diferença em relação à rota
de texto seja o envio da imagem. Schema, validação e construção dos campos são
compartilhados; do contrário a comparação incluiria a diferença de tratamento.
"""

from __future__ import annotations

from typing import Any

from parser.degraus import Degrau, SaidaEmDegraus
from parser.fontes.render import DPI_PADRAO, renderizar, _validar_dpi
from parser.ollama import ClienteOllama, ExtratorBaseadoEmModelo
from parser.portas import Pagina

__all__ = ["ExtratorVLM"]

INSTRUCAO_VISUAL = (
    "A imagem mostra uma página com uma tabela. Leia a tabela e extraia os itens. "
    "Atenção ao alinhamento das colunas: o cabeçalho pode estar rotacionado e a "
    "tabela pode não ter linhas de grade. Use exatamente os valores impressos; "
    "não calcule nem estime. Se um valor não aparecer, omita o campo."
)


class ExtratorVLM(ExtratorBaseadoEmModelo):
    """Envia cada página renderizada como imagem a um modelo de visão."""

    def __init__(
        self,
        cliente: ClienteOllama,
        campos: list[str],
        caminho_pdf: str,
        *,
        instrucao: str | None = None,
        dpi: int = DPI_PADRAO,
        degrau_maximo: Degrau | None = None,
        raciocinar: bool = False,
        tokens_maximos: int | None = None,
        contexto: int | None = None,
    ) -> None:
        """
        Args:
            caminho_pdf: o documento original. A renderização precisa do arquivo,
                não do formato canônico — limitação real desta estratégia, e um
                dos pontos em que ela é menos substituível que a determinística.
            dpi: resolução da imagem. **Registre-o junto do resultado**: é
                variável do experimento, e duas execuções com DPI diferente não
                são comparáveis.

                Vale também para o `contexto`: mais resolução significa mais
                tokens de entrada, e a entrada disputa espaço com a resposta.
            contexto: teto de entrada **mais** saída. Nesta rota é o parâmetro
                mais sensível: uma página renderizada consome ~2200 tokens só de
                entrada, e o padrão do servidor (4096) deixa pouco para a
                resposta. Foi a causa medida das respostas vazias (ADR-0018).
            degrau_maximo: o degrau de saída mais livre permitido (SPEC §4.4).
                Fixá-lo torna uma bateria de execuções comparável entre si; deixá-lo
                aberto maximiza a chance de obter saída de um modelo pequeno.
            raciocinar: liga o canal de raciocínio do modelo. Desligado por ser o
                caso mais simples — **não** por estar provado que resolve alguma
                coisa: a medição mostrou que desligar quase não altera a geração.
                Existe para poder ser medido. Ver `parser.degraus`.
        """
        _validar_dpi(dpi)
        super().__init__(cliente, campos, instrucao=instrucao or INSTRUCAO_VISUAL)
        self.caminho_pdf = caminho_pdf
        self.dpi = dpi
        self.saida = SaidaEmDegraus(
            cliente,
            campos,
            degrau_maximo=degrau_maximo,
            raciocinar=raciocinar,
            tokens_maximos=tokens_maximos,
            contexto=contexto,
        )
        self.degraus_usados: list[Degrau] = []
        """O degrau que produziu cada página, na ordem.

        Guardado porque só rodadas no mesmo degrau são comparáveis: sem este
        registro, a matriz mediria também a diferença de restrição (ADR-0005).
        """

    def _consultar(self, pagina: Pagina) -> Any:
        imagem = renderizar(self.caminho_pdf, pagina=pagina.numero, dpi=self.dpi)
        resultado = self.saida.obter(self._prompt(), imagens=[imagem])
        self.degraus_usados.append(resultado.degrau)
        return resultado.dados
