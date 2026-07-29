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
