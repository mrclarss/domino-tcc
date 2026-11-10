import re

from liga.game.engine import MAX_TIMEOUTS, TURN_SECONDS, forfeit, new_state, seconds_left, tick


def test_forfeit_gives_win_to_opponent():
    state = new_state(seed=2)
    state["scores"] = {"1": 10, "2": 20}
    assert forfeit(state, 1) == (True, None)
    assert state["status"] == "finished"
    assert state["end"]["winner"] == 2 and state["end"]["reason"] == "desistencia"
    assert state["end"]["points"] == {"1": 10, "2": 25}


def test_timeout_draws_then_passes():
    state = new_state(seed=4)
    player = state["turn"]
    hand = len(state["hands"][str(player)])
    bone = len(state["boneyard"])
    start = state["turn_started"]
    assert seconds_left(state, start + 10) == TURN_SECONDS - 10
    assert not tick(state, start + TURN_SECONDS - 1)
    assert tick(state, start + TURN_SECONDS + 1)
    assert len(state["hands"][str(player)]) == hand + 1
    assert len(state["boneyard"]) == bone - 1
    assert state["turn"] != player


def test_timeout_passes_when_cemiterio_empty():
    state = new_state(seed=4)
    state["boneyard"] = []
    player = state["turn"]
    hand = len(state["hands"][str(player)])
    tick(state, state["turn_started"] + TURN_SECONDS + 1)
    assert len(state["hands"][str(player)]) == hand
    assert state["turn"] != player or state["status"] == "finished"


def test_repeated_timeouts_count_as_abandon():
    state = new_state(seed=5)
    player = state["turn"]
    now = state["turn_started"]
    for _ in range(MAX_TIMEOUTS * 2 + 2):
        now += TURN_SECONDS + 1
        tick(state, now)
        if state["status"] == "finished":
            break
    assert state["status"] == "finished"
    assert state["end"]["reason"] in ("abandono", "travada")


def _token(client, path):
    return re.search(r'name="csrf" value="(\w+)"', client.get(path).get_data(as_text=True)).group(1)


def _user(app, client, name):
    token = _token(client, "/cadastrar")
    client.post("/cadastrar", data={"csrf": token, "nome": name, "username": name, "email": f"{name}@example.com", "password": "Senha#forte123"})
    with app.app_context():
        from liga.services import accounts

        accounts.mark_verified(accounts.user_by_username(name)["id"])


def test_leave_dupla_opponent_wins_and_lobby_cancel(app):
    a, b = app.test_client(), app.test_client()
    _user(app, a, "sai_a")
    _user(app, b, "sai_b")
    token = _token(a, "/partida")
    rid = a.post("/partida", data={"csrf": token, "mode": "online", "difficulty": "medio"}).headers["Location"].split("/")[2]
    code = a.get(f"/sala/{rid}/estado").get_json()["code"]
    b.post("/partida", data={"csrf": _token(b, "/partida"), "codigo": code})
    a.post(f"/sala/{rid}/comecar", data={"csrf": token})
    data = a.get(f"/partida/{rid}/estado").get_json()
    assert data["seconds_left"] is not None and data["seconds_left"] <= TURN_SECONDS
    r = a.post(f"/partida/{rid}/sair", data={"csrf": token})
    assert r.headers["Location"].endswith(f"/partida/{rid}/fim")
    page = b.get(f"/partida/{rid}/fim").get_data(as_text=True)
    assert "sai_a saiu da partida" in page, page[page.find("<main"):][:1500]
    assert "VOLTAR AO MENU" in page
    rid2 = a.post("/partida", data={"csrf": token, "mode": "online", "difficulty": "medio"}).headers["Location"].split("/")[2]
    a.post(f"/partida/{rid2}/sair", data={"csrf": token})
    assert a.get(f"/sala/{rid2}/estado").get_json()["status"] == "cancelled"


def test_leave_ai_returns_to_menu(app):
    a = app.test_client()
    _user(app, a, "sai_ia")
    token = _token(a, "/partida")
    loc = a.post("/partida", data={"csrf": token, "mode": "ai", "difficulty": "facil"}).headers["Location"]
    mid = loc.split("/")[2]
    if loc.endswith("/fim"):
        return
    r = a.post(f"/partida/{mid}/sair", data={"csrf": token})
    assert r.headers["Location"] == "/"
    assert "Partidas em andamento" not in a.get("/partida").get_data(as_text=True)
