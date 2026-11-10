from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from liga.security import current_user, verified_required
from liga.services import accounts, matches

bp = Blueprint("play", __name__)


@bp.route("/partida", methods=["GET", "POST"])
@verified_required
def new():
    user = current_user()
    if request.method == "POST" and request.form.get("codigo"):
        match_id, error = matches.join_room(user["id"], request.form.get("codigo", ""))
        if error:
            flash(error, "error")
            return redirect(url_for("play.new"))
        match = matches.get_match(match_id)
        if match["status"] == "waiting":
            return redirect(url_for("play.lobby", match_id=match_id))
        return redirect(url_for("play.match", match_id=match_id))
    if request.method == "POST":
        mode = request.form.get("mode", "ai")
        difficulty = request.form.get("difficulty", "facil")
        if mode == "online":
            match_id, _code = matches.create_room(user["id"], difficulty)
            return redirect(url_for("play.lobby", match_id=match_id))
        match_id = matches.create_ai(user["id"], difficulty)
        match = matches.get_match(match_id)
        if match["status"] == "finished":
            return redirect(url_for("play.result", match_id=match_id))
        return redirect(url_for("play.match", match_id=match_id))
    return render_template("play/new.html", opens=matches.open_matches(user["id"]))


@bp.route("/sala/<int:match_id>")
@verified_required
def lobby(match_id):
    match = matches.get_match(match_id)
    if match is None or matches.slot_of(match, current_user()["id"]) is None:
        return redirect(url_for("play.new"))
    if match["status"] != "waiting":
        return redirect(url_for("play.match", match_id=match_id))
    user = current_user()
    guest = accounts.user_by_id(match["player2_id"]) if match["player2_id"] else None
    host = accounts.user_by_id(match["player1_id"])
    return render_template(
        "play/lobby.html",
        match=match,
        owner=match["player1_id"] == user["id"],
        guest=guest["display_name"] if guest else None,
        host=host["display_name"] if host else "Jogador 1",
    )


@bp.route("/sala/<int:match_id>/estado")
@verified_required
def lobby_state(match_id):
    match = matches.get_match(match_id)
    user = current_user()
    if match is None or matches.slot_of(match, user["id"]) is None:
        return jsonify({"ok": False}), 404
    if match["status"] == "waiting":
        guest = accounts.user_by_id(match["player2_id"]) if match["player2_id"] else None
        owner = match["player1_id"] == user["id"]
        return jsonify(
            {
                "ok": True,
                "status": "waiting",
                "code": match["room_code"],
                "guest": guest["display_name"] if guest else None,
                "owner": owner,
                "can_start": owner and bool(match["player2_id"]),
            }
        )
    return jsonify(
        {
            "ok": True,
            "status": match["status"],
            "url": url_for("play.match", match_id=match_id),
        }
    )


@bp.route("/sala/<int:match_id>/comecar", methods=["POST"])
@verified_required
def begin(match_id):
    started, error = matches.start_room(current_user()["id"], match_id)
    if error:
        flash(error, "error")
        return redirect(url_for("play.lobby", match_id=match_id))
    return redirect(url_for("play.match", match_id=started))


@bp.route("/partida/<int:match_id>/falar", methods=["POST"])
@verified_required
def speak(match_id):
    body = request.get_json(silent=True) or {}
    payload, error = matches.say(match_id, current_user()["id"], body.get("body"))
    if error:
        return jsonify({"ok": False, "error": error}), 409
    payload["result_url"] = url_for("play.result", match_id=match_id)
    return jsonify(payload)


@bp.route("/partida/<int:match_id>")
@verified_required
def match(match_id):
    row = matches.get_match(match_id)
    if row is None or matches.slot_of(row, current_user()["id"]) is None:
        return redirect(url_for("play.new"))
    if row["status"] == "waiting":
        return redirect(url_for("play.lobby", match_id=match_id))
    if row["status"] == "finished":
        return redirect(url_for("play.result", match_id=match_id))
    return render_template(
        "play/match.html",
        match=row,
        sound=bool(current_user()["sound_on"]),
    )


@bp.route("/partida/<int:match_id>/estado")
@verified_required
def state(match_id):
    payload, error = matches.view_for(match_id, current_user()["id"])
    if error:
        return jsonify({"ok": False, "error": error}), 404
    payload["result_url"] = url_for("play.result", match_id=match_id)
    return jsonify(payload)


@bp.route("/partida/<int:match_id>/jogar", methods=["POST"])
@verified_required
def act(match_id):
    body = request.get_json(silent=True) or {}
    kind = body.get("action")
    if kind not in ("play", "draw", "pass"):
        return jsonify({"ok": False, "error": "Ação desconhecida."}), 400
    raw_tile = body.get("tile_id")
    try:
        tile_id = int(raw_tile) if raw_tile is not None else None
    except (TypeError, ValueError):
        tile_id = None
    payload, error = matches.action(
        match_id,
        current_user()["id"],
        kind,
        tile_id=tile_id,
        side=body.get("side") if body.get("side") in ("left", "right", "center") else None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 409
    payload["result_url"] = url_for("play.result", match_id=match_id)
    return jsonify(payload)


@bp.route("/partida/<int:match_id>/sair", methods=["POST"])
@verified_required
def leave(match_id):
    row = matches.get_match(match_id)
    error = matches.leave(match_id, current_user()["id"])
    if error:
        flash(error, "error")
        return redirect(url_for("play.new"))
    if row is not None and row["mode"] == "online" and row["status"] == "playing":
        flash("Você saiu da partida. A vitória foi para o adversário.", "info")
        return redirect(url_for("play.result", match_id=match_id))
    flash("Você saiu da partida.", "info")
    return redirect(url_for("main.home"))


@bp.route("/partida/<int:match_id>/fim")
@verified_required
def result(match_id):
    row = matches.get_match(match_id)
    user = current_user()
    if row is None or matches.slot_of(row, user["id"]) is None:
        return redirect(url_for("play.new"))
    if row["status"] != "finished":
        return redirect(url_for("play.match", match_id=match_id))
    viewer = matches.slot_of(row, user["id"])
    names = matches.player_names(row)
    winner = row["winner_slot"]
    ended = matches.load_state(row["state_json"]) or {}
    reason = (ended.get("end") or {}).get("reason")
    if winner == 0:
        mood = "triste"
        title = "Empate!"
        blurb = "Foi quase! Estude mais um pouco."
    elif winner == viewer and reason in ("desistencia", "abandono"):
        mood = "feliz"
        title = "Você ganhou!"
        loser = names[2 if viewer == 1 else 1]
        blurb = f"{loser} saiu da partida" + (" (tempo esgotado)." if reason == "abandono" else ".")
    elif winner == viewer:
        mood = "feliz"
        title = "Você ganhou!"
        blurb = "Ebaaa! Você ligou as fórmulas direitinho."
    elif reason in ("desistencia", "abandono"):
        mood = "triste"
        title = "Você saiu da partida"
        blurb = "A vitória foi para o adversário." if reason == "desistencia" else "Seu tempo acabou várias vezes seguidas."
    else:
        mood = "triste"
        state = matches.load_state(row["state_json"])
        count = state["placed"][str(viewer)] if state else 0
        title = "Você perdeu!"
        blurb = f"Aah... Recomendo que estude mais um pouco! Você ligou {count} peças certas!"
    return render_template(
        "play/result.html",
        match=row,
        names=names,
        viewer=viewer,
        mood=mood,
        title=title,
        blurb=blurb,
        winner=winner,
    )
