# NOVO: pacote de testes automatizados — o projeto original não tinha nenhum.
#
# Este conftest.py prepara um ambiente isolado antes de importar app.py:
# - define variáveis de ambiente de teste (nunca use estes valores em produção)
# - usa um banco SQLite temporário, criado do zero a cada rodada de testes
#
# Como rodar (dentro da pasta linkaggreg/, com o ambiente virtual ativado):
#   pip install -r requirements-dev.txt
#   pytest

import os
import sys
import tempfile

# Precisa ser definido ANTES de "import app", porque app.py lê essas variáveis
# de ambiente assim que o módulo é carregado.
os.environ.setdefault("SECRET_KEY", "chave-apenas-para-os-testes-automatizados")
os.environ.setdefault("FLASK_DEBUG", "true")
# NOVO: login por usuário em vez de e-mail — variáveis renomeadas de acordo.
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "senha-teste-123")
os.environ.setdefault("VIEWER_USERNAME", "viewer")
os.environ.setdefault("VIEWER_PASSWORD", "senha-teste-123")

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_path}")

import pytest  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import app as flask_app  # noqa: E402


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    # Desliga a checagem de CSRF só nos testes, para simplificar os POSTs simulados.
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as test_client:
        yield test_client


def login_as_admin(client):
    return client.post(
        "/login",
        data={
            "username": os.environ["ADMIN_USERNAME"],
            "password": os.environ["ADMIN_PASSWORD"],
        },
        follow_redirects=True,
    )
