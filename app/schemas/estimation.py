"""Contratos de `POST /api/v1/estimate` y de las respuestas de error."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.config import get_settings
from app.services.schemas import ErrorType

MIN_TRANSCRIPTION_CHARS = 50

FinishReason = Literal["stop", "length", "other"]


class EstimationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "transcription": (
                        "Cliente: necesitamos una landing para captar alumnos conectada a "
                        "HubSpot y un blog para publicar noticias dos veces al mes."
                    )
                }
            ]
        },
    )

    transcription: str = Field(
        min_length=MIN_TRANSCRIPTION_CHARS,
        description="Transcripción de la reunión con el cliente (texto plano).",
    )

    @field_validator("transcription")
    @classmethod
    def _max_length(cls, value: str) -> str:
        # El máximo es configurable (ESTIMATION_MAX_TRANSCRIPTION_CHARS), no un literal.
        limit = get_settings().estimation_max_transcription_chars
        if len(value) > limit:
            raise ValueError(f"la transcripción supera el máximo de {limit} caracteres")
        return value


class TokenUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class EstimationResponse(BaseModel):
    estimation: str = Field(description="Estimación en Markdown generada por el LLM.")
    model: str = Field(description="Modelo exacto que sirvió la respuesta.")
    provider: str
    usage: TokenUsage
    finish_reason: FinishReason = Field(
        description="stop: terminó de forma natural; length: truncada por max_tokens."
    )
    latency_ms: float = Field(ge=0, description="Latencia de la llamada al LLM.")
    cost_usd: float | None = Field(description="Coste estimado; nulo si el modelo no tiene precio.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorDetail(BaseModel):
    error_type: ErrorType
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail
