# ADR-0028 — Postura de segurança do servidor de inferência

**Status:** aceito · **Data:** 2026-08-13

> **Não existe "relatório de segurança perfeito"** — nem para este projeto, nem
> para nenhum sistema real. O próprio OWASP LLM Top 10 declara isso
> explicitamente para injeção de instrução: "there is no perfect mitigation".
> Este ADR segue o mesmo princípio que rege todo o resto do projeto
> ("sem eval, sem produção" — medir, não presumir): registra o que foi
> **verificado** (com fonte), o que foi **implementado e testado**, e o que
> **continua risco declarado**, sem fingir cobertura que não existe.
>
> **Escopo, registrado em 2026-08-14:** as seções de código (dois
> detectores em `diagnostico.py`, suporte a Basic Auth via URL em
> `ollama.py`) e a versão mínima do Ollama valem pros **dois cenários** —
> qualquer instância do Ollama, local ou remota, se beneficia de estar na
> versão corrigida. As seções de **rede** (firewall, reverse proxy,
> `fail2ban`) só se aplicam quando o Ollama é exposto **além de
> localhost** — o caso do servidor do Cenário B. No Cenário A (notebook
> pessoal, Ollama local), essas seções não têm o que proteger: não há
> exposição de rede pra fechar.

## Contexto

Pedido explícito do usuário: rodar o experimento de avaliação de modelos
(`ADR-0026`) contra um servidor próprio da empresa — com PDFs de terceiros
alimentando prompt de modelos open-weight — sem introduzir vulnerabilidade
na infraestrutura da empresa. Três perguntas, todas legítimas e nenhuma
respondida antes deste registro:

1. Como não ser invadido, rodando um servidor de inferência exposto o
   suficiente pra ser usado remotamente?
2. Como não processar injeção de instrução vinda do PDF?
3. Como não vazar informação (do prompt, do documento, do servidor)?

Duas dessas perguntas **já estavam registradas como aberto** antes deste ADR
— não são achado novo, são item antigo finalmente atacado:

- **P0.6** (`PLANO.md`, "Mapa completo dos P0 da auditoria externa"): "Sem
  fronteira de segurança pra entrada não confiável (sandbox, limites de
  recurso/tempo/páginas/pixels)".
- **Achado da auditoria independente, nunca corrigido**: "injeção de
  instrução vinda do PDF" e "célula de planilha começando por `=`" —
  citados em `PLANO.md` junto aos achados adicionais da auditoria externa,
  nunca até hoje com código associado.

## Decisão

Três camadas, cada uma com escopo diferente — código deste repositório,
configuração do servidor, e risco que nenhum dos dois resolve sozinho.

### 1. Código: dois detectores novos, testados (`src/parser/diagnostico.py`)

**`possivel-injecao-de-instrucao`** — sonda por página (`_SONDAS`, mesmo
registro de `ADR-0021`): procura frases-gatilho clássicas de injeção de
instrução (OWASP LLM01), em português e inglês ("ignore previous
instructions", "ignore as instruções anteriores", "system prompt", etc.),
normalizando espaço em branco antes de comparar — `get_text()` quebra linha
entre blocos próximos mesmo dentro da mesma frase visual, e a versão inicial
deste detector não normalizava, perdendo o caso comum (frase que atravessa
quebra de linha), não a exceção. Severidade `ALERTA`: a lista de frases é
**ponto de partida declarado, não exaustiva** — quem monta PDF malicioso não
está limitado a estas frases, e a ação recomendada (isolar o texto extraído
como dado citado, nunca concatenado como comando, no prompt) importa mais
que a detecção em si.

**`possivel-injecao-de-formula`** — achado de `validar_registros`: valor de
campo **texto** (nunca numérico — o schema já rejeitaria sintaxe de fórmula
num campo `float`) que começa com `=`, `+`, `-`, `@` ou tabulação. É a
injeção de fórmula clássica (OWASP): uma planilha (Excel, LibreOffice,
Sheets) executa esse valor como fórmula ao abrir o CSV que este projeto
grava, não como texto — e o valor veio de um PDF de origem não confiável,
nunca digitado por humano. Severidade `BLOQUEIA`.

### 2. Configuração do servidor — verificado contra fonte real, não genérico

**Versão do Ollama, não negociável:** `CVE-2026-7482` ("Bleeding Llama",
CVSS 9,1) é um vazamento de memória **não autenticado** — três chamadas ao
endpoint `/api/create`, sem autenticação, com um GGUF malformado, e o
processo devolve memória de outros processos (variável de ambiente, chave de
API, prompt de outro usuário). Corrigido na **v0.17.1**. O instalador
(`instalar_servidor.py`, área de trabalho) e o script do projeto
(`1-preparar-maquina.ps1`) verificam a versão instalada e recusam prosseguir
abaixo dela.

**Rede — nunca `OLLAMA_HOST=0.0.0.0` exposto à internet.** Por padrão o
Ollama escuta só em `127.0.0.1` — comportamento correto, não mexer. Para
rodar o experimento a partir da sua máquina contra o servidor da empresa
(pergunta separada, já respondida nesta sessão antes deste ADR), a API
**precisa** ficar alcançável de fora do próprio servidor — mas isso não
significa "abrir pra internet": a rede confiável (VPN da empresa, ou
`OLLAMA_HOST` restrito ao IP interno + firewall liberando só o IP de quem
mede) é o que torna a exposição comparável a "localhost de um perímetro
maior", não a "porta pública". A API do Ollama **não tem autenticação
própria** — se precisar de acesso além da rede interna confiável, a
recomendação é reverse proxy com autenticação (Basic Auth/API key) na
frente, nunca a porta 11434 exposta direto.

> **Achado real, corrigido em código (não só documentado):** o transporte
> HTTP do projeto (`ollama._TransporteHTTP`) só mandava `Content-Type` —
> nenhum cabeçalho de autenticação. Colocar um proxy com Basic Auth na
> frente do Ollama, sem mais nada, teria quebrado o próprio caminho de uso
> ("como meu PC se comunica com o servidor?"): a chamada real receberia
> `401` do proxy, e não havia como o perfil informar credencial nenhuma.
> Corrigido com `ollama._extrair_credenciais`: `Rota.url` (`configuracao.py`)
> aceita a convenção `http://usuario:senha@host:porta` — o transporte separa
> as credenciais da URL, monta o cabeçalho `Authorization: Basic ...`, e
> envia a URL sem credencial nenhuma em texto claro. Nenhum campo novo no
> perfil; a URL já era o único lugar que declarava o endereço do servidor.
> Testado em `tests/test_ollama.py::TestCredenciaisNaUrl` (6 casos).

**`OLLAMA_MAX_LOADED_MODELS=1`** — resposta à pergunta "como garantir que
cada modelo roda uma única vez e não compete por recurso com outro modelo?"
(feita antes deste ADR): força o Ollama a descarregar o modelo anterior
antes de carregar o próximo, no próprio servidor — garantia de verdade,
não só disciplina de quem chama.

**Origem do modelo — preferir `library/` oficial a namespace de
comunidade.** Só um modelo da escada (`ibm/granite-docling`) vem de
namespace fora do catálogo `library/` principal do Ollama — os demais
seguem a convenção oficial. Não é sinal de risco automático (é publicado
sob o nome `ibm`, org verificável), mas é a distinção que existe e vale
declarar: pesos de fonte não-oficial não passam por nenhuma checagem
central, e formato de serialização de peso pode carregar exploração (o
caso documentado é `pickle`, não o formato GGUF que o Ollama usa — mas a
mesma `CVE-2026-7482` mostra que parsing de GGUF também pode ter bug de
memória explorável).

**Ferramentas concretas recomendadas pra fechar rede e autenticação —
instaladas e configuradas no instalador de servidor (fora deste
repositório; `1-preparar-maquina.ps1` deste repositório roda em máquina
emprestada de terceiro pro Cenário A, `ADR-0019`, e deliberadamente **não**
mexe em firewall/proxy de máquina que não é sua):**

| Ferramenta | Fecha o quê |
|---|---|
| Caddy (reverse proxy + Basic Auth), caminho padrão | API do Ollama não tem autenticação própria — Ollama continua só em localhost, nunca exposto direto; Caddy escuta na porta pública e só repassa depois de autenticar |
| `ufw` (Linux) / regra do Windows Firewall | Libera **a porta do proxy** (não a do Ollama) só pro IP/faixa confiável — achado real ao revisar com o usuário: abrir a porta do Ollama diretamente seria inútil (nada escuta ali fora de localhost) quando o proxy está ativo, e perigoso (sem senha nenhuma) se alguém desligasse o proxy sem perceber a implicação |
| `fail2ban` (só Linux) | Bane IP após tentativa de autenticação falhada repetida no proxy |
| Trivy (Aqua Security) | Varredura de vulnerabilidade mais ampla que `pip-audit` — cobre pacote de sistema operacional |

**Caminho sem proxy, deliberadamente mais arriscado:** só existe pra quem
sabe o que está abrindo mão. Sem Caddy, `OLLAMA_HOST=0.0.0.0:11434` expõe o
Ollama direto na rede, sem autenticação nenhuma — o firewall (IP/faixa
confiável) fica sendo a **única** camada de proteção. Não é o caminho
recomendado; existe porque negar a opção também seria decisão no escuro
sobre o ambiente de quem instala.

Nenhuma delas é sandbox de processo nem verificação de integridade de peso
GGUF — os dois residuais já declarados acima continuam sem ferramenta
adotada.

### 3. Risco que nenhuma das duas camadas acima resolve — declarado, não escondido

- **Sandbox de processo, limites de recurso/tempo/páginas/pixels (P0.6)** —
  continua **aberto**. Os dois detectores novos são visibilidade
  (avisam que uma página é suspeita), não contenção (não impedem um PDF de
  180 páginas ou um valor de tamanho absurdo de consumir recurso sem limite).
  Fica para item futuro dedicado, com medição de qual limite é razoável —
  não um número escolhido sem dado, mesmo princípio de todo o resto do
  projeto.
- **Lista de frases-gatilho não é exaustiva** — declarado no próprio
  docstring do código (`PADROES_DE_INSTRUCAO_SUSPEITA`). Defesa em
  profundidade (a orientação corrente da pesquisa em 2026) significa: este
  detector é **uma camada**, não a defesa inteira. A camada que de fato
  impede o ataque é arquitetural — nunca concatenar texto extraído do
  documento como se fosse instrução do sistema no prompt — e isso é
  responsabilidade de quem monta o prompt (`parser.degraus`/prompts em
  `prompts/`), não deste detector.
- **Integridade de peso de modelo — só metade do problema tem solução, e a
  outra metade não é falta de ferramenta.** São dois riscos distintos, e a
  formulação anterior deste ADR os misturava:
  - **Adulteração em trânsito (arquivo mudou entre o registro e o disco):**
    ✅ **já resolvida — pelo próprio Ollama, sem ferramenta extra.** `ollama
    pull` verifica o SHA256 de cada blob contra o manifesto do registro
    (armazenamento é content-addressed: o nome do arquivo em disco é o
    hash). Vale pra qualquer modelo puxado via `ollama pull`, `library/`
    oficial ou namespace de organização (`ibm/granite-docling` está
    publicado pela conta oficial `ollama.com/ibm`, confirmado).
  - **Arquivo original malicioso, já com hash "correto" desde a origem
    (explora bug do *parser* de GGUF, não do arquivo):** continua **sem
    ferramenta de mercado adotada** — checksum não ajuda aqui, porque só
    prova que o arquivo não mudou depois de baixado, não que o autor
    original não incluiu algo malicioso. `ModelScan`/`Guardian` (Protect
    AI) focam em `pickle`, formato que este projeto não usa (GGUF via
    Ollama não desserializa objeto arbitrário do mesmo jeito). A defesa
    real contra esta classe (a mesma do `CVE-2026-7482`, que era um bug no
    leitor de GGUF, não uma falha de integridade de arquivo) é manter o
    Ollama na versão corrigida — já automatizado — e preferir organização
    verificável a upload anônimo, que reduz a chance sem eliminá-la.
- **Dependência Python sem varredura de vulnerabilidade automatizada** —
  `pip-audit` entra no instalador (ver `instalar_servidor.py`), mas não há
  execução periódica nem trava de CI — mesma lacuna que `P0.7` (ambiente não
  travado) já registra.

## Consequências

**A favor:** duas lacunas antigas (P0.6 parcial, achado de auditoria nunca
corrigido) ganham código testado; a versão do Ollama passa a ser verificada,
não presumida — fecha a vulnerabilidade mais crítica encontrada
(`CVE-2026-7482`); a orientação de rede é específica pra este projeto
(medir contra servidor remoto), não um "não exponha nunca" genérico que
inviabilizaria o próprio pedido do usuário.

**Contra:** nenhuma das camadas aqui é sandbox de verdade — um PDF
adversarial ainda pode consumir recurso sem limite, e a lista de
frases-gatilho tem taxa de falso-negativo desconhecida (não medida contra
corpus adversarial real). Isso é declarado, não escondido — ver seção
anterior.

## Testes

`tests/test_diagnostico.py::TestPossivelInjecaoDeInstrucao` (4 casos,
incluindo insensibilidade a maiúsculas e frase que atravessa quebra de
linha), `TestInjecaoDeFormula` (4 casos, incluindo que número negativo
legítimo não é confundido com fórmula) e
`tests/test_ollama.py::TestCredenciaisNaUrl` (6 casos, incluindo que a
senha não vaza pra URL final e que `ClienteOllama` encaminha a URL com
credenciais sem decodificar nada — quem decodifica é o transporte).

## Fontes

- [CVE-2026-7482 — Ollama Information Disclosure Vulnerability](https://www.sentinelone.com/vulnerability-database/cve-2026-7482/)
- [Bleeding Llama: Critical Unauthenticated Memory Leak in Ollama](https://www.cyera.com/research/bleeding-llama-critical-unauthenticated-memory-leak-in-ollama)
- [Ollama vulnerability highlights danger of AI frameworks with unrestricted access](https://www.csoonline.com/article/4168584/ollama-vulnerability-highlights-danger-of-ai-frameworks-with-unrestricted-access.html)
- [Securing Ollama: Auth, TLS, Network Isolation](https://localaimaster.com/blog/securing-ollama-guide)
- [Local LLM Security Best Practices for Enterprise in 2026](https://www.sitepoint.com/local-llm-security-best-practices-2026/)
- [Prompt Injection Defense for Production AI Agents: A Complete 2026 Guide](https://www.getmaxim.ai/articles/prompt-injection-defense-for-production-ai-agents-a-complete-2026-guide/)
- [Open-Weight AI Models: A Cybersecurity Threat in 2026](https://www.avepoint.com/blog/protect/open-weight-ai-models-cybersecurity-threat)
- [Poisoned Pipelines: Malicious AI Model and Skill Repositories](https://labs.cloudsecurityalliance.org/research/csa-research-note-malicious-ai-model-repositories-attack-sur/)
