"""Experimento 04: top_p y top_k.

Se ejecutan en el modelo legacy (LLM_LEGACY_MODEL). También se muestran dos rechazos:
temperature y top_p a la vez (excluyentes desde Claude 4.5) y top_k en claude-haiku-5-5.

Uso: uv run python -m experiments.04_sampling
"""

import anthropic
from anthropic.types import MessageParam

from app.config import Settings
from app.services.llm_service import build_client, call_raw
from experiments._common import Tracker, ensure_api_key, header

PROMPT = "Completa la frase con una sola palabra: «El mejor lenguaje para empezar a programar es»"
MAX_TOKENS = 30


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)
    messages: list[MessageParam] = [{"role": "user", "content": PROMPT}]
    legacy = settings.legacy_model

    header(f"04 · top_p y top_k en {legacy}")
    for top_p in (0.1, 0.95):
        result = call_raw(
            messages,
            model=legacy,
            api_version=settings.legacy_api_version,
            top_p=top_p,
            max_tokens=MAX_TOKENS,
            client=client,
            settings=settings,
        )
        tracker.show(f"top_p={top_p}", result)
    for top_k in (1, 50):
        result = call_raw(
            messages,
            model=legacy,
            api_version=settings.legacy_api_version,
            top_k=top_k,
            max_tokens=MAX_TOKENS,
            client=client,
            settings=settings,
        )
        tracker.show(f"top_k={top_k}", result)

    header("04 · Combinaciones no admitidas (se esperan 400)")
    result = call_raw(
        messages,
        model=legacy,
        api_version=settings.legacy_api_version,
        temperature=0.5,
        top_p=0.9,
        max_tokens=MAX_TOKENS,
        client=client,
        settings=settings,
    )
    tracker.show(f"temperature + top_p en {legacy}", result, expected_error=True)
    result = call_raw(messages, top_k=5, max_tokens=MAX_TOKENS, client=client, settings=settings)
    tracker.show(f"top_k en {settings.model}", result, expected_error=True)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
