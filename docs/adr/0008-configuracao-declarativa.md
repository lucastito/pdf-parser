# ADR-0008 — Configuração declarativa: perfis e prompts fora do código

**Status:** aceito · **Data:** 2026-07-29

## Contexto

O projeto será entregue a uma equipe que vai executá-lo e evoluí-lo **sem acesso a
um assistente de programação**, possivelmente num servidor. Isso torna uma pergunta
central: quando alguém precisar mudar a resolução do OCR, adicionar um modelo novo,
ou apontar o parser para outro documento — **onde essa pessoa olha?**

Levantamento do estado anterior a esta decisão:

| Parâmetro | Onde estava |
|---|---|
| Resolução do OCR (350) | `extratores/ocr.py` |
| Resolução do experimento (150) | `cli.py` |
| Layout da tabela | `perfis/*.json` |
| Ordem dos campos | `extratores/pdfplumber_.py` |
| Mapeamento de rótulos | `mapeamento.py` |
| Instruções ao modelo | `ollama.py` e `extratores/vlm.py` |
| Tolerância numérica | `avaliacao.py` |

Sete parâmetros ajustáveis em sete arquivos, cinco deles em código Python. Nenhum
com registro de **por que** tem aquele valor.

## Decisão

Tudo que é ajustável sai do código e vai para arquivos declarativos. O código passa
a **ler configuração**, nunca a decidir valores.

```
perfis/<dominio>.json      documento, layout, resolução, campos, tolerância
prompts/<nome>.md          instrução ao modelo, guardrails, justificativa, histórico
```

O código conserva apenas **defaults de segurança** — valores que evitam falha se a
configuração omitir algo — e cada um aponta para o ADR que o mediu.

### O que vai para o perfil

Configuração é o que muda quando **o documento** muda. Ordem dos campos, faixas de
coordenadas, mapeamento de rótulos, resolução por rota.

### O que vai para o prompt

O arquivo de prompt não contém só a instrução. Contém também:

- **guardrails** — o que o modelo não deve fazer (calcular, estimar, inventar campo);
- **justificativa de cada regra** — por que ela existe, e o que acontece sem ela;
- **histórico** — o que foi tentado antes e por que mudou.

Sem a justificativa, a próxima pessoa remove uma regra por parecer redundante e
reintroduz um problema já resolvido.

### O que **não** vai para o Ollama

Uma confusão a desfazer: o servidor de inferência **não guarda** resolução, layout
nem regra de negócio. Ele recebe texto ou imagem e devolve resposta. A separação é:

| Camada | Responsabilidade |
|---|---|
| Perfil (arquivo) | resolução, layout, campos, tolerância |
| Prompt (arquivo) | instrução e guardrails |
| Esquema (código) | forma da saída, imposta na decodificação |
| Servidor de inferência | apenas executa |

## Requisito de extensibilidade

A configuração precisa acomodar, **sem alteração de código**:

- **modelo novo** (outro LLM ou modelo de visão) — troca de nome e endereço no perfil;
- **documento novo** — novo arquivo de perfil, com seu layout e resolução;
- **formato de entrada novo** — o perfil já declara o tipo; o adapter é o único
  código a escrever, e formatos previstos mas não implementados falham alto;
- **destino novo** — idem.

O risco a evitar é o oposto do problema atual: configuração que vira depósito de
opções acopladas. Mitigação — o perfil é organizado por **rota** (`ocr`, `vlm`,
`posicional`), cada uma com seus próprios parâmetros, e nenhuma seção depende de
outra.

## Consequências

- Mudar resolução, layout ou prompt deixa de exigir editar Python.
- Cada valor passa a ter justificativa rastreável ao ADR que o mediu.
- Um parâmetro esquecido no perfil cai no default do código, que é seguro e
  documentado — não em erro obscuro.
- Custo: mais uma camada de indireção, e a possibilidade de perfil e código
  divergirem. Mitigado por validação do perfil na carga, falhando alto.
- Prompts versionados em arquivo permitem diferenciar mudança de prompt de mudança
  de modelo na comparação — o que hoje seria impossível distinguir.
