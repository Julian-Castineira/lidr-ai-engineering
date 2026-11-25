import logging
from typing import Any

import pytest

from app.config import Settings
from app.services.llm_service import query_claude
from app.services.schemas import QueryError, QueryResult
from tests.conftest import FAKE_KEY, FakeClient, make_message


def run(client: FakeClient, settings: Settings, *args: Any, **kwargs: Any) -> Any:
    return query_claude(*args, client=client, settings=settings, **kwargs)  # type: ignore[arg-type]


def test_successful_query(settings: Settings) -> None:
    client = FakeClient(make_message("Un LLM es...", model="claude-haiku-5-5"))

    result = run(client, settings, "¿Qué es un LLM?", system_prompt="Eres un profesor.")

    assert isinstance(result, QueryResult)
    assert result.content == "Un LLM es..."
    assert result.model == "claude-haiku-5-5"
    assert result.id == "msg_test_001"
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 10_000
    assert result.output_tokens == 2_000
    assert result.cost_usd == pytest.approx(0.002)
    assert result.latency_ms >= 0

    call = client.calls[0]
    assert call["system"] == "Eres un profesor."
    assert call["messages"] == [{"role": "user", "content": "¿Qué es un LLM?"}]
    assert call["max_tokens"] == 4096
    assert call["model"] == "claude-haiku-5-5"


def test_lesson_dict_fields_are_present(settings: Settings) -> None:
    result = run(FakeClient(make_message()), settings, "Hola")

    assert {
        "content",
        "model",
        "id",
        "input_tokens",
        "output_tokens",
        "stop_reason",
        "cost_usd",
        "latency_ms",
    } <= result.model_dump().keys()


def test_optional_params_are_not_sent_when_unset(settings: Settings) -> None:
    client = FakeClient(make_message())

    run(client, settings, "Hola")

    call = client.calls[0]
    assert "system" not in call
    assert "output_config" not in call
    assert "temperature" not in call.get("extra_body", {})


def test_optional_params_are_sent_as_given(settings: Settings) -> None:
    settings = settings.model_copy(update={"effort": "low"})
    client = FakeClient(make_message())

    run(client, settings, "Hola", temperature=0.3, model="claude-haiku-4-5", max_tokens=100)

    call = client.calls[0]
    assert call["extra_body"] == {"temperature": 0.3}
    assert call["output_config"] == {"effort": "low"}
    assert call["model"] == "claude-haiku-4-5"
    assert call["max_tokens"] == 100


def test_temperature_from_settings(settings: Settings) -> None:
    settings = settings.model_copy(update={"temperature": 0.7})
    client = FakeClient(make_message())

    run(client, settings, "Hola")

    assert client.calls[0]["extra_body"] == {"temperature": 0.7}


def test_text_is_read_by_block_type(settings: Settings) -> None:
    client = FakeClient(make_message("Respuesta final", thinking=""))

    result = run(client, settings, "Hola")

    assert result.content == "Respuesta final"
    assert result.block_types == ["thinking", "text"]


@pytest.mark.parametrize("message", ["", "   \n\t"])
def test_empty_message_is_rejected_without_calling(settings: Settings, message: str) -> None:
    client = FakeClient()

    result = run(client, settings, message)

    assert isinstance(result, QueryError)
    assert result.error_type == "validation"
    assert client.calls == []


def test_missing_api_key(settings_without_key: Settings) -> None:
    client = FakeClient()

    result = run(client, settings_without_key, "Hola")

    assert isinstance(result, QueryError)
    assert result.error_type == "configuration"
    assert "ANTHROPIC_API_KEY" in result.error
    assert client.calls == []


def test_truncated_response_warns(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient(make_message("Texto parc", stop_reason="max_tokens"))

    with caplog.at_level(logging.WARNING):
        result = run(client, settings, "Hola")

    assert isinstance(result, QueryResult)
    assert result.content == "Texto parc"
    assert result.stop_reason == "max_tokens"
    assert "max_tokens" in caplog.text


def test_refusal_is_a_typed_error(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient(
        make_message("texto parcial", stop_reason="refusal", refusal_category="cyber")
    )

    with caplog.at_level(logging.WARNING):
        result = run(client, settings, "Hola")

    assert isinstance(result, QueryError)
    assert result.error_type == "refusal"
    assert "cyber" in result.error
    assert "texto parcial" not in result.error
    assert result.status_code is None
    assert "refusal" in caplog.text


def test_refusal_without_category(settings: Settings) -> None:
    client = FakeClient(make_message(None, stop_reason="refusal", refusal_category=None))

    result = run(client, settings, "Hola")

    assert isinstance(result, QueryError)
    assert result.error_type == "refusal"


def test_cost_falls_back_to_requested_model(settings: Settings) -> None:
    client = FakeClient(make_message(model="claude-haiku-5-5-variante-desconocida"))

    result = run(client, settings, "Hola")

    assert result.cost_usd == pytest.approx(0.002)


def test_unknown_model_cost_is_none(settings: Settings) -> None:
    client = FakeClient(make_message(model="otro-modelo"))

    result = run(client, settings, "Hola", model="otro-modelo")

    assert isinstance(result, QueryResult)
    assert result.cost_usd is None


def test_api_key_never_in_result(settings: Settings) -> None:
    result = run(FakeClient(make_message()), settings, "Hola")
    assert FAKE_KEY not in result.model_dump_json()


def test_api_version_override_is_sent_as_header(settings: Settings) -> None:
    client = FakeClient(make_message())

    run(client, settings, "Hola", api_version="2023-06-01")

    assert client.calls[0]["extra_headers"] == {"anthropic-version": "2023-06-01"}


def test_api_version_is_not_overridden_by_default(settings: Settings) -> None:
    client = FakeClient(make_message())

    run(client, settings, "Hola")

    assert "extra_headers" not in client.calls[0]
