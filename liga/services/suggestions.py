from liga.db import get_db, transaction, utc_now


def add(user_id: int, text: str) -> str | None:
    body = " ".join((text or "").split())
    if len(body) < 8:
        return "Escreva pelo menos 8 caracteres."
    if len(body) > 400:
        return "A sugestão cabe em 400 caracteres."
    with transaction() as db:
        db.execute(
            "INSERT INTO suggestions (user_id, body, created_at) VALUES (?, ?, ?)",
            (user_id, body, utc_now()),
        )
    return None


def mine(user_id: int):
    return get_db().execute(
        """
        SELECT body, created_at FROM suggestions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (user_id,),
    ).fetchall()
