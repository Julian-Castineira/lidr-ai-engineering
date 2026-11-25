import anthropic
from anthropic.types import Message

from tests.conftest import (
    make_connection_error,
    make_message,
    make_status_error,
    make_timeout_error,
)


def test_make_message_builds_valid_sdk_message() -> None:
    message = make_message("hola", thinking="", refusal_category=None)

    assert isinstance(message, Message)
    assert [block.type for block in message.content] == ["thinking", "text"]
    assert message.usage.input_tokens == 10_000


def test_make_refusal_message_has_stop_details() -> None:
    message = make_message(None, stop_reason="refusal", refusal_category="cyber")

    assert message.stop_details is not None
    assert message.stop_details.category == "cyber"


def test_make_status_error_uses_sdk_classes() -> None:
    assert isinstance(make_status_error(401), anthropic.AuthenticationError)
    assert isinstance(make_status_error(529), anthropic.InternalServerError)
    assert make_status_error(429).status_code == 429


def test_network_errors_use_sdk_classes() -> None:
    assert isinstance(make_timeout_error(), anthropic.APITimeoutError)
    assert isinstance(make_connection_error(), anthropic.APIConnectionError)
