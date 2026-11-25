"""Estimación de proyectos con arquitectura CAG: contexto precargado + una llamada al LLM."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Literal

import anthropic

from app.config import Settings, get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_eur, load_examples, render_example
from app.services.llm_service import aquery_claude
from app.services.schemas import QueryError, QueryResult

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_VERSION = "v1"
TRANSCRIPTION_TAG = "transcripcion"

FinishReason = Literal["stop", "length", "other"]


@dataclass(frozen=True)
class EstimationPrompt:
    system: str
    user_message: str
    prompt_version: str


@dataclass(frozen=True)
class EstimationOutcome:
    result: QueryResult
    finish_reason: FinishReason
    prompt_version: str


def to_finish_reason(stop_reason: str | None) -> FinishReason:
    """Motivo de finalización independiente del proveedor."""
    if stop_reason in ("end_turn", "stop_sequence"):
        return "stop"
    if stop_reason == "max_tokens":
        return "length"
    return "other"


async def estimate(
    transcription: str,
    *,
    client: anthropic.AsyncAnthropic | None = None,
    settings: Settings | None = None,
) -> EstimationOutcome | QueryError:
    """Construye el contexto CAG, consulta al LLM y registra las métricas de la llamada.

    Nunca registra la transcripción ni la estimación (pueden contener datos personales).
    """
    settings = settings or get_settings()
    prompt = build_estimation_prompt(transcription, settings=settings)
    result = await aquery_claude(
        prompt.user_message, prompt.system, client=client, settings=settings
    )
    if isinstance(result, QueryError):
        logger.warning(
            "estimation_failed error_type=%s status_code=%s prompt_version=%s",
            result.error_type,
            result.status_code,
            prompt.prompt_version,
        )
        return result

    finish_reason = to_finish_reason(result.stop_reason)
    logger.info(
        "estimation_completed model=%s input_tokens=%d output_tokens=%d latency_ms=%.0f "
        "cost_usd=%s finish_reason=%s stop_reason=%s prompt_version=%s",
        result.model,
        result.input_tokens,
        result.output_tokens,
        result.latency_ms,
        result.cost_usd,
        finish_reason,
        result.stop_reason,
        prompt.prompt_version,
    )
    return EstimationOutcome(
        result=result, finish_reason=finish_reason, prompt_version=prompt.prompt_version
    )


@lru_cache
def _load_template(version: str) -> Template:
    path = PROMPTS_DIR / f"estimation_system.{version}.md"
    return Template(path.read_text(encoding="utf-8"))


def _examples_section(num_examples: int, settings: Settings) -> str:
    if num_examples == 0:
        return ""
    examples = load_examples(settings.estimation_hourly_rates)[:num_examples]
    blocks = [
        f"### Ejemplo {index}\n\n{render_example(example, settings.estimation_hourly_rates)}"
        for index, example in enumerate(examples, start=1)
    ]
    return "\n## Ejemplos\n\n" + "\n\n---\n\n".join(blocks) + "\n"


def _user_message(transcription: str) -> str:
    # La etiqueta de cierre dentro del texto no debe poder cerrar el bloque antes de tiempo.
    closing = f"</{TRANSCRIPTION_TAG}>"
    safe = transcription.replace(closing, f"</ {TRANSCRIPTION_TAG}>")
    return (
        "Estima el proyecto descrito en esta transcripción de reunión:\n\n"
        f"<{TRANSCRIPTION_TAG}>\n{safe}\n{closing}"
    )


def build_estimation_prompt(
    transcription: str,
    *,
    num_examples: int = len(ESTIMATION_EXAMPLES),
    use_examples: bool = True,
    settings: Settings | None = None,
) -> EstimationPrompt:
    """System prompt (rol, tarifas, ejemplos, formato) y mensaje de usuario con la transcripción.

    Es determinista: las mismas entradas producen exactamente el mismo prompt.
    """
    settings = settings or get_settings()
    available = len(ESTIMATION_EXAMPLES)
    if not 0 <= num_examples <= available:
        raise ValueError(
            f"num_examples debe estar entre 0 y {available} (recibido {num_examples})."
        )

    rates = "\n".join(
        f"- {role}: {format_eur(rate)} EUR/h"
        for role, rate in settings.estimation_hourly_rates.items()
    )
    system = _load_template(PROMPT_VERSION).substitute(
        rates=rates,
        examples=_examples_section(num_examples if use_examples else 0, settings),
    )
    return EstimationPrompt(
        system=system,
        user_message=_user_message(transcription),
        prompt_version=PROMPT_VERSION,
    )
