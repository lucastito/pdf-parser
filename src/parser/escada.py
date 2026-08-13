"""A escada de modelos, e quem roda o quê — **uma fonte, não três**.

Este módulo existe por um defeito medido. A lista de modelos vivia em três lugares
— o instalador em PowerShell, a constante da linha de comando, e a tabela do
levantamento — e os três divergiram: o instalador ficou com 8 de 13 modelos, um
modelo entrou no instalador sem estar na escada documentada, e o teste que deveria
pegar isso comparava dois dos três lugares que já concordavam entre si.

Aqui a escada é dado: nome, rota, tamanho **verificado no catálogo**, fabricante.
Quem precisa da lista deriva dela — o instalador, o diagnóstico, a bateria.

## O que a memória de vídeo decide, e o que não decide

**Não decide se o modelo roda.** O servidor reparte sozinho: carrega na placa o que
couber e deixa o resto na memória do sistema. Medido em 2026-08-02, na máquina de
referência (placa de 2 GB): `qwen3:4b` ocupa 3,28 GB, dos quais **0,54 GB (16%) na
placa** e 2,75 GB na memória do sistema — maior que a placa inteira, e roda.

**Decide a fração que vai acelerada.** Daí os dois conjuntos por máquina:

- **obrigatório** — cabe na placa com folga, roda acelerado. Sustenta a comparação
  *entre* máquinas, porque todas o executam nas mesmas condições;
- **estendido** — só cabe somando a memória do sistema, roda repartido. Mede **o
  custo de exceder a placa**, e é o que leva a família independente aos envelopes
  menores, que de outro modo ficariam sem controle de fabricante.

A alocação concreta por máquina vive em `experimentos/ALOCACAO-POR-MAQUINA.md`, e
**é rascunho** até as máquinas relatarem memória real e divisão medida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "ESCADA",
    "Modelo",
    "MODELOS_DO_EXPERIMENTO",
    "obrigatorios",
    "estendidos",
    "modelo_de_falha",
]

Rota = Literal["visao", "texto", "ambas"]


@dataclass(frozen=True)
class Modelo:
    """Um degrau da escada.

    `tamanho_gb` é o tamanho de download **verificado no catálogo**, não estimado:
    três números do levantamento anterior estavam errados, e um deles alocava um
    modelo de 7,6 GB como se pedisse 12 — o que tirava a família independente de
    duas máquinas sem necessidade.
    """

    nome: str
    rota: Rota
    tamanho_gb: float
    fabricante: str
    pergunta: str
    """O que só este degrau responde. Modelo que não isola variável nova não entra,
    por melhor que seja sua reputação (ADR-0014)."""

    @property
    def le_imagem(self) -> bool:
        return self.rota in ("visao", "ambas")

    @property
    def le_texto(self) -> bool:
        return self.rota in ("texto", "ambas")


ESCADA: tuple[Modelo, ...] = (
    # --- Visão: generalistas pequenos, do menor ao maior -------------------
    Modelo("minicpm-v4.6:1b", "visao", 1.6, "OpenBMB", "o piso — o menor da escada"),
    Modelo("qwen3-vl:2b", "visao", 1.9, "Alibaba", "denominador comum, porte menor"),
    Modelo("qwen3-vl:4b", "visao", 3.3, "Alibaba", "denominador comum, porte médio"),
    Modelo("qwen3-vl:8b", "visao", 6.1, "Alibaba", "efeito do tamanho, resto constante"),
    Modelo("minicpm-v4.5:8b", "visao", 6.1, "OpenBMB", "codificador visual sobre outra base"),
    # --- Visão: especializados em documento --------------------------------
    Modelo("glm-ocr", "visao", 2.2, "Zhipu", "especializado em documento, e minúsculo"),
    Modelo("deepseek-ocr:3b", "visao", 6.7, "DeepSeek", "compressão óptica de contexto"),
    Modelo(
        "ibm/granite-docling",
        "visao",
        0.522,
        "IBM",
        "especializado em documento, o menor da escada inteira",
    ),
    # --- Visão: reintegrado (revisão de 2026-08-13, ver MODELOS.md) ---------
    Modelo(
        "granite3.2-vision:2b",
        "visao",
        2.4,
        "IBM",
        "reintegrado — descartado em 2026-08-01 por benchmark de terceiro, mesmo "
        "argumento que reintegrou deepseek-ocr: o projeto tem instrumentação "
        "própria para diagnosticar a falha atribuída a ele",
    ),
    # --- Texto --------------------------------------------------------------
    Modelo("qwen3:1.7b", "texto", 1.4, "Alibaba", "piso da rota de texto"),
    Modelo("qwen3:4b", "texto", 2.5, "Alibaba", "denominador comum com a referência"),
    Modelo("qwen3:8b", "texto", 5.2, "Alibaba", "efeito do tamanho, resto constante"),
    Modelo("qwen3:14b", "texto", 9.3, "Alibaba", "limite prático do envelope de 12 GB"),
    Modelo(
        "deepseek-r1:7b",
        "texto",
        4.7,
        "DeepSeek",
        "raciocínio dedicado, destilado, porte menor",
    ),
    Modelo("deepseek-r1:8b", "texto", 5.2, "DeepSeek", "raciocínio dedicado, destilado"),
    Modelo("nemotron-3-nano:4b", "texto", 2.8, "NVIDIA", "fabricante novo, porte comparável"),
    Modelo("granite4.1:8b", "texto", 5.3, "IBM", "fabricante novo, porte médio, texto apenas"),
    # --- Família independente, nas duas rotas -------------------------------
    Modelo("gemma4:12b", "ambas", 7.6, "Google", "família independente, e multimodal"),
    # --- Geração nova da família de referência: unifica texto e visão -------
    Modelo(
        "qwen3.5:0.8b",
        "ambas",
        1.0,
        "Alibaba",
        "nativamente multimodal — a unificação texto+visão custa qualidade?",
    ),
    Modelo("qwen3.5:4b", "ambas", 3.4, "Alibaba", "mesma pergunta do 0.8b, porte médio"),
    Modelo("qwen3.5:9b", "ambas", 6.6, "Alibaba", "mesma pergunta, porte maior"),
    # --- MoE esparso, comparado entre fabricantes ---------------------------
    Modelo(
        "nemotron-3.5-lightning:30b",
        "texto",
        25.0,
        "NVIDIA",
        "MoE esparso (3B ativado de 30B) — mesma pergunta do Qwen3.5, fabricante cruzado",
    ),
    # --- Fabricante europeu, unifica as duas rotas num modelo denso --------
    Modelo(
        "ministral-3:3b",
        "ambas",
        3.0,
        "Mistral AI",
        "único fabricante europeu da escada, porte de edge — alcança até a máquina "
        "de referência",
    ),
    Modelo(
        "mistral-small3.2:24b",
        "ambas",
        15.0,
        "Mistral AI",
        "mesmo fabricante, porte maior — efeito do tamanho dentro da família europeia",
    ),
    # --- Teto: existem para falhar e marcar o limite ------------------------
    Modelo("qwen3-vl:30b", "visao", 20.0, "Alibaba", "teto de visão"),
    Modelo("qwen3:30b", "texto", 19.0, "Alibaba", "teto de texto"),
)
"""Os degraus, do menor ao maior dentro de cada grupo.

**Os três portes da família de referência** (`2b`, `4b`, `8b`) ficam de propósito:
são três pontos com origem, geração e quantização constantes, o que dá a curva de
tamanho mais limpa que o experimento pode ter. O de 4 bilhões é, além disso, o
modelo com mais medição acumulada no projeto.

**Revisão de 2026-08-13** (detalhe completo e "o que não entrou" em
`experimentos/MODELOS.md`): acrescentou três fabricantes novos (NVIDIA, IBM,
Mistral AI — eram cinco, agora oito), reintegrou `granite3.2-vision` pelo mesmo
motivo que já tinha reintegrado `deepseek-ocr`, e acrescentou a geração
`qwen3.5` (nativamente multimodal) ao lado da família de referência, sem
substituí-la. Todo tamanho abaixo é o de download **verificado** na página do
modelo em `ollama.com/library/...` — nunca estimado.
"""

MODELOS_DO_EXPERIMENTO: tuple[str, ...] = tuple(m.nome for m in ESCADA)
"""Nomes, para quem só precisa da lista. Derivado — nunca escrito à mão."""

FOLGA_DA_PLACA = 0.85
"""Fração da memória de vídeo utilizável por um modelo.

O resto é contexto, buffers e o que o sistema já ocupa. Encher a placa até a borda
faz o servidor repartir de qualquer forma — e aí o modelo aparece como acelerado
sem estar.
"""

FOLGA_DA_MEMORIA = 0.60
"""Fração da memória do sistema utilizável.

Conservador de propósito: a máquina é de outra pessoa, que pode estar usando-a. Um
modelo que ocupe toda a memória livre leva o sistema a paginar em disco, e aí o
tempo medido é do disco, não do modelo.
"""

TETO_SEM_ACELERACAO_GB = 7.0
"""Maior modelo que uma máquina sem aceleração real ainda vale a pena baixar.

**O limite ali é tempo, não memória.** A máquina de referência tem memória de
sobra e placa que não acelera: pelo critério de memória, ela baixaria a escada
inteira — 54 GB — e levaria dias por página nos maiores.

Medido: uma página pela rota de visão custou 77 minutos com um modelo de 3,3 GB.
O teto deixa passar a família independente (7,6 GB fica de fora por pouco, e é
uma escolha a revisar quando houver medição de tempo por tamanho) e corta os de
20 GB, que não produziriam resultado em prazo útil.
"""

MULTIPLO_MAXIMO_DA_PLACA = 1.6
"""Quantas vezes a placa um modelo repartido pode chegar a ocupar.

**Memória não é o único custo — tempo é o que inviabiliza.** Sem este limite, a
máquina de referência (placa de 2 GB, memória farta) baixaria a escada inteira,
inclusive os modelos de 20 GB: caberiam na memória e levariam **dias** por página
em processador, porque quase nada estaria acelerado.

O limite mantém o conjunto estendido no seu propósito — medir o custo de exceder a
placa um pouco —, em vez de virar "roda tudo, devagar". Máquina sem placa útil usa
a memória como referência, já que ali a placa não é o gargalo.
"""


def obrigatorios(vram_gb: float) -> list[Modelo]:
    """Modelos que cabem na placa — rodam acelerados.

    É o conjunto que sustenta a comparação **entre** máquinas: todas executam nas
    mesmas condições, então a diferença medida é da máquina.
    """
    teto = vram_gb * FOLGA_DA_PLACA
    return [m for m in ESCADA if m.tamanho_gb <= teto]


def _teto_pratico(vram_gb: float, ram_livre_gb: float, *, placa_util: bool) -> float:
    """O maior modelo que a máquina roda **em tempo aceitável**, não só o que cabe.

    Dois limites, e vale o menor:

    - **memória** — o que cabe somando placa e sistema, com folga;
    - **proporção** — no máximo algumas vezes a placa, porque além disso quase nada
      fica acelerado e o tempo por página passa de horas.

    `placa_util=False` desliga o segundo: numa máquina cuja placa não acelera (a de
    referência mede 17,1 contra 17,5 tokens/s), a proporção não diz nada — o
    gargalo é o processador, e o limite honesto é a memória.
    """
    por_memoria = vram_gb + ram_livre_gb * FOLGA_DA_MEMORIA
    if not placa_util:
        # Sem aceleração, o limite é quanto tempo se aceita esperar. Medido na
        # máquina de referência: uma página pela rota de visão levou 77 minutos
        # com um modelo de 3,3 GB. O dobro disso já são horas por página, e a
        # bateria inteira viraria semanas — para medir o que a curva já mostra.
        return min(por_memoria, TETO_SEM_ACELERACAO_GB)
    return min(por_memoria, vram_gb * MULTIPLO_MAXIMO_DA_PLACA)


def estendidos(
    vram_gb: float, ram_livre_gb: float, *, placa_util: bool = True
) -> list[Modelo]:
    """Modelos que só cabem somando a memória do sistema — rodam repartidos.

    Medem o custo de exceder a placa, e levam a família independente aos envelopes
    menores. Sem eles, uma máquina de 6 GB não rodaria nenhum modelo de fabricante
    independente, e o controle de origem se perderia justamente onde a curva dobra.

    Args:
        placa_util: a placa acelera de fato? Deve vir de **medição** — carregar um
            modelo e comparar —, nunca do nome da peça. A máquina de referência tem
            placa que funciona e não acelera, e tratá-la como aceleradora produziria
            uma lista de modelos que levaria dias por página.
    """
    piso = vram_gb * FOLGA_DA_PLACA
    teto = _teto_pratico(vram_gb, ram_livre_gb, placa_util=placa_util)
    return [m for m in ESCADA if piso < m.tamanho_gb <= teto]


def modelo_de_falha(
    vram_gb: float, ram_livre_gb: float, *, placa_util: bool = True
) -> Modelo | None:
    """O degrau seguinte ao que a máquina comporta — existe para falhar.

    Escada que só sobe enquanto funciona não revela o teto, e o teto é o que
    orienta decisão de infraestrutura.

    **É relativo à máquina, não absoluto:** a de referência tenta um de 8 bilhões e
    a maior tenta um de 30, e nenhuma baixa 20 GB à toa.

    Devolve `None` quando a máquina comporta a escada inteira — não há o que
    tentar, e inventar um modelo maior só para falhar seria medir o catálogo, não
    a máquina. **`None` é resultado**, e significa "esta máquina não encontrou o
    próprio limite nesta escada": informação legítima sobre o teto superior.
    """
    teto = _teto_pratico(vram_gb, ram_livre_gb, placa_util=placa_util)
    acima = [m for m in ESCADA if m.tamanho_gb > teto]
    return min(acima, key=lambda m: m.tamanho_gb) if acima else None


def fabricantes(modelos: list[Modelo]) -> set[str]:
    """Origens distintas no conjunto.

    Serve à verificação que o ADR-0014 exige: concentração de origem faz uma
    conclusão sobre *uma família* parecer conclusão sobre *modelos abertos*.
    """
    return {m.fabricante for m in modelos}


TODOS_OS_FABRICANTES = frozenset(m.fabricante for m in ESCADA)


def _completar_fabricantes(
    escolhidos: list[Modelo], vram_gb: float, ram_livre_gb: float
) -> list[Modelo]:
    """Garante que toda máquina veja todas as origens, custe um modelo a mais.

    **Cobertura de fabricante é requisito, não sobra.** O ADR-0014 registra o erro
    de montar uma escada concentrada numa família: se ela fosse ruim no documento
    testado, a conclusão registrada seria *"modelos abertos não servem"* quando o
    correto seria *"aquela família não serve"*.

    O limite de tempo, aplicado sozinho, reintroduzia esse erro pela porta dos
    fundos: a máquina sem aceleração perdia a família independente, justamente a
    que existe como controle. Aqui, quando uma origem ficaria de fora, entra **o
    menor modelo dela que ainda caiba na memória** — aceitando que rode devagar,
    porque um ponto lento de uma família é melhor que nenhum.
    """
    presentes = {m.fabricante for m in escolhidos}
    faltando = TODOS_OS_FABRICANTES - presentes
    if not faltando:
        return escolhidos

    cabe_na_memoria = vram_gb + ram_livre_gb * FOLGA_DA_MEMORIA
    extras = []
    for origem in sorted(faltando):
        candidatos = [
            m for m in ESCADA if m.fabricante == origem and m.tamanho_gb <= cabe_na_memoria
        ]
        if candidatos:
            extras.append(min(candidatos, key=lambda m: m.tamanho_gb))
    return escolhidos + extras


def alocar(
    vram_gb: float, ram_livre_gb: float, *, placa_util: bool = True
) -> dict[str, list[Modelo]]:
    """O que uma máquina baixa, e por quê — a decisão inteira num lugar.

    Devolve três conjuntos, que respondem a perguntas diferentes:

    - `obrigatorio` — cabe na placa, roda acelerado. Sustenta a comparação **entre**
      máquinas, porque todas o executam nas mesmas condições;
    - `estendido` — cabe somando a memória do sistema, roda repartido. Mede o custo
      de exceder a placa, e inclui o que for preciso para **toda origem estar
      representada**;
    - `falha` — um degrau acima do que a máquina comporta. Existe para não executar,
      e marcar onde o limite está. Lista vazia significa que a máquina comporta a
      escada inteira — que também é resultado.

    Args:
        placa_util: a placa acelera de fato? **Vem de medição**, não do nome da
            peça: a máquina de referência tem placa que funciona e não acelera
            (17,1 contra 17,5 tokens/s), e tratá-la como aceleradora produziria uma
            lista que levaria dias por página.
    """
    obrigatorio = obrigatorios(vram_gb)
    estendido = estendidos(vram_gb, ram_livre_gb, placa_util=placa_util)
    completo = _completar_fabricantes(obrigatorio + estendido, vram_gb, ram_livre_gb)
    falha = modelo_de_falha(vram_gb, ram_livre_gb, placa_util=placa_util)

    escolhidos = {m.nome for m in completo}
    return {
        "obrigatorio": obrigatorio,
        "estendido": [m for m in completo if m not in obrigatorio],
        # O de falha não pode estar entre os que se espera que rodem: baixá-lo duas
        # vezes desperdiça banda, e contá-lo como esperado inverteria a leitura do
        # resultado — a falha dele é o dado.
        "falha": [falha] if falha and falha.nome not in escolhidos else [],
    }
