"""Fixtures compartilhadas.

O PDF de exemplo é gerado em tempo de execução, não versionado. Assim a suíte
não depende de arquivo externo, não carrega binário no repositório e não esbarra
em licença de documento de terceiro.
"""

import pytest


@pytest.fixture
def pdf_exemplo(tmp_path):
    """Um PDF mínimo com texto nativo e uma tabela simples."""
    import fitz

    caminho = tmp_path / "exemplo.pdf"
    documento = fitz.open()

    pagina = documento.new_page()
    pagina.insert_text((72, 72), "Composição por 100 g")
    pagina.insert_text((72, 100), "Proteína (g)")
    pagina.insert_text((200, 100), "2,6")
    pagina.insert_text((72, 120), "Fibra (g)")
    pagina.insert_text((200, 120), "Tr")

    documento.save(caminho)
    documento.close()
    return caminho


@pytest.fixture
def pdf_sem_texto(tmp_path):
    """Uma página em branco, sem camada de texto — o caso do documento digitalizado.

    Não é um scan de verdade (não há imagem nenhuma), mas é indistinguível dele
    para qualquer verificação que dependa só de `get_text`: zero palavras.
    """
    import fitz

    caminho = tmp_path / "sem-texto.pdf"
    documento = fitz.open()
    documento.new_page()
    documento.save(caminho)
    documento.close()
    return caminho


@pytest.fixture
def pdf_texto_corrido(tmp_path):
    """Uma página de prosa — texto nativo, sem estrutura de tabela.

    Densidade numérica baixa o bastante para `triagem.triar` classificar como
    `Classe.CONTEXTO`, não `Classe.DADOS`: é o caso em que não existe tabela
    para calibrar, e o roteador não deveria tentar uma.
    """
    import fitz

    caminho = tmp_path / "texto-corrido.pdf"
    documento = fitz.open()
    pagina = documento.new_page()
    paragrafo = (
        "Este relatório descreve o método empregado na coleta de amostras e "
        "resume as condições observadas em campo durante o período de referência "
        "sem apresentar nenhuma tabela de valores nesta página em particular"
    )
    for i, palavra in enumerate(paragrafo.split()):
        pagina.insert_text((72 + (i % 8) * 60, 100 + (i // 8) * 20), palavra)
    documento.save(caminho)
    documento.close()
    return caminho


@pytest.fixture
def pdf_tabela_sem_unidade_reconhecivel(tmp_path):
    """Uma tabela numérica real, mas sem o sinal que a calibração geométrica usa
    como âncora (`_faixa_de_unidades` exige tokens como "(g)", "(kcal)").

    Representa a classe de documento em que a heurística atual (ajustada ao
    formato de tabela nutricional) falha limpo — o caso que ADR-0024 já previa
    e que deve escalar para o nível 3 (modelo), não travar o lote.
    """
    import fitz

    caminho = tmp_path / "tabela-sem-parenteses.pdf"
    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), "Item")
    pagina.insert_text((160, 72), "Valor 1")
    pagina.insert_text((220, 72), "Valor 2")
    for i in range(12):
        y = 100 + i * 18
        pagina.insert_text((72, y), f"{i + 1} Componente {i + 1}")
        pagina.insert_text((160, y), str(10 + i))
        pagina.insert_text((220, y), str(20 + i))
    documento.save(caminho)
    documento.close()
    return caminho


@pytest.fixture
def pdf_tabular(tmp_path):
    """Um PDF com tabela extraível: rótulos, unidades e itens em colunas.

    Reproduz a estrutura que o extrator posicional espera — rótulo à esquerda,
    unidade em seguida, valores em colunas, nomes dos itens na parte inferior —
    para que os testes de lote e de calibração não dependam de documento externo.
    """
    import fitz

    caminho = tmp_path / "tabular.pdf"
    documento = fitz.open()
    pagina = documento.new_page(width=595, height=842)

    linhas = [
        ("Energia", "(kcal)", 400.0, ["124", "360", "128", "358", "130"]),
        ("Proteína", "(g)", 350.0, ["2,6", "7,3", "2,5", "7,2", "2,6"]),
        ("Lipídeos", "(g)", 300.0, ["1,0", "1,9", "0,2", "0,3", "Tr"]),
        ("Carboidrato", "(g)", 250.0, ["25,8", "77,5", "28,1", "78,8", "28,2"]),
    ]
    for rotulo, unidade, y, valores in linhas:
        pagina.insert_text((112, y), rotulo)
        pagina.insert_text((136, y), unidade)
        for i, valor in enumerate(valores):
            pagina.insert_text((160 + i * 40, y), valor)

    # Nomes dos itens, um por coluna, na área inferior.
    for i, nome in enumerate(
        ["1 Item um", "2 Item dois", "3 Item tres", "4 Item quatro", "5 Item cinco"]
    ):
        pagina.insert_text((160 + i * 40, 600), nome)

    documento.save(caminho)
    documento.close()
    return caminho


@pytest.fixture
def pdf_tabela_calibravel(tmp_path):
    """Uma tabela grande o bastante para a calibração geométrica reconhecer.

    `pdf_tabular` (acima) tem só 5 itens — abaixo de `MIN_COLUNAS_DE_VALOR`
    (8) em `parser.calibracao`, que foi calibrado contra o documento-caso e
    exige tabela de muitos itens para não confundir ruído com estrutura. Este
    fixture usa 10 para passar com folga, e nomes de item sem dígito para não
    derrubar a proporção não-numérica que localiza a faixa de identificadores.
    """
    import fitz

    caminho = tmp_path / "tabela-calibravel.pdf"
    documento = fitz.open()
    pagina = documento.new_page(width=595, height=842)

    itens = 10
    linhas = [
        ("Energia", "(kcal)", 400.0, [str(100 + i * 20) for i in range(itens)]),
        ("Proteína", "(g)", 350.0, [str(round(1.0 + i * 0.6, 1)) for i in range(itens)]),
        ("Lipídeos", "(g)", 300.0, [str(round(0.5 + i * 0.3, 1)) for i in range(itens)]),
        ("Carboidrato", "(g)", 250.0, [str(round(10.0 + i * 2.5, 1)) for i in range(itens)]),
    ]
    for rotulo, unidade, y, valores in linhas:
        pagina.insert_text((112, y), rotulo)
        pagina.insert_text((136, y), unidade)
        for i, valor in enumerate(valores):
            pagina.insert_text((160 + i * 40, y), valor)

    # Sem dígito no nome: um "0"/"1" aqui derrubaria a proporção não-numérica
    # que a calibração usa para achar a faixa de identificadores (limiar 0,7).
    palavras = [
        "Alfa",
        "Beta",
        "Gama",
        "Delta",
        "Epsilon",
        "Zeta",
        "Eta",
        "Teta",
        "Iota",
        "Kapa",
    ]
    for i in range(itens):
        pagina.insert_text((160 + i * 40, 600), f"Produto Modelo {palavras[i]}")

    documento.save(caminho)
    documento.close()
    return caminho
