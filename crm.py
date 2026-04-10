import aiosqlite
from app.config import ASESORES
from app.database import get_db


async def get_conversation_history(user: str, limit: int = 10) -> list[dict]:
    """Recupera los últimos N turnos de conversación de un usuario."""
    db: aiosqlite.Connection = await get_db()
    try:
        async with db.execute(
            """
            SELECT role, content FROM conversations
            WHERE user = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        # Invertir para orden cronológico
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
    finally:
        await db.close()


async def save_message(user: str, role: str, content: str) -> None:
    """Persiste un turno de conversación (role: 'user' o 'assistant')."""
    db: aiosqlite.Connection = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (user, role, content) VALUES (?, ?, ?)",
            (user, role, content),
        )
        await db.commit()
    finally:
        await db.close()


async def assign_asesor() -> str:
    """Round-robin persistente: el contador se guarda en la BD, no en memoria."""
    db: aiosqlite.Connection = await get_db()
    try:
        async with db.execute("SELECT counter FROM asesor_counter WHERE id = 1") as cursor:
            row = await cursor.fetchone()
        counter: int = row["counter"] if row else 0
        asesor: str = ASESORES[counter % len(ASESORES)]
        await db.execute(
            "UPDATE asesor_counter SET counter = counter + 1 WHERE id = 1"
        )
        await db.commit()
        return asesor
    finally:
        await db.close()


async def save_lead(user: str, message: str, score: str) -> dict:
    """Asigna asesor y guarda el lead en la BD. Retorna el lead completo."""
    asesor = await assign_asesor()
    db: aiosqlite.Connection = await get_db()
    try:
        async with db.execute(
            "INSERT INTO leads (user, message, asesor, score) VALUES (?, ?, ?, ?) RETURNING *",
            (user, message, asesor, score),
        ) as cursor:
            row = await cursor.fetchone()
        await db.commit()
        return dict(row) if row else {"user": user, "asesor": asesor, "score": score}
    finally:
        await db.close()


async def get_leads(limit: int = 50) -> list[dict]:
    """Lista los últimos leads para el panel de administración."""
    db: aiosqlite.Connection = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
