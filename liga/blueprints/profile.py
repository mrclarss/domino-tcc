import os

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from liga.art import PALETTE, axolotl_svg
from liga.security import current_user, login_required
from liga.services import accounts
from liga.services.accounts import BANNERS

bp = Blueprint("profile", __name__)


def _avatar_file(user):
    if user["avatar"] != "custom" or not user["avatar_ext"]:
        return None
    path = os.path.join(current_app.config["AVATARS"], f"{user['id']}.{user['avatar_ext']}")
    if os.path.exists(path):
        return path
    return None


@bp.route("/avatar/<int:user_id>")
def avatar_image(user_id):
    row = accounts.user_by_id(user_id)
    if row is None:
        abort(404)
    path = _avatar_file(row)
    if path:
        return send_file(path)
    color = row["avatar"] if row["avatar"] in PALETTE else "rosa"
    return Response(axolotl_svg(color, "feliz"), mimetype="image/svg+xml")


@bp.route("/perfil")
@login_required
def view():
    user = current_user()
    fresh = accounts.public_user(accounts.user_by_id(user["id"]))
    return render_template(
        "profile/view.html",
        user=fresh,
        level=accounts.level_for(fresh["wins"]),
        recent=accounts.recent_matches(fresh["id"]),
    )


@bp.route("/perfil/editar", methods=["GET", "POST"])
@login_required
def edit():
    user = accounts.public_user(accounts.user_by_id(current_user()["id"]))
    if request.method == "POST":
        avatar = request.form.get("avatar", user["avatar"])
        error = accounts.update_profile(
            user["id"],
            request.form.get("nome", ""),
            request.form.get("username", ""),
            request.form.get("bio", ""),
            avatar,
            request.form.get("banner", "teal"),
        )
        upload = request.files.get("foto")
        if error:
            flash(error, "error")
            return redirect(url_for("profile.edit"))
        else:
            if upload and upload.filename:
                saved = _save_upload(user["id"], upload)
                if saved:
                    flash(saved, "error")
                else:
                    flash("Perfil salvo.", "info")
            else:
                flash("Perfil salvo.", "info")
            return redirect(url_for("profile.view"))
    fresh = accounts.public_user(accounts.user_by_id(user["id"]))
    return render_template(
        "profile/edit.html",
        user=fresh,
        palette=PALETTE,
        banners=BANNERS,
        level=accounts.level_for(fresh["wins"]),
    )


def _save_upload(user_id, upload) -> str | None:
    data = upload.read()
    if len(data) > 1_500_000:
        return "A foto precisa ter menos de 1,5 MB."
    ext = _sniff(data)
    if ext is None:
        return "Envie uma imagem PNG, JPG ou WebP."
    folder = current_app.config["AVATARS"]
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if old.startswith(f"{user_id}."):
            os.remove(os.path.join(folder, old))
    with open(os.path.join(folder, f"{user_id}.{ext}"), "wb") as handle:
        handle.write(data)
    accounts.set_custom_avatar(user_id, ext)
    return None


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


@bp.route("/niveis")
@login_required
def levels():
    user = accounts.public_user(accounts.user_by_id(current_user()["id"]))
    return render_template(
        "profile/levels.html",
        user=user,
        level=accounts.level_for(user["wins"]),
    )


@bp.route("/dados")
@login_required
def data():
    user = accounts.public_user(accounts.user_by_id(current_user()["id"]))
    level = accounts.level_for(user["wins"])
    rows = [
        ("Nome", user["display_name"]),
        ("Usuário", f"@{user['username']}"),
        ("E-mail", user["email"]),
        ("Bio", user["bio"] or "—"),
        ("Nível", str(level["level"])),
        ("Vitórias", str(user["wins"])),
        ("Derrotas", str(user["losses"])),
        ("Empates", str(user["draws"])),
        ("Pontos", str(user["points"])),
    ]
    return render_template("profile/data.html", rows=rows)
