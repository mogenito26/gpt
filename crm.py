import aiosqlite
<<<<<<< HEAD
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
=======
from database import DB_PATH

async def save_lead(user_id: str, message: str, score: str):
    # Aquí asignamos a un asesor de Seguros Candia por defecto
    asesor_asignado = "Hermogenes Candia" 
    async with aiosqlite.connect(DB_PATH) as db:
>>>>>>> 7e7d061 (Guardar cambios antes de hacer pull)
        await db.execute(
            "INSERT INTO leads (user_id, last_message, score, asesor) VALUES (?, ?, ?, ?)",
            (user_id, message, score, asesor_asignado)
        )
        await db.commit()
    return {"status": "success", "asesor": asesor_asignado}

async def get_leads(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]