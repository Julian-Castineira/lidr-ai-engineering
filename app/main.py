"""Aplicación FastAPI: une configuración, cliente del LLM y routers.

Arranque: `uv run uvicorn app.main:app --reload` (documentación en /docs).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app import __version__
from app.config import AppEnv, LogLevel, Settings, get_settings
from app.context.examples import load_examples
from app.routers import estimations
from app.services.llm_service import build_async_client

# A nivel DEBUG estos loggers registran el cuerpo de las peticiones (la transcripción).
SDK_LOGGERS = ("anthropic", "httpx", "httpx2", "httpcore")

DESCRIPTION = """
Estimador de proyectos de software con arquitectura **CAG** (Cache-Augmented Generation):
recibe la transcripción de una reunión con un cliente y devuelve una estimación en Markdown
(tareas, horas, costes, equipo y duración) generada por un LLM con ejemplos y tarifas
precargados en el contexto. Sin base de datos ni retrieval.
"""


def configure_logging(level: LogLevel) -> None:
    """Nivel de la aplicación según LOG_LEVEL, sin bajar nunca el de los SDK de WARNING."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    logging.getLogger("app").setLevel(level)
    for name in SDK_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, logging.getLevelName(level)))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Misma fuente de configuración que los endpoints (incluidos los overrides de los tests).
    settings = app.dependency_overrides.get(get_settings, get_settings)()
    if settings.anthropic_api_key is None:
        raise RuntimeError(
            "Falta la variable ANTHROPIC_API_KEY: configúrala en .env para arrancar."
        )
    # Todos los roles de los ejemplos deben tener tarifa: mejor no arrancar que dar 500.
    load_examples(settings.estimation_hourly_rates)
    configure_logging(settings.log_level)

    app.state.llm_client = build_async_client(settings)
    try:
        yield
    finally:
        await app.state.llm_client.close()


app = FastAPI(
    title="Estimador CAG",
    description=DESCRIPTION,
    version=__version__,
    lifespan=lifespan,
)
# El prefijo de versión se define solo aquí, no en el router.
app.include_router(estimations.router, prefix="/api/v1")


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: AppEnv


@app.get("/health", response_model=HealthResponse, tags=["salud"])
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Estado del servicio. No consulta al LLM."""
    return HealthResponse(status="healthy", version=__version__, environment=settings.app_env)
