import httpx
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from database import get_conversation_history

# Configuración de logs
logger = logging.getLogger(__name__)

# Carga de variables de entorno
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("OPENAI_API_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")  # 🔴 FIX: movida al .env

# Validación de variables de entorno críticas
if not api_key or len(api_key) < 20:  # 🔴 FIX: validación compatible con todos los formatos de key
    raise ValueError("❌ OPENAI_API_KEY no configurada correctamente en el .env")

if not N8N_WEBHOOK_URL:
    raise ValueError("❌ N8N_WEBHOOK_URL no configurada en el .env")

client = AsyncOpenAI(api_key=api_key)

# 🟡 FIX: System Prompt cargado desde archivo externo si existe,
# con fallback al prompt embebido para no romper arranques sin el archivo.
_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"

if _PROMPT_PATH.exists():
    SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8").strip()
    logger.info("✅ System Prompt cargado desde system_prompt.txt")
else:
    logger.warning("⚠️  system_prompt.txt no encontrado, usando prompt embebido.")
    SYSTEM_PROMPT = """Eres el asesor experto de Seguros Candia, aliado de SURA Colombia (Código de Asesor: 9736). 
Tu misión es asesorar y facilitar la cotización inmediata.

REGLAS PARA COTIZACIÓN EN LÍNEA:
1. SI EL CLIENTE BUSCA SEGURO DE CARRO/MOVILIDAD: Invítalo a cotizar en segundos usando este link:
   https://www.suraenlinea.com/movilidad/sura/seguro-de-carro?asesor=9736

2. SI EL CLIENTE BUSCA SEGURO DE VIAJES: Dile que SURA ofrece la mejor cobertura internacional y entrégale este link:
   https://www.suraenlinea.com/viajes/sura?codigoAsesor=9736

3. SI EL CLIENTE BUSCA ARRENDAMIENTO DIGITAL: Explícale que puede calcular su póliza aquí:
   https://www.suraenlinea.com/arrendamiento-digital/sura/cotizacion/calculadora?asesor=9736

PARA OTROS PRODUCTOS (Vida, Salud, Hogar, Moto, Empresas):
- Solicita los datos básicos (Nombre, Ciudad, Teléfono, Numero de documento).
- Dile que (Liliana/Laura) le enviarán una propuesta personalizada.
Luego envia un mensaje al whatsapp 3158939181 y/o 3126722989

ESTILO DE RESPUESTA:
- Sé amable, profesional y eficiente.
- Usa el nombre de la agencia "Seguros Candia" para generar confianza.
- Cuando entregues un link, di algo como: "Para tu comodidad, puedes obtener un precio exacto ahora mismo en este enlace oficial de SURA:"."""

# Límite de caracteres por mensaje de usuario
MAX_MESSAGE_LENGTH = 2000


async def generate_response(user: str, message: str) -> str:
    # 🟢 FIX: validación de longitud del mensaje
    if len(message) > MAX_MESSAGE_LENGTH:
        logger.warning(f"Mensaje de {user} excede el límite ({len(message)} chars)")
        return "Tu mensaje es demasiado largo. Por favor resúmelo en menos palabras."

    try:  # 🟡 FIX: manejo de errores para no tumbar la request
        history = await get_conversation_history(user, limit=6)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4  # 🟢 FIX: bajado de 0.7 para respuestas más consistentes
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"❌ Error generando respuesta para {user}: {e}")
        return "En este momento no puedo responder. Por favor intenta de nuevo en unos segundos."


async def score_lead(message: str) -> str:
    # 🟡 FIX: prompt más estricto para evitar clasificaciones ambiguas
    prompt_instrucciones = (
        "Responde ÚNICAMENTE con una sola palabra en español, sin puntuación ni explicación: "
        "'caliente' si el usuario muestra interés real en comprar o cotizar un seguro, "
        "o 'frio' si solo está explorando, saludando o preguntando algo genérico. "
        f"Mensaje del usuario: {message}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_instrucciones}],
            temperature=0
        )
        result = response.choices[0].message.content.strip().lower()
        score = "caliente" if "caliente" in result else "frio"
        logger.info(f"Lead clasificado como: {score}")
        return score

    except Exception as e:
        logger.error(f"❌ Error clasificando lead: {e}")
        return "frio"  # En caso de error, no notificar n8n


async def notify_n8n(user: str, message: str, score: str, ai_res: str):
    """Envía el lead a n8n solo si es caliente."""
    if score != "caliente":
        return

    payload = {
        "agencia": "Seguros Candia",
        "cliente": user,
        "consulta": message,
        "respuesta_ia": ai_res
    }

    async with httpx.AsyncClient() as httpx_client:
        try:
            await httpx_client.post(N8N_WEBHOOK_URL, json=payload, timeout=10.0)
            logger.info(f"✅ Notificación enviada a n8n para {user}")
        except Exception as e:
            # 🟢 FIX: se loggea el payload para poder recuperar el lead manualmente
            logger.error(f"❌ Error avisando a n8n para {user}: {e}. Payload perdido: {payload}")
