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
