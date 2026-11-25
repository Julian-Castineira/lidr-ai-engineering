"""Acceso a Claude mediante la Messages API de Anthropic.

Único módulo de la aplicación que depende del SDK de Anthropic: el resto consume
`QueryResult` / `QueryError`.
"""

import logging
import time
from collections.abc import Sequence
from typing import Any

import anthropic
from anthropic.types import Message, MessageParam

from app.config import Effort, Settings, get_settings
from app.services.pricing import calculate_cost, load_pricing
from app.services.schemas import ErrorType, QueryError, QueryResult

logger = logging.getLogger(__name__)


def build_client(settings: Settings) -> anthropic.Anthropic:
    """Cliente con timeout y reintentos de la configuración.

    Los reintentos ante errores transitorios (conexión, 408, 409, 429, 5xx) los hace el
    SDK con backoff exponencial; no se añade otra capa de reintentos.
    """
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    return anthropic.Anthropic(
        api_key=api_key,
        timeout=settings.timeout_s,
        max_retries=settings.max_retries,
    )


def call_raw(
    messages: Sequence[MessageParam],
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    effort: Effort | None = None,
    stop_sequences: list[str] | None = None,
    thinking: dict[str, Any] | None = None,
    api_version: str | None = None,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> QueryResult | QueryError:
    """Llamada a la Messages API con métricas y errores tipados.

    Los parámetros opcionales solo se envían si se fijan aquí o en la configuración; si
    el modelo no los admite, el 400 del proveedor se devuelve como `bad_request`.
    """
    settings = settings or get_settings()
    if settings.anthropic_api_key is None:
        return QueryError(
            error="Falta la variable ANTHROPIC_API_KEY (configúrala en .env).",
            error_type="configuration",
        )

    requested_model = model or settings.model
    request: dict[str, Any] = {
        "model": requested_model,
        "max_tokens": max_tokens or settings.max_tokens,
        "messages": list(messages),
    }
    if system:
        request["system"] = system

    effort = effort or settings.effort
    if effort is not None:
        request["output_config"] = {"effort": effort}
    if stop_sequences:
        request["stop_sequences"] = stop_sequences
    if thinking is not None:
        request["thinking"] = thinking

    # El SDK 2.x retiró temperature/top_p/top_k de su firma (la API los sigue aceptando
    # en los modelos que los admiten), así que van en extra_body.
    temperature = temperature if temperature is not None else settings.temperature
    sampling = {"temperature": temperature, "top_p": top_p, "top_k": top_k}
    extra_body = {name: value for name, value in sampling.items() if value is not None}
    if extra_body:
        request["extra_body"] = extra_body
    # Solo si se pide: p. ej. 2023-06-01, la última versión que admite parámetros de muestreo.
    if api_version:
        request["extra_headers"] = {"anthropic-version": api_version}

    client = client or build_client(settings)
    start = time.perf_counter()
    try:
        response = client.messages.create(**request)
    except anthropic.AnthropicError as exc:
        error = map_error(exc)
        logger.warning(
            "Llamada a %s fallida: %s (%s)", requested_model, error.error_type, error.error
        )
        return error
    latency_ms = (time.perf_counter() - start) * 1000

    return _to_result(response, requested_model, latency_ms, settings)


def query_claude(
    message: str,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    *,
    max_tokens: int | None = None,
    api_version: str | None = None,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> QueryResult | QueryError:
    """Consulta de un solo turno (la función reutilizable de la lección)."""
    if not message.strip():
        return QueryError(error="El mensaje no puede estar vacío.", error_type="validation")
    return call_raw(
        [{"role": "user", "content": message}],
        model=model,
        system=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        api_version=api_version,
        client=client,
        settings=settings,
    )


def validate_history(messages: Sequence[MessageParam]) -> str | None:
    """Devuelve el motivo por el que el historial no es válido, o None si lo es."""
    if not messages:
        return "El historial está vacío."
    expected = "user"
    for index, message in enumerate(messages):
        role = message.get("role")
        if role != expected:
            return f"El mensaje {index} tiene rol {role!r}; se esperaba {expected!r}."
        content = message.get("content")
        if isinstance(content, str) and not content.strip():
            return f"El mensaje {index} está vacío."
        expected = "assistant" if role == "user" else "user"
    if messages[-1]["role"] != "user":
        return "El último mensaje debe ser del usuario."
    return None


class Conversation:
    """Conversación multiturno: el historial vive aquí y se reenvía completo en cada turno."""

    def __init__(
        self,
        system_prompt: str | None = None,
        *,
        history: Sequence[MessageParam] = (),
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        client: anthropic.Anthropic | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = client
        self._settings = settings
        self._history: list[MessageParam] = list(history)

    @property
    def history(self) -> list[MessageParam]:
        return list(self._history)

    def send(self, message: str) -> QueryResult | QueryError:
        candidate: list[MessageParam] = [*self._history, {"role": "user", "content": message}]
        problem = validate_history(candidate)
        if problem:
            return QueryError(error=problem, error_type="validation")

        result = call_raw(
            candidate,
            model=self.model,
            system=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            client=self._client,
            settings=self._settings,
        )
        # Solo se confirma el turno si la llamada fue bien: un fallo no altera el historial.
        if isinstance(result, QueryResult):
            self._history = [*candidate, {"role": "assistant", "content": result.content}]
        return result


def map_error(exc: anthropic.AnthropicError) -> QueryError:
    """Traduce una excepción del SDK a un error tipado (de la más específica a la más general)."""
    status_code = exc.status_code if isinstance(exc, anthropic.APIStatusError) else None
    error_type: ErrorType
    if isinstance(exc, anthropic.AuthenticationError):
        error_type = "authentication"
    elif isinstance(exc, anthropic.PermissionDeniedError):
        error_type = "permission"
    elif isinstance(exc, anthropic.NotFoundError):
        error_type = "not_found"
    elif isinstance(exc, anthropic.BadRequestError):
        error_type = "bad_request"
    elif isinstance(exc, anthropic.RateLimitError):
        error_type = "rate_limit"
    elif isinstance(exc, anthropic.APIStatusError):
        error_type = "server" if exc.status_code >= 500 else "api"
    elif isinstance(exc, anthropic.APITimeoutError):  # antes que su clase padre
        error_type = "timeout"
    elif isinstance(exc, anthropic.APIConnectionError):
        error_type = "connection"
    else:
        error_type = "api"
    message = exc.message if isinstance(exc, anthropic.APIError) else str(exc)
    return QueryError(error=message, error_type=error_type, status_code=status_code)


def _to_result(
    response: Message, requested_model: str, latency_ms: float, settings: Settings
) -> QueryResult | QueryError:
    # stop_reason se comprueba antes de leer el contenido.
    if response.stop_reason == "refusal":
        category = response.stop_details.category if response.stop_details else None
        logger.warning("El modelo declinó la petición (refusal, categoría %s)", category)
        return QueryError(
            error=f"El modelo declinó la petición (categoría: {category or 'no informada'}).",
            error_type="refusal",
        )

    # Por tipo de bloque, no por posición: puede haber bloques thinking antes del texto.
    text = "".join(block.text for block in response.content if block.type == "text")
    thinking = [block.thinking for block in response.content if block.type == "thinking"]
    if response.stop_reason == "max_tokens":
        logger.warning(
            "Respuesta truncada: se alcanzó max_tokens (%s tokens de salida)",
            response.usage.output_tokens,
        )

    usage = response.usage
    cache_creation = usage.cache_creation_input_tokens or 0
    cache_read = usage.cache_read_input_tokens or 0
    cost = calculate_cost(
        response.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        pricing=load_pricing(settings.pricing_json),
        fallback_model=requested_model,
    )
    return QueryResult(
        content=text,
        model=response.model,
        id=response.id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        stop_reason=response.stop_reason,
        stop_sequence=response.stop_sequence,
        cost_usd=cost,
        latency_ms=latency_ms,
        block_types=[block.type for block in response.content],
        thinking=thinking,
    )
