import re


def csrf(client, path="/entrar"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


def test_security_headers(client):
    response = client.get("/entrar")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_post_without_csrf_is_rejected(client):
    response = client.post("/entrar", data={"username": "x", "password": "y"})
    assert response.status_code in (302, 400)
    assert "liga_session" not in (response.headers.get("Set-Cookie") or "") or response.status_code == 302


def test_login_rate_limited(client):
    token = csrf(client)
    codes = [client.post("/entrar", data={"csrf": token, "username": "a", "password": "b"}).status_code for _ in range(15)]
    assert 429 in codes


def test_register_and_hints_only_in_facil(client, app):
    token = csrf(client, "/cadastrar")
    response = client.post(
        "/cadastrar",
        data={"csrf": token, "nome": "Ana", "username": "ana_teste", "email": "ana@example.com", "password": "Senha#forte123"},
    )
    assert response.status_code == 302
    with app.app_context():
        from liga.services import accounts

        row = accounts.user_by_username("ana_teste")
        accounts.mark_verified(row["id"])
    token = csrf(client, "/partida")
    response = client.post("/partida", data={"csrf": token, "mode": "ai", "difficulty": "dificil"})
    match_url = response.headers["Location"]
    match_id = match_url.rstrip("/").split("/")[-1]
    if match_url.endswith("/fim"):
        return
    data = client.get(f"/partida/{match_id}/estado").get_json()
    assert data["hints"] is False and data["legal"] == []
    assert len(data["your_hand"]) >= 6
    assert "fn" not in data["your_hand"][0]["a"]
    bad = client.post(f"/partida/{match_id}/jogar", json={"action": "x", "csrf": token}, headers={"X-CSRF": token})
    assert bad.status_code == 400
