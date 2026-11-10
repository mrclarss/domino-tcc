# Deploy (liga.steify.com)

- Código em `/var/www/liga/app` (clone deste repo, branch `main`), venv em `/var/www/liga/venv`.
- Dados (SQLite, avatares) em `/var/www/liga/instance`, dono `liga`, fora do git.
- Segredos em `/var/www/liga/.env` (modo 600, nunca no git):
  `LIGA_ENV=production`, `SECRET_KEY=...`, `LIGA_INSTANCE=/var/www/liga/instance` e, se houver, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`.
- Serviço `deploy/liga.service` (systemd, usuário sem root `liga`, sandbox), gunicorn só em `127.0.0.1:8130`.
- Nginx `deploy/nginx.conf` com certificado Let's Encrypt (webroot `/var/www/letsencrypt`), atrás do Cloudflare.
- Um worker só: o limite de tentativas e as travas das partidas ficam em memória.

Atualizar: `git -C /var/www/liga/app pull && /var/www/liga/venv/bin/pip install -r requirements.txt && systemctl restart liga`.

Sem SMTP em produção a confirmação de e-mail é dispensada e a recuperação de senha fica desligada (o código nunca aparece na tela).
