"""Experimento 07: razonamiento extendido.

- claude-haiku-5-5: razonamiento adaptativo; la profundidad se controla con effort.
  display="summarized" hace visible un resumen (por defecto llega vacío).
- Modelo legacy: presupuesto fijo con budget_tokens (≥1024 y menor que max_tokens).
- Rechazos esperados: budget_tokens en el modelo por defecto y thinking con temperature≠1.

Uso: uv run python -m experiments.07_thinking
"""

import anthropic
from anthropic.types import MessageParam

from app.config import Settings
from app.services.llm_service import build_client, call_raw
from experiments._common import Tracker, ensure_api_key, header

PROMPT = (
    "Un tren sale a las 9:40 y tarda 2 h 35 min; hace una parada de 18 min a mitad de camino "
    "que no está incluida. ¿A qué hora llega? Responde con la hora y una frase de explicación."
)
MAX_TOKENS = 2048
BUDGET = {"type": "enabled", "budget_tokens": 1024}
ADAPTIVE_SUMMARIZED = {"type": "adaptive", "display": "summarized"}


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)
    messages: list[MessageParam] = [{"role": "user", "content": PROMPT}]
    legacy = settings.legacy_model

    header(f"07 · Razonamiento adaptativo en {settings.model}")
    for effort in ("low", "high"):
        result = call_raw(
            messages,
            effort=effort,
            thinking=ADAPTIVE_SUMMARIZED,
            max_tokens=MAX_TOKENS,
            client=client,
            settings=settings,
        )
        tracker.show(f"effort={effort}", result, show_thinking=True)

    header(f"07 · Presupuesto fijo en {legacy}")
    result = call_raw(
        messages,
        model=legacy,
        api_version=settings.legacy_api_version,
        thinking=BUDGET,
        max_tokens=MAX_TOKENS,
        client=client,
        settings=settings,
    )
    tracker.show("budget_tokens=1024", result, show_thinking=True)

    header("07 · Combinaciones no admitidas (se esperan 400)")
    result = call_raw(
        messages,
        model=legacy,
        api_version=settings.legacy_api_version,
        thinking=BUDGET,
        temperature=0.5,
        max_tokens=MAX_TOKENS,
        client=client,
        settings=settings,
    )
    tracker.show(f"thinking + temperature=0.5 en {legacy}", result, expected_error=True)
    result = call_raw(
        messages, thinking=BUDGET, max_tokens=MAX_TOKENS, client=client, settings=settings
    )
    tracker.show(f"budget_tokens en {settings.model}", result, expected_error=True)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
