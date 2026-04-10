from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY
from app.crm import get_conversation_history

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Eres un asesor experto en seguros SURA Colombia.
Tu objetivo es ayudar al cliente a encontrar el seguro ideal para sus necesidades,
explicar coberturas, precios aproximados y guiarlo hacia una cotización formal.

Pautas:
- Sé amigable, claro y profesional.
- Si el cliente pregunta por precios, da rangos aproximados y menciona que un asesor
  humano contactará para una cotización exacta.
- Nunca inventes coberturas o precios exactos que no conozcas.
- Si el cliente no habla de seguros, redirige la conversación con amabilidad.
- Responde siempre en español."""

SCORE_PROMPT = """Analiza el siguiente mensaje de un cliente en una aseguradora.
Clasifícalo como "caliente" si expresa intención de compra, pide precio, cotización,
quiere contratar o muestra urgencia. Clasifícalo como "frio" en cualquier otro caso.

Responde ÚNICAMENTE con una de estas dos palabras: caliente  o  frio

Mensaje del cliente: {message}"""


async def generate_response(user: str, message: str) -> str:
    """
    Genera respuesta del LLM incluyendo el historial de conversación del usuario.
    """
    history = await get_conversation_history(user, limit=10)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


async def score_lead(message: str) -> str:
    """
    Usa el propio LLM para clasificar la intención del lead.
    Más robusto que keywords: detecta variaciones semánticas.
    """
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": SCORE_PROMPT.format(message=message)}
        ],
        temperature=0,
        max_tokens=5,
    )
    result = response.choices[0].message.content.strip().lower()
    return "caliente" if "caliente" in result else "frio"
