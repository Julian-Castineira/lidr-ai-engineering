"""Experimento 06: stop_sequences detiene la generación al aparecer una secuencia.

Uso: uv run python -m experiments.06_stop_sequences
"""

import anthropic
from anthropic.types import MessageParam

from app.config import Settings
from app.services.llm_service import build_client, call_raw
from experiments._common import Tracker, ensure_api_key, header

PROMPT = "Escribe los números del 1 al 10 separados por comas, sin nada más."
STOP = "7"


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)
    messages: list[MessageParam] = [{"role": "user", "content": PROMPT}]

    header(f"06 · stop_sequences en {settings.model}")
    result = call_raw(messages, max_tokens=512, effort="low", client=client, settings=settings)
    tracker.show("Sin stop_sequences", result)
    result = call_raw(
        messages,
        max_tokens=512,
        effort="low",
        stop_sequences=[STOP],
        client=client,
        settings=settings,
    )
    tracker.show(f"stop_sequences=[{STOP!r}]", result)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
