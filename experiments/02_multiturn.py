"""Experimento 02: conversación multiturno sin estado en la API (se reenvía el historial).

Uso: uv run python -m experiments.02_multiturn
"""

import anthropic

from app.config import Settings
from app.services.llm_service import Conversation, build_client
from experiments._common import Tracker, ensure_api_key, header

TURNS = [
    "Hola, me llamo Ana y estoy aprendiendo a usar la API de Claude.",
    "¿Qué parámetro es obligatorio en cada llamada a la Messages API?",
    "¿Recuerdas cómo me llamo? Responde solo con mi nombre.",
]


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)

    header(f"02 · Multiturno ({settings.model})")
    chat = Conversation(
        "Eres un asistente conciso. Responde en una o dos frases.",
        max_tokens=1024,
        client=client,
        settings=settings,
    )
    for number, message in enumerate(TURNS, start=1):
        print(f"\n> Usuario: {message}")
        sent = len(chat.history) + 1
        tracker.show(f"Turno {number} ({sent} mensajes enviados)", chat.send(message))

    print(f"\nHistorial final: {len(chat.history)} mensajes (alternancia user/assistant).")
    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
