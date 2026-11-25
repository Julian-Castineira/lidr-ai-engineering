"""Contratos de salida del servicio de LLM."""

from typing import Literal

from pydantic import BaseModel, Field

ErrorType = Literal[
    "configuration",
    "validation",
    "authentication",
    "permission",
    "not_found",
    "bad_request",
    "rate_limit",
    "server",
    "timeout",
    "connection",
    "refusal",
    "api",
]


class QueryResult(BaseModel):
    """Respuesta correcta de Claude con sus métricas.

    `model_dump()` incluye los campos del dict de la lección (content, model, id,
    input_tokens, output_tokens, stop_reason, cost_usd) más los de observabilidad.
    """

    content: str
    model: str  # modelo exacto que sirvió la respuesta
    id: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    stop_reason: str | None
    stop_sequence: str | None = None
    cost_usd: float | None
    latency_ms: float = Field(ge=0)
    # Tipos de bloque en el orden recibido (p. ej. ["thinking", "text"]).
    block_types: list[str] = Field(default_factory=list)
    # Texto de los bloques de razonamiento; vacío si el modelo no lo devuelve visible.
    thinking: list[str] = Field(default_factory=list)


class QueryError(BaseModel):
    """Fallo de una consulta: configuración, validación, negativa o error del proveedor."""

    error: str
    error_type: ErrorType
    status_code: int | None = None
