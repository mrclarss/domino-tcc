import os
import secrets
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE = os.environ.get("LIGA_INSTANCE") or os.path.join(ROOT, "instance")
PRODUCTION = os.environ.get("LIGA_ENV", "development") == "production"


def _secret() -> str:
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key
    if PRODUCTION:
        raise RuntimeError("SECRET_KEY é obrigatória em produção.")
    os.makedirs(INSTANCE, exist_ok=True)
    path = os.path.join(INSTANCE, "secret_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            saved = handle.read().strip()
            if saved:
                return saved
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(key)
    os.chmod(path, 0o600)
    return key


class Config:
    SECRET_KEY = _secret()
    PRODUCTION = PRODUCTION
    JSON_AS_ASCII = False
    SESSION_COOKIE_NAME = "liga_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PRODUCTION
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    DATABASE = os.path.join(INSTANCE, "liga.sqlite")
    AVATARS = os.path.join(INSTANCE, "avatars")
    # Só em desenvolvimento o código de confirmação aparece na tela.
    SHOW_CODES = not PRODUCTION and os.environ.get("LIGA_SHOW_CODES", "1") == "1"
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    RATE_LIMIT = os.environ.get("LIGA_RATE_LIMIT", "1") == "1"
