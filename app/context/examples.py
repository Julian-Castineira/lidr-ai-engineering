"""Estimaciones de ejemplo (few-shot) del estimador. Todas son ficticias.

Los ejemplos guardan solo tareas, roles y horas: costes y totales se calculan al
presentarlos con las tarifas configuradas, así que no pueden quedar incoherentes.
"""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

CENT = Decimal("0.01")


class ExampleTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    hours: Decimal = Field(gt=0)


class EstimationExample(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    meeting_summary: str = Field(min_length=1)
    tasks: tuple[ExampleTask, ...] = Field(min_length=1)
    team: tuple[str, ...] = Field(min_length=1)
    duration_weeks: int = Field(gt=0)


def _task(name: str, role: str, hours: int | str) -> ExampleTask:
    return ExampleTask(name=name, role=role, hours=Decimal(hours))


ESTIMATION_EXAMPLES: tuple[EstimationExample, ...] = (
    EstimationExample(
        title="Landing de captación con CRM",
        meeting_summary=(
            "Una academia de idiomas quiere una landing para su campaña de otoño con un "
            "formulario que cree el contacto en su CRM y le envíe un correo de bienvenida. "
            "Ya tienen logotipo y textos; necesitan diseño responsive y medir conversiones."
        ),
        tasks=(
            _task("Diseño de la landing (escritorio y móvil)", "diseño", 12),
            _task("Maquetación responsive", "desarrollo", 16),
            _task("Formulario e integración con la API del CRM", "desarrollo", 10),
            _task("Correo de bienvenida automatizado", "desarrollo", 4),
            _task("Etiquetado de analítica y conversiones", "desarrollo", 4),
            _task("Pruebas en navegadores y dispositivos", "QA", 6),
            _task("Coordinación y reuniones de seguimiento", "gestión", 4),
        ),
        team=("1 diseñador", "1 desarrollador web", "1 QA a tiempo parcial"),
        duration_weeks=2,
    ),
    EstimationExample(
        title="Tienda online pequeña",
        meeting_summary=(
            "Un obrador artesano quiere vender online unos 40 productos con pago con tarjeta, "
            "gastos de envío por zona y un panel sencillo para gestionar pedidos y stock. "
            "No tienen web actual ni catálogo digital."
        ),
        tasks=(
            _task("Diseño de catálogo, ficha de producto y carrito", "diseño", 24),
            _task("Configuración de la plataforma de comercio y el tema", "desarrollo", 20),
            _task("Pasarela de pago y pruebas de cobro", "desarrollo", 12),
            _task("Reglas de envío por zona", "desarrollo", 8),
            _task("Carga inicial del catálogo (40 productos)", "desarrollo", 10),
            _task("Pruebas del proceso de compra completo", "QA", 12),
            _task("Formación al cliente y gestión del proyecto", "gestión", 10),
        ),
        team=("1 diseñador", "1 desarrollador", "1 QA", "1 jefe de proyecto a tiempo parcial"),
        duration_weeks=4,
    ),
    EstimationExample(
        title="App móvil interna de partes de trabajo",
        meeting_summary=(
            "Una empresa de mantenimiento quiere sustituir los partes en papel por una app "
            "para sus 25 técnicos: fotos, firma del cliente, funcionamiento sin conexión y "
            "sincronización con un panel web para la oficina."
        ),
        tasks=(
            _task("Diseño de flujos y pantallas de la app", "diseño", 30),
            _task("App multiplataforma: partes, fotos y firma", "desarrollo", 80),
            _task("Modo sin conexión y sincronización", "desarrollo", 40),
            _task("API y panel web de la oficina", "desarrollo", 60),
            _task("Pruebas funcionales y en campo", "QA", 40),
            _task("Publicación en tiendas internas y despliegue", "desarrollo", 12),
            _task("Gestión del proyecto y validaciones con usuarios", "gestión", 30),
        ),
        team=(
            "1 diseñador",
            "2 desarrolladores (móvil y backend)",
            "1 QA",
            "1 jefe de proyecto a tiempo parcial",
        ),
        duration_weeks=10,
    ),
    EstimationExample(
        title="Integración entre ERP y plataforma de facturación",
        meeting_summary=(
            "Una distribuidora quiere que los pedidos de su ERP generen facturas en su "
            "plataforma de facturación sin intervención manual, con reintentos ante fallos "
            "y un informe diario de incidencias. No requiere interfaz de usuario."
        ),
        tasks=(
            _task("Análisis de las dos APIs y mapeo de campos", "desarrollo", 12),
            _task("Servicio de sincronización de pedidos a facturas", "desarrollo", 32),
            _task("Reintentos, idempotencia y registro de errores", "desarrollo", 12),
            _task("Informe diario de incidencias por correo", "desarrollo", 6),
            _task("Pruebas con datos de ejemplo y casos límite", "QA", 16),
            _task("Coordinación con los proveedores de ambos sistemas", "gestión", 10),
        ),
        team=("1 desarrollador backend", "1 QA a tiempo parcial"),
        duration_weeks=4,
    ),
    EstimationExample(
        title="Chatbot de atención al cliente para la web",
        meeting_summary=(
            "Una clínica dental quiere un asistente en su web que responda preguntas "
            "frecuentes sobre tratamientos, horarios y precios orientativos, y que derive a "
            "recepción cuando no sepa responder. Tienen un documento de preguntas frecuentes."
        ),
        tasks=(
            _task("Diseño de la conversación y del widget", "diseño", 10),
            _task("Preparación de la base de conocimiento", "desarrollo", 12),
            _task("Integración del modelo de lenguaje y del widget", "desarrollo", 24),
            _task("Derivación a recepción y aviso por correo", "desarrollo", 8),
            _task("Batería de preguntas de evaluación y ajustes", "QA", 14),
            _task("Gestión del proyecto y revisión con la clínica", "gestión", 8),
        ),
        team=("1 diseñador conversacional", "1 desarrollador", "1 QA a tiempo parcial"),
        duration_weeks=3,
    ),
)


def format_eur(amount: Decimal) -> str:
    """Importe con 2 decimales en formato español: 1.234,50."""
    rounded = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_hours(hours: Decimal) -> str:
    """Horas sin ceros sobrantes y con coma decimal: 10, 20,5."""
    text = format(hours.normalize(), "f")
    return text.replace(".", ",")


def _rate_for(role: str, rates: Mapping[str, Decimal]) -> Decimal:
    if role not in rates:
        raise ValueError(f"El rol «{role}» no tiene tarifa configurada (ESTIMATION_HOURLY_RATES).")
    return rates[role]


def render_example(example: EstimationExample, rates: Mapping[str, Decimal]) -> str:
    """Estimación del ejemplo en Markdown, con costes y totales calculados aquí."""
    rows = []
    total_hours = Decimal(0)
    total_cost = Decimal(0)
    for task in example.tasks:
        cost = (task.hours * _rate_for(task.role, rates)).quantize(CENT, rounding=ROUND_HALF_UP)
        total_hours += task.hours
        total_cost += cost
        rows.append(
            f"| {task.name} | {task.role} | {format_hours(task.hours)} | {format_eur(cost)} |"
        )

    return "\n".join(
        [
            f"**Resumen de la reunión:** {example.meeting_summary}",
            "",
            f"## Estimación: {example.title}",
            "",
            "| Tarea | Rol | Horas | Coste (EUR) |",
            "|---|---|---|---|",
            *rows,
            "",
            f"**Total de horas:** {format_hours(total_hours)}",
            f"**Coste total:** {format_eur(total_cost)} EUR",
            f"**Equipo recomendado:** {', '.join(example.team)}",
            f"**Duración:** {example.duration_weeks} semanas",
        ]
    )


def load_examples(
    rates: Mapping[str, Decimal],
    examples: Sequence[EstimationExample] = ESTIMATION_EXAMPLES,
) -> tuple[EstimationExample, ...]:
    """Catálogo comprobado contra las tarifas: falla si algún rol no tiene tarifa."""
    for example in examples:
        for task in example.tasks:
            _rate_for(task.role, rates)
    return tuple(examples)
