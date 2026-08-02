"""Dimensionamento do contexto: quanto pedir, e por quê.

O contexto limita **entrada mais saída, somadas**. Herdá-lo do padrão do
servidor foi a causa de uma conclusão errada que este projeto publicou: as
respostas vinham vazias, e a culpa foi atribuída ao modelo por uma sessão
inteira (ADR-0018).

O erro simétrico é menos óbvio e mais perigoso. Cada token de contexto cobra
memória, linearmente. Pedir muito faz o modelo não caber, e um servidor que não
consegue alocar despeja o trabalho para o processador — ficando ordens de
grandeza mais lento **sem sinal algum**. O número resultante sairia como "esta
máquina é lenta", que é a contaminação silenciosa do ADR-0019.

Por isso o cálculo é um mínimo entre três limites, nunca "o maior valor que dá":

    necessário = (entrada_medida + saída_esperada) × folga
    viável     = (memória_livre − peso) / custo_por_token
    usar       = min(nativo, viável, necessário)

O primeiro termo é **medido**, não estimado. Com imagem, a entrada é a maior
parte, e varia com a resolução — supor um valor foi exatamente o que falhou.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Afericao", "CustoDeMemoria", "aferir", "dimensionar"]

FOLGA_PADRAO = 1.5
"""Margem sobre o necessário.

Não é número mágico: com a maior saída observada (5948 tokens) e a maior
entrada (2233), o necessário é ~8200 e a folga leva a ~12300 — abaixo dos 16384
que uma medição confirmou não cortar, e acima de qualquer caso medido.

Existe porque a saída de uma página seguinte pode ser maior que a da página
medida, e errar para baixo desperdiça a chamada inteira.
"""


@dataclass(frozen=True)
class CustoDeMemoria:
    """Quanto um modelo ocupa, em função do contexto pedido.

    Medido num modelo de visão de 4B quantizado: 3,6 GB com contexto de 4096 e
    8,0 GB com 32768. A reta ajustada com esses dois pontos previu o terceiro
    (16384 → 5,5 GB) com **0,4% de erro** — que é a diferença entre curva
    ajustada e curva com poder preditivo.

    Atenção ao que isto **não** é: o valor cobre o processo inteiro (cache de
    atenção, buffers, codificador visual), não o cache isolado que a literatura
    calcula. E a inclinação depende da arquitetura — vale para o modelo em que
    foi medida, e outros precisam ser medidos.
    """

    peso_gb: float
    """Memória do modelo com contexto zero — o intercepto da reta."""

    por_token_gb: float
    """Memória adicional por token de contexto."""

    @classmethod
    def a_partir_de_dois_pontos(
        cls,
        *,
        contexto_a: int,
        memoria_a_gb: float,
        contexto_b: int,
        memoria_b_gb: float,
    ) -> CustoDeMemoria:
        """Ajusta a reta a duas medições da mesma máquina e modelo.

        Levanta:
            ValueError: se os contextos forem iguais — dois pontos coincidentes
                não definem reta, e aceitar isso produziria inclinação infinita.
        """
        if contexto_a == contexto_b:
            raise ValueError("são necessários dois contextos distintos para ajustar a reta")

        inclinacao = (memoria_b_gb - memoria_a_gb) / (contexto_b - contexto_a)
        return cls(peso_gb=memoria_a_gb - contexto_a * inclinacao, por_token_gb=inclinacao)

    def memoria_para(self, contexto: int) -> float:
        """Memória prevista, em GB, para o contexto pedido."""
        return self.peso_gb + contexto * self.por_token_gb

    def contexto_que_cabe(self, memoria_livre_gb: float) -> int:
        """O maior contexto que cabe na memória disponível.

        Levanta:
            ValueError: se nem o peso do modelo couber. Falhar aqui é
                deliberado: a alternativa é o servidor cair para o processador
                em silêncio, e o resultado ser atribuído à máquina em vez da
                configuração (ADR-0019).
        """
        sobra = memoria_livre_gb - self.peso_gb
        if sobra <= 0:
            raise ValueError(
                f"o modelo não cabe: pesa {self.peso_gb:.1f} GB e há "
                f"{memoria_livre_gb:.1f} GB livres. Rodar assim empurra o "
                "trabalho para o processador sem aviso, e o tempo medido "
                "descreveria a configuração, não a máquina."
            )
        return int(sobra / self.por_token_gb)


def dimensionar(
    *,
    entrada: int,
    saida_esperada: int,
    folga: float = FOLGA_PADRAO,
    nativo: int | None = None,
    memoria_livre_gb: float | None = None,
    custo: CustoDeMemoria | None = None,
) -> int:
    """Quanto contexto pedir ao servidor.

    Args:
        entrada: tokens que o pedido consome, **medidos** numa chamada barata.
            Com imagem é a maior parte do orçamento e varia com a resolução;
            estimá-lo foi o erro que produziu a conclusão errada do ADR-0018.
        saida_esperada: tokens que a resposta deve ocupar. Sai da maior resposta
            já observada para o mesmo tipo de pedido.
        folga: margem sobre o necessário. Errar para baixo desperdiça a chamada
            inteira; errar para cima cobra memória.
        nativo: contexto máximo do modelo. Pedir além disto seria recusado.
        memoria_livre_gb: memória disponível. Sem ela, **nenhum** teto de
            memória é aplicado — inventar um seria número mágico (ADR-0008).
        custo: a curva de memória daquele modelo naquela máquina. Só tem efeito
            junto com `memoria_livre_gb`.

    Levanta:
        ValueError: se nem o peso do modelo couber na memória informada.
    """
    limites = [int((entrada + saida_esperada) * folga)]

    if nativo:
        limites.append(nativo)

    if memoria_livre_gb is not None and custo is not None:
        limites.append(custo.contexto_que_cabe(memoria_livre_gb))

    return min(limites)


@dataclass(frozen=True)
class Afericao:
    """O que uma chamada barata revelou sobre um modelo, antes da bateria."""

    modelo: str
    entrada: int
    """Tokens que **este** modelo consome com **esta** entrada. Medido."""

    contexto: int
    """Contexto calculado a partir da entrada medida, não herdado."""


def aferir(
    modelo: str,
    *,
    medir,
    prompt: str,
    imagens: list[str] | None = None,
    saida_esperada: int = 2607,
    nativo: int | None = None,
    memoria_livre_gb: float | None = None,
    custo: CustoDeMemoria | None = None,
) -> Afericao:
    """Mede a entrada de um modelo e calcula o contexto **dele**.

    Existe porque o mesmo erro apareceu três vezes neste projeto, cada vez num
    nível acima: contexto herdado do padrão do servidor (ADR-0018), teto de saída
    elevado sem resolver, e contexto fixado para um modelo e usado por seis.

    A raiz é sempre a mesma — **um número que depende da entrada tratado como
    constante**. E a entrada varia por modelo: medido na mesma imagem,
    `qwen3-vl:2b` consome 2159 tokens e `glm-ocr` consome 2791.

    Args:
        medir: função que faz a chamada e devolve os tokens de entrada. Injetada
            para que o teste exercite o contrato sem servidor.
        saida_esperada: quantos tokens a resposta deve ocupar. O padrão vem da
            maior saída já observada para uma página inteira.

    Raises:
        ValueError: se nem a entrada couber no contexto nativo. **Falhar aqui é
            o propósito** — sem isso a bateria roda, é cortada no meio, e quem
            está do outro lado descobre depois de horas.

    A chamada pede **um** token de saída: mede a entrada sem gerar resposta. O
    custo real é carregar o modelo, que a bateria pagaria em seguida de qualquer
    forma.
    """
    entrada = medir(modelo, prompt, imagens)

    if nativo and entrada >= nativo:
        raise ValueError(
            f"{modelo}: a entrada sozinha ({entrada} tokens) não cabe no contexto "
            f"nativo ({nativo}). Reduza a resolução da imagem ou fatie a tarefa — "
            "rodar assim seria cortado no meio, depois de horas."
        )

    contexto = dimensionar(
        entrada=entrada,
        saida_esperada=saida_esperada,
        nativo=nativo,
        memoria_livre_gb=memoria_livre_gb,
        custo=custo,
    )

    if contexto <= entrada:
        raise ValueError(
            f"{modelo}: o contexto viável ({contexto}) não cabe nem a entrada "
            f"({entrada}). Não há espaço para resposta alguma."
        )

    return Afericao(modelo=modelo, entrada=entrada, contexto=contexto)
