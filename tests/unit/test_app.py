"""Aplicación completa: arranque, /health, OpenAPI y configuración del registro."""

import logging
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import __version__
from app.config import Settings, get_settings
from app.main import SDK_LOGGERS, app
from app.routers.estimations import get_llm_client
from tests.conftest import FAKE_KEY, FakeAsyncClient, make_message

TRANSCRIPTION = "Cliente: queremos una landing con formulario conectado al CRM y un blog sencillo."


def make_settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[call-arg]


@pytest.fixture
def use_settings() -> Iterator[Callable[[Callable[[], Settings]], None]]:
    def apply(factory: Callable[[], Settings]) -> None:
        app.dependency_overrides[get_settings] = factory

    yield apply
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_health(use_settings: Callable[[Callable[[], Settings]], None]) -> None:
    fake = FakeAsyncClient()
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY, APP_ENV="test"))
    app.dependency_overrides[get_llm_client] = lambda: fake

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": __version__, "environment": "test"}
    assert fake.calls == []


def test_openapi_and_docs(use_settings: Callable[[Callable[[], Settings]], None]) -> None:
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY))

    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        docs = client.get("/docs")

    assert docs.status_code == 200
    assert schema["info"]["title"] == "Estimador CAG"
    assert schema["info"]["version"] == __version__
    assert schema["info"]["description"]
    assert set(schema["paths"]) == {"/api/v1/estimate", "/health"}
    operation = schema["paths"]["/api/v1/estimate"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "EstimationRequest"
    )
    assert {"200", "422", "502", "503", "504"} <= set(operation["responses"])
    assert "EstimationResponse" in schema["components"]["schemas"]


def test_startup_fails_without_api_key(
    use_settings: Callable[[Callable[[], Settings]], None],
) -> None:
    use_settings(lambda: make_settings())

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"), TestClient(app):
        pass


def test_startup_fails_with_invalid_configuration(
    use_settings: Callable[[Callable[[], Settings]], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY))

    with pytest.raises(ValidationError, match="provider"), TestClient(app):
        pass


def test_startup_error_does_not_reveal_secrets(
    use_settings: Callable[[Callable[[], Settings]], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY))

    with pytest.raises(ValidationError) as exc_info, TestClient(app):
        pass

    assert FAKE_KEY not in str(exc_info.value)


def test_llm_client_is_created_and_closed(
    use_settings: Callable[[Callable[[], Settings]], None],
) -> None:
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY))

    with TestClient(app):
        client = app.state.llm_client
        assert not client.is_closed()

    assert client.is_closed()


def test_log_level_warning_hides_info(
    use_settings: Callable[[Callable[[], Settings]], None], caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeAsyncClient(make_message("## Estimación"))
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY, LOG_LEVEL="WARNING"))
    app.dependency_overrides[get_llm_client] = lambda: fake

    with caplog.at_level(logging.DEBUG), TestClient(app) as client:
        response = client.post("/api/v1/estimate", json={"transcription": TRANSCRIPTION})

    assert response.status_code == 200
    assert not any("estimation_completed" in record.getMessage() for record in caplog.records)


def test_debug_level_keeps_sdk_loggers_quiet(
    use_settings: Callable[[Callable[[], Settings]], None],
) -> None:
    # A nivel DEBUG el SDK registraría el cuerpo de la petición, con la transcripción.
    use_settings(lambda: make_settings(ANTHROPIC_API_KEY=FAKE_KEY, LOG_LEVEL="DEBUG"))

    with TestClient(app):
        assert logging.getLogger("app").getEffectiveLevel() == logging.DEBUG
        for name in SDK_LOGGERS:
            assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
