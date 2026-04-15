import aiosqlite
<<<<<<< HEAD

DB_PATH = "seguros_candia.db"  # 👈 Te faltaba definir esta constante

async def get_db() -> aiosqlite.Connection:
    """Abre una conexión independiente por request (evita conflictos de threading)."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def init_db() -> None:
    """Crea las tablas si no existen. Se llama una sola vez al iniciar la app."""
    conn = await aiosqlite.connect(DB_PATH)  # 👈 Usa la constante DB_PATH
    
    # Tabla de leads
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user       TEXT    NOT NULL,
            message    TEXT    NOT NULL,
            asesor     TEXT    NOT NULL,
            score      TEXT    NOT NULL DEFAULT 'frio',
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Tabla de conversations
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user       TEXT NOT NULL,
            role       TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Tabla de asesor_counter
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS asesor_counter (
            id      INTEGER PRIMARY KEY CHECK(id = 1),
            counter INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # Insertar contador inicial si no existe
    await conn.execute("""
        INSERT OR IGNORE INTO asesor_counter (id, counter) VALUES (1, 0)
    """)
    
    await conn.commit()
    await conn.close()
    print("✅ Base de datos inicializada correctamente")
=======
import os

DB_PATH = "seguros_candia.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Tabla para mensajes (memoria de la IA)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                role TEXT,
                content TEXT
            )
        """)
        # Tabla para prospectos (Leads)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                last_message TEXT,
                score TEXT,
                asesor TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def save_message(user_id: str, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", 
                         (user_id, role, content))
        await db.commit()

async def get_conversation_history(user_id: str, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?", 
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            # Invertimos para que el orden sea cronológico para la IA
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
>>>>>>> 7e7d061 (Guardar cambios antes de hacer pull)
