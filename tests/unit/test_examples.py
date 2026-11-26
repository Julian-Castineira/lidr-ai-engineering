"""Ejemplos del contexto CAG: catálogo válido y costes calculados por código."""

from decimal import Decimal

import pytest

from app.config import DEFAULT_HOURLY_RATES
from app.context.examples import (
    ESTIMATION_EXAMPLES,
    EstimationExample,
    ExampleTask,
    format_eur,
    load_examples,
    render_example,
)

RATES = {"desarrollo": Decimal("62.50"), "diseño": Decimal("50.00")}


def two_task_example() -> EstimationExample:
    return EstimationExample(
        title="Web corporativa",
        meeting_summary="Web de cinco páginas con formulario de contacto.",
        tasks=[
            ExampleTask(name="Maquetación", role="desarrollo", hours=Decimal(10)),
            ExampleTask(name="Diseño visual", role="diseño", hours=Decimal(4)),
        ],
        team=["1 desarrollador", "1 diseñador"],
        duration_weeks=2,
    )


def test_catalog_has_five_valid_examples() -> None:
    assert len(ESTIMATION_EXAMPLES) == 5
    for example in ESTIMATION_EXAMPLES:
        assert example.title.strip()
        assert example.meeting_summary.strip()
        assert example.tasks
        assert all(task.hours > 0 for task in example.tasks)
        assert example.team
        assert example.duration_weeks > 0


def test_every_example_role_has_a_default_rate() -> None:
    roles = {task.role for example in ESTIMATION_EXAMPLES for task in example.tasks}
    assert roles <= set(DEFAULT_HOURLY_RATES)


def test_load_examples_returns_catalog_with_default_rates() -> None:
    assert load_examples(DEFAULT_HOURLY_RATES) == ESTIMATION_EXAMPLES


def test_render_computes_costs_and_totals() -> None:
    rendered = render_example(two_task_example(), RATES)

    assert "| Maquetación | desarrollo | 10 | 625,00 |" in rendered
    assert "| Diseño visual | diseño | 4 | 200,00 |" in rendered
    assert "**Total de horas:** 14" in rendered
    assert "**Coste total:** 825,00 EUR" in rendered
    assert "**Duración:** 2 semanas" in rendered
    assert "1 desarrollador, 1 diseñador" in rendered


def test_render_rounds_half_up_and_formats_thousands() -> None:
    example = two_task_example().model_copy(
        update={"tasks": [ExampleTask(name="API", role="desarrollo", hours=Decimal("20.5"))]}
    )

    rendered = render_example(example, {"desarrollo": Decimal("62.55")})

    # 20,5 h a 62,55 EUR/h = 1.282,275 → 1.282,28 (ROUND_HALF_UP)
    assert "| API | desarrollo | 20,5 | 1.282,28 |" in rendered
    assert "**Coste total:** 1.282,28 EUR" in rendered


def test_format_eur() -> None:
    assert format_eur(Decimal("825")) == "825,00"
    assert format_eur(Decimal("1234567.891")) == "1.234.567,89"


def test_role_without_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="diseño"):
        render_example(two_task_example(), {"desarrollo": Decimal("62.50")})


def test_catalog_with_role_without_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="QA"):
        load_examples({role: rate for role, rate in DEFAULT_HOURLY_RATES.items() if role != "QA"})


def test_examples_are_immutable() -> None:
    with pytest.raises(ValueError):
        ESTIMATION_EXAMPLES[0].title = "otro"  # type: ignore[misc]
