"""Contratos HTTP del estimador: validación de la petición y forma de la respuesta."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from app.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsage

# El máximo de longitud depende de la configuración y se prueba en el endpoint.


def test_valid_request_is_stripped() -> None:
    request = EstimationRequest(transcription="  " + "a" * 50 + "  ")

    assert request.transcription == "a" * 50


@pytest.mark.parametrize("transcription", ["a" * 49, " " * 80, "  " + "a" * 49 + "  "])
def test_too_short_transcription(transcription: str) -> None:
    with pytest.raises(ValidationError, match="transcription"):
        EstimationRequest(transcription=transcription)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        EstimationRequest(transcription="a" * 60, model="otro")  # type: ignore[call-arg]


def test_response_computes_total_tokens_and_utc_timestamp() -> None:
    response = EstimationResponse(
        estimation="## Estimación",
        model="claude-haiku-5-5",
        provider="anthropic",
        usage=TokenUsage(input_tokens=4_000, output_tokens=1_000),
        finish_reason="stop",
        latency_ms=1234.5,
        cost_usd=0.0009,
    )

    body = response.model_dump(mode="json")
    assert body["usage"] == {"input_tokens": 4_000, "output_tokens": 1_000, "total_tokens": 5_000}
    assert response.created_at.tzinfo is UTC
    assert body["created_at"].endswith("Z")


def test_response_rejects_unknown_finish_reason() -> None:
    with pytest.raises(ValidationError, match="finish_reason"):
        EstimationResponse(
            estimation="x",
            model="m",
            provider="anthropic",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            finish_reason="end_turn",  # type: ignore[arg-type]
            latency_ms=1,
            cost_usd=None,
        )
