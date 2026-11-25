"""Experimentos ejecutados contra un proveedor simulado que imita las reglas de cada modelo."""

import importlib
from typing import Any

import pytest
from anthropic.types import Message

from app.config import Settings
from app.services.schemas import QueryError, QueryResult
from experiments._common import Tracker
from tests.conftest import make_message, make_status_error

DEFAULT = "claude-haiku-5-5"
LEGACY = "claude-haiku-4-5-20251001"
EXPERIMENTS = [
    "01_basic",
    "02_multiturn",
    "03_temperature",
    "04_sampling",
    "05_max_tokens",
    "06_stop_sequences",
    "07_thinking",
    "08_model_comparison",
]


class SimulatedClient:
    """Responde como la API: la versión 2026-10-21 rechaza el muestreo en todo modelo; Haiku
    5.5 rechaza muestreo y budget_tokens; Haiku 4.5 (con API 2023-06-01) no admite
    temperature con top_p ni thinking con temperature distinta de 1."""

    def __init__(self, unavailable: set[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.unavailable = unavailable or set()
        self.messages = self

    def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        model = kwargs["model"]
        sampling = kwargs.get("extra_body", {})
        thinking = kwargs.get("thinking") or {}
        api_version = kwargs.get("extra_headers", {}).get("anthropic-version")
        if model in self.unavailable:
            raise make_status_error(404, f"model: {model}")
        if sampling and api_version != "2023-06-01":
            # La versión de API del SDK 2.x (2026-10-21) elimina los parámetros de muestreo.
            raise make_status_error(400, "temperature: Extra inputs are not permitted")
        if model == DEFAULT and (sampling or thinking.get("type") == "enabled"):
            raise make_status_error(400, "parámetro no admitido por este modelo")
        if model == LEGACY and {"temperature", "top_p"} <= sampling.keys():
            raise make_status_error(400, "temperature y top_p no pueden usarse a la vez")
        if model == LEGACY and thinking and sampling.get("temperature", 1) != 1:
            raise make_status_error(400, "thinking requiere temperature 1")
        if kwargs["max_tokens"] < 100:
            return make_message("Texto cort", model=model, stop_reason="max_tokens")
        if kwargs.get("stop_sequences"):
            return make_message(
                "1, 2, 3, 4, 5, 6, ",
                model=model,
                stop_reason="stop_sequence",
                stop_sequence=kwargs["stop_sequences"][0],
            )
        return make_message(
            f"Respuesta de {model}", model=model, thinking="resumen" if thinking else None
        )


def load(name: str) -> Any:
    return importlib.import_module(f"experiments.{name}")


@pytest.mark.parametrize("name", EXPERIMENTS)
def test_experiment_runs_and_reports_cost(
    name: str, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient()

    exit_code = load(name).main(client=client, settings=settings)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Resumen:" in out
    assert "coste total" in out
    assert "Errores no esperados" not in out
    assert all(call["max_tokens"] <= 2048 for call in client.calls)


@pytest.mark.parametrize("name", EXPERIMENTS)
def test_experiment_without_key_explains_setup(
    name: str, settings_without_key: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient()

    exit_code = load(name).main(client=client, settings=settings_without_key)

    assert exit_code != 0
    assert ".env" in capsys.readouterr().out
    assert client.calls == []


def test_temperature_runs_on_legacy_and_shows_rejection(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient()
    load("03_temperature").main(client=client, settings=settings)

    legacy_temps = [c["extra_body"]["temperature"] for c in client.calls if c["model"] == LEGACY]
    assert legacy_temps == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    assert client.calls[-1]["model"] == DEFAULT
    assert "ERROR ESPERADO [bad_request 400]" in capsys.readouterr().out


def test_sampling_uses_legacy_and_shows_both_rejections(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient()
    load("04_sampling").main(client=client, settings=settings)

    out = capsys.readouterr().out
    assert out.count("ERROR ESPERADO [bad_request 400]") == 2
    assert [c["model"] for c in client.calls[:4]] == [LEGACY] * 4


def test_max_tokens_shows_truncation(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    load("05_max_tokens").main(client=SimulatedClient(), settings=settings)

    out = capsys.readouterr().out
    assert "stop_reason=max_tokens" in out
    assert "AVISO: respuesta truncada" in out


def test_stop_sequence_is_shown(settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    load("06_stop_sequences").main(client=SimulatedClient(), settings=settings)

    assert "stop_reason=stop_sequence ('7')" in capsys.readouterr().out


def test_thinking_separates_reasoning_and_rejections(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient()
    load("07_thinking").main(client=client, settings=settings)

    out = capsys.readouterr().out
    assert "[razonamiento 1]" in out
    assert [c["output_config"]["effort"] for c in client.calls[:2]] == ["low", "high"]
    assert client.calls[2]["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert out.count("ERROR ESPERADO [bad_request 400]") == 2


def test_comparison_retries_default_without_temperature(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient()
    load("08_model_comparison").main(client=client, settings=settings)

    out = capsys.readouterr().out
    assert "ERROR ESPERADO [bad_request 400]" in out
    assert f"{DEFAULT} repetido sin temperature" in out
    assert "bloques=text" in out


def test_unavailable_legacy_model_is_reported_without_failing(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    client = SimulatedClient(unavailable={LEGACY})

    exit_code = load("03_temperature").main(client=client, settings=settings)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[not_found 404]" in out
    assert f"el modelo legacy {LEGACY} ya no está disponible" in out


def test_not_found_for_another_model_gets_generic_notice(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    tracker = Tracker(settings)

    tracker.show(
        "x", QueryError(error="model: otro-modelo", error_type="not_found", status_code=404)
    )

    out = capsys.readouterr().out
    assert "puede haberse retirado" in out
    assert "modelo legacy" not in out


def test_tracker_accumulates_tokens_and_cost(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    tracker = Tracker(settings)
    result = QueryResult(
        content="x",
        model=DEFAULT,
        id="m",
        input_tokens=100,
        output_tokens=50,
        stop_reason="end_turn",
        cost_usd=0.001,
        latency_ms=10,
    )

    tracker.show("a", result)
    tracker.show("b", result)
    tracker.show(
        "c", QueryError(error="x", error_type="bad_request", status_code=400), expected_error=True
    )
    tracker.summary()

    assert tracker.calls == 3
    assert (tracker.input_tokens, tracker.output_tokens) == (200, 100)
    assert tracker.cost_usd == pytest.approx(0.002)
    assert tracker.errors == []
    assert "coste total = 0.002000 USD" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name", ["03_temperature", "04_sampling", "07_thinking", "08_model_comparison"]
)
def test_legacy_calls_use_legacy_api_version(name: str, settings: Settings) -> None:
    client = SimulatedClient()
    load(name).main(client=client, settings=settings)

    legacy_calls = [c for c in client.calls if c["model"] == LEGACY]
    assert legacy_calls
    assert all(c.get("extra_headers") == {"anthropic-version": "2023-06-01"} for c in legacy_calls)
    assert all("extra_headers" not in c for c in client.calls if c["model"] == DEFAULT)
