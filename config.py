import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "leads.db")
ASESORES: list[str] = os.getenv("ASESORES", "Liliana Candia,Laura Alzate").split(",")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY no está configurada en el archivo .env")
