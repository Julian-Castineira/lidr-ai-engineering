"""Utilidades compartidas por los experimentos: impresión de resultados y coste acumulado."""

import io
import sys
from dataclasses import dataclass, field

from app.config import Settings
from app.services.schemas import QueryError, QueryResult

# En Windows, con la salida redirigida (Git Bash, pipes), Python usa cp1252 y las tildes
# salen corruptas; los experimentos escriben siempre en UTF-8.
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

ENV_HELP = (
    "Falta ANTHROPIC_API_KEY.\n"
    "  1. Copia .env.example a .env\n"
    "  2. Rellena ANTHROPIC_API_KEY con tu clave (https://platform.claude.com/settings/keys)\n"
    "  3. Vuelve a ejecutar el experimento.\n"
    "Los experimentos hacen llamadas reales a la API y tienen coste (céntimos)."
)


def ensure_api_key(settings: Settings) -> bool:
    """Imprime cómo configurar .env si falta la clave; devuelve si se puede continuar."""
    if settings.anthropic_api_key is None:
        print(ENV_HELP)
        return False
    return True


def header(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


@dataclass
class Tracker:
    """Acumula llamadas, tokens y coste de un experimento."""

    settings: Settings
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    unpriced_calls: int = 0
    errors: list[str] = field(default_factory=list)

    def show(
        self,
        label: str,
        result: QueryResult | QueryError,
        *,
        expected_error: bool = False,
        show_thinking: bool = False,
    ) -> None:
        self.calls += 1
        print(f"\n--- {label}")
        if isinstance(result, QueryError):
            self._show_error(result, expected_error)
            return

        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        if result.cost_usd is None:
            self.unpriced_calls += 1
        else:
            self.cost_usd += result.cost_usd

        if show_thinking:
            for index, thinking in enumerate(result.thinking, start=1):
                text = thinking.strip() or "(razonamiento no visible)"
                print(f"[razonamiento {index}]\n{text}\n")
        print(result.content or "(sin texto)")
        cost = "n/d" if result.cost_usd is None else f"{result.cost_usd:.6f} USD"
        stop = result.stop_reason
        if result.stop_sequence is not None:
            stop = f"{stop} ({result.stop_sequence!r})"
        print(
            f"[{result.model} | stop_reason={stop} | bloques={','.join(result.block_types)} | "
            f"tokens in/out={result.input_tokens}/{result.output_tokens} | "
            f"{result.latency_ms:.0f} ms | {cost}]"
        )
        if result.stop_reason == "max_tokens":
            print("AVISO: respuesta truncada por max_tokens.")

    def _show_error(self, error: QueryError, expected_error: bool) -> None:
        status = f" {error.status_code}" if error.status_code else ""
        prefix = "ERROR ESPERADO" if expected_error else "ERROR"
        print(f"{prefix} [{error.error_type}{status}]: {error.error}")
        if error.error_type == "not_found":
            print(
                f"AVISO: el modelo puede haberse retirado. Si es el legacy "
                f"({self.settings.legacy_model}), estos experimentos ya no son reproducibles; "
                "cambia LLM_LEGACY_MODEL en .env."
            )
        if not expected_error:
            self.errors.append(error.error_type)

    def summary(self) -> None:
        print(f"\n{'-' * 72}")
        print(
            f"Resumen: {self.calls} llamadas | tokens in/out = "
            f"{self.input_tokens}/{self.output_tokens} | coste total = {self.cost_usd:.6f} USD"
        )
        if self.unpriced_calls:
            print(f"({self.unpriced_calls} llamadas sin precio configurado no suman al coste)")
        if self.errors:
            print(f"Errores no esperados: {', '.join(self.errors)}")
