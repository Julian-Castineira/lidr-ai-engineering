# Design

## Context

Repositorio sin código: solo `README.md`, `CLAUDE.md`, `.gitignore` (plantilla Python que ya ignora `.env`, `.venv`, `.pytest_cache`, `.ruff_cache`) y `openspec/`. Este cambio fija el stack del repo. La Sesión 2 prevé un servicio FastAPI con `app/{main.py, config.py, routers/estimations.py, services/llm_service.py, context/examples.py}`; la estructura de esta sesión debe ser el embrión de esa, no un proyecto paralelo. Motivación y alcance en `proposal.md`; requisitos en `specs/llm-client` y `specs/llm-experiments`.

Datos del proveedor verificados en la documentación oficial de Anthropic el 2026-11-25:
- `claude-haiku-5-5`, **modelo por defecto**: 0,10/0,50 USD/MTok hasta 100K tokens de prompt y 0,50/2,50 por encima. Thinking adaptativo activo por defecto y descontado de `max_tokens`; `effort` por defecto `medium`. Devuelve 400 con `temperature` ≠ 1, `top_p` ≠ 0,99, cualquier `top_k`, `budget_tokens` y prefill. Puede responder con `stop_reason: "refusal"` sin fallback en servidor. Con el display por defecto, los bloques `thinking` llegan vacíos.
- `claude-haiku-4-5-20251001`, **modelo legacy, solo para experimentos** (alias `claude-haiku-4-5`): «Active (legacy)», 1/5 USD/MTok, 200K de contexto. Admite `temperature`/`top_p`/`top_k` y `thinking.budget_tokens`.

## Goals / Non-Goals

**Goals:**
- Un único punto de acceso a Claude (`app/services/llm_service.py`) que la Sesión 2 inyecte en sus routers sin cambios de contrato.
- Toda la lógica determinista (coste, validación de historial, extracción de texto) en funciones puras testeables sin red.
- Experimentos que reutilizan el servicio en lugar de llamar al SDK directamente, salvo donde el propio experimento consiste en pasar parámetros que el servicio no expone.

**Non-Goals:**
- Abstracción multi-proveedor completa (interfaz + adaptadores): con un solo proveedor sería especulativa. Se aísla el SDK en el servicio para que añadirla después sea local.
- Logging estructurado/OpenTelemetry: se usa `logging` estándar; la observabilidad formal llega con la API.

## Decisions

### D1. Estructura: paquete `app/` en la raíz con `uv`
```
pyproject.toml  uv.lock  .python-version  .env.example
app/__init__.py
app/config.py                 # Settings (pydantic-settings)
app/services/llm_service.py   # query_claude, Conversation, mapeo de errores
app/services/pricing.py       # tabla de precios y cálculo de coste (puro)
app/services/schemas.py       # QueryResult, QueryError (Pydantic)
experiments/01_basic.py … 08_model_comparison.py, experiments/_common.py
tests/unit/…  tests/live/test_smoke.py  tests/conftest.py
```
- **Por qué**: coincide con la estructura prevista para la Sesión 2 (`app/config.py`, `app/services/llm_service.py`), así la siguiente sesión añade `main.py` y `routers/` sin mover nada.
- **Alternativa descartada**: layout `src/<paquete>/` — más correcto para librerías publicables, pero obligaría a renombrar o reestructurar en la Sesión 2 y el código no se publica en PyPI.
- **Alternativa descartada**: notebook Jupyter como en el curso — no testeable ni revisable en PR con facilidad; los experimentos como scripts sí lo son.
- `pyproject.toml` declara el proyecto sin build backend (aplicación, no librería) con `tool.uv` en modo `package = false`; los tests importan `app` desde la raíz con `pythonpath = ["."]` en la config de pytest.

### D2. Configuración con `pydantic-settings`
- `Settings` con prefijo vacío para `ANTHROPIC_API_KEY` (nombre estándar que también lee el SDK) y prefijo `LLM_` para el resto: `LLM_MODEL` (por defecto `claude-haiku-5-5`), `LLM_TEMPERATURE` (0–1, opcional, sin valor por defecto), `LLM_EFFORT` (`low|medium|high|xhigh|max`, opcional, sin valor por defecto), `LLM_MAX_TOKENS` (≥1, por defecto 4096), `LLM_TIMEOUT_S` (por defecto 60), `LLM_MAX_RETRIES` (por defecto 2) y `LLM_LEGACY_MODEL` (por defecto `claude-haiku-4-5-20251001`, solo para experimentos).
- **Por qué `max_tokens` 4096 y no los 1000 de la lección**: en Haiku 5.5 el razonamiento adaptativo consume `max_tokens`, y con 1000 una respuesta media puede quedarse sin texto. El coste añadido en el peor caso es de 0,0015 USD por llamada. **Alternativa descartada**: desactivar el thinking (`{"type": "disabled"}`) para mantener 1000. La documentación recomienda bajar `effort` en vez de desactivarlo, y desactivarlo ocultaría el comportamiento real del modelo vigente.
- API key como `SecretStr | None`: su `repr` enmascara el valor; la ausencia se detecta al consultar (error tipado `configuration`), no al importar, para que tests y `--help` funcionen sin clave.
- La tabla de precios vive en `app/services/pricing.py` como constante tipada con fecha de verificación, con override opcional por `LLM_PRICING_JSON`. **Por qué en código y no solo en `.env`**: es una tabla anidada con tramos que en una variable de entorno sería ilegible; sigue siendo configuración (un solo sitio, sin lógica) y el override permite cambiarla sin tocar código.
- **Alternativa descartada**: `python-dotenv` + `os.getenv` — sin validación de tipos ni rangos; `pydantic-settings` ya lee `.env` y valida.

### D3. Contrato de `query_claude`
```python
def query_claude(message: str, system_prompt: str | None = None,
                 model: str | None = None, temperature: float | None = None,
                 *, max_tokens: int | None = None, client: Anthropic | None = None,
                 settings: Settings | None = None) -> QueryResult | QueryError
```
- Los cuatro primeros parámetros respetan la firma de la lección; los de solo palabra clave permiten inyectar cliente y configuración en tests y en la Sesión 2 (FastAPI `Depends`).
- `QueryResult` (Pydantic): `content, model, id, input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, stop_reason, cost_usd: float | None, latency_ms: float`. `model_dump()` da el dict de la lección más los campos extra.
- `QueryError` (Pydantic): `error: str, error_type: Literal["configuration","validation","authentication","permission","not_found","bad_request","rate_limit","server","timeout","connection","refusal","api"], status_code: int | None`.
- **Por qué devolver el error en vez de lanzarlo**: es el contrato de la lección y facilita los experimentos; el tipo unión obliga al llamador a distinguir. **Alternativa descartada**: excepciones propias — más idiomático en Python, pero rompe el contrato de la lección; la Sesión 2 podrá mapear `QueryError.error_type` a códigos HTTP en el router.
- `temperature` y `effort` se envían solo si el llamador o la configuración los fijan. El SDK instalado (`anthropic` 2.14) retiró `temperature`, `top_p` y `top_k` de la firma de `messages.create` (siguen existiendo en la API), así que se envían por `extra_body`, el mecanismo documentado por el SDK para ello. `temperature` pasa de 0,3 por defecto (lección) a `None`, porque el modelo por defecto rechaza cualquier valor distinto de 1. `effort` va en `output_config={"effort": ...}`. No se mantiene una lista de capacidades por modelo: el 400 del proveedor es la fuente de verdad y se devuelve como `bad_request`. **Alternativa descartada**: una tabla de capacidades por modelo que filtre parámetros en silencio. Ocultaría errores de uso y habría que mantenerla con cada modelo nuevo.

### D4. Extracción de texto por tipo de bloque
Se concatenan los bloques con `type == "text"`; nunca `response.content[0].text`. **Por qué**: con thinking (Haiku 4.5 con presupuesto, Haiku 5.5 por defecto) el primer bloque puede ser `thinking`. Los bloques de razonamiento se exponen aparte solo en el experimento de thinking.

### D5. Cálculo de coste determinista
`cost_usd = (input·p_in + output·p_out + cache_write·p_cw + cache_read·p_cr) / 1e6`, con tramo elegido por `input + cache_write + cache_read` frente al umbral del modelo (100.000 en Haiku 5.5). Se resuelve el precio por `response.model` (el modelo realmente servido) y, si no está, por el modelo pedido; si ninguno está, `None` + aviso. Se usa `Decimal` internamente y se redondea a 6 decimales al devolver, para evitar errores de coma flotante en los tests.

### D6. Errores y reintentos
- Cliente creado con `max_retries` y `timeout` de la configuración; **no** se añade capa de reintento propia (el SDK ya reintenta conexión, 408, 409, 429 y ≥500 con backoff y respeta `retry-after`). Así se cumple «sin duplicar los reintentos del SDK».
- Mapeo en cadena de más específica a más general: `AuthenticationError`→`authentication`, `PermissionDeniedError`→`permission`, `NotFoundError`→`not_found`, `BadRequestError`→`bad_request`, `RateLimitError`→`rate_limit`, `InternalServerError`/`APIStatusError` con status ≥500 (incluye 529)→`server`, resto de `APIStatusError`→`api`, `APITimeoutError`→`timeout` (antes que su padre), `APIConnectionError`→`connection`.
- El mensaje del error se toma de la excepción del SDK; se comprueba en tests que no contiene la API key.
- La negativa del modelo no es una excepción, sino un HTTP 200 con `stop_reason == "refusal"`. Se comprueba `stop_reason` antes de leer `content` y se devuelve `QueryError(error_type="refusal")` con `stop_details.category` en el mensaje (con guarda, porque puede ser nulo). No se reintenta ni se usa el parámetro `fallbacks`, que Haiku 5.5 no admite.

### D7. Multiturno
Clase `Conversation` (historial en memoria del proceso) con `send(message) -> QueryResult | QueryError`: añade el turno de usuario a una copia, llama, y solo si hay éxito confirma usuario + asistente en el historial. La validación de alternancia es una función pura reutilizable por la Sesión 2 cuando el historial llegue del cliente HTTP. **Alternativa descartada**: persistir historial — fuera de alcance; la API seguirá siendo stateless.

### D8. Experimentos
Scripts `experiments/NN_<tema>.py` ejecutables con `uv run python -m experiments.NN_<tema>`. Los experimentos de parámetros que el servicio no expone (`top_p`, `top_k`, `stop_sequences`, `thinking`) usan un helper `call_raw(**params)` en `llm_service` que comparte cliente, medición de latencia, coste y mapeo de errores con `query_claude`, para no duplicar lógica. Un `_common.py` imprime resultados y acumula el coste total. Todos los `max_tokens` ≤ 2.048.

Reparto de modelos:

| Experimento | Modelo por defecto (`claude-haiku-5-5`) | Modelo legacy (`LLM_LEGACY_MODEL`) |
|---|---|---|
| 01 básico, 02 multiturno, 05 `max_tokens`, 06 `stop_sequences` | sí | — |
| 03 `temperature`, 04 `top_p`/`top_k` | solo para mostrar el 400 | ejecución real con API `2023-06-01` |
| 07 razonamiento | adaptativo, `effort` `low` y `high`, `display: "summarized"` para ver el resumen | `budget_tokens=1024`, `max_tokens=2048` |
| 08 comparación | mismo prompt, con y sin `temperature` | mismo prompt |

- **Por qué mantener el modelo legacy en experimentos**: es el único Haiku disponible donde se observa el efecto real de los parámetros de muestreo y del presupuesto fijo de la lección. **Alternativa descartada**: hacerlo todo con Haiku 5.5 y mostrar solo los rechazos. Es más simple, pero pierde el objetivo didáctico. Si el modelo legacy se retira, `_common.py` reconoce el `not_found` de ese modelo e imprime un aviso en vez de fallar.
- En el experimento 05 con Haiku 5.5 se usa `effort` `low` y un `max_tokens` bajo, que puede cortar en mitad del razonamiento. La salida muestra entonces `stop_reason` `max_tokens` sin texto, que es en sí un resultado didáctico.

### D10. Versión de API para el modelo legacy
El SDK 2.x fija `anthropic-version: 2026-10-21`, versión que elimina `temperature`, `top_p` y `top_k` en todos los modelos (comprobado en la ejecución real: 400 «Extra inputs are not permitted» también en Haiku 4.5). La guía oficial de migración indica que las peticiones que dependen de valores no por defecto se mantengan en `2023-06-01`.
- `call_raw` y `query_claude` aceptan `api_version` (solo palabra clave), que se envía como `extra_headers={"anthropic-version": ...}`; sin él no se toca la cabecera del SDK.
- `Settings.legacy_api_version` (`LLM_LEGACY_API_VERSION`, por defecto `2023-06-01`). Los experimentos la pasan en **todas** las llamadas al modelo legacy, para que sus rechazos se deban a las reglas del modelo y no a la versión.
- **Alternativa descartada**: usar solo la versión vigente y mostrar el rechazo. Más simple y alineado con la API actual, pero pierde el efecto observable de los parámetros de la lección.
- **Alternativa descartada**: fijar `2023-06-01` en todo el cliente. Afectaría al modelo por defecto y a la Sesión 2 sin necesidad.

### D9. Tests
- `pytest` con cliente falso inyectado (objeto con `messages.create` que devuelve un `Message` construido con los tipos del SDK o lanza sus excepciones). Para las excepciones del SDK se construye un `httpx2.Response` falso (`httpx2` es dependencia transitiva del SDK).
- Reintentos (requisito «Reintentos acotados»): se prueban con un `Anthropic(http_client=httpx2.Client(transport=httpx2.MockTransport(...)))` real (el SDK 2.x usa `httpx2`, fork compatible de `httpx`), que ejercita los reintentos nativos del SDK sin red y permite contar las peticiones. **Alternativa descartada**: `respx` — haría lo mismo con una dependencia más. Coste aceptado: ~1 s de backoff del SDK por test de reintento.
- Smoke test real en `tests/live/` contra el modelo por defecto con `effort` `low` y `max_tokens=256`, para que el razonamiento no agote el límite; marcador `live`, excluido por defecto con `addopts = "-m 'not live'"`; se activa con `uv run pytest -m live` y requiere `ANTHROPIC_API_KEY` (si falta, `skip`).
- Calidad: `ruff check`, `ruff format --check` y `mypy app` (si se aprueba `mypy`).

## Risks / Trade-offs

- [Haiku 4.5 legacy con fecha mínima de retirada ya pasada] → solo lo usan los experimentos 03, 04, 07 y 08; es configurable (`LLM_LEGACY_MODEL`) y su retirada se muestra como aviso, sin romper la suite ni el servicio.
- [Razonamiento por defecto que encarece y alarga las respuestas] → `max_tokens` 4096 acotado, `effort` configurable y tokens/latencia medidos por llamada.
- [Negativas del clasificador de seguridad en peticiones legítimas] → error tipado `refusal` con su categoría; no hay fallback en servidor para Haiku 5.5, así que la decisión (reformular o cambiar de modelo) queda en el llamador.
- [Precios desactualizados] → constante con fecha de verificación y override por entorno; un modelo desconocido da `cost_usd=None` en vez de un coste falso.
- [Tests acoplados a la forma interna del SDK (`Message`, excepciones)] → se construyen con los tipos públicos del SDK; una actualización mayor del SDK puede requerir ajustar fixtures, pero no el contrato.
- [Los experimentos gastan dinero real] → `max_tokens` acotados, coste total impreso, coste estimado < 0,10 USD por pasada completa documentado en la memoria.
- [Fijar `LLM_TEMPERATURE` con el modelo por defecto provoca 400 en todas las llamadas] → sin valor por defecto, y documentado en `.env.example` que solo aplica a modelos que lo admiten.

## Migration Plan

Sin datos ni despliegue. Instalación: `uv sync`, copiar `.env.example` a `.env` y rellenar la clave. Rollback: no fusionar el PR o revertir el merge commit.

## Open Questions (resueltas)

- Resuelta: `uv add` instaló `anthropic` 2.14.0 (con `httpx2`), `pydantic-settings` 2.16.3, `pytest` 9.2, `ruff` 0.17.6 y `mypy` 2.4.1, fijados en `uv.lock`. Cambios respecto al diseño inicial: parámetros de muestreo por `extra_body` (D3) y `httpx2` en los tests (D9).
