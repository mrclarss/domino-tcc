"""Envio dos códigos por e-mail (SMTP opcional, configurado por variáveis de ambiente)."""

import smtplib
from email.message import EmailMessage

from flask import current_app


def enabled() -> bool:
    return bool(current_app.config.get("SMTP_HOST") and current_app.config.get("MAIL_FROM"))


def send_code(to: str, code: str, purpose: str) -> bool:
    if not enabled():
        return False
    cfg = current_app.config
    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = "Liga! · seu código" if purpose == "verify" else "Liga! · recuperar senha"
    msg.set_content(f"Seu código do Liga! é {code}. Ele vale por pouco tempo. Se não foi você, ignore.")
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as smtp:
            smtp.starttls()
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("falha ao enviar código")
        return False
