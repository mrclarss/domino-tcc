from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from liga.art import axolotl_svg
from liga.game.chemistry import RULES
from liga.security import current_user, login_required
from liga.services import accounts, matches, suggestions

_ZONE = timezone(timedelta(hours=-3))
_DIFFICULTY = {"facil": "Fácil", "medio": "Médio", "dificil": "Difícil"}

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    user = current_user()
    level = accounts.level_for(user["wins"]) if user else None
    return render_template("main/home.html", level=level)


@bp.route("/como-jogar")
def tutorial():
    return render_template("main/tutorial.html", rules=RULES)


@bp.route("/menu")
def menu():
    return render_template("main/menu.html")


@bp.route("/ranking")
def ranking():
    tab = request.args.get("aba", "geral")
    user = current_user()
    pending = []
    if tab == "amigos":
        rows = accounts.friends_ranking(user["id"]) if user else []
        pending = accounts.pending_requests(user["id"]) if user else []
    else:
        tab = "geral"
        rows = accounts.ranking()
    position = accounts.position_of(user["id"]) if user else None
    return render_template(
        "main/ranking.html",
        rows=rows,
        tab=tab,
        position=position,
        pending=pending,
    )


def _when(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value).astimezone(_ZONE)
    except (TypeError, ValueError):
        return ""
    return moment.strftime("%d/%m · %H:%M")


def _match_cards(user_id: int):
    cards = []
    for match in matches.history(user_id):
        slot = matches.slot_of(match, user_id)
        names = matches.player_names(match)
        opponent = names[2 if slot == 1 else 1]
        status = match["status"]
        if status == "waiting":
            href = url_for("play.lobby", match_id=match["id"])
            label, tone = "Aguardando", "wait"
        elif status == "playing":
            href = url_for("play.match", match_id=match["id"])
            label, tone = "Em jogo", "play"
        else:
            href = url_for("play.result", match_id=match["id"])
            winner = match["winner_slot"]
            if winner == 0:
                label, tone = "Empate", "draw"
            elif winner == slot:
                label, tone = "Vitória", "win"
            else:
                label, tone = "Derrota", "loss"
        mode = "IA" if match["mode"] == "ai" else "Online"
        level = _DIFFICULTY.get(match["difficulty"] or "", "")
        detail = f"{mode} · {level}" if level else mode
        points = match["p1_points"] if slot == 1 else match["p2_points"]
        cards.append(
            {
                "href": href,
                "label": label,
                "tone": tone,
                "opponent": opponent,
                "detail": f"{detail} · {_when(match['finished_at'] or match['created_at'])}",
                "points": points,
            }
        )
    return cards


@bp.route("/partidas")
@login_required
def played():
    user = current_user()
    return render_template("main/matches.html", cards=_match_cards(user["id"]))


@bp.route("/sugestao", methods=["GET", "POST"])
@login_required
def suggest():
    user = current_user()
    if request.method == "POST":
        error = suggestions.add(user["id"], request.form.get("texto", ""))
        flash(error or "Sugestão enviada. Obrigado.", "error" if error else "info")
        return redirect(url_for("main.suggest"))
    rows = [
        {"body": row["body"], "when": _when(row["created_at"])}
        for row in suggestions.mine(user["id"])
    ]
    return render_template("main/suggest.html", rows=rows)


@bp.route("/mascote/<mood>.svg")
def mascot(mood):
    color = request.args.get("cor", "rosa")
    if mood not in {"feliz", "triste", "neutro"}:
        abort(404)
    return Response(axolotl_svg(color, mood), mimetype="image/svg+xml")


@bp.route("/termos")
def terms():
    return render_template("settings/terms.html")


@bp.route("/amigos", methods=["POST"])
@login_required
def add_friend():
    error = accounts.request_friend(current_user()["id"], request.form.get("username", ""))
    flash(error or "Pedido enviado.", "error" if error else "info")
    return redirect(url_for("main.ranking", aba="amigos"))


@bp.route("/amigos/<int:request_id>", methods=["POST"])
@login_required
def answer_friend(request_id):
    error = accounts.respond_friend(
        current_user()["id"],
        request_id,
        request.form.get("aceitar") == "1",
    )
    if error:
        flash(error, "error")
    return redirect(url_for("main.ranking", aba="amigos"))
