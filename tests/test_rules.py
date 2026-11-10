"""Regras oficiais do Liga (seção 13)."""

from liga.game import engine
from liga.game.engine import (
    FORMULA,
    NAME,
    build_tiles,
    can_pass,
    draw,
    face,
    final_points,
    is_carroca,
    new_state,
    pass_turn,
    play,
)


def bare(hand1, hand2, boneyard=(), board=(), turn=1):
    state = new_state(seed=1)
    state.update(
        hands={"1": list(hand1), "2": list(hand2)},
        boneyard=list(boneyard),
        board=list(board),
        turn=turn,
        must_carroca=False,
        drew=False,
    )
    return state


def tile_id(state, a, b):
    for tid, tile in state["tiles"].items():
        if (tile["a"], tile["b"]) == (a, b):
            return tid
    raise KeyError((a, b))


def test_double_set_of_56_tiles_with_name_and_function_faces():
    tiles = build_tiles()
    assert len(tiles) == 56
    for tile in tiles.values():
        assert {tile["a"] % 2, tile["b"] % 2} == {NAME, FORMULA}
    assert sum(is_carroca(t) for t in tiles.values()) == 14


def test_deal_seven_each_rest_in_cemiterio():
    state = new_state(seed=3)
    assert len(state["hands"]["1"]) == 7
    assert len(state["hands"]["2"]) == 7
    assert len(state["boneyard"]) == 56 - 14
    every = state["hands"]["1"] + state["hands"]["2"] + state["boneyard"]
    assert sorted(every) == list(range(56))


def test_carroca_holder_starts_and_must_open_with_it():
    for seed in range(60):
        state = new_state(seed=seed)
        holders = [p for p in (1, 2) if any(is_carroca(state["tiles"][t]) for t in state["hands"][str(p)])]
        if holders:
            assert state["turn"] in holders
            assert state["must_carroca"]
            plain = [t for t in state["hands"][str(state["turn"])] if not is_carroca(state["tiles"][t])]
            if plain:
                ok, _ = play(state, state["turn"], plain[0], "center")
                assert not ok
        else:
            assert state["turn"] in (1, 2)
            assert not state["must_carroca"]


def test_random_starter_when_nobody_has_carroca():
    starters = set()
    for seed in range(400):
        state = new_state(seed=seed)
        if not state["must_carroca"]:
            starters.add(state["turn"])
    assert starters == {1, 2}


def test_name_connects_only_with_its_formula():
    alcohol_name = face(4, NAME)
    state = bare([], [])
    opener = tile_id(state, face(0, NAME), face(4, FORMULA))  # Ácido / R–OH
    good = tile_id(state, face(4, NAME), face(5, FORMULA))   # Álcool / cetona
    wrong = tile_id(state, face(5, NAME), face(6, FORMULA))
    state["hands"] = {"1": [opener, wrong, 0], "2": [good, 1]}
    assert play(state, 1, opener, "center") == (True, None)
    # ponta direita mostra a fórmula R–OH: só liga com o NOME Álcool
    assert state["board"][-1]["right"] == face(4, FORMULA)
    ok, _ = play(state, 2, good, "right")
    assert ok
    assert state["board"][-1]["left"] == alcohol_name
    assert state["board"][-1]["right"] == face(5, FORMULA)


def test_turns_alternate():
    state = bare([], [])
    a = tile_id(state, face(0, NAME), face(1, FORMULA))
    b = tile_id(state, face(1, NAME), face(2, FORMULA))
    state["hands"] = {"1": [a, 5], "2": [b, 6]}
    play(state, 1, a, "center")
    assert state["turn"] == 2
    ok, err = play(state, 1, 5, "right")
    assert not ok and "vez" in err


def test_must_draw_before_pass_and_may_keep_drawing():
    state = bare([], [])
    opener = tile_id(state, face(0, NAME), face(0, FORMULA))
    stuck = tile_id(state, face(6, NAME), face(6, FORMULA))
    filler = [tile_id(state, face(3, NAME), face(3, FORMULA)), tile_id(state, face(3, FORMULA), face(3, NAME))]
    state["board"] = [{"id": opener, "left": face(0, NAME), "right": face(0, FORMULA)}]
    state["hands"] = {"1": [stuck], "2": [7]}
    state["boneyard"] = list(filler)
    ok, err = pass_turn(state, 1)
    assert not ok and "Puxe" in err
    assert draw(state, 1) == (True, None)
    assert can_pass(state, 1)
    assert draw(state, 1) == (True, None)  # pode continuar puxando
    assert pass_turn(state, 1) == (True, None)
    assert state["turn"] == 2 and state["drew"] is False


def test_cannot_draw_when_has_a_move():
    state = bare([], [])
    opener = tile_id(state, face(0, NAME), face(1, FORMULA))
    fits = tile_id(state, face(1, NAME), face(2, FORMULA))
    state["board"] = [{"id": opener, "left": face(0, NAME), "right": face(1, FORMULA)}]
    state["hands"] = {"1": [fits], "2": [9]}
    state["boneyard"] = [20]
    ok, _ = draw(state, 1)
    assert not ok


def test_pass_without_draw_only_when_cemiterio_empty():
    state = bare([], [])
    opener = tile_id(state, face(0, NAME), face(0, FORMULA))
    state["board"] = [{"id": opener, "left": face(0, NAME), "right": face(0, FORMULA)}]
    state["hands"] = {"1": [tile_id(state, face(6, NAME), face(6, FORMULA))], "2": [tile_id(state, face(0, NAME), face(5, FORMULA))]}
    assert pass_turn(state, 1) == (True, None)
    assert state["status"] == "playing" and state["turn"] == 2


def test_empty_hand_wins_and_scoring():
    state = bare([], [])
    last = tile_id(state, face(2, NAME), face(3, FORMULA))
    state["hands"] = {"1": [last], "2": [1, 2, 3]}
    state["scores"] = {"1": 20, "2": 15}
    play(state, 1, last, "center")
    assert state["status"] == "finished"
    end = state["end"]
    assert end["winner"] == 1
    assert end["hits"] == {"1": 25, "2": 15}
    assert end["points"] == {"1": 25 + 7, "2": 15}


def test_five_points_per_hit():
    state = bare([], [])
    a = tile_id(state, face(0, NAME), face(1, FORMULA))
    state["hands"] = {"1": [a, 4], "2": [5]}
    play(state, 1, a, "center")
    assert state["scores"]["1"] == 5


def blocked_state(hand1, hand2):
    state = bare([], [])
    opener = tile_id(state, face(0, NAME), face(0, FORMULA))
    state["board"] = [{"id": opener, "left": face(0, NAME), "right": face(0, FORMULA)}]
    dead = [t for t, tile in state["tiles"].items() if function_of_both(tile) and t != opener]
    state["hands"] = {"1": dead[:hand1], "2": dead[hand1 : hand1 + hand2]}
    return state


def function_of_both(tile):
    return tile["a"] // 2 != 0 and tile["b"] // 2 != 0


def test_blocked_table_fewer_pieces_wins():
    state = blocked_state(2, 4)
    state["scores"] = {"1": 10, "2": 30}
    assert pass_turn(state, 1) == (True, None)
    assert state["status"] == "finished"
    assert state["end"]["winner"] == 1
    assert state["end"]["reason"] == "travada"
    assert state["end"]["points"] == {"1": 10 + 15, "2": 30}


def test_blocked_table_same_pieces_is_draw():
    state = blocked_state(3, 3)
    state["scores"] = {"1": 10, "2": 20}
    pass_turn(state, 1)
    assert state["end"]["winner"] == 0
    assert state["end"]["points"] == {"1": 10, "2": 20}


def test_final_points_helper():
    assert final_points({"1": 30, "2": 20}, 2) == {"1": 30, "2": 35}
    assert final_points({"1": 30, "2": 20}, 0) == {"1": 30, "2": 20}


def test_ai_games_always_finish():
    from liga.game.ai import choose_action

    for difficulty in ("facil", "medio", "dificil"):
        for seed in range(25):
            state = new_state(seed=seed)
            for _ in range(500):
                if state["status"] != "playing":
                    break
                player = state["turn"]
                kind, payload = choose_action(state, player, difficulty)
                if kind == "play":
                    ok, err = play(state, player, payload["tile_id"], payload["side"])
                elif kind == "draw":
                    ok, err = draw(state, player)
                else:
                    ok, err = pass_turn(state, player)
                if not ok and engine.can_pass(state, player):
                    ok, err = pass_turn(state, player)
                assert ok, err
            assert state["status"] == "finished"
