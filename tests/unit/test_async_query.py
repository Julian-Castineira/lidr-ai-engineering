"""Consulta asíncrona: mismo contrato de resultado y errores que la síncrona."""

import time
from typing import Any

import anthropic
import anyio
import httpx2
import pytest

from app.config import Settings
from app.services.llm_service import acall_raw, aquery_claude, query_claude
from app.services.schemas import QueryError, QueryResult
from tests.conftest import (
    FAKE_KEY,
    FakeAsyncClient,
    FakeClient,
    make_connection_error,
    make_message,
    make_status_error,
    make_timeout_error,
)

pytestmark = pytest.mark.anyio


async def test_result_matches_sync_query(settings: Settings) -> None:
    async_client = FakeAsyncClient(make_message())
    sync_client = FakeClient(make_message())

    result = await aquery_claude(
        "¿Qué es un LLM?", "Eres un profesor.", client=async_client, settings=settings
    )
    expected = query_claude(
        "¿Qué es un LLM?", "Eres un profesor.", client=sync_client, settings=settings
    )

    assert isinstance(result, QueryResult)
    assert isinstance(expected, QueryResult)
    assert result.content == "Respuesta de prueba"
    assert result.model == "claude-haiku-5-5"
    assert result.id == "msg_test_001"
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 10_000
    assert result.output_tokens == 2_000
    assert result.cost_usd == pytest.approx(0.002)
    assert result.latency_ms >= 0
    assert result.provider == "anthropic"
    # La petición enviada es la misma que construye la variante síncrona.
    assert async_client.calls == sync_client.calls
    assert async_client.calls[0]["system"] == "Eres un profesor."
    assert result.model_dump(exclude={"latency_ms"}) == expected.model_dump(exclude={"latency_ms"})


async def test_acall_raw_accepts_raw_messages(settings: Settings) -> None:
    client = FakeAsyncClient(make_message(text="ok"))

    result = await acall_raw(
        [{"role": "user", "content": "Hola"}],
        system="Breve.",
        max_tokens=128,
        client=client,
        settings=settings,
    )

    assert isinstance(result, QueryResult)
    assert result.content == "ok"
    assert client.calls[0]["max_tokens"] == 128


@pytest.mark.parametrize(
    ("error", "error_type", "status_code"),
    [
        (make_status_error(401), "authentication", 401),
        (make_status_error(429), "rate_limit", 429),
        (make_status_error(529), "server", 529),
        (make_timeout_error(), "timeout", None),
        (make_connection_error(), "connection", None),
    ],
)
async def test_errors_match_sync_query(
    settings: Settings, error: Exception, error_type: str, status_code: int | None
) -> None:
    result = await aquery_claude("Hola", client=FakeAsyncClient(error), settings=settings)
    expected = query_claude("Hola", client=FakeClient(error), settings=settings)

    assert isinstance(result, QueryError)
    assert result.error_type == error_type
    assert result.status_code == status_code
    assert result == expected


async def test_missing_api_key(settings_without_key: Settings) -> None:
    client = FakeAsyncClient(make_message())

    result = await aquery_claude("Hola", client=client, settings=settings_without_key)

    assert isinstance(result, QueryError)
    assert result.error_type == "configuration"
    assert client.calls == []


async def test_refusal(settings: Settings) -> None:
    client = FakeAsyncClient(
        make_message(text=None, stop_reason="refusal", refusal_category="cyber")
    )

    result = await aquery_claude("Hola", client=client, settings=settings)

    assert isinstance(result, QueryError)
    assert result.error_type == "refusal"
    assert "cyber" in result.error


async def test_empty_message(settings: Settings) -> None:
    client = FakeAsyncClient(make_message())

    result = await aquery_claude("   ", client=client, settings=settings)

    assert isinstance(result, QueryError)
    assert result.error_type == "validation"
    assert client.calls == []


async def test_concurrent_queries_do_not_block(settings: Settings) -> None:
    client = FakeAsyncClient(make_message(), make_message(), delay_s=0.2)
    results: list[QueryResult | QueryError] = []

    async def run() -> None:
        results.append(await aquery_claude("Hola", client=client, settings=settings))

    start = time.perf_counter()
    async with anyio.create_task_group() as tg:
        tg.start_soon(run)
        tg.start_soon(run)
    elapsed = time.perf_counter() - start

    assert len(results) == 2
    assert all(isinstance(result, QueryResult) for result in results)
    assert elapsed < 0.4


# --- Reintentos: cliente asíncrono real del SDK con transporte simulado (sin red) ---

SUCCESS_BODY: dict[str, Any] = {
    "id": "msg_retry",
    "type": "message",
    "role": "assistant",
    "model": "claude-haiku-5-5",
    "content": [{"type": "text", "text": "ok"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 10, "output_tokens": 5},
}


async def test_transient_error_is_retried_by_the_sdk(settings: Settings) -> None:
    requests: list[httpx2.Request] = []
    responses = [
        httpx2.Response(
            529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}
        ),
        httpx2.Response(200, json=SUCCESS_BODY),
    ]

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return responses.pop(0)

    client = anthropic.AsyncAnthropic(
        api_key=FAKE_KEY,
        max_retries=2,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )

    result = await aquery_claude("Hola", client=client, settings=settings)

    assert isinstance(result, QueryResult)
    assert result.content == "ok"
    assert len(requests) == 2
