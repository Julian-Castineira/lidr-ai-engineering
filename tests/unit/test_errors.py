from typing import Any

import anthropic
import httpx2
import pytest

from app.config import Settings
from app.services.llm_service import query_claude
from app.services.schemas import QueryError
from tests.conftest import (
    FAKE_KEY,
    FakeClient,
    make_connection_error,
    make_status_error,
    make_timeout_error,
)


def query_with_error(settings: Settings, exc: Exception) -> Any:
    return query_claude("Hola", client=FakeClient(exc), settings=settings)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (400, "bad_request"),
        (401, "authentication"),
        (403, "permission"),
        (404, "not_found"),
        (429, "rate_limit"),
        (500, "server"),
        (529, "server"),
        (402, "api"),
    ],
)
def test_status_errors_are_mapped(settings: Settings, status: int, error_type: str) -> None:
    result = query_with_error(settings, make_status_error(status, "mensaje del proveedor"))

    assert isinstance(result, QueryError)
    assert result.error_type == error_type
    assert result.status_code == status
    assert "mensaje del proveedor" in result.error


def test_timeout_is_mapped(settings: Settings) -> None:
    result = query_with_error(settings, make_timeout_error())

    assert isinstance(result, QueryError)
    assert result.error_type == "timeout"
    assert result.status_code is None


def test_connection_error_is_mapped(settings: Settings) -> None:
    result = query_with_error(settings, make_connection_error())

    assert isinstance(result, QueryError)
    assert result.error_type == "connection"
    assert result.status_code is None


def test_error_message_does_not_leak_api_key(settings: Settings) -> None:
    result = query_with_error(settings, make_status_error(401, "invalid x-api-key"))

    assert FAKE_KEY not in result.model_dump_json()


# --- Reintentos: cliente real del SDK con transporte simulado (sin red) ---

SUCCESS_BODY = {
    "id": "msg_retry",
    "type": "message",
    "role": "assistant",
    "model": "claude-haiku-5-5",
    "content": [{"type": "text", "text": "ok"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 10, "output_tokens": 5},
}


def error_body(error_type: str) -> dict[str, Any]:
    return {"type": "error", "error": {"type": error_type, "message": error_type}}


def sdk_client(responses: list[httpx2.Response], requests: list[httpx2.Request]) -> Any:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return responses.pop(0)

    return anthropic.Anthropic(
        api_key=FAKE_KEY,
        max_retries=2,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def test_non_transient_error_is_not_retried(settings: Settings) -> None:
    requests: list[httpx2.Request] = []
    client = sdk_client([httpx2.Response(401, json=error_body("authentication_error"))], requests)

    result = query_claude("Hola", client=client, settings=settings)

    assert isinstance(result, QueryError)
    assert result.error_type == "authentication"
    assert len(requests) == 1


def test_transient_error_is_retried_by_the_sdk(settings: Settings) -> None:
    requests: list[httpx2.Request] = []
    client = sdk_client(
        [
            httpx2.Response(529, json=error_body("overloaded_error")),
            httpx2.Response(200, json=SUCCESS_BODY),
        ],
        requests,
    )

    result = query_claude("Hola", client=client, settings=settings)

    assert not isinstance(result, QueryError)
    assert result.content == "ok"
    assert len(requests) == 2
