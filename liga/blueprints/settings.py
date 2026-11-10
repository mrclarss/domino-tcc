from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from liga.security import current_user, login_required
from liga.services import accounts

bp = Blueprint("settings", __name__)


@bp.route("/configuracoes", methods=["GET", "POST"])
def index():
    user = current_user()
    if request.method == "POST" and user:
        accounts.update_settings(
            user["id"],
            request.form.get("theme", "light"),
            request.form.get("sound") == "1",
            request.form.get("notify") == "1",
        )
        flash("Configurações salvas.", "info")
        return redirect(url_for("settings.index"))
    fresh = accounts.public_user(accounts.user_by_id(user["id"])) if user else None
    return render_template("settings/index.html", user=fresh)


@bp.route("/configuracoes/email", methods=["GET", "POST"])
@login_required
def email():
    user = current_user()
    if request.method == "POST":
        if not accounts.check_password(user["id"], request.form.get("senha", "")):
            flash("Senha atual incorreta.", "error")
            return redirect(url_for("settings.email"))
        else:
            error = accounts.change_email(user["id"], request.form.get("email", ""))
            if error:
                flash(error, "error")
                return redirect(url_for("settings.email"))
            else:
                from liga.blueprints.auth import start_code

                flash("E-mail atualizado.", "info")
                return start_code(user["id"], "verify")
    return render_template("settings/email.html")


@bp.route("/configuracoes/senha", methods=["GET", "POST"])
@login_required
def password():
    user = current_user()
    if request.method == "POST":
        if not accounts.check_password(user["id"], request.form.get("atual", "")):
            flash("Senha atual incorreta.", "error")
            return redirect(url_for("settings.password"))
        elif request.form.get("nova") != request.form.get("confirm"):
            flash("As senhas não coincidem.", "error")
            return redirect(url_for("settings.password"))
        else:
            error = accounts.set_password(user["id"], request.form.get("nova", ""))
            if error:
                flash(error, "error")
                return redirect(url_for("settings.password"))
            else:
                flash("Senha atualizada.", "info")
                return redirect(url_for("settings.index"))
    return render_template("settings/password.html")
