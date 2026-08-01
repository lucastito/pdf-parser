# Glossário

> Existe porque **a mesma palavra estava sendo usada para três coisas** — o Lucas
> perguntou *"o degrau é por dpi?"* e a pergunta era sintoma, não confusão dele.
>
> Termo usado fora deste vocabulário é erro de escrita, não estilo.

## Os três sentidos que colidiam

| Termo correto | O que é | Onde vive |
|---|---|---|
| **degrau de saída** | quanto a resposta do modelo é restringida | `Degrau` em `degraus.py` |
| **posição na escada** | tamanho do modelo, do menor ao maior | `MODELOS.md`, ADR-0014 |
| **envelope** | capacidade de memória da máquina | ADR-0014 |

Os três eram chamados de "degrau". Agora só o primeiro é.

---

## Vocabulário

### degrau de saída

As três formas de restringir a resposta do modelo, da mais estrita à mais livre:
esquema como gramática → `format: json` → texto livre com recorte.

São as hipóteses **H1, H2 e H3** (ADR-0020). Não têm relação com tamanho de
modelo nem com capacidade de máquina.

### posição na escada

O lugar de um modelo na sequência ordenada por tamanho — de `minicpm-v4.6:1b`
(1,6 GB) a `qwen3-vl:30b` (20 GB). Responde *"maior é melhor?"*.

**Especializados em documento não têm posição**: `glm-ocr` e `deepseek-ocr`
existem em um tamanho só, e respondem outra pergunta — *"especializado bate
generalista?"*.

### envelope

A memória de vídeo da máquina: 2, 6, 8, 12 ou 16 GB. Define **quais** modelos
cabem, não quão bem eles leem.

> Capacidade de memória **não** é capacidade de computação. A máquina de
> referência tem 2 GB e mesmo assim executa em processador, porque a arquitetura
> da placa (2017) está abaixo do que o servidor exige. **Verificar as duas
> coisas** (ADR-0014).

### hipótese

Uma das **nove** variações de configuração que a triagem testa (ADR-0020): os três
degraus de saída, raciocínio, contexto, fatiamento, guardrails, resolução da
imagem, e variante instruct contra thinking.

O **dpi é a H8** — uma hipótese entre nove, não um "degrau".

### característica

Um traço estrutural da **página**: rotacionada, digitalizada, tabela sem grade,
multi-coluna, células mescladas (ADR-0021).

A triagem roda **uma página por característica** — não todos os documentos, e não
várias páginas do mesmo tipo.

### classe de conteúdo

O que a página contém: `DADOS`, `CONTEXTO` ou `DESCARTAVEL` (`triagem.Classe`).

**Eixo ortogonal à característica**: uma página é `DADOS` **e**
`DIGITALIZADA` ao mesmo tempo.

### rota

Uma estratégia de extração: `posicional`, `pdfplumber`, `camelot`, `ocr`,
`linear`, `pymupdf`, `llm`, `vlm`. Mais as variantes `-menor`, que rodam o mesmo
extrator com um modelo menor.

### denominador comum

Os modelos que rodam em **todas** as máquinas. São o ponto de contato que torna a
comparação legítima — sem eles, cada máquina produziria resultados sem base
comum.

Hoje: `qwen3-vl:2b` **e** `qwen3-vl:4b`. Em par, medem também o efeito do tamanho
com todo o resto constante.

### erro × omissão

Duas falhas de gravidade oposta, contadas **separado** (ADR-0020):

- **omissão** — não preencheu; vira pendência para revisão humana. Aceitável.
- **erro** — preencheu errado; entra na planilha como dado bom. Grave.

Um extrator que omite 20% e nunca erra é **melhor** para este caso de uso que um
que erra 10% — e a acurácia simples diria o contrário.

### página de referência

A **página 29** do documento-caso, usada em todas as medições comparáveis.

> **Armadilha registrada:** o intervalo do perfil é interpretado como **índice
> base-0**. `[28, 29, 1]` lê `doc[28]`, que é a **página 29** do PDF. Confundir os
> dois faz a medição ler a página seguinte e não casar com o gabarito — aconteceu.

### prompt-base

A instrução comum a todos os modelos no **experimento**, congelada antes da
triagem (ADR-0022).

Distinta do **prompt montado** do produto, que varia por documento conforme o que
o diagnóstico detecta (ADR-0023). Propósitos diferentes: um mede modelos sob
condição controlada, o outro processa documento desconhecido.
