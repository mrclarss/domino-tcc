import re
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from liga.art import PALETTE
from liga.db import get_db, transaction, utc_now

USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BANNERS = {"teal": "#01a29a", "roxo": "#8e5cff", "mar": "#3d7ea6", "noite": "#243056"}
LEVELS = [
    (1, 0, "Toda ligação começa por uma ponta."),
    (2, 5, "Parabéns, você está aprendendo mais sobre química orgânica."),
    (3, 10, "As funções oxigenadas já se encaixam na sua memória."),
    (4, 20, "Você reconhece álcool, fenol, éter e éster de primeira."),
    (5, 35, "Cetona, aldeído e ácido já não te escapam."),
    (6, 55, "Quase um mestre das ligações."),
    (7, 80, "Você ligou a química orgânica de ponta a ponta."),
]


def public_user(row):
    if row is None:
        return None
    data = dict(row)
    data.pop("password_hash", None)
    return data


def user_by_id(user_id):
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def user_by_login(login: str):
    key = login.strip()
    return get_db().execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
        (key, key.lower()),
    ).fetchone()


def user_by_username(username: str):
    return get_db().execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
        (username.strip(),),
    ).fetchone()


def user_by_email(email: str):
    return get_db().execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
        (email.strip().lower(),),
    ).fetchone()


def register(display_name, username, email, password):
    name = (display_name or "").strip()
    user = (username or "").strip()
    mail = (email or "").strip().lower()
    if not name or len(name) > 40:
        return None, "Diga como quer ser chamado."
    if not USERNAME.match(user):
        return None, "Usuário: 3 a 20 letras, números ou _."
    if not EMAIL.match(mail):
        return None, "E-mail inválido."
    if not password or len(password) < 6:
        return None, "A senha precisa ter pelo menos 6 caracteres."
    try:
        with transaction() as db:
            cursor = db.execute(
                """
                INSERT INTO users (username, email, password_hash, display_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user, mail, generate_password_hash(password), name, utc_now()),
            )
            return cursor.lastrowid, None
    except Exception:
        return None, "Usuário ou e-mail já cadastrado."


def authenticate(login, password):
    row = user_by_login(login)
    if row is None or not check_password_hash(row["password_hash"], password or ""):
        return None
    return row


def check_password(user_id, password) -> bool:
    row = user_by_id(user_id)
    return bool(row) and check_password_hash(row["password_hash"], password or "")


def set_password(user_id, password) -> str | None:
    if not password or len(password) < 6:
        return "A senha precisa ter pelo menos 6 caracteres."
    with transaction() as db:
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
    return None


def update_profile(user_id, display_name, username, bio, avatar, banner):
    name = (display_name or "").strip()
    user = (username or "").strip()
    text = (bio or "").strip()
    if not name or len(name) > 40:
        return "Diga como quer ser chamado."
    if not USERNAME.match(user):
        return "Usuário: 3 a 20 letras, números ou _."
    if len(text) > 140:
        return "A bio cabe em 140 caracteres."
    if avatar not in PALETTE and avatar != "custom":
        avatar = "rosa"
    if banner not in BANNERS:
        banner = "teal"
    try:
        with transaction() as db:
            db.execute(
                """
                UPDATE users
                SET display_name = ?, username = ?, bio = ?, avatar = ?, banner = ?
                WHERE id = ?
                """,
                (name, user, text, avatar, banner, user_id),
            )
        return None
    except Exception:
        return "Esse usuário já está em uso."


def set_custom_avatar(user_id, ext: str) -> None:
    with transaction() as db:
        db.execute(
            "UPDATE users SET avatar = 'custom', avatar_ext = ? WHERE id = ?",
            (ext, user_id),
        )


def update_settings(user_id, theme, sound_on, notify_on) -> None:
    if theme not in ("light", "dark"):
        theme = "light"
    with transaction() as db:
        db.execute(
            "UPDATE users SET theme = ?, sound_on = ?, notify_on = ? WHERE id = ?",
            (theme, 1 if sound_on else 0, 1 if notify_on else 0, user_id),
        )


def change_email(user_id, email) -> str | None:
    mail = (email or "").strip().lower()
    if not EMAIL.match(mail):
        return "E-mail inválido."
    try:
        with transaction() as db:
            db.execute(
                "UPDATE users SET email = ?, email_verified = 0 WHERE id = ?",
                (mail, user_id),
            )
        return None
    except Exception:
        return "Esse e-mail já está em uso."


def mark_verified(user_id) -> None:
    with transaction() as db:
        db.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))


def issue_code(user_id, purpose, payload=None) -> str:
    code = f"{secrets_code()}"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).replace(microsecond=0).isoformat()
    with transaction() as db:
        db.execute(
            "UPDATE email_codes SET used = 1 WHERE user_id = ? AND purpose = ? AND used = 0",
            (user_id, purpose),
        )
        db.execute(
            """
            INSERT INTO email_codes (user_id, purpose, code, payload, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, purpose, code, payload, expires),
        )
    return code


def secrets_code() -> str:
    from secrets import randbelow

    return f"{randbelow(10000):04d}"


def latest_code(user_id, purpose):
    return get_db().execute(
        """
        SELECT * FROM email_codes
        WHERE user_id = ? AND purpose = ? AND used = 0
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, purpose),
    ).fetchone()


def consume_code(user_id, purpose, code):
    row = latest_code(user_id, purpose)
    if row is None:
        return None, "Código incorreto."
    if row["code"] != (code or "").strip():
        with transaction() as db:
            db.execute(
                "UPDATE email_codes SET tries = tries + 1, used = CASE WHEN tries + 1 >= 5 THEN 1 ELSE used END WHERE id = ?",
                (row["id"],),
            )
        return None, "Código incorreto."
    if row["expires_at"] < utc_now():
        return None, "Código expirado. Peça outro."
    with transaction() as db:
        db.execute("UPDATE email_codes SET used = 1 WHERE id = ?", (row["id"],))
    return row, None


def level_for(wins: int) -> dict:
    current = LEVELS[0]
    index = 0
    for i, item in enumerate(LEVELS):
        if wins >= item[1]:
            current = item
            index = i
    if index + 1 < len(LEVELS):
        nxt = LEVELS[index + 1]
        span = max(1, nxt[1] - current[1])
        missing = nxt[1] - wins
        percent = max(0, min(100, round((wins - current[1]) * 100 / span)))
        next_level = nxt[0]
        next_need = nxt[1]
    else:
        missing = 0
        percent = 100
        next_level = None
        next_need = current[1]
    return {
        "level": current[0],
        "quote": current[2],
        "missing": missing,
        "percent": percent,
        "next_level": next_level,
        "floor": current[1],
        "next_need": next_need,
    }


def ranking(limit=20):
    return get_db().execute(
        """
        SELECT id, username, display_name, avatar, avatar_ext, wins, points
        FROM users
        ORDER BY points DESC, wins DESC, username COLLATE NOCASE
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def position_of(user_id) -> int:
    row = user_by_id(user_id)
    if row is None:
        return 0
    ahead = get_db().execute(
        """
        SELECT COUNT(*) AS n FROM users
        WHERE points > ? OR (points = ? AND wins > ?)
        """,
        (row["points"], row["points"], row["wins"]),
    ).fetchone()
    return ahead["n"] + 1


def friend_ids(user_id) -> list[int]:
    rows = get_db().execute(
        """
        SELECT requester_id, addressee_id FROM friendships
        WHERE status = 'accepted' AND (requester_id = ? OR addressee_id = ?)
        """,
        (user_id, user_id),
    ).fetchall()
    ids = []
    for row in rows:
        ids.append(row["addressee_id"] if row["requester_id"] == user_id else row["requester_id"])
    return ids


def friends_ranking(user_id):
    ids = friend_ids(user_id)
    ids.append(user_id)
    marks = ",".join("?" for _ in ids)
    return get_db().execute(
        f"""
        SELECT id, username, display_name, avatar, avatar_ext, wins, points
        FROM users WHERE id IN ({marks})
        ORDER BY points DESC, wins DESC
        """,
        ids,
    ).fetchall()


def pending_requests(user_id):
    return get_db().execute(
        """
        SELECT f.id, u.username, u.display_name
        FROM friendships f
        JOIN users u ON u.id = f.requester_id
        WHERE f.addressee_id = ? AND f.status = 'pending'
        ORDER BY f.id DESC
        """,
        (user_id,),
    ).fetchall()


def request_friend(user_id, username) -> str | None:
    other = user_by_username(username)
    if other is None:
        return "Não encontrei esse usuário."
    if other["id"] == user_id:
        return "Você já está do seu lado da mesa."
    pair = get_db().execute(
        """
        SELECT * FROM friendships
        WHERE (requester_id = ? AND addressee_id = ?)
           OR (requester_id = ? AND addressee_id = ?)
        """,
        (user_id, other["id"], other["id"], user_id),
    ).fetchone()
    if pair and pair["status"] == "accepted":
        return "Vocês já são amigos."
    if pair and pair["status"] == "pending":
        return "O pedido já está esperando."
    with transaction() as db:
        db.execute(
            """
            INSERT INTO friendships (requester_id, addressee_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (user_id, other["id"], utc_now()),
        )
    return None


def respond_friend(user_id, request_id, accept: bool) -> str | None:
    row = get_db().execute(
        "SELECT * FROM friendships WHERE id = ? AND addressee_id = ? AND status = 'pending'",
        (request_id, user_id),
    ).fetchone()
    if row is None:
        return "Pedido não encontrado."
    with transaction() as db:
        if accept:
            db.execute("UPDATE friendships SET status = 'accepted' WHERE id = ?", (request_id,))
        else:
            db.execute("DELETE FROM friendships WHERE id = ?", (request_id,))
    return None


def recent_matches(user_id, limit=5):
    return get_db().execute(
        """
        SELECT * FROM matches
        WHERE status = 'finished' AND (player1_id = ? OR player2_id = ?)
        ORDER BY finished_at DESC
        LIMIT ?
        """,
        (user_id, user_id, limit),
    ).fetchall()
