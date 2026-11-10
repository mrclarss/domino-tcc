"""Três níveis da Liga IA, em cima das mesmas regras da mesa."""

from __future__ import annotations

import random

from liga.game.engine import can_pass, draw, is_carroca, legal_moves, mate, pass_turn, play


def choose_action(state: dict, player: int, difficulty: str) -> tuple[str, dict | None]:
    moves = legal_moves(state, player)
    if moves:
        return "play", _pick(state, player, moves, difficulty)
    if state["boneyard"]:
        return "draw", None
    return "pass", None


def run_ai_turn(state: dict, difficulty: str, slot: int = 2) -> dict:
    guard = 0
    while state["status"] == "playing" and state["turn"] == slot and guard < 80:
        guard += 1
        kind, payload = choose_action(state, slot, difficulty)
        if kind == "play":
            ok, _error = play(state, slot, payload["tile_id"], payload["side"])
        elif kind == "draw":
            ok, _error = draw(state, slot)
        else:
            ok, _error = pass_turn(state, slot)
        if not ok and can_pass(state, slot):
            ok, _error = pass_turn(state, slot)
        if not ok:
            break
    return state


def _pick(state: dict, player: int, moves: list[dict], difficulty: str) -> dict:
    options = [(item["tile_id"], side) for item in moves for side in item["sides"]]
    if difficulty == "facil":
        tile_id, side = random.choice(options)
        return {"tile_id": tile_id, "side": side}

    def rank(option):
        tile_id, side = option
        follow = _followers(state, player, tile_id, side)
        weight = 1 if difficulty == "medio" else 5
        keep = 2 if is_carroca(state["tiles"][tile_id]) else 0
        return follow * weight - keep, random.random() if difficulty == "medio" else 0

    tile_id, side = max(options, key=rank)
    return {"tile_id": tile_id, "side": side}


def _followers(state: dict, player: int, tile_id: int, side: str) -> int:
    tile = state["tiles"][tile_id]
    if side == "center":
        exposed = {tile["a"], tile["b"]}
    else:
        end = state["board"][0]["left"] if side == "left" else state["board"][-1]["right"]
        exposed = {tile["b"] if tile["a"] == mate(end) else tile["a"]}
    total = 0
    for other_id in state["hands"][str(player)]:
        if other_id == tile_id:
            continue
        other = state["tiles"][other_id]
        if mate(other["a"]) in exposed or mate(other["b"]) in exposed:
            total += 1
    return total
