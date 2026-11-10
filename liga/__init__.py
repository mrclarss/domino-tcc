import os

from flask import Flask, flash, redirect, render_template, request, url_for
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix

from liga.blueprints import register
from liga.config import Config
from liga.db import init_db
from liga.security import csrf_ok, current_user, ensure_csrf, rate_limited, reject_csrf

AUTH_ENDPOINTS = {"auth.login", "auth.register", "auth.confirm", "auth.forgot", "auth.reset", "settings.email", "settings.password"}

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "script-src 'self'; connect-src 'self'; font-src 'self' data: https://fonts.gstatic.com; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)


def create_app() -> Flask:
    app = Flask(__name__, instance_path=os.path.dirname(Config.DATABASE))
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    init_db(app)
    register(app)

    @app.template_global()
    def csrf_input():
        return Markup(f'<input type="hidden" name="csrf" value="{ensure_csrf()}">')

    def art_url(name: str, fallback: str = "img/logo.png") -> str:
        """Arte nova do axolotl se o arquivo existir; senão a antiga (fácil de reverter)."""
        path = os.path.join(app.static_folder, "img", name)
        return url_for("static", filename=f"img/{name}" if os.path.exists(path) else fallback)

    @app.context_processor
    def inject():
        user = current_user()
        return {
            "art": art_url,
            "csrf_token": ensure_csrf(),
            "current_user": user,
            "theme": (user or {}).get("theme") or "light",
        }

    @app.before_request
    def protect():
        ensure_csrf()
        if request.method == "POST":
            if app.config["RATE_LIMIT"]:
                bucket = "auth" if request.endpoint in AUTH_ENDPOINTS else "post"
                if rate_limited(bucket):
                    return "Muitas tentativas. Espere um minuto.", 429
            if not csrf_ok():
                return reject_csrf()

    @app.after_request
    def headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", CSP)
        if app.config["PRODUCTION"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(404)
    def missing(_error):
        return render_template("main/error.html"), 404

    @app.errorhandler(413)
    def too_big(_error):
        flash("Arquivo grande demais.", "error")
        return redirect(request.referrer or url_for("main.home"))

    return app
