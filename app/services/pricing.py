"""Tabla de precios de Claude y cálculo determinista del coste de una llamada."""

import logging
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, TypeAdapter, field_validator

logger = logging.getLogger(__name__)

# Fecha en la que se comprobaron los precios en https://platform.claude.com/docs/en/about-claude/pricing
PRICING_VERIFIED_ON = date(2026, 11, 25)

_PER_MILLION = Decimal(1_000_000)


class PriceTier(BaseModel):
    """Precios en USD por millón de tokens para prompts de hasta `max_prompt_tokens`."""

    max_prompt_tokens: int | None  # None = sin límite superior
    input: Decimal
    output: Decimal
    cache_write: Decimal  # escritura de caché de 5 minutos (la duración por defecto)
    cache_read: Decimal


class ModelPricing(BaseModel):
    tiers: list[PriceTier]

    @field_validator("tiers")
    @classmethod
    def _last_tier_is_open(cls, tiers: list[PriceTier]) -> list[PriceTier]:
        if not tiers or tiers[-1].max_prompt_tokens is not None:
            raise ValueError("el último tramo debe tener max_prompt_tokens = null")
        return tiers

    def tier_for(self, prompt_tokens: int) -> PriceTier:
        for tier in self.tiers:
            if tier.max_prompt_tokens is None or prompt_tokens <= tier.max_prompt_tokens:
                return tier
        raise AssertionError("unreachable: el último tramo siempre es abierto")


def _flat(input_: str, output: str, cache_write: str, cache_read: str) -> ModelPricing:
    return ModelPricing(
        tiers=[
            PriceTier(
                max_prompt_tokens=None,
                input=Decimal(input_),
                output=Decimal(output),
                cache_write=Decimal(cache_write),
                cache_read=Decimal(cache_read),
            )
        ]
    )


_HAIKU_4_5 = _flat("1", "5", "1.25", "0.10")

PRICING: dict[str, ModelPricing] = {
    "claude-haiku-5-5": ModelPricing(
        tiers=[
            PriceTier(
                max_prompt_tokens=100_000,
                input=Decimal("0.10"),
                output=Decimal("0.50"),
                cache_write=Decimal("0.125"),
                cache_read=Decimal("0.01"),
            ),
            PriceTier(
                max_prompt_tokens=None,
                input=Decimal("0.50"),
                output=Decimal("2.50"),
                cache_write=Decimal("0.625"),
                cache_read=Decimal("0.05"),
            ),
        ]
    ),
    "claude-haiku-4-5-20251001": _HAIKU_4_5,
    "claude-haiku-4-5": _HAIKU_4_5,
}

_PRICING_ADAPTER = TypeAdapter(dict[str, ModelPricing])


def load_pricing(pricing_json: str | None = None) -> dict[str, ModelPricing]:
    """Devuelve la tabla por defecto fusionada con el override JSON, si lo hay."""
    if not pricing_json:
        return dict(PRICING)
    try:
        override = _PRICING_ADAPTER.validate_json(pricing_json)
    except Exception as exc:
        raise ValueError(f"LLM_PRICING_JSON no es válido: {exc}") from exc
    return {**PRICING, **override}


def calculate_cost(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    pricing: dict[str, ModelPricing] | None = None,
    fallback_model: str | None = None,
) -> float | None:
    """Coste en USD de una llamada, o None si el modelo no tiene precio conocido.

    El tramo se elige por la longitud total del prompt (entrada + caché) y se aplica a
    toda la petición, como hace la facturación de Anthropic.
    """
    table = pricing if pricing is not None else PRICING
    model_pricing = table.get(model) or (table.get(fallback_model) if fallback_model else None)
    if model_pricing is None:
        logger.warning("No hay precio configurado para el modelo %r; cost_usd = None", model)
        return None

    prompt_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
    tier = model_pricing.tier_for(prompt_tokens)
    total = (
        input_tokens * tier.input
        + output_tokens * tier.output
        + cache_creation_input_tokens * tier.cache_write
        + cache_read_input_tokens * tier.cache_read
    ) / _PER_MILLION
    return float(round(total, 6))
