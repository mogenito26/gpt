from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.ai_engine import generate_response, score_lead
from app.crm import get_leads, save_lead, save_message
from app.database import init_db


# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])


# ── Lifespan: inicializa la BD al arrancar ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


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
    allow_origins=["*"],   # En producción: reemplazar con tu dominio
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


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
    """
    Endpoint principal del chat.
    - Genera respuesta del LLM con historial.
    - Clasifica intención del lead con el LLM.
    - Guarda conversación y lead (si es caliente).
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    # Generar respuesta y score en paralelo
    import asyncio
    ai_response, lead_score = await asyncio.gather(
        generate_response(req.user, req.message),
        score_lead(req.message),
    )

    # Persistir ambos turnos de conversación
    await save_message(req.user, "user", req.message)
    await save_message(req.user, "assistant", ai_response)

    # Guardar lead si muestra intención de compra
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
    """Panel admin: lista los últimos leads capturados."""
    return await get_leads(limit=limit)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
