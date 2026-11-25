from typing import Any

import pytest
from anthropic.types import MessageParam

from app.config import Settings
from app.services.llm_service import Conversation, validate_history
from app.services.schemas import QueryError, QueryResult
from tests.conftest import FakeClient, make_message, make_status_error


def conversation(client: FakeClient, settings: Settings, **kwargs: Any) -> Conversation:
    return Conversation(client=client, settings=settings, **kwargs)  # type: ignore[arg-type]


def test_second_turn_resends_full_history(settings: Settings) -> None:
    client = FakeClient(make_message("Hola, Ana."), make_message("Te llamas Ana."))
    chat = conversation(client, settings, system_prompt="Eres breve.")

    chat.send("Me llamo Ana.")
    result = chat.send("¿Cómo me llamo?")

    assert isinstance(result, QueryResult)
    assert client.calls[1]["messages"] == [
        {"role": "user", "content": "Me llamo Ana."},
        {"role": "assistant", "content": "Hola, Ana."},
        {"role": "user", "content": "¿Cómo me llamo?"},
    ]
    assert client.calls[1]["system"] == "Eres breve."
    assert chat.history[-1] == {"role": "assistant", "content": "Te llamas Ana."}
    assert len(chat.history) == 4


@pytest.mark.parametrize(
    "history",
    [
        [{"role": "assistant", "content": "Hola"}],
        [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}],
    ],
)
def test_invalid_history_is_rejected_without_calling(
    settings: Settings, history: list[MessageParam]
) -> None:
    client = FakeClient()
    chat = conversation(client, settings, history=history)

    result = chat.send("Siguiente")

    assert isinstance(result, QueryError)
    assert result.error_type == "validation"
    assert client.calls == []
    assert chat.history == history


def test_failed_turn_keeps_previous_history(settings: Settings) -> None:
    client = FakeClient(make_message("Primera respuesta"), make_status_error(529))
    chat = conversation(client, settings)
    chat.send("Primera pregunta")
    before = chat.history

    result = chat.send("Segunda pregunta")

    assert isinstance(result, QueryError)
    assert chat.history == before


def test_history_property_is_a_copy(settings: Settings) -> None:
    chat = conversation(FakeClient(make_message()), settings)
    chat.send("Hola")

    chat.history.clear()

    assert len(chat.history) == 2


@pytest.mark.parametrize(
    ("messages", "valid"),
    [
        ([{"role": "user", "content": "hola"}], True),
        (
            [
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "hola"},
                {"role": "user", "content": "adiós"},
            ],
            True,
        ),
        ([], False),
        ([{"role": "user", "content": "  "}], False),
        ([{"role": "user", "content": "hola"}, {"role": "assistant", "content": "x"}], False),
    ],
)
def test_validate_history(messages: list[MessageParam], valid: bool) -> None:
    assert (validate_history(messages) is None) is valid
