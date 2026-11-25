"""Endpoint de estimación. El prefijo /api/v1 se fija al incluir el router en main.py."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings, get_settings
from app.schemas.estimation import (
    ErrorDetail,
    ErrorResponse,
    EstimationRequest,
    EstimationResponse,
    TokenUsage,
)
from app.services.estimation_service import estimate
from app.services.llm_service import AsyncLLMClient
from app.services.schemas import ErrorType, QueryError

router = APIRouter(tags=["estimaciones"])

# Código HTTP por categoría de error. 502: falla el proveedor del que dependemos, no nosotros.
HTTP_STATUS_BY_ERROR: dict[ErrorType, int] = {
    "validation": 422,
    "refusal": 422,
    "rate_limit": 503,
    "configuration": 503,
    "timeout": 504,
    "authentication": 502,
    "permission": 502,
    "not_found": 502,
    "bad_request": 502,
    "server": 502,
    "connection": 502,
    "api": 502,
}

# Mensajes genéricos: el mensaje original del proveedor solo va al registro.
ERROR_MESSAGES: dict[ErrorType, str] = {
    "validation": "La petición no es válida.",
    "refusal": "El modelo ha declinado generar la estimación para esta transcripción.",
    "rate_limit": "El proveedor de IA está limitando las peticiones. Inténtalo más tarde.",
    "configuration": "El servicio no está configurado correctamente.",
    "timeout": "El proveedor de IA no ha respondido a tiempo.",
    "authentication": "El servicio no ha podido autenticarse con el proveedor de IA.",
    "permission": "El servicio no tiene permiso para usar el proveedor de IA.",
    "not_found": "El modelo configurado no está disponible en el proveedor de IA.",
    "bad_request": "El proveedor de IA ha rechazado la petición.",
    "server": "El proveedor de IA no está disponible en este momento.",
    "connection": "No se ha podido conectar con el proveedor de IA.",
    "api": "Error inesperado del proveedor de IA.",
}

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in [
        (422, "Petición inválida o estimación declinada por el modelo."),
        (502, "Fallo del proveedor de IA."),
        (503, "Proveedor limitado o servicio mal configurado."),
        (504, "Timeout del proveedor de IA."),
    ]
}


def get_llm_client(request: Request) -> AsyncLLMClient:
    """Cliente asíncrono compartido, creado en el lifespan de la aplicación."""
    client: AsyncLLMClient = request.app.state.llm_client
    return client


def _http_error(error: QueryError) -> HTTPException:
    detail = ErrorDetail(error_type=error.error_type, message=ERROR_MESSAGES[error.error_type])
    return HTTPException(
        status_code=HTTP_STATUS_BY_ERROR[error.error_type], detail=detail.model_dump()
    )


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    responses=ERROR_RESPONSES,
    summary="Estima un proyecto a partir de la transcripción de una reunión",
)
async def create_estimation(
    body: EstimationRequest,
    client: Annotated[AsyncLLMClient, Depends(get_llm_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EstimationResponse:
    outcome = await estimate(body.transcription, client=client, settings=settings)
    if isinstance(outcome, QueryError):
        raise _http_error(outcome)

    result = outcome.result
    return EstimationResponse(
        estimation=result.content,
        model=result.model,
        provider=result.provider,
        usage=TokenUsage(input_tokens=result.input_tokens, output_tokens=result.output_tokens),
        finish_reason=outcome.finish_reason,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
    )
