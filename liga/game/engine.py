"""Mesa do dominó Liga, seguindo as regras oficiais (seção 13).

Cada face é um número 0..13: função = face // 2, tipo = face % 2
(0 = NOME, 1 = FUNÇÃO/fórmula). Uma ponta só liga com a mesma função
no outro tipo: o nome "Álcool" liga com a fórmula "R–OH" e vice-versa.
São 56 peças (o dobro do dominó comum). Carroça = NOME/FUNÇÃO da mesma função.
"""

from __future__ import annotations

import random
import time

from liga.game.chemistry import FUNCTIONS

HAND_SIZE = 7
POINTS_PER_HIT = 5
NAME, FORMULA = 0, 1
TURN_SECONDS = 60  # tempo de cada jogada
MAX_TIMEOUTS = 3  # vezes seguidas sem jogar = abandono


def face(function: int, kind: int) -> int:
    return function * 2 + kind


def function_of(value: int) -> int:
    return value // 2


def kind_of(value: int) -> int:
    return value % 2


def mate(value: int) -> int:
    """Face que liga com esta: mesma função, outro tipo."""
    return value ^ 1


def label(value: int) -> str:
    info = FUNCTIONS[function_of(value)]
    return info["tile"] if kind_of(value) == NAME else info["formula"]


def is_carroca(tile: dict) -> bool:
    return tile["b"] == mate(tile["a"])


def build_tiles() -> dict[int, dict]:
    tiles = {}
    for i in range(7):
        for j in range(i, 7):
            for a, b in ((face(i, NAME), face(j, FORMULA)), (face(i, FORMULA), face(j, NAME))):
                number = len(tiles)
                tiles[number] = {"id": number, "a": a, "b": b}
    return tiles


def new_state(hand_size: int = HAND_SIZE, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    tiles = build_tiles()
    order = list(tiles)
    rng.shuffle(order)
    hands = {"1": order[:HAND_SIZE], "2": order[HAND_SIZE : HAND_SIZE * 2]}
    boneyard = order[HAND_SIZE * 2 :]
    holders = [p for p in (1, 2) if any(is_carroca(tiles[t]) for t in hands[str(p)])]
    starter = rng.choice(holders or [1, 2])
    return {
        "tiles": tiles,
        "hands": hands,
        "boneyard": boneyard,
        "board": [],
        "turn": starter,
        "must_carroca": bool(holders),
        "drew": False,
        "status": "playing",
        "scores": {"1": 0, "2": 0},
        "placed": {"1": 0, "2": 0},
        "misses": {"1": 0, "2": 0},
        "seq": 0,
        "last": None,
        "log": [],
        "end": None,
        "turn_started": time.time(),
        "timeouts": {"1": 0, "2": 0},
    }


def _sides(state: dict, tile: dict) -> list[str]:
    if not state["board"]:
        if state.get("must_carroca") and not is_carroca(tile):
            return []
        return ["center"]
    sides = []
    if mate(state["board"][0]["left"]) in (tile["a"], tile["b"]):
        sides.append("left")
    if mate(state["board"][-1]["right"]) in (tile["a"], tile["b"]):
        sides.append("right")
    return sides


def moves_of(state: dict, player: int) -> list[dict]:
    """Jogadas possíveis do jogador, ignorando de quem é a vez."""
    moves = []
    for tile_id in state["hands"][str(player)]:
        sides = _sides(state, state["tiles"][tile_id])
        if sides:
            moves.append({"tile_id": tile_id, "sides": sides})
    return moves


def legal_moves(state: dict, player: int) -> list[dict]:
    if state["status"] != "playing" or state["turn"] != player:
        return []
    return moves_of(state, player)


def can_draw(state: dict, player: int) -> bool:
    return (
        state["status"] == "playing"
        and state["turn"] == player
        and bool(state["boneyard"])
        and (state["drew"] or not legal_moves(state, player))
    )


def can_pass(state: dict, player: int) -> bool:
    if state["status"] != "playing" or state["turn"] != player:
        return False
    if state["drew"]:
        return True
    return not state["boneyard"] and not legal_moves(state, player)


def play(state: dict, player: int, tile_id, side: str) -> tuple[bool, str | None]:
    if state["status"] != "playing" or state["turn"] != player:
        return False, "Ainda não é a sua vez."
    slot = str(player)
    if tile_id not in state["hands"][slot]:
        return False, "Essa peça não está na sua mão."
    tile = state["tiles"][tile_id]
    sides = _sides(state, tile)
    if not sides:
        state["misses"][slot] += 1
        if not state["board"] and state.get("must_carroca"):
            return False, "Abra a mesa com uma carroça (nome e função iguais)."
        return False, "Essa peça não liga com nenhuma ponta."
    if side not in sides:
        side = sides[0]

    if side == "center":
        placed = {"id": tile_id, "left": tile["a"], "right": tile["b"]}
        state["board"].append(placed)
        verb, name = "open", f"{label(tile['a'])} / {label(tile['b'])}"
    elif side == "left":
        end = state["board"][0]["left"]
        other = tile["b"] if tile["a"] == mate(end) else tile["a"]
        state["board"].insert(0, {"id": tile_id, "left": other, "right": mate(end)})
        verb, name = "play", FUNCTIONS[function_of(end)]["tile"]
    else:
        end = state["board"][-1]["right"]
        other = tile["b"] if tile["a"] == mate(end) else tile["a"]
        state["board"].append({"id": tile_id, "left": mate(end), "right": other})
        verb, name = "play", FUNCTIONS[function_of(end)]["tile"]

    state["hands"][slot].remove(tile_id)
    state["must_carroca"] = False
    state["scores"][slot] += POINTS_PER_HIT
    state["placed"][slot] += 1
    state.setdefault("timeouts", {"1": 0, "2": 0})[slot] = 0
    _touch(state, player, verb, name, tile_id)
    if not state["hands"][slot]:
        _finish(state, player, "vazia")
    else:
        _next(state, player)
    return True, None


def draw(state: dict, player: int) -> tuple[bool, str | None]:
    if state["status"] != "playing" or state["turn"] != player:
        return False, "Ainda não é a sua vez."
    if not state["boneyard"]:
        return False, "O cemitério está vazio."
    if not can_draw(state, player):
        return False, "Você tem uma jogada. Ligue uma peça."
    state["hands"][str(player)].append(state["boneyard"].pop())
    state["drew"] = True
    state.setdefault("timeouts", {"1": 0, "2": 0})[str(player)] = 0
    _touch(state, player, "draw", "")
    return True, None


def pass_turn(state: dict, player: int) -> tuple[bool, str | None]:
    if state["status"] != "playing" or state["turn"] != player:
        return False, "Ainda não é a sua vez."
    if not can_pass(state, player):
        if state["boneyard"]:
            return False, "Puxe pelo menos uma peça do cemitério antes de passar."
        return False, "Você tem uma jogada. Ligue uma peça."
    _touch(state, player, "pass", "")
    if blocked(state):
        _finish(state, 0, "travada")
    else:
        _next(state, player)
    return True, None


def forfeit(state: dict, player: int) -> tuple[bool, str | None]:
    """Quem sai da partida perde; o adversário vence."""
    if state["status"] != "playing":
        return False, "Essa partida já terminou."
    _touch(state, player, "leave", "")
    _finish(state, 2 if player == 1 else 1, "desistencia")
    return True, None


def seconds_left(state: dict, now: float | None = None) -> int:
    now = time.time() if now is None else now
    started = state.get("turn_started", now)
    return max(0, int(round(started + TURN_SECONDS - now)))


def tick(state: dict, now: float | None = None) -> bool:
    """Aplica o tempo esgotado: puxa do cemitério se der, senão passa.
    Quem estoura o tempo MAX_TIMEOUTS vezes seguidas abandona e perde."""
    now = time.time() if now is None else now
    changed = False
    guard = 0
    while state["status"] == "playing" and guard < 10:
        started = state.setdefault("turn_started", now)
        deadline = started + TURN_SECONDS
        if now < deadline:
            break
        guard += 1
        changed = True
        player = state["turn"]
        slot = str(player)
        timeouts = state.setdefault("timeouts", {"1": 0, "2": 0})
        timeouts[slot] += 1
        if timeouts[slot] >= MAX_TIMEOUTS:
            _touch(state, player, "timeout", "")
            _finish(state, 2 if player == 1 else 1, "abandono")
            break
        if state["boneyard"] and not state["drew"]:
            state["hands"][slot].append(state["boneyard"].pop())
            state["drew"] = True
        _touch(state, player, "timeout", "")
        if blocked(state):
            _finish(state, 0, "travada")
            break
        _next(state, player)
        state["turn_started"] = deadline
    return changed


def blocked(state: dict) -> bool:
    return not state["boneyard"] and not moves_of(state, 1) and not moves_of(state, 2)


def final_points(scores: dict, winner: int) -> dict:
    """Vencedor soma os seus pontos e metade dos do adversário; o resto fica com os seus."""
    out = {"1": scores["1"], "2": scores["2"]}
    if winner in (1, 2):
        loser = "2" if winner == 1 else "1"
        out[str(winner)] += scores[loser] // 2
    return out


def pieces(state: dict, player: int) -> int:
    return len(state["hands"][str(player)])


# compatibilidade: "pips" agora é a quantidade de peças na mão
pips = pieces


def describe(last: dict | None, viewer: int, names: dict[int, str]) -> str:
    if not last:
        return ""
    actor = last["actor"]
    who = "Você" if actor == viewer else names.get(actor, "Oponente")
    verb = last["verb"]
    name = last.get("name") or ""
    if verb == "play":
        return f"{who} ligou na ponta {name}."
    if verb == "open":
        return f"{who} abriu a mesa com {name}."
    if verb == "draw":
        return f"{who} puxou uma peça do cemitério."
    if verb == "pass":
        return f"{who} passou a vez."
    if verb == "timeout":
        return f"O tempo de {who if who != 'Você' else 'você'} acabou."
    if verb == "leave":
        return f"{who} saiu da partida."
    return ""


def _next(state: dict, player: int) -> None:
    state["turn"] = 2 if player == 1 else 1
    state["drew"] = False
    state["turn_started"] = time.time()


def _touch(state: dict, actor: int, verb: str, name: str, tile_id: int | None = None) -> None:
    state["seq"] += 1
    state["last"] = {"actor": actor, "verb": verb, "name": name, "seq": state["seq"], "tile": tile_id}
    state["log"].append({"actor": actor, "verb": verb, "name": name})
    state["log"] = state["log"][-15:]


def _finish(state: dict, winner: int, reason: str) -> None:
    if reason == "travada":
        left, right = pieces(state, 1), pieces(state, 2)
        winner = 1 if left < right else 2 if right < left else 0
    state["status"] = "finished"
    state["end"] = {
        "winner": winner,
        "reason": reason,
        "pips": {"1": pieces(state, 1), "2": pieces(state, 2)},
        "hits": dict(state["scores"]),
        "points": final_points(state["scores"], winner),
        "placed": dict(state["placed"]),
    }
