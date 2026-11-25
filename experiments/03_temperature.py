"""Experimento 03: efecto de temperature (0 frente a 1).

claude-haiku-5-5 rechaza cualquier temperatura distinta de 1, así que el efecto se observa
en el modelo legacy (LLM_LEGACY_MODEL) y después se muestra el rechazo del modelo por defecto.

Uso: uv run python -m experiments.03_temperature
"""

import anthropic

from app.config import Settings
from app.services.llm_service import build_client, query_claude
from experiments._common import Tracker, ensure_api_key, header

PROMPT = "Inventa un nombre original para una cafetería. Responde solo con el nombre."
TEMPERATURES = (0.0, 1.0)
REPETITIONS = 3


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)

    for temperature in TEMPERATURES:
        header(f"03 · temperature={temperature} en {settings.legacy_model} ({REPETITIONS} veces)")
        for attempt in range(1, REPETITIONS + 1):
            result = query_claude(
                PROMPT,
                model=settings.legacy_model,
                api_version=settings.legacy_api_version,
                temperature=temperature,
                max_tokens=50,
                client=client,
                settings=settings,
            )
            tracker.show(f"temperature={temperature} · intento {attempt}", result)

    header(f"03 · temperature=0 en {settings.model} (se espera un 400)")
    result = query_claude(PROMPT, temperature=0.0, max_tokens=50, client=client, settings=settings)
    tracker.show("temperature=0 en el modelo por defecto", result, expected_error=True)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
