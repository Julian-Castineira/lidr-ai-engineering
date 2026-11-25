"""Experimento 05: truncado por max_tokens.

En claude-haiku-5-5 el razonamiento también consume max_tokens: con un límite muy bajo la
respuesta puede cortarse antes de escribir texto.

Uso: uv run python -m experiments.05_max_tokens
"""

import anthropic

from app.config import Settings
from app.services.llm_service import build_client, call_raw
from experiments._common import Tracker, ensure_api_key, header

PROMPT = "Explica la historia de la inteligencia artificial desde 1950 hasta hoy."
LIMITS = (20, 150, 1024)


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)

    header(f"05 · max_tokens en {settings.model} (effort=low)")
    for limit in LIMITS:
        result = call_raw(
            [{"role": "user", "content": PROMPT}],
            max_tokens=limit,
            effort="low",
            client=client,
            settings=settings,
        )
        tracker.show(f"max_tokens={limit}", result)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
