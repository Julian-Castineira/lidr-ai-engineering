"""Prueba contra la API real de Anthropic (con coste). Solo se ejecuta con `pytest -m live`."""

import pytest

from app.config import Settings
from app.services.llm_service import call_raw
from app.services.schemas import QueryResult

pytestmark = pytest.mark.live


def test_real_call_returns_text_and_metrics() -> None:
    settings = Settings()
    if settings.anthropic_api_key is None:
        pytest.skip("ANTHROPIC_API_KEY no configurada")

    result = call_raw(
        [{"role": "user", "content": "Responde solo con la palabra: hola"}],
        max_tokens=256,
        effort="low",
        settings=settings,
    )

    assert isinstance(result, QueryResult), result
    assert result.model.startswith(settings.model)
    assert result.content.strip()
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    assert result.cost_usd is not None
    assert result.cost_usd > 0
