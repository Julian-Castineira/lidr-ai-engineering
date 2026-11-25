"""Dobles de prueba del SDK de Anthropic: sin red, sin API key real y sin coste."""

from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types import Message, RefusalStopDetails, TextBlock, ThinkingBlock, Usage

from app.config import Settings

FAKE_KEY = "fake-test-key-not-a-real-secret"
API_URL = "https://api.anthropic.com/v1/messages"


def make_message(
    text: str | None = "Respuesta de prueba",
    *,
    model: str = "claude-haiku-5-5",
    input_tokens: int = 10_000,
    output_tokens: int = 2_000,
    stop_reason: str = "end_turn",
    stop_sequence: str | None = None,
    thinking: str | None = None,
    refusal_category: str | None = None,
    cache_creation_input_tokens: int | None = None,
    cache_read_input_tokens: int | None = None,
    message_id: str = "msg_test_001",
) -> Message:
    content: list[Any] = []
    if thinking is not None:
        content.append(ThinkingBlock(type="thinking", thinking=thinking, signature="sig"))
    if text is not None:
        content.append(TextBlock(type="text", text=text))
    stop_details = (
        RefusalStopDetails(type="refusal", category=refusal_category)  # type: ignore[arg-type]
        if stop_reason == "refusal"
        else None
    )
    return Message(
        id=message_id,
        type="message",
        role="assistant",
        model=model,
        content=content,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        stop_sequence=stop_sequence,
        stop_details=stop_details,
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
        ),
    )


_STATUS_ERRORS: dict[int, type[anthropic.APIStatusError]] = {
    400: anthropic.BadRequestError,
    401: anthropic.AuthenticationError,
    403: anthropic.PermissionDeniedError,
    404: anthropic.NotFoundError,
    429: anthropic.RateLimitError,
    500: anthropic.InternalServerError,
    529: anthropic.OverloadedError,
}


def make_status_error(
    status: int, message: str = "error del proveedor"
) -> anthropic.APIStatusError:
    body = {"type": "error", "error": {"type": "api_error", "message": message}}
    response = httpx2.Response(status, json=body, request=httpx2.Request("POST", API_URL))
    error_cls = _STATUS_ERRORS.get(status, anthropic.APIStatusError)
    return error_cls(message, response=response, body=body)


def make_timeout_error() -> anthropic.APITimeoutError:
    return anthropic.APITimeoutError(request=httpx2.Request("POST", API_URL))


def make_connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=httpx2.Request("POST", API_URL))


class FakeMessages:
    def __init__(self, responses: list[Message | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeMessages: no quedan respuestas programadas")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    """Sustituto de `anthropic.Anthropic` con la única superficie que usa el servicio."""

    def __init__(self, *responses: Message | Exception) -> None:
        self.messages = FakeMessages(list(responses))

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.messages.calls


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, ANTHROPIC_API_KEY=FAKE_KEY)  # type: ignore[call-arg]


@pytest.fixture
def settings_without_key() -> Settings:
    return Settings(_env_file=None, ANTHROPIC_API_KEY=None)  # type: ignore[call-arg]


@pytest.fixture
def fake_client() -> Callable[..., FakeClient]:
    return FakeClient
