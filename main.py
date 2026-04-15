from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import aiosqlite
import asyncio
import os
from ai_engine import generate_response, score_lead, notify_n8n
from database import init_db, save_message  # <-- Revisa que diga 'init_db'
from crm import save_lead
# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

DB_PATH = "seguros_candia.db"

# ── Funciones de base de datos ────────────────────────────────────────────────
async def get_db():
    """Abre conexión a la BD"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def init_db() -> None:
    """Crea las tablas si no existen"""
    async with aiosqlite.connect(DB_PATH) as db:
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user       TEXT NOT NULL,
                role       TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS asesor_counter (
                id      INTEGER PRIMARY KEY CHECK(id = 1),
                counter INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            INSERT OR IGNORE INTO asesor_counter (id, counter) VALUES (1, 0)
        """)
        await db.commit()
    print("✅ Base de datos inicializada")

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
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, user, message, asesor, score, created_at FROM leads ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ── Funciones de IA ───────────────────────────────────────────────────────────
async def generate_response(user: str, message: str) -> str:
    """Genera respuesta usando el LLM"""
    message_lower = message.lower()
    
    if "seguro" in message_lower or "cotizar" in message_lower:
        return "¡Claro! En Seguros Sura te ofrecemos: Vida, Salud, Vehículo y Hogar. ¿Cuál te interesa cotizar?"
    elif "vida" in message_lower:
        return "El Seguro de Vida Sura protege a tu familia. Incluye cobertura por fallecimiento, incapacidad y enfermedades graves. ¿Te gustaría una cotización personalizada?"
    elif "salud" in message_lower:
        return "El Seguro de Salud Sura te da acceso a nuestra red de especialistas. ¿Para cuántas personas necesitas la cobertura?"
    elif "vehículo" in message_lower or "auto" in message_lower:
        return "El Seguro de Vehículo Sura cubre daños, robo y responsabilidad civil. ¿Podrías indicarme el modelo y año de tu auto?"
    elif "hogar" in message_lower or "casa" in message_lower:
        return "El Seguro de Hogar Sura protege tu vivienda y pertenencias. ¿En qué ciudad está ubicada tu propiedad?"
    elif "gracias" in message_lower:
        return "¡A ti por contactarnos! Quedo atento a cualquier otra duda."
    else:
        return "En Seguros Sura ofrecemos soluciones para proteger lo que más importa: Vida, Salud, Vehículo y Hogar. ¿Sobre cuál te gustaría más información?"

async def score_lead(message: str) -> str:
    """Clasifica la intención del lead: 'caliente' o 'frio'"""
    message_lower = message.lower()
    palabras_calientes = ["cotizar", "precio", "valor", "quiero", "me interesa", "información", "aplicar", "adquirir"]
    
    if any(palabra in message_lower for palabra in palabras_calientes):
        return "caliente"
    return "frio"

# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando aplicación...")
    await init_db()
    yield
    print("👋 Cerrando aplicación...")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Asesor IA SURA",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Servir archivos estáticos (frontend)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
else:
    @app.get("/")
    async def root():
        return {"mensaje": "API de Asesor IA SURA funcionando", "endpoints": {"health": "/health", "chat": "/chat (POST)", "leads": "/leads"}}

# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    user: str = Field(..., min_length=1, max_length=100)

class ChatResponse(BaseModel):
    response: str
    score: str
    asesor: str | None = None
    lead_guardado: bool = False

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    """Endpoint principal del chat"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    
    ai_response, lead_score = await asyncio.gather(
        generate_response(req.user, req.message),
        score_lead(req.message),
    )
    
    await save_message(req.user, "user", req.message)
    await save_message(req.user, "assistant", ai_response)
    
    lead_data = None
    if lead_score == "caliente":
        lead_data = await save_lead(req.user, req.message, lead_score)
    
    return ChatResponse(
        response=ai_response,
        score=lead_score,
        asesor=lead_data["asesor"] if lead_data else None,
        lead_guardado=lead_data is not None,
    )

@app.get("/leads")
@limiter.limit("10/minute")
async def list_leads(request: Request, limit: int = 50) -> list[dict]:
    """Panel admin: lista los últimos leads capturados"""
    return await get_leads(limit=limit)

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
    