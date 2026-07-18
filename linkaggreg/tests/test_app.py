# NOVO: testes automatizados cobrindo as rotas principais e as validações
# adicionadas nesta rodada de melhorias (URL http/https e limite de tentativas
# de login). Rode com "pytest" dentro da pasta linkaggreg/.

from conftest import login_as_admin


def test_index_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_add_link_requires_login(client):
    # Sem sessão de admin/editor, /add deve recusar e voltar para a home.
    resp = client.get("/add", follow_redirects=True)
    assert resp.status_code == 200
    assert "Apenas usuários Admin/Editor" in resp.get_data(as_text=True)


def test_login_with_correct_credentials(client):
    resp = login_as_admin(client)
    assert resp.status_code == 200
    assert "Login realizado com sucesso" in resp.get_data(as_text=True)


def test_add_link_rejects_javascript_url(client):
    # Antes desta rodada de melhorias, uma URL "javascript:..." era aceita e
    # gravada normalmente — este teste garante que isso não volta a acontecer.
    login_as_admin(client)
    resp = client.post(
        "/add",
        data={
            "title": "Teste malicioso",
            "url": "javascript:alert(1)",
            "description": "",
            "active": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "URL inválida" in resp.get_data(as_text=True)


def test_add_link_accepts_https_url(client):
    login_as_admin(client)
    resp = client.post(
        "/add",
        data={
            "title": "Site de teste",
            "url": "https://exemplo.com",
            "description": "descrição de teste",
            "active": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Link adicionado com sucesso" in resp.get_data(as_text=True)


def test_login_rate_limit_blocks_after_five_attempts(client):
    # IP exclusivo deste teste, para não interferir na contagem dos testes acima.
    remote = {"REMOTE_ADDR": "203.0.113.9"}
    payload = {"username": "nao-existe", "password": "senha-errada"}

    for _ in range(5):
        resp = client.post("/login", data=payload, environ_overrides=remote)
        assert resp.status_code in (200, 302)

    resp = client.post("/login", data=payload, environ_overrides=remote)
    assert resp.status_code == 429
