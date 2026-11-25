import logging

import pytest

from app.services.pricing import PRICING, calculate_cost, load_pricing


def test_haiku_5_5_cost() -> None:
    cost = calculate_cost("claude-haiku-5-5", input_tokens=10_000, output_tokens=2_000)
    assert cost == pytest.approx(0.002)


@pytest.mark.parametrize("model", ["claude-haiku-4-5-20251001", "claude-haiku-4-5"])
def test_haiku_4_5_cost(model: str) -> None:
    assert calculate_cost(model, input_tokens=1_000, output_tokens=200) == pytest.approx(0.002)


def test_cache_tokens_are_priced() -> None:
    # 1M de escritura de caché a 1,25 USD + 1M de lectura a 0,10 USD (Haiku 4.5).
    cost = calculate_cost(
        "claude-haiku-4-5",
        input_tokens=0,
        output_tokens=0,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    assert cost == pytest.approx(1.35)


def test_upper_tier_applies_to_whole_request() -> None:
    # 90K de entrada + 20K leídos de caché = 110K de prompt: tramo superior para todo.
    cost = calculate_cost(
        "claude-haiku-5-5",
        input_tokens=90_000,
        output_tokens=1_000,
        cache_read_input_tokens=20_000,
    )
    expected = (90_000 * 0.50 + 1_000 * 2.50 + 20_000 * 0.05) / 1_000_000
    assert cost == pytest.approx(expected)


def test_prompt_at_threshold_uses_lower_tier() -> None:
    cost = calculate_cost("claude-haiku-5-5", input_tokens=100_000, output_tokens=0)
    assert cost == pytest.approx(0.01)


def test_unknown_model_returns_none_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        cost = calculate_cost("claude-desconocido", input_tokens=10, output_tokens=10)

    assert cost is None
    assert "claude-desconocido" in caplog.text


def test_fallback_model_is_used_when_served_model_is_unknown() -> None:
    cost = calculate_cost(
        "claude-haiku-5-5-snapshot-raro",
        input_tokens=10_000,
        output_tokens=2_000,
        fallback_model="claude-haiku-5-5",
    )
    assert cost == pytest.approx(0.002)


def test_pricing_override_from_json() -> None:
    pricing = load_pricing(
        '{"modelo-propio": {"tiers": [{"max_prompt_tokens": null, "input": 2, "output": 4,'
        ' "cache_write": 0, "cache_read": 0}]}}'
    )

    assert "claude-haiku-5-5" in pricing  # el override se fusiona, no reemplaza
    cost = calculate_cost(
        "modelo-propio", input_tokens=500_000, output_tokens=250_000, pricing=pricing
    )
    assert cost == pytest.approx(2.0)


def test_invalid_pricing_override_fails() -> None:
    with pytest.raises(ValueError):
        load_pricing('{"modelo": {"tiers": "no-es-una-lista"}}')


def test_every_model_has_an_open_last_tier() -> None:
    for name, pricing in PRICING.items():
        assert pricing.tiers[-1].max_prompt_tokens is None, name
