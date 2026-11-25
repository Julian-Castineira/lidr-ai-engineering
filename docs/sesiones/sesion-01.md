# Sesión 01 · LLMs y setup de entorno de trabajo

## Enunciado resumido

1. **Alta en los proveedores** (sin código): crear cuenta en Anthropic y OpenAI, activar facturación (mínimo 5 USD en el plan Build), fijar un límite de gasto y generar una API key. La clave no se escribe nunca en el código ni en el repositorio: vive en un `.env` excluido por `.gitignore`.
2. **Estructura de una llamada a la API de Anthropic**: Messages API, `system` como parámetro de primer nivel, `messages` con alternancia estricta `user`/`assistant`, API sin estado (el historial se reenvía), parámetros (`max_tokens`, `temperature`, `top_p`, `top_k`, `stop_sequences`, razonamiento extendido), estructura de la respuesta (`content`, `stop_reason`, `usage`), errores tipados del SDK y una función reutilizable `query_claude` que devuelve contenido, tokens y coste.

Esta entrega cubre el punto 2 como código. El punto 1 es un trámite manual en las consolas de los proveedores; solo deja como rastro en el repo el `.env.example` y la exclusión de `.env`. La entrega se centra en Anthropic: OpenAI queda fuera de alcance.

## Qué se ha hecho

Se fija el stack del repositorio y se crea la primera capa de la aplicación, pensada para que la Sesión 2 (servicio FastAPI) la consuma sin moverla.

| Pieza | Dónde | Qué hace |
|---|---|---|
| Configuración | `app/config.py`, `.env.example` | Pydantic Settings: API key como `SecretStr` (nunca se imprime), modelo, `temperature` y `effort` opcionales, `max_tokens`, timeout, reintentos, modelo legacy y override de precios. |
| Precios | `app/services/pricing.py` | Tabla con fecha de verificación y tramos por longitud de prompt; coste calculado con `Decimal`. Un modelo sin precio da `cost_usd = None` y un aviso, nunca un coste inventado. |
| Servicio LLM | `app/services/llm_service.py` | `query_claude` (la función de la lección), `call_raw` para parámetros avanzados, `Conversation` multiturno y mapeo de errores. Mide latencia, tokens (incluidos los de caché) y coste por llamada. |
| Contratos | `app/services/schemas.py` | `QueryResult` (el dict de la lección más latencia, caché, bloques y razonamiento) y `QueryError` con categoría y código HTTP. |
| Experimentos | `experiments/01…08` | Llamada básica, multiturno, `temperature`, `top_p`/`top_k`, `max_tokens`, `stop_sequences`, razonamiento y comparación de modelos. Cada uno imprime métricas y el coste total. |
| Tests | `tests/unit`, `tests/live` | 88 tests sin red ni clave (LLM simulado, reintentos con el cliente real del SDK sobre un transporte simulado) y un smoke test real opt-in. |

El diseño se especificó antes con OpenSpec: `openspec/changes/add-claude-api-client/` (propuesta, specs `llm-client` y `llm-experiments`, diseño y tareas).

## Decisiones

- **Modelo por defecto `claude-haiku-5-5` en lugar del de los apuntes** (`claude-haiku-4-5-20251001`). El de los apuntes es legacy y su fecha mínima de retirada (15-10-2026) ya ha pasado. Consecuencias que se han trasladado al código:
  - Haiku 5.5 rechaza (400) `temperature` ≠ 1, `top_p` ≠ 0,99, cualquier `top_k` y `thinking.budget_tokens`. Por eso `query_claude` ya no envía `temperature=0.3` por defecto (pasa a `None`), y los experimentos de muestreo y presupuesto fijo se ejecutan contra el modelo legacy configurable (`LLM_LEGACY_MODEL`) mientras exista, mostrando además el rechazo en Haiku 5.5.
  - Razona de forma adaptativa por defecto y ese razonamiento consume `max_tokens`: el límite por defecto sube de 1.000 a 4.096 y la profundidad se regula con `effort`.
  - Puede devolver bloques `thinking` antes del texto: el texto se extrae por tipo de bloque, nunca con `content[0].text`.
  - Puede declinar peticiones (`stop_reason: "refusal"`) sin fallback en servidor: se devuelve como `QueryError` de tipo `refusal`.
- **SDK `anthropic` 2.14 y versión de API `2026-10-21`**: el SDK envía por defecto `anthropic-version: 2026-10-21`, versión que **elimina `temperature`, `top_p` y `top_k` en todos los modelos** (400 «Extra inputs are not permitted» incluso en Haiku 4.5; detectado en la primera ejecución real). Siguiendo la guía oficial de migración, las llamadas al modelo legacy de los experimentos se envían con `anthropic-version: 2023-06-01` (`LLM_LEGACY_API_VERSION`); el resto de la aplicación usa la versión vigente. Como el SDK también quitó esos parámetros de su firma, se envían por `extra_body`. El SDK usa `httpx2` en lugar de `httpx`.
- **Errores devueltos, no lanzados**: se respeta el contrato `{"error": ...}` de la lección con un tipo (`QueryError`) que obliga a distinguir el fallo. Los reintentos ante 408/409/429/5xx y fallos de red los hace el SDK (`max_retries`); no se duplica esa lógica.
- **Paquete `app/` en la raíz y scripts en lugar de notebook**: coincide con la estructura prevista para la Sesión 2 y se puede testear y revisar en un PR.

### Precios verificados (documentación oficial de Anthropic, 25-11-2026)

| Modelo | Entrada | Salida | Escritura caché 5 min | Lectura caché |
|---|---|---|---|---|
| `claude-haiku-5-5` (prompt ≤ 100K tokens) | 0,10 USD/MTok | 0,50 USD/MTok | 0,125 USD/MTok | 0,01 USD/MTok |
| `claude-haiku-5-5` (prompt > 100K tokens) | 0,50 USD/MTok | 2,50 USD/MTok | 0,625 USD/MTok | 0,05 USD/MTok |
| `claude-haiku-4-5-20251001` | 1 USD/MTok | 5 USD/MTok | 1,25 USD/MTok | 0,10 USD/MTok |

## Cómo probarlo

```bash
uv sync
cp .env.example .env                 # rellenar ANTHROPIC_API_KEY

# Sin coste: tests, lint y tipos
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy app experiments

# Con coste (céntimos): smoke test y experimentos
uv run pytest -m live
uv run python -m experiments.01_basic
uv run python -m experiments.02_multiturn
uv run python -m experiments.03_temperature
uv run python -m experiments.04_sampling
uv run python -m experiments.05_max_tokens
uv run python -m experiments.06_stop_sequences
uv run python -m experiments.07_thinking
uv run python -m experiments.08_model_comparison
```

Coste estimado de una pasada completa (smoke test + ocho experimentos): menos de 0,10 USD.

## Verificación

- Sin red: 94 tests unitarios en verde; `ruff check`, `ruff format --check` y `mypy --strict` sin errores.
- Con la API real (25-11-2026): smoke test en verde y los ocho experimentos ejecutados sin errores no esperados. Coste total de todas las ejecuciones, incluida una primera pasada fallida por la versión de API: ≈ 0,01 USD.

### Extracto de resultados reales

| Experimento | Observación |
|---|---|
| 02 multiturno | El historial crece 1 → 3 → 5 mensajes y en el turno 3 el modelo recuerda el nombre dado en el turno 1. Los tokens de entrada suben (62 → 143 → 243) porque se reenvía todo. |
| 03 `temperature` (Haiku 4.5, API 2023-06-01) | Con 0: «Café Brújula» las tres veces. Con 1: «Brújula de Café», «Café Solsticio», «Café Lumina». En Haiku 5.5 con la API vigente: 400 «temperature: Extra inputs are not permitted». |
| 04 `top_p`/`top_k` | Funcionan en Haiku 4.5 con la API 2023-06-01; `temperature` + `top_p` a la vez: 400 «cannot both be specified»; `top_k` en Haiku 5.5: 400. |
| 05 `max_tokens` | Con 20 tokens: `stop_reason=max_tokens` y aviso de truncado. |
| 06 `stop_sequences` | Con `["7"]` la salida se corta en «1, 2, 3, 4, 5, 6, » y `stop_reason=stop_sequence ('7')`. |
| 07 razonamiento | Haiku 5.5 devuelve bloques `thinking,text` con resumen visible (`display: "summarized"`), ~2 s. Haiku 4.5 con `budget_tokens=1024`: 0,0013 USD frente a 0,0001 USD en Haiku 5.5. Rechazos esperados: thinking con `temperature` 0,5 en 4.5 y `budget_tokens` en 5.5. |
| 08 comparación | Mismo prompt: Haiku 5.5 38/300 tokens y 0,00015 USD; Haiku 4.5 28/171 tokens y 0,00088 USD. Haiku 5.5 cuenta más tokens de entrada (nuevo tokenizador), pero cuesta ~6 veces menos. |
