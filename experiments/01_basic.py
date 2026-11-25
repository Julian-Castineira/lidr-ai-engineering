"""Experimento 01: llamada básica con system prompt y métricas.

Uso: uv run python -m experiments.01_basic
"""

import anthropic

from app.config import Settings
from app.services.llm_service import build_client, query_claude
from experiments._common import Tracker, ensure_api_key, header


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)

    header(f"01 · Llamada básica ({settings.model})")
    result = query_claude(
        "Explica en dos frases qué es un LLM.",
        system_prompt="Eres un profesor de IA. Responde en español, de forma clara y breve.",
        max_tokens=1024,
        client=client,
        settings=settings,
    )
    tracker.show("Pregunta con system prompt", result)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
