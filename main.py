from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import asyncio
import os

from ai_engine import generate_response, score_lead, notify_n8n
from database import init_db, save_message, save_lead, get_leads

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando aplicación...")
    await init_db()
    yield
    print("👋 Cerrando aplicación...")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Asesor IA Seguros Candia",
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

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
else:
    @app.get("/")
    async def root():
        return {"mensaje": "API Asesor IA Seguros Candia funcionando"}

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
        await notify_n8n(req.user, req.message, lead_score, ai_response)

    return ChatResponse(
        response=ai_response,
        score=lead_score,
        asesor=lead_data["asesor"] if lead_data else None,
        lead_guardado=lead_data is not None,
    )

@app.get("/leads")
@limiter.limit("10/minute")
async def list_leads(request: Request, limit: int = 50) -> list[dict]:
    return await get_leads(limit=limit)

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
    
