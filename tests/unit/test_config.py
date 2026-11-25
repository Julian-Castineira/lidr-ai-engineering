import re
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]
FAKE_KEY = "fake-test-key-not-a-real-secret"


def make_settings(**env: str) -> Settings:
    # _env_file=None: los tests no deben depender de un .env local.
    return Settings(_env_file=None, **env)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "ANTHROPIC_API_KEY",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "LLM_EFFORT",
        "LLM_MAX_TOKENS",
        "LLM_TIMEOUT_S",
        "LLM_MAX_RETRIES",
        "LLM_LEGACY_MODEL",
        "LLM_LEGACY_API_VERSION",
        "LLM_PRICING_JSON",
        "LLM_PROVIDER",
        "APP_ENV",
        "LOG_LEVEL",
        "ESTIMATION_HOURLY_RATES",
        "ESTIMATION_MAX_TRANSCRIPTION_CHARS",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    settings = make_settings()

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == FAKE_KEY
    assert settings.model == "claude-haiku-5-5"
    assert settings.max_tokens == 4096
    assert settings.temperature is None
    assert settings.effort is None
    assert settings.timeout_s == 60
    assert settings.max_retries == 2
    assert settings.legacy_model == "claude-haiku-4-5-20251001"
    assert settings.legacy_api_version == "2023-06-01"


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    monkeypatch.setenv("LLM_EFFORT", "low")
    monkeypatch.setenv("LLM_MAX_TOKENS", "1000")
    settings = make_settings()

    assert settings.model == "claude-haiku-4-5"
    assert settings.temperature == 0.3
    assert settings.effort == "low"
    assert settings.max_tokens == 1000


def test_api_key_is_optional_at_load_time() -> None:
    assert make_settings().anthropic_api_key is None


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("LLM_TEMPERATURE", "1.5"),
        ("LLM_TEMPERATURE", "-0.1"),
        ("LLM_EFFORT", "extreme"),
        ("LLM_MAX_TOKENS", "0"),
    ],
)
def test_invalid_values_name_the_variable(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValidationError) as exc_info:
        make_settings()

    field = variable.removeprefix("LLM_").lower()
    assert field in str(exc_info.value)


def test_api_key_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    settings = make_settings()

    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings)
    assert FAKE_KEY not in settings.model_dump_json()


def test_env_example_matches_settings() -> None:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*([A-Z_]+)=", content, flags=re.M))

    # Los campos con alias se leen sin el prefijo LLM_.
    expected = {
        field.validation_alias
        if isinstance(field.validation_alias, str)
        else f"LLM_{name.upper()}"
        for name, field in Settings.model_fields.items()
    }
    assert documented == expected


def test_env_example_has_no_real_key() -> None:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"ANTHROPIC_API_KEY=\S", content)


def test_env_example_loads_as_dotenv(tmp_path: Path) -> None:
    # Las variables vacías de .env.example deben tratarse como «no definidas».
    env_file = tmp_path / ".env"
    env_file.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")

    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.anthropic_api_key is None
    assert settings.temperature is None
    assert settings.effort is None
    assert settings.model == "claude-haiku-5-5"


def test_app_defaults() -> None:
    settings = make_settings()

    assert settings.provider == "anthropic"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.estimation_hourly_rates == {
        "desarrollo": Decimal("62.50"),
        "diseño": Decimal("50.00"),
        "gestión": Decimal("55.00"),
        "QA": Decimal("45.00"),
    }
    assert settings.estimation_max_transcription_chars == 60_000


def test_app_variables_are_read_without_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("ESTIMATION_HOURLY_RATES", '{"desarrollo": 70, "QA": 40.5}')
    monkeypatch.setenv("ESTIMATION_MAX_TRANSCRIPTION_CHARS", "1000")
    settings = make_settings()

    assert settings.app_env == "production"
    assert settings.log_level == "WARNING"
    assert settings.estimation_hourly_rates == {"desarrollo": Decimal("70"), "QA": Decimal("40.5")}
    assert settings.estimation_max_transcription_chars == 1000


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("LLM_PROVIDER", "openai"),
        ("APP_ENV", "staging"),
        ("LOG_LEVEL", "VERBOSE"),
        ("ESTIMATION_HOURLY_RATES", '{"desarrollo": 0}'),
        ("ESTIMATION_HOURLY_RATES", '{"desarrollo": -10}'),
        ("ESTIMATION_HOURLY_RATES", "{}"),
        ("ESTIMATION_MAX_TRANSCRIPTION_CHARS", "49"),
    ],
)
def test_invalid_app_values_name_the_variable(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValidationError) as exc_info:
        make_settings()

    message = str(exc_info.value)
    assert variable in message or variable.removeprefix("LLM_").lower() in message
