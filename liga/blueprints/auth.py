from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from liga import mail

from liga.security import current_user, login_required, login_user, logout_user
from liga.services import accounts

bp = Blueprint("auth", __name__)


def start_code(user_id: int, purpose: str, payload=None):
    """Gera e entrega o código. Sem SMTP em produção, a confirmação de e-mail é
    dispensada e a recuperação de senha fica desligada (nunca mostrar código na tela)."""
    row = accounts.user_by_id(user_id)
    if mail.enabled():
        code = accounts.issue_code(user_id, purpose, payload)
        mail.send_code(row["email"], code, purpose)
        session["code_purpose"] = purpose
        return redirect(url_for("auth.confirm"))
    if current_app.config["SHOW_CODES"]:
        accounts.issue_code(user_id, purpose, payload)
        session["code_purpose"] = purpose
        return redirect(url_for("auth.confirm"))
    if purpose == "verify":
        accounts.mark_verified(user_id)
        return redirect(url_for("main.home"))
    session.pop("pending_user_id", None)
    flash("A recuperação de senha por e-mail ainda não está disponível.", "info")
    return redirect(url_for("auth.login"))


def _purpose() -> str:
    return session.get("code_purpose") or "verify"


def _subject_id():
    if _purpose() == "verify" and current_user():
        return current_user()["id"]
    return session.get("pending_user_id")


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_user() and current_user()["email_verified"]:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        row = accounts.authenticate(request.form.get("username", ""), request.form.get("password", ""))
        if row is None:
            flash("Usuário ou senha incorretos.", "error")
            return redirect(url_for("auth.login"))
        else:
            login_user(row["id"], remember=bool(request.form.get("lembrar")))
            if not row["email_verified"]:
                if accounts.latest_code(row["id"], "verify") is None:
                    return start_code(row["id"], "verify")
                session["code_purpose"] = "verify"
                return redirect(url_for("auth.confirm"))
            return redirect(url_for("main.home"))
    return render_template("auth/login.html")


@bp.route("/disponivel")
def available():
    me = current_user()
    me_id = me["id"] if me else None
    payload = {}
    username = request.args.get("username", "").strip()
    email = request.args.get("email", "").strip().lower()
    if accounts.USERNAME.match(username):
        row = accounts.user_by_username(username)
        payload["username"] = row is None or row["id"] == me_id
    if accounts.EMAIL.match(email):
        row = accounts.user_by_email(email)
        payload["email"] = row is None or row["id"] == me_id
    return jsonify(payload)


@bp.route("/cadastrar", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form = {
            "nome": request.form.get("nome", ""),
            "username": request.form.get("username", ""),
            "email": request.form.get("email", ""),
        }
        user_id, error = accounts.register(
            form["nome"],
            form["username"],
            form["email"],
            request.form.get("password", ""),
        )
        if error:
            session["register_form"] = form
            flash(error, "error")
            return redirect(url_for("auth.register"))
        login_user(user_id, remember=bool(request.form.get("lembrar")))
        return start_code(user_id, "verify")
    form = session.pop("register_form", None) or {"nome": "", "username": "", "email": ""}
    return render_template("auth/register.html", form=form)


@bp.route("/sair", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("main.home"))


@bp.route("/senha/esqueci", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        row = accounts.user_by_login(request.form.get("email", ""))
        if row is None:
            flash("Se esse e-mail existir, enviamos um código.", "info")
            return redirect(url_for("auth.login"))
        session["pending_user_id"] = row["id"]
        return start_code(row["id"], "reset")
    return render_template("auth/forgot.html")


@bp.route("/confirmar", methods=["GET", "POST"])
def confirm():
    user_id = _subject_id()
    purpose = _purpose()
    if not user_id:
        return redirect(url_for("auth.login"))
    active = accounts.latest_code(user_id, purpose)
    if request.method == "POST" and request.form.get("reenviar"):
        flash("Novo código gerado.", "info")
        return start_code(user_id, purpose, active["payload"] if active else None)
    if request.method == "POST":
        digits = "".join(request.form.get(f"d{i}", "") for i in range(4))
        row, error = accounts.consume_code(user_id, purpose, digits)
        if error:
            flash(error, "error")
            return redirect(url_for("auth.confirm"))
        elif purpose == "reset":
            session["reset_user_id"] = user_id
            return redirect(url_for("auth.reset"))
        else:
            accounts.mark_verified(user_id)
            login_user(user_id, remember=True)
            flash("E-mail confirmado.", "info")
            return redirect(url_for("main.home"))
    active = accounts.latest_code(user_id, purpose)
    return render_template(
        "auth/confirm.html",
        code=active["code"] if active and current_app.config["SHOW_CODES"] else "",
        purpose=purpose,
    )


@bp.route("/senha/nova", methods=["GET", "POST"])
def reset():
    user_id = session.get("reset_user_id")
    if not user_id:
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        if request.form.get("password") != request.form.get("confirm"):
            flash("As senhas não coincidem.", "error")
            return redirect(url_for("auth.reset"))
        else:
            error = accounts.set_password(user_id, request.form.get("password", ""))
            if error:
                flash(error, "error")
                return redirect(url_for("auth.reset"))
            else:
                session.pop("reset_user_id", None)
                login_user(user_id, remember=True)
                accounts.mark_verified(user_id)
                flash("Senha atualizada.", "info")
                return redirect(url_for("main.home"))
    return render_template("auth/reset.html")


@bp.route("/entrar/google")
def google():
    flash("O login com Google não está configurado neste servidor local.", "info")
    return redirect(url_for("auth.register"))
