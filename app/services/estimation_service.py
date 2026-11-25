"""Estimación de proyectos con arquitectura CAG: contexto precargado + una llamada al LLM."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template

from app.config import Settings, get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_eur, load_examples, render_example

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_VERSION = "v1"
TRANSCRIPTION_TAG = "transcripcion"


@dataclass(frozen=True)
class EstimationPrompt:
    system: str
    user_message: str
    prompt_version: str


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
