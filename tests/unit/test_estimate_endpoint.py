"""POST /api/v1/estimate con el LLM simulado: contrato, errores y registro."""

import logging
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.routers.estimations import get_llm_client
from app.routers.estimations import router as estimations_router
from tests.conftest import (
    FakeAsyncClient,
    make_connection_error,
    make_message,
    make_status_error,
    make_timeout_error,
)

TRANSCRIPTION = (
    "Cliente: necesitamos una landing para captar alumnos conectada a HubSpot y un blog "
    "para publicar noticias dos veces al mes. Contacto: Ana Pérez, ana@ejemplo.test."
)
ESTIMATION = "## Estimación: Landing\n\n| Tarea | Rol | Horas | Coste (EUR) |"


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def build_client(settings: Settings, fake: FakeAsyncClient) -> TestClient:
    app = FastAPI()
    app.include_router(estimations_router, prefix="/api/v1")
    app.dependency_overrides[get_llm_client] = lambda: fake
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def post(client: TestClient, transcription: str = TRANSCRIPTION) -> dict[str, object]:
    response = client.post("/api/v1/estimate", json={"transcription": transcription})
    return {"status": response.status_code, "body": response.json()}


def test_successful_estimation(settings: Settings) -> None:
    fake = FakeAsyncClient(make_message(ESTIMATION, input_tokens=4_000, output_tokens=1_000))

    result = post(build_client(settings, fake))

    assert result["status"] == 200
    body = result["body"]
    assert isinstance(body, dict)
    assert body["estimation"] == ESTIMATION
    assert body["model"] == "claude-haiku-5-5"
    assert body["provider"] == "anthropic"
    assert body["usage"] == {"input_tokens": 4_000, "output_tokens": 1_000, "total_tokens": 5_000}
    assert body["finish_reason"] == "stop"
    assert body["latency_ms"] >= 0
    assert body["cost_usd"] == pytest.approx(0.0009)
    assert body["created_at"].endswith("Z")


def test_llm_receives_context_and_transcription(settings: Settings) -> None:
    fake = FakeAsyncClient(make_message(ESTIMATION))

    post(build_client(settings, fake))

    call = fake.calls[0]
    assert "estimador experto" in call["system"]
    assert "### Ejemplo 5" in call["system"]
    assert TRANSCRIPTION not in call["system"]
    assert call["messages"] == [
        {"role": "user", "content": call["messages"][0]["content"]},
    ]
    assert f"<transcripcion>\n{TRANSCRIPTION}\n</transcripcion>" in call["messages"][0]["content"]


def test_model_without_price_returns_null_cost(settings: Settings) -> None:
    # Sin precio ni el modelo devuelto ni el configurado (que es el de reserva del cálculo).
    unpriced = settings.model_copy(update={"model": "modelo-sin-precio"})
    fake = FakeAsyncClient(make_message(ESTIMATION, model="modelo-sin-precio"))

    result = post(build_client(unpriced, fake))

    assert result["status"] == 200
    assert result["body"]["cost_usd"] is None  # type: ignore[index]


@pytest.mark.parametrize(
    ("stop_reason", "finish_reason"),
    [
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("max_tokens", "length"),
        ("pause_turn", "other"),
    ],
)
def test_finish_reason_is_normalized(
    settings: Settings, stop_reason: str, finish_reason: str
) -> None:
    fake = FakeAsyncClient(make_message(ESTIMATION, stop_reason=stop_reason))

    result = post(build_client(settings, fake))

    assert result["status"] == 200
    assert result["body"]["finish_reason"] == finish_reason  # type: ignore[index]


def test_truncation_is_logged(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeAsyncClient(make_message(ESTIMATION, stop_reason="max_tokens"))

    with caplog.at_level(logging.WARNING):
        post(build_client(settings, fake))

    assert any("truncada" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "body",
    [
        {"transcription": "demasiado corta"},
        {"transcription": " " * 100},
        {"transcription": "a" * 60_001},
        {},
        {"transcription": TRANSCRIPTION, "model": "otro"},
    ],
)
def test_invalid_requests_do_not_call_the_llm(settings: Settings, body: dict[str, str]) -> None:
    fake = FakeAsyncClient()
    client = build_client(settings, fake)

    response = client.post("/api/v1/estimate", json=body)

    assert response.status_code == 422
    assert fake.calls == []


def test_max_length_comes_from_injected_settings(settings: Settings) -> None:
    limited = settings.model_copy(update={"estimation_max_transcription_chars": 200})
    fake = FakeAsyncClient(make_message(ESTIMATION))
    client = build_client(limited, fake)

    too_long = client.post("/api/v1/estimate", json={"transcription": "a" * 201})
    at_limit = client.post("/api/v1/estimate", json={"transcription": "a" * 200})

    assert too_long.status_code == 422
    error = too_long.json()["detail"][0]
    assert error["loc"] == ["body", "transcription"]
    assert "200" in error["msg"]
    # La respuesta de error no devuelve la transcripción.
    assert "a" * 201 not in too_long.text
    assert at_limit.status_code == 200
    assert len(fake.calls) == 1


def test_invalid_utf8_body_is_400(settings: Settings) -> None:
    fake = FakeAsyncClient()

    response = build_client(settings, fake).post(
        "/api/v1/estimate",
        content=b'{"transcription": "\xe9\xe9"}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert fake.calls == []


def test_non_json_body_is_rejected(settings: Settings) -> None:
    fake = FakeAsyncClient()

    response = build_client(settings, fake).post(
        "/api/v1/estimate", content=b"no es json", headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert fake.calls == []


@pytest.mark.parametrize(
    ("error", "status", "error_type"),
    [
        (make_status_error(401, "invalid x-api-key"), 502, "authentication"),
        (make_status_error(403, "permiso denegado"), 502, "permission"),
        (make_status_error(404, "modelo inexistente"), 502, "not_found"),
        (make_status_error(400, "prompt is too long"), 502, "bad_request"),
        (make_status_error(429, "rate limited"), 503, "rate_limit"),
        (make_status_error(500, "internal error"), 502, "server"),
        (make_status_error(529, "overloaded"), 502, "server"),
        (make_timeout_error(), 504, "timeout"),
        (make_connection_error(), 502, "connection"),
        (make_status_error(418, "I'm a teapot"), 502, "api"),
    ],
)
def test_provider_errors_are_translated(
    settings: Settings, error: Exception, status: int, error_type: str
) -> None:
    result = post(build_client(settings, FakeAsyncClient(error)))

    assert result["status"] == status
    detail = result["body"]["detail"]  # type: ignore[index]
    assert detail["error_type"] == error_type
    assert detail["message"]
    # El mensaje es genérico: nunca el texto literal del proveedor.
    if hasattr(error, "message"):
        assert error.message not in detail["message"]


def test_refusal_is_422(settings: Settings) -> None:
    fake = FakeAsyncClient(make_message(None, stop_reason="refusal", refusal_category="cyber"))

    result = post(build_client(settings, fake))

    assert result["status"] == 422
    assert result["body"]["detail"]["error_type"] == "refusal"  # type: ignore[index]


def test_missing_key_is_503(settings_without_key: Settings) -> None:
    fake = FakeAsyncClient(make_message(ESTIMATION))

    result = post(build_client(settings_without_key, fake))

    assert result["status"] == 503
    assert result["body"]["detail"]["error_type"] == "configuration"  # type: ignore[index]
    assert fake.calls == []


def test_success_is_logged_without_transcription(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeAsyncClient(make_message(ESTIMATION, input_tokens=4_000, output_tokens=1_000))

    with caplog.at_level(logging.DEBUG):
        post(build_client(settings, fake))

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for field in (
        "model=claude-haiku-5-5",
        "input_tokens=4000",
        "output_tokens=1000",
        "latency_ms=",
        "cost_usd=0.0009",
        "finish_reason=stop",
        "prompt_version=v1",
    ):
        assert field in logged
    assert "Ana Pérez" not in logged
    assert "ana@ejemplo.test" not in logged
    assert ESTIMATION not in logged


def test_failure_is_logged_without_transcription(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeAsyncClient(make_status_error(429))

    with caplog.at_level(logging.DEBUG):
        post(build_client(settings, fake))

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "error_type=rate_limit" in logged
    assert "Ana Pérez" not in logged


def test_rates_from_settings_reach_the_prompt(settings: Settings) -> None:
    custom = settings.model_copy(
        update={
            "estimation_hourly_rates": {**settings.estimation_hourly_rates, "QA": Decimal("40")}
        }
    )
    fake = FakeAsyncClient(make_message(ESTIMATION))

    post(build_client(custom, fake))

    assert "- QA: 40,00 EUR/h" in fake.calls[0]["system"]
