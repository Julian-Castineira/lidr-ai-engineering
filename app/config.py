"""Configuración de la aplicación, leída de variables de entorno y de `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        # `LLM_TEMPERATURE=` en .env significa «no definida», no cadena vacía.
        env_ignore_empty=True,
        extra="ignore",
    )

    # Nombre estándar de la variable, sin prefijo: es el que también lee el SDK.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    model: str = "claude-haiku-5-5"
    # Sin valor por defecto: claude-haiku-5-5 rechaza cualquier temperatura distinta de 1.
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    effort: Effort | None = None
    max_tokens: int = Field(default=4096, ge=1)
    timeout_s: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    # Solo para los experimentos de parámetros que el modelo por defecto no admite.
    legacy_model: str = "claude-haiku-4-5-20251001"
    # La versión de API del SDK 2.x (2026-10-21) elimina temperature/top_p/top_k en todos
    # los modelos; las llamadas al modelo legacy de los experimentos usan esta otra.
    legacy_api_version: str = "2023-06-01"
    # Override opcional de la tabla de precios (JSON con la misma forma que pricing.PRICING).
    pricing_json: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
