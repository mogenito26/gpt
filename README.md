# Asesor IA SURA — Bot de ventas

## Estructura del proyecto

```
sura_bot/
├── app/
│   ├── config.py       # Variables de entorno (API key, BD, asesores)
│   ├── database.py     # Conexiones async a SQLite, init de tablas
│   ├── ai_engine.py    # Generación de respuesta + scoring con OpenAI async
│   ├── crm.py          # Historial, leads, round-robin persistente
│   └── main.py         # FastAPI: endpoints, CORS, rate limiting
├── index.html          # Frontend web chat (production-ready)
├── requirements.txt
├── .env                # ← NUNCA subir a git
├── .env.example        # Plantilla sin valores reales
└── .gitignore
```

## Setup rápido

```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env y poner tu OPENAI_API_KEY real

# 4. Correr el backend
uvicorn app.main:app --reload --port 8000

# 5. Abrir el frontend
# Abrir index.html en el navegador (doble clic o live server)
```

## Endpoints

| Método | Ruta      | Descripción                          |
|--------|-----------|--------------------------------------|
| POST   | `/chat`   | Enviar mensaje, recibir respuesta IA |
| GET    | `/leads`  | Listar leads capturados              |
| GET    | `/health` | Health check                         |

## Correcciones aplicadas vs versión original

| Problema original               | Corrección                                      |
|---------------------------------|-------------------------------------------------|
| API key hardcodeada             | `os.getenv()` + archivo `.env`                  |
| Endpoint síncrono bloqueante    | `async def` + `AsyncOpenAI`                     |
| SQLite global con thread-unsafe | `aiosqlite` con conexión por request            |
| Sin historial de conversación   | Tabla `conversations`, historial en cada prompt |
| Scoring por keywords frágil     | Scoring semántico con el propio LLM             |
| Round-robin no persistente      | Contador en BD (`asesor_counter`)               |
| Sin rate limiting               | `slowapi` (20 req/min por IP)                   |
| Sin CORS                        | `CORSMiddleware`                                |
| Frontend sin manejo de errores  | `try/catch`, feedback visual, typing indicator  |
| URL localhost hardcodeada       | Variable `API_URL` configurable                 |
