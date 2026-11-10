"""Persistência das partidas. A mesa em si mora no motor, não no SQL."""

from __future__ import annotations

import json
import secrets
import threading
from copy import deepcopy

from datetime import datetime, timedelta, timezone

from liga.db import get_db, transaction, utc_now
from liga.game.chemistry import FUNCTIONS
from liga.game.engine import (
    HAND_SIZE,
    can_draw,
    can_pass,
    describe,
    draw,
    function_of,
    kind_of,
    label,
    legal_moves,
    mate,
    new_state,
    pass_turn,
    pieces,
    play,
    seconds_left,
    tick,
    forfeit,
    TURN_SECONDS,
)

ROOM_TTL_MINUTES = 30

DIFFICULTIES = ("facil", "medio", "dificil")

_guard = threading.Lock()
_locks: dict[int, threading.Lock] = {}
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PHRASES = ("Boa!", "Quase!", "Sua vez", "Boa jogada", "Vamos!", "Ops", "De novo!", "Haha")
EMOJIS = ("😄", "😮", "🔥", "👏", "🧪", "💪", "😎", "🤔")


def _mutex(match_id: int) -> threading.Lock:
    with _guard:
        if match_id not in _locks:
            _locks[match_id] = threading.Lock()
        return _locks[match_id]


def dump_state(state: dict) -> str:
    raw = deepcopy(state)
    raw["tiles"] = {str(key): value for key, value in raw["tiles"].items()}
    return json.dumps(raw, ensure_ascii=False)


def load_state(text: str | None) -> dict | None:
    if not text:
        return None
    raw = json.loads(text)
    raw["tiles"] = {int(key): value for key, value in raw["tiles"].items()}
    return raw


def create_ai(user_id: int, difficulty: str) -> int:
    if difficulty not in DIFFICULTIES:
        difficulty = "facil"
    hand_size = HAND_SIZE
    state = new_state()
    if state["turn"] == 2:
        from liga.game.ai import run_ai_turn

        run_ai_turn(state, difficulty, 2)
    with transaction() as db:
        cursor = db.execute(
            """
            INSERT INTO matches (
                mode, difficulty, hand_size, status, player1_id, state_json, created_at
            ) VALUES ('ai', ?, ?, 'playing', ?, ?, ?)
            """,
            (difficulty, hand_size, user_id, dump_state(state), utc_now()),
        )
        match_id = cursor.lastrowid
        _store_finish(db, match_id, state)
    return match_id


def create_room(user_id: int, difficulty: str) -> tuple[int, str]:
    if difficulty not in DIFFICULTIES:
        difficulty = "facil"
    code = _unique_code()
    with transaction() as db:
        cursor = db.execute(
            """
            INSERT INTO matches (
                mode, difficulty, hand_size, status, room_code, player1_id, created_at
            ) VALUES ('online', ?, ?, 'waiting', ?, ?, ?)
            """,
            (difficulty, HAND_SIZE, code, user_id, utc_now()),
        )
        return cursor.lastrowid, code


def join_room(user_id: int, code: str):
    cleaned = (code or "").strip().upper()
    with transaction() as db:
        match = db.execute(
            "SELECT * FROM matches WHERE room_code = ?",
            (cleaned,),
        ).fetchone()
        if match is None:
            return None, "Sala não encontrada."
        if match["player1_id"] == user_id:
            return match["id"], None
        if match["player2_id"] and match["player2_id"] != user_id:
            return None, "Essa sala já está completa."
        if match["player2_id"] == user_id:
            return match["id"], None
        if match["status"] != "waiting":
            return None, "Essa partida já começou."
        db.execute(
            """
            UPDATE matches
            SET player2_id = ?
            WHERE id = ? AND status = 'waiting' AND player2_id IS NULL
            """,
            (user_id, match["id"]),
        )
        return match["id"], None


def start_room(user_id: int, match_id: int):
    with transaction() as db:
        match = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if match is None or slot_of(match, user_id) is None:
            return None, "Sala não encontrada."
        if match["player1_id"] != user_id:
            return None, "Só quem criou a sala começa a partida."
        if match["status"] != "waiting":
            return match["id"], None
        if not match["player2_id"]:
            return None, "Ainda falta a outra pessoa."
        state = new_state()
        db.execute(
            """
            UPDATE matches
            SET status = 'playing', state_json = ?
            WHERE id = ? AND status = 'waiting'
            """,
            (dump_state(state), match_id),
        )
        return match_id, None


def get_match(match_id: int):
    return get_db().execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()


def slot_of(match, user_id: int) -> int | None:
    if match["player1_id"] == user_id:
        return 1
    if match["player2_id"] == user_id:
        return 2
    return None


def history(user_id: int):
    return get_db().execute(
        """
        SELECT * FROM matches
        WHERE player1_id = ? OR player2_id = ?
        ORDER BY id DESC
        LIMIT 40
        """,
        (user_id, user_id),
    ).fetchall()


def open_matches(user_id: int):
    expire_stale(user_id)
    return get_db().execute(
        """
        SELECT * FROM matches
        WHERE status IN ('waiting', 'playing')
          AND (player1_id = ? OR player2_id = ?)
        ORDER BY id DESC
        """,
        (user_id, user_id),
    ).fetchall()


def expire_stale(user_id: int) -> None:
    """Salas esperando há muito tempo somem; partidas paradas aplicam o tempo."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=ROOM_TTL_MINUTES)).replace(microsecond=0).isoformat()
    with transaction() as tx:
        tx.execute(
            "UPDATE matches SET status = 'cancelled' WHERE status = 'waiting' AND created_at < ? AND (player1_id = ? OR player2_id = ?)",
            (cutoff, user_id, user_id),
        )
    rows = db.execute(
        "SELECT id FROM matches WHERE status = 'playing' AND (player1_id = ? OR player2_id = ?)",
        (user_id, user_id),
    ).fetchall()
    for row in rows:
        with _mutex(row["id"]):
            with transaction() as tx:
                match = tx.execute("SELECT * FROM matches WHERE id = ?", (row["id"],)).fetchone()
                state = load_state(match["state_json"])
                if state and _advance(match, state):
                    _save(tx, match["id"], state)


def _advance(match, state: dict) -> bool:
    changed = False
    for _ in range(10):
        if state["status"] != "playing":
            break
        if match["mode"] == "ai" and state["turn"] == 2:
            from liga.game.ai import run_ai_turn

            run_ai_turn(state, match["difficulty"] or "facil", 2)
            changed = True
            continue
        if not tick(state):
            break
        changed = True
    return changed


def leave(match_id: int, user_id: int):
    with _mutex(match_id):
        with transaction() as db:
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
            if match is None:
                return "Partida não encontrada."
            viewer = slot_of(match, user_id)
            if viewer is None:
                return "Essa mesa não é sua."
            if match["status"] == "waiting":
                if viewer == 1:
                    db.execute("UPDATE matches SET status = 'cancelled' WHERE id = ?", (match_id,))
                else:
                    db.execute("UPDATE matches SET player2_id = NULL WHERE id = ?", (match_id,))
                return None
            if match["status"] != "playing":
                return None
            state = load_state(match["state_json"])
            forfeit(state, viewer)
            _save(db, match_id, state)
            return None


def player_names(match) -> dict[int, str]:
    from liga.services.accounts import user_by_id

    first = user_by_id(match["player1_id"])
    names = {1: first["display_name"] if first else "Jogador 1"}
    if match["mode"] == "ai":
        names[2] = "Liga IA"
    else:
        second = user_by_id(match["player2_id"]) if match["player2_id"] else None
        names[2] = second["display_name"] if second else "Jogador 2"
    return names


def view_for(match_id: int, user_id: int) -> tuple[dict | None, str | None]:
    with _mutex(match_id):
        with transaction() as db:
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
            if match is None:
                return None, "Partida não encontrada."
            viewer = slot_of(match, user_id)
            if viewer is None:
                return None, "Essa mesa não é sua."
            if match["status"] == "waiting":
                return {"status": "waiting", "match_id": match_id, "room_code": match["room_code"]}, None
            state = load_state(match["state_json"])
            if _advance(match, state):
                _save(db, match_id, state)
            names = _names_in(db, match)
            return _public(match, state, viewer, names, _recent_chat(db, match_id, viewer, names)), None


def say(match_id: int, user_id: int, body: str):
    text = (body or "").strip()
    if text not in PHRASES and text not in EMOJIS:
        return None, "Escolha uma frase ou um emoji."
    with _mutex(match_id):
        with transaction() as db:
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
            if match is None:
                return None, "Partida não encontrada."
            viewer = slot_of(match, user_id)
            if viewer is None:
                return None, "Essa mesa não é sua."
            if match["status"] != "playing":
                return None, "O chat abre quando a partida começa."
            last = db.execute(
                """
                SELECT created_at FROM chats
                WHERE match_id = ? AND player_slot = ?
                ORDER BY id DESC LIMIT 1
                """,
                (match_id, viewer),
            ).fetchone()
            if last and _too_soon(last["created_at"]):
                return None, "Espere um instante."
            db.execute(
                """
                INSERT INTO chats (match_id, player_slot, body, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (match_id, viewer, text, utc_now()),
            )
            state = load_state(match["state_json"])
            names = _names_in(db, match)
            return _public(match, state, viewer, names, _recent_chat(db, match_id, viewer, names)), None


def action(match_id: int, user_id: int, kind: str, tile_id=None, side=None):
    with _mutex(match_id):
        with transaction() as db:
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
            if match is None:
                return None, "Partida não encontrada."
            viewer = slot_of(match, user_id)
            if viewer is None:
                return None, "Essa mesa não é sua."
            if match["status"] != "playing":
                return None, "Essa partida não está em jogo."
            state = load_state(match["state_json"])
            if _advance(match, state):
                _save(db, match_id, state)
                if state["status"] != "playing" or state["turn"] != viewer:
                    names = _names_in(db, match)
                    payload = _public(match, state, viewer, names, _recent_chat(db, match_id, viewer, names))
                    payload["ok"] = False
                    payload["error"] = "Seu tempo acabou."
                    return payload, None
            if kind == "play":
                if tile_id is None:
                    return None, "Escolha uma peça."
                ok, error = play(state, viewer, int(tile_id), side or "")
            elif kind == "draw":
                ok, error = draw(state, viewer)
            elif kind == "pass":
                ok, error = pass_turn(state, viewer)
            else:
                return None, "Ação desconhecida."
            if not ok:
                return None, error
            detail = json.dumps({"tile_id": tile_id, "side": side}, ensure_ascii=False)
            db.execute(
                """
                INSERT INTO moves (match_id, player_slot, action, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (match_id, viewer, kind, detail, utc_now()),
            )
            if match["mode"] == "ai" and state["status"] == "playing" and state["turn"] == 2:
                from liga.game.ai import run_ai_turn

                run_ai_turn(state, match["difficulty"] or "facil", 2)
            _save(db, match_id, state)
            names = _names_in(db, match)
            return _public(match, state, viewer, names, _recent_chat(db, match_id, viewer, names)), None


def _too_soon(stamp: str) -> bool:
    try:
        previous = datetime.fromisoformat(stamp)
    except ValueError:
        return False
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - previous).total_seconds() < 0.8


def _recent_chat(db, match_id: int, viewer: int, names: dict[int, str]):
    rows = db.execute(
        """
        SELECT id, player_slot, body FROM chats
        WHERE match_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (match_id,),
    ).fetchall()
    items = []
    for row in reversed(rows):
        slot = row["player_slot"]
        items.append(
            {
                "id": row["id"],
                "slot": slot,
                "body": row["body"],
                "name": names.get(slot, ""),
                "you": slot == viewer,
            }
        )
    return items


def _save(db, match_id: int, state: dict) -> None:
    db.execute(
        "UPDATE matches SET state_json = ?, status = ? WHERE id = ?",
        (dump_state(state), state["status"], match_id),
    )
    _store_finish(db, match_id, state)


def _store_finish(db, match_id: int, state: dict) -> None:
    if state["status"] != "finished":
        return
    row = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    end = state["end"]
    db.execute(
        """
        UPDATE matches
        SET status = 'finished', winner_slot = ?, p1_points = ?, p2_points = ?,
            p1_pips = ?, p2_pips = ?, finished_at = COALESCE(finished_at, ?)
        WHERE id = ?
        """,
        (
            end["winner"],
            end["points"]["1"],
            end["points"]["2"],
            end["pips"]["1"],
            end["pips"]["2"],
            utc_now(),
            match_id,
        ),
    )
    if row["stats_applied"]:
        return
    _award(db, row["player1_id"], slot=1, end=end)
    if row["player2_id"]:
        _award(db, row["player2_id"], slot=2, end=end)
    db.execute("UPDATE matches SET stats_applied = 1 WHERE id = ?", (match_id,))


def _award(db, user_id: int, slot: int, end: dict) -> None:
    winner = end["winner"]
    gained = end["points"][str(slot)]
    if winner == 0:
        column = "draws"
    elif winner == slot:
        column = "wins"
    else:
        column = "losses"
    db.execute(
        f"UPDATE users SET {column} = {column} + 1, points = points + ? WHERE id = ?",
        (gained, user_id),
    )


def _names_in(db, match) -> dict[int, str]:
    first = db.execute("SELECT display_name FROM users WHERE id = ?", (match["player1_id"],)).fetchone()
    names = {1: first["display_name"] if first else "Jogador 1"}
    if match["mode"] == "ai":
        names[2] = "Liga IA"
        return names
    if match["player2_id"]:
        second = db.execute(
            "SELECT display_name FROM users WHERE id = ?",
            (match["player2_id"],),
        ).fetchone()
        names[2] = second["display_name"] if second else "Jogador 2"
    else:
        names[2] = "Jogador 2"
    return names


def _half(value: int, hints: bool) -> dict:
    info = FUNCTIONS[function_of(value)]
    named = kind_of(value) == 0
    half = {
        "face": value,
        "kind": "nome" if named else "funcao",
        "text": info["tile"] if named else info["struct"],
    }
    if hints:
        half["fn"] = function_of(value)
        half["hint"] = info["struct"] if named else info["tile"]
        half["mate"] = label(mate(value))
    return half


def _face(state: dict, tile_id: int, hints: bool, left: int | None = None, right: int | None = None) -> dict:
    tile = state["tiles"][tile_id]
    a = tile["a"] if left is None else left
    b = tile["b"] if right is None else right
    return {"id": tile_id, "a": _half(a, hints), "b": _half(b, hints)}


def _public(match, state: dict, viewer: int, names: dict[int, str], chat=None) -> dict:
    hints = (match["difficulty"] or "facil") == "facil"
    playing = state["status"] == "playing"
    your_moves = legal_moves(state, viewer) if playing else []
    log = [describe(item | {"seq": 0}, viewer, names) for item in state["log"]]
    return {
        "ok": True,
        "match_id": match["id"],
        "mode": match["mode"],
        "difficulty": match["difficulty"] or "facil",
        "hints": hints,
        "status": state["status"],
        "you": viewer,
        "turn": state["turn"],
        "your_turn": playing and state["turn"] == viewer,
        "your_hand": [_face(state, tile_id, hints) for tile_id in state["hands"][str(viewer)]],
        "board": [
            _face(state, item["id"], hints, item["left"], item["right"]) for item in state["board"]
        ],
        "boneyard": len(state["boneyard"]),
        "pieces": {"1": pieces(state, 1), "2": pieces(state, 2)},
        "scores": state["scores"],
        "legal": your_moves if hints else [],
        "must_carroca": bool(state.get("must_carroca")) and not state["board"],
        "names": {"1": names[1], "2": names[2]},
        "seq": state["seq"],
        "last_actor": state["last"]["actor"] if state["last"] else None,
        "last_tile": state["last"].get("tile") if state["last"] else None,
        "message": describe(state["last"], viewer, names),
        "chat": chat or [],
        "phrases": list(PHRASES),
        "emojis": list(EMOJIS),
        "log": [line for line in log if line],
        "end": state["end"],
        "can_draw": can_draw(state, viewer),
        "can_pass": can_pass(state, viewer),
        "seconds_left": seconds_left(state) if playing else None,
        "turn_seconds": TURN_SECONDS,
    }


def _unique_code() -> str:
    db = get_db()
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if db.execute("SELECT 1 FROM matches WHERE room_code = ?", (code,)).fetchone() is None:
            return code
    return "".join(secrets.choice(ALPHABET) for _ in range(8))
