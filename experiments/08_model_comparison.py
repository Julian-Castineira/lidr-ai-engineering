"""Experimento 08: mismo prompt en el modelo por defecto y en el legacy.

Compara bloques de respuesta, tokens (el tokenizador de claude-haiku-5-5 cuenta ~30 % más),
latencia y coste, y muestra qué ocurre al enviar temperature a cada modelo.

Uso: uv run python -m experiments.08_model_comparison
"""

import anthropic

from app.config import Settings
from app.services.llm_service import build_client, query_claude
from app.services.schemas import QueryError
from experiments._common import Tracker, ensure_api_key, header

PROMPT = "Resume en tres viñetas las ventajas de usar una API stateless para un chatbot."
TEMPERATURE = 0.5
MAX_TOKENS = 1024


def main(client: anthropic.Anthropic | None = None, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not ensure_api_key(settings):
        return 1
    client = client or build_client(settings)
    tracker = Tracker(settings)
    models = (settings.model, settings.legacy_model)
    # Cada modelo con su versión de API: la vigente para el por defecto y la legacy para el otro.
    api_versions = {settings.model: None, settings.legacy_model: settings.legacy_api_version}

    header("08 · Mismo prompt en ambas generaciones")
    for model in models:
        result = query_claude(
            PROMPT,
            model=model,
            api_version=api_versions[model],
            max_tokens=MAX_TOKENS,
            client=client,
            settings=settings,
        )
        tracker.show(model, result)

    header(f"08 · Mismo prompt con temperature={TEMPERATURE}")
    for model in models:
        result = query_claude(
            PROMPT,
            model=model,
            api_version=api_versions[model],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            client=client,
            settings=settings,
        )
        rejected = isinstance(result, QueryError) and result.error_type == "bad_request"
        tracker.show(f"{model} con temperature", result, expected_error=rejected)
        if rejected:
            retry = query_claude(
                PROMPT,
                model=model,
                api_version=api_versions[model],
                max_tokens=MAX_TOKENS,
                client=client,
                settings=settings,
            )
            tracker.show(f"{model} repetido sin temperature", retry)

    tracker.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
