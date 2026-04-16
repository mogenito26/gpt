import aiosqlite

DB_PATH = "seguros_candia.db"

async def init_db() -> None:
    """Crea las tablas si no existen (con limpieza de estructura antigua)"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Verificar columnas existentes y recrear tabla si es necesario
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leads'")
        table_exists = await cursor.fetchone()
        
        if table_exists:
            # Verificar qué columnas tiene la tabla actual
            cursor = await db.execute("PRAGMA table_info(leads)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'user' not in column_names:
                print("⚠️ Tabla 'leads' antigua detectada. Recreando...")
                # Guardar datos existentes si los hay
                await db.execute("ALTER TABLE leads RENAME TO leads_old")
                
                # Crear tabla nueva con estructura correcta
                await db.execute("""
                    CREATE TABLE leads (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        user       TEXT    NOT NULL,
                        message    TEXT    NOT NULL,
                        asesor     TEXT    NOT NULL,
                        score      TEXT    NOT NULL DEFAULT 'frio',
                        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                
                # Migrar datos antiguos (si los hay)
                try:
                    await db.execute("""
                        INSERT INTO leads (id, message, asesor, score, created_at)
                        SELECT id, message, asesor, score, created_at FROM leads_old
                    """)
                    print("✅ Datos migrados correctamente")
                except Exception as e:
                    print(f"⚠️ No se pudieron migrar datos antiguos: {e}")
                
                await db.execute("DROP TABLE leads_old")
                print("✅ Tabla 'leads' recreada correctamente")
        
        # Crear tabla leads si no existe
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user       TEXT    NOT NULL,
                message    TEXT    NOT NULL,
                asesor     TEXT    NOT NULL,
                score      TEXT    NOT NULL DEFAULT 'frio',
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        
        # Crear tabla conversations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user       TEXT NOT NULL,
                role       TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        
        # Crear tabla asesor_counter
        await db.execute("""
            CREATE TABLE IF NOT EXISTS asesor_counter (
                id      INTEGER PRIMARY KEY CHECK(id = 1),
                counter INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # Insertar contador inicial
        await db.execute("""
            INSERT OR IGNORE INTO asesor_counter (id, counter) VALUES (1, 0)
        """)
        
        await db.commit()
    
    print("✅ Base de datos inicializada correctamente")

async def save_message(user: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (user, role, content) VALUES (?, ?, ?)",
            (user, role, content)
        )
        await db.commit()

async def get_next_asesor() -> str:
    """Asigna el siguiente asesor en orden circular"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT counter FROM asesor_counter WHERE id = 1")
        row = await cursor.fetchone()
        counter = row[0] if row else 0
        asesores = ["Carlos", "Maria", "Jorge", "Laura"]
        asesor = asesores[counter % len(asesores)]
        await db.execute("UPDATE asesor_counter SET counter = counter + 1 WHERE id = 1")
        await db.commit()
        return asesor

async def save_lead(user: str, message: str, score: str) -> dict:
    """Guarda un lead caliente y asigna un asesor"""
    asesor = await get_next_asesor()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO leads (user, message, asesor, score) VALUES (?, ?, ?, ?)",
            (user, message, asesor, score)
        )
        await db.commit()
    return {"asesor": asesor, "user": user, "score": score}

async def get_leads(limit: int = 50) -> list[dict]:
    """Obtiene la lista de leads capturados"""
    async with aiosqlite.connect(DB_PATH) as db:
        async def get_conversation_history(user: str, limit: int = 10) -> list[dict]:
    """Obtiene el historial de conversación de un usuario"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT role, content FROM conversations 
               WHERE user = ? 
               ORDER BY created_at ASC 
               LIMIT ?""",
            (user, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, user, message, asesor, score, created_at FROM leads ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
