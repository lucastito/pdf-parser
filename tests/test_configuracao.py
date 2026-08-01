"""Configuração declarativa: perfis e prompts fora do código.

O que estes testes protegem: que a equipe que herdar o projeto possa mudar
resolução, layout, campos, modelo ou prompt **sem editar Python** — e que um
parâmetro esquecido caia num default documentado em vez de erro obscuro.

O risco oposto também é testado: configuração não pode virar depósito de opções
acopladas. Cada rota é independente, e o perfil falha na carga se estiver
inconsistente.
"""

import json

import pytest

from parser.configuracao import (
    ConfiguracaoInvalida,
    carregar_perfil,
    carregar_prompt,
)

PERFIL_MINIMO = {
    "nome": "exemplo",
    "documento": "doc.pdf",
    "rotas": {"posicional": {"layout": {"x_rotulos": [110, 133]}}},
}


def _escrever(tmp_path, dados, nome="p.json"):
    caminho = tmp_path / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


class TestCargaDePerfil:
    def test_carrega_perfil_minimo(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, PERFIL_MINIMO))
        assert p.nome == "exemplo"

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="não encontrado"):
            carregar_perfil(tmp_path / "nao-existe.json")

    def test_json_invalido_falha_claro(self, tmp_path):
        caminho = tmp_path / "ruim.json"
        caminho.write_text("{isto não é json", encoding="utf-8")
        with pytest.raises(ConfiguracaoInvalida, match="JSON"):
            carregar_perfil(caminho)

    def test_sem_nome_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="nome"):
            carregar_perfil(_escrever(tmp_path, {"rotas": {}}))

    def test_sem_rotas_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="rotas"):
            carregar_perfil(_escrever(tmp_path, {"nome": "x"}))


class TestDefaultsDocumentados:
    """Parâmetro omitido cai em default seguro, não em erro obscuro."""

    def test_resolucao_do_ocr_tem_default(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, {**PERFIL_MINIMO, "rotas": {"ocr": {}}}))
        assert p.rota("ocr").dpi == 350

    def test_resolucao_do_vlm_tem_default(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, {**PERFIL_MINIMO, "rotas": {"vlm": {}}}))
        assert p.rota("vlm").dpi == 150

    def test_tolerancia_tem_default(self, tmp_path):
        assert carregar_perfil(_escrever(tmp_path, PERFIL_MINIMO)).tolerancia == 0.01

    def test_perfil_sobrepoe_o_default(self, tmp_path):
        dados = {**PERFIL_MINIMO, "rotas": {"ocr": {"dpi": 200}}}
        assert carregar_perfil(_escrever(tmp_path, dados)).rota("ocr").dpi == 200

    def test_default_cita_a_origem_do_valor(self):
        """Um número sem procedência é um número que ninguém pode questionar."""
        from parser.configuracao import DEFAULTS

        for chave, definicao in DEFAULTS.items():
            assert definicao.get("origem"), f"{chave} sem origem documentada"


class TestExtensibilidade:
    """Modelo novo, documento novo e formato novo entram sem tocar em código."""

    def test_modelo_novo_e_so_configuracao(self, tmp_path):
        dados = {
            **PERFIL_MINIMO,
            "rotas": {"vlm": {"modelo": "modelo-que-nao-existe-ainda:8b", "dpi": 200}},
        }
        rota = carregar_perfil(_escrever(tmp_path, dados)).rota("vlm")
        assert rota.modelo == "modelo-que-nao-existe-ainda:8b"
        assert rota.dpi == 200

    def test_endereco_do_servidor_e_configuravel(self, tmp_path):
        dados = {**PERFIL_MINIMO, "rotas": {"vlm": {"url": "http://servidor:11434"}}}
        assert (
            carregar_perfil(_escrever(tmp_path, dados)).rota("vlm").url
            == "http://servidor:11434"
        )

    def test_rota_desconhecida_falha_claro(self, tmp_path):
        """Nome de rota errado é erro de digitação, e deve aparecer como tal."""
        dados = {**PERFIL_MINIMO, "rotas": {"rota-inventada": {}}}
        with pytest.raises(ConfiguracaoInvalida, match="rota-inventada"):
            carregar_perfil(_escrever(tmp_path, dados))

    def test_rotas_sao_independentes(self, tmp_path):
        """Configurar uma rota não pode afetar outra."""
        dados = {**PERFIL_MINIMO, "rotas": {"ocr": {"dpi": 400}, "vlm": {"dpi": 100}}}
        p = carregar_perfil(_escrever(tmp_path, dados))
        assert p.rota("ocr").dpi == 400
        assert p.rota("vlm").dpi == 100

    def test_rota_ausente_e_reportada(self, tmp_path):
        p = carregar_perfil(_escrever(tmp_path, PERFIL_MINIMO))
        with pytest.raises(ConfiguracaoInvalida, match="ocr"):
            p.rota("ocr")


class TestPrompt:
    def test_carrega_prompt_de_arquivo(self, tmp_path):
        caminho = tmp_path / "p.md"
        caminho.write_text(
            "# Título\n\n## Instrução\n\nExtraia os itens.\n\n"
            "## Guardrails\n\n- Não estime valores.\n",
            encoding="utf-8",
        )
        p = carregar_prompt(caminho)
        assert "Extraia os itens" in p.instrucao
        assert "Não estime" in p.guardrails

    def test_instrucao_e_guardrails_viajam_juntos(self, tmp_path):
        """O texto enviado ao modelo inclui os guardrails — separá-los na hora do
        envio anularia o propósito de tê-los escrito."""
        caminho = tmp_path / "p.md"
        caminho.write_text(
            "## Instrução\n\nFaça X.\n\n## Guardrails\n\n- Não faça Y.\n", encoding="utf-8"
        )
        texto = carregar_prompt(caminho).texto()
        assert "Faça X" in texto
        assert "Não faça Y" in texto

    def test_sem_secao_de_instrucao_falha_claro(self, tmp_path):
        caminho = tmp_path / "p.md"
        caminho.write_text("# Só um título\n", encoding="utf-8")
        with pytest.raises(ConfiguracaoInvalida, match="Instrução"):
            carregar_prompt(caminho)

    def test_arquivo_inexistente_falha_claro(self, tmp_path):
        with pytest.raises(ConfiguracaoInvalida, match="não encontrado"):
            carregar_prompt(tmp_path / "nao-existe.md")

    def test_registra_a_versao_do_prompt(self, tmp_path):
        """Comparar rodadas exige distinguir mudança de prompt de mudança de modelo."""
        caminho = tmp_path / "p.md"
        caminho.write_text(
            "## Instrução\n\nFaça X.\n\n## Histórico\n\n- v2: ajustado\n- v1: inicial\n",
            encoding="utf-8",
        )
        assert carregar_prompt(caminho).impressao_digital


class TestPerfisDoProjeto:
    """Contra os arquivos reais, não fixtures."""

    def test_perfis_existentes_carregam(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        perfis = list((raiz / "perfis").glob("*.json"))
        assert perfis, "nenhum perfil no projeto"
        for caminho in perfis:
            carregar_perfil(caminho)

    def test_prompts_existentes_carregam(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        prompts = list((raiz / "prompts").glob("*.md"))
        assert prompts, "nenhum prompt no projeto"
        for caminho in prompts:
            carregar_prompt(caminho)

    def test_o_mapeamento_cobre_os_campos_que_as_rotas_leem(self):
        """Campo não mapeado não vota junto com suas variantes.

        Medido sobre as saídas reais das quatro rotas determinísticas: elas leem
        o mesmo campo com nomes diferentes por três causas distintas —

        | Causa | Exemplo |
        |---|---|
        | acento perdido no OCR | `Proteina` / `Proteína` |
        | ordem trocada pela rotação | `Fibra Alimentar` / `Alimentar Fibra` |

        Cada variante fora do mapeamento vira uma coluna própria, com uma rota
        votando nela, e a concordância se perde.

        Este teste fixa os campos que o documento-caso realmente tem. Falha se
        alguém acrescentar rota que leia um campo novo sem declará-lo.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        perfil = carregar_perfil(raiz / "perfis" / "nutricional.json")

        esperados = {
            "energia_kcal",
            "energia_kj",
            "proteina_g",
            "lipideos_g",
            "carboidrato_g",
            "fibra_g",
            "colesterol_mg",
            "umidade_pct",
            "cinzas_g",
            "calcio_mg",
            "magnesio_mg",
        }
        faltando = esperados - set(perfil.mapeamento)
        assert not faltando, f"campos sem mapeamento declarado: {sorted(faltando)}"

    def test_o_denominador_comum_e_um_par_de_tamanhos(self):
        """Duas rotas de visão da mesma família, só o tamanho mudando.

        O denominador comum amarra a comparação entre as cinco máquinas. Em par,
        ele entrega de graça o experimento mais limpo da escada: mesma origem,
        mesma geração, mesma quantização — qualquer diferença é atribuível ao
        tamanho e a mais nada (ADR-0014).

        O menor também importa por outra razão: com 1,9 GB ele cabe na placa de
        2 GB da máquina de referência, que com o modelo de 3,3 GB rodava 86% no
        processador. É a diferença entre medir placa pequena e medir execução
        híbrida.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        perfil = carregar_perfil(raiz / "perfis" / "nutricional.json")

        modelos = {
            rota.modelo
            for nome, rota in perfil.rotas.items()
            if nome.startswith("vlm") and rota.modelo
        }
        assert len(modelos) >= 2, f"denominador comum não é par: {modelos}"

    def test_rotas_por_modelo_declaram_semente(self):
        """Sem semente declarada, a geração é irrepetível e nada é comparável.

        Vale a mesma lógica do contexto (ADR-0018): correção que existe no código
        e fica desligada no arquivo que as medições usam é a pior combinação,
        porque a próxima rodada herda o defeito em silêncio.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        for caminho in (raiz / "perfis").glob("*.json"):
            perfil = carregar_perfil(caminho)
            # Toda rota por modelo, inclusive as do denominador em par
            # (`vlm`, `vlm-menor`): declarar numa e esquecer na outra é o
            # defeito que estes testes existem para pegar.
            for nome, rota in perfil.rotas.items():
                if not (nome.startswith("llm") or nome.startswith("vlm")):
                    continue
                assert rota.extras.get("semente") is not None, (
                    f"{caminho.name}: a rota {nome!r} não declara 'semente' — "
                    "a geração fica irrepetível"
                )

    def test_o_mapeamento_nao_acolhe_leitura_corrompida(self):
        """`Energia (kd)` é erro de OCR, não variante legítima de `Energia (kJ)`.

        Mapeá-lo faria a leitura errada votar como se fosse boa — e a votação
        confirmaria o erro com confiança alta, que é o modo de falha que a
        consolidação existe para evitar.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        perfil = carregar_perfil(raiz / "perfis" / "nutricional.json")

        todas = {v for variantes in perfil.mapeamento.values() for v in variantes}
        assert "Energia (kd)" not in todas

    def test_rotas_por_modelo_declaram_contexto(self):
        """Sem declaração vale o padrão do servidor, e ele foi a causa medida.

        O padrão do Ollama é 4096 e limita entrada **mais** saída. Uma página
        renderizada consome ~2200 só de entrada, então o que sobra não comporta a
        resposta — e o corte volta como resposta vazia, sintoma que já custou uma
        sessão inteira de investigação atribuída ao modelo errado (ADR-0018).

        O código sabe enviar `num_ctx` desde então, mas o perfil não o declarava:
        a correção estava disponível e desligada, que é a pior das combinações,
        porque a próxima medição herdaria o defeito em silêncio.

        Este teste vale para o perfil **real**, não para fixture — é o arquivo que
        as medições usam.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        for caminho in (raiz / "perfis").glob("*.json"):
            perfil = carregar_perfil(caminho)
            # Toda rota por modelo, inclusive as do denominador em par
            # (`vlm`, `vlm-menor`): declarar numa e esquecer na outra é o
            # defeito que estes testes existem para pegar.
            for nome, rota in perfil.rotas.items():
                if not (nome.startswith("llm") or nome.startswith("vlm")):
                    continue
                assert rota.extras.get("contexto"), (
                    f"{caminho.name}: a rota {nome!r} não declara 'contexto' e "
                    "herdaria o padrão de 4096 do servidor"
                )


class TestPadraoDeRotaIndependeDeComoFoiCriada:
    """O padrão por rota tem de valer nos dois caminhos de construção.

    `Rota.de_dados("vlm", {})` aplicava o padrão declarado (`vlm.dpi = 150`), mas
    `Rota(nome="vlm")` deixava dpi em 0 — e 0 é rejeitado na montagem do extrator,
    com "dpi deve ser positivo".

    O mesmo objeto lógico com padrões diferentes conforme o caminho de construção
    é uma armadilha: o perfil vindo de JSON funciona, o construído em código
    quebra, e a mensagem de erro não sugere a causa.
    """

    def test_dpi_padrao_vale_para_o_construtor(self):
        from parser.configuracao import DEFAULTS, Rota

        assert Rota(nome="vlm").dpi == DEFAULTS["vlm.dpi"]["valor"]
        assert Rota(nome="ocr").dpi == DEFAULTS["ocr.dpi"]["valor"]

    def test_construtor_e_de_dados_concordam(self):
        from parser.configuracao import Rota

        for nome in ("vlm", "ocr", "llm", "posicional"):
            assert (
                Rota(nome=nome).dpi == Rota.de_dados(nome, {}).dpi
            ), f"padrão de dpi diverge para a rota {nome!r}"

    def test_dpi_explicito_continua_mandando(self):
        from parser.configuracao import Rota

        assert Rota(nome="vlm", dpi=72).dpi == 72
        assert Rota.de_dados("vlm", {"dpi": 72}).dpi == 72

    def test_rota_sem_padrao_declarado_fica_em_zero(self):
        """Rota que não renderiza imagem não tem dpi — 0 é o valor correto."""
        from parser.configuracao import Rota

        assert Rota(nome="posicional").dpi == 0
