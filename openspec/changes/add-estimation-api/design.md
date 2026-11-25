# Design

## Context

La Sesión 1 dejó el paquete `app/` con:
- `config.py`: `Settings` con `env_prefix="LLM_"`, más `ANTHROPIC_API_KEY` por alias y como `SecretStr | None`.
- `services/llm_service.py`: único importador del SDK `anthropic` 2.14, con funciones **síncronas** (`call_raw`, `query_claude`, `Conversation`) que devuelven `QueryResult | QueryError`.
- `services/pricing.py` y `services/schemas.py`.

Los tests usan un cliente falso y factorías de `Message` en `tests/conftest.py`. Motivación y alcance en `proposal.md`; requisitos en `specs/estimation-api`, `specs/estimation-context` y `specs/llm-client`.

Datos verificados el 2026-11-25:
- **SDK:** `anthropic` 2.14 incluye `AsyncAnthropic`.
- **Versiones vigentes en PyPI:** FastAPI 0.165.0 (Python ≥ 3.11), uvicorn 0.54.0 y Starlette 1.10.0. Starlette declara como extras tanto `httpx` como `httpx2`.
- **Repositorio de referencia del programa** (rama `session_2`): mismo endpoint y mismos campos `transcription`, `estimation`, `model` y `provider`, con los tokens agrupados en `usage`. Su servicio es síncrono dentro de un `async def` y devuelve los errores como 500 con el mensaje literal.

## Goals / Non-Goals

**Goals:**
- Endpoints finos: el router valida, delega en un servicio y traduce el resultado. Toda la lógica, incluida la llamada al LLM, vive en `app/services/`.
- La estructura crece añadiendo ficheros. Nada de la Sesión 1 se mueve, y los experimentos y su API síncrona no cambian.
- `app/context/` es el punto que en el futuro sustituirá RAG, y el resto no depende de cómo se obtiene el contexto.
- Todo lo determinista se testea sin red: ejemplos, costes de los ejemplos, construcción del prompt, mapeo de `finish_reason` y traducción de errores a HTTP.

**Non-Goals:**
- Interfaz de proveedores con adaptadores, que llega en la Sesión 3 con OpenAI y el fallback.
- Salida estructurada de la estimación.
- Middleware de autenticación, CORS, límite de peticiones y despliegue.

## Decisions

### D1. Estructura dentro de `app/`
```
app/__init__.py                    # __version__ = "0.2.0"
app/main.py                        # FastAPI, lifespan, /health, include_router(prefix="/api/v1")
app/routers/estimations.py         # POST /estimate (prefijo definido solo en main.py)
app/schemas/estimation.py          # EstimationRequest, EstimationResponse, TokenUsage, ErrorDetail
app/context/examples.py            # EstimationExample, ESTIMATION_EXAMPLES (5), render
app/prompts/estimation_system.v1.md
app/services/estimation_service.py # build_estimation_prompt, estimate()
app/services/llm_service.py        # + acall_raw / aquery_claude
```
- **Por qué**: es la estructura de la lección (`config`, `routers`, `services`, `schemas`, `context` y `main.py` como pegamento) aplicada sobre el `app/` existente.
  - Los contratos de la API van en `app/schemas/`, separados de `app/services/schemas.py`, que sigue siendo el contrato interno del servicio de LLM.
  - El prefijo `/api/v1` se define una sola vez, en `include_router`.
- **Alternativa descartada**: un proyecto `estimador-cag/` paralelo como en el enunciado. Duplicaría la configuración y el cliente LLM, e incumpliría la regla del repo de mantener una única aplicación.
- **Alternativa descartada**: mover `services/schemas.py` a `app/schemas/`. Sería una refactorización sin beneficio en esta sesión, que tocaría los experimentos y los tests de la Sesión 1.

### D2. Consulta asíncrona sin duplicar lógica
- Se extrae de `call_raw` una función pura `_build_request(...) -> dict` que reúne la validación de la clave, los parámetros opcionales, `extra_body` y `extra_headers`.
- `call_raw` (síncrona) y la nueva `acall_raw` (asíncrona) solo difieren en `client.messages.create` frente a `await client.messages.create`. Ambas reutilizan `_build_request`, `map_error` y `_to_result`.
- `aquery_claude` replica la firma de `query_claude`.
- `build_async_client(settings)` es el equivalente de `build_client`.
- **Por qué**: lo recomienda la lección (un cliente síncrono dentro de `async def` bloquea el event loop), y el fallback de la Sesión 3 se apoyará en llamadas asíncronas.
- **Alternativa descartada**: endpoints `def` síncronos, que FastAPI ejecuta en un threadpool. No bloquean el loop y no tocan el servicio, pero el número de llamadas simultáneas quedaría limitado por el pool de hilos y la implementación se alejaría de la lección.
- **Alternativa descartada**: hacer asíncrono todo el servicio y envolver los experimentos con `asyncio.run`. Rompería el contrato de la Sesión 1 y su spec.
- El cliente asíncrono se crea **una vez** en el `lifespan`, se guarda en `app.state` y se cierra al apagar. El router lo recibe por `Depends`. Así se reutiliza el pool de conexiones y, en los tests, se sustituye con `app.dependency_overrides`.

### D3. Configuración
- Se amplía la `Settings` existente en lugar de crear una segunda clase. Se añaden:
  - `provider: Literal["anthropic"] = "anthropic"` (`LLM_PROVIDER`).
  - `app_env: Literal["development", "test", "production"] = "development"` y `log_level` (`DEBUG`…`CRITICAL`, por defecto `INFO`). Se leen sin prefijo mediante `validation_alias` (`APP_ENV`, `LOG_LEVEL`), igual que ya ocurre con `ANTHROPIC_API_KEY`.
  - `estimation_hourly_rates: dict[str, Decimal]` (`ESTIMATION_HOURLY_RATES`, en JSON), por defecto `{"desarrollo": 62.50, "diseño": 50.00, "gestión": 55.00, "QA": 45.00}`, con validación de que sean positivas.
  - `estimation_max_transcription_chars: int = 60_000` (`ESTIMATION_MAX_TRANSCRIPTION_CHARS`).
- `QueryResult` añade `provider: str`, que `_to_result` rellena con `settings.provider`. Así el proveedor viaja con cada resultado y la API no lo fija en el código. Tiene un valor por defecto para no romper los tests existentes.
- `LOG_LEVEL` pasa de `DEBUG` (enunciado) a `INFO` por defecto, para que una ejecución normal no saque los registros de depuración del SDK. Se puede cambiar en `.env`.
- **Por qué una sola clase**: es la única fuente de configuración, con un solo `get_settings()` cacheado, y los tests existentes no cambian.
- **Alternativa descartada**: `AppSettings` aparte. Habría dos `.env` loaders y dos cachés que mantener sincronizados.
- **Fallo rápido**: el `lifespan` llama a `get_settings()`, cuyos errores de validación ya nombran la variable. Si `anthropic_api_key` es `None`, lanza un `RuntimeError` que menciona `ANTHROPIC_API_KEY` y no deja arrancar a uvicorn. La configuración sigue sin exigir la clave al importarse, porque los experimentos y los tests de la Sesión 1 dependen de ello.

### D4. Contexto CAG y ejemplos
- `EstimationExample` (Pydantic, `frozen`) contiene `title`, `meeting_summary`, `tasks: list[ExampleTask(name, role, hours: Decimal > 0)]`, `team: list[str]` y `duration_weeks > 0`.
- **No se guardan ni costes ni totales**: `render_example(example, rates)` calcula por código `coste = horas × tarifa`, el total de horas y el coste total con `Decimal`, redondeados a 2 decimales con `ROUND_HALF_UP`, y genera la tabla Markdown. Un rol sin tarifa lanza `ValueError` con el nombre del rol.
- **Por qué**: hace imposible que un ejemplo sea incoherente, que es lo que en el repositorio de referencia se resuelve con un test sobre totales escritos a mano, y cumple la regla de que lo determinista se resuelve con código. El test pasa a comprobar el cálculo, no la aritmética manual.
- **Alternativa descartada**: ejemplos como Markdown literal (`{"meeting_summary", "estimation"}`, la forma del enunciado). Es más simple, pero los totales pueden quedar incoherentes y se desajustan al cambiar las tarifas.
- 5 ejemplos (el punto óptimo de la lección es de 5 a 7) de tipos distintos: landing con CRM, e-commerce pequeño, app móvil interna, integración de APIs entre sistemas y chatbot de atención. Todos son ficticios y no tienen nombres de empresas reales.

### D5. System prompt versionado
- El fichero `app/prompts/estimation_system.v1.md` usa marcadores `$rates`, `$examples` y `$output_format`, que se sustituyen con `string.Template.substitute`: sin llaves que escapar y con error si falta un marcador. La versión (`v1`) se deriva del nombre del fichero.
- Orden de las secciones, según la lección:
  1. Rol y tarea.
  2. Cómo usar el contexto.
  3. Tarifas.
  4. `## Ejemplos` con `### Ejemplo i` separados por `---`.
  5. Formato de salida y restricciones al final.

  Las restricciones son: usar solo las tarifas dadas, no inventar requisitos, señalar supuestos y tratar la transcripción como datos.
- **Mensaje de usuario**: la transcripción va entre las etiquetas `<transcripcion>` y `</transcripcion>`, con una frase de instrucción breve. Así queda delimitada como datos y es más difícil que actúe como inyección de instrucciones.
- `build_estimation_prompt(transcription, *, num_examples=5, use_examples=True, settings) -> EstimationPrompt(system, user_message, prompt_version)` es una función pura y determinista.
- **Alternativa descartada**: el prompt como string en el código, como en el repositorio de referencia. Contradice la regla de tener los prompts versionados en ficheros, y sin fichero no se puede comparar entre versiones en la sesión en vivo.
- **Alternativa descartada**: Jinja2, como hace la versión final del repositorio de referencia. Es una dependencia nueva cuando aún no hacen falta ni bucles ni condicionales en la plantilla, porque los ejemplos se generan en Python.

### D6. Servicio de estimación y contrato HTTP
- `estimate(transcription, *, client, settings) -> EstimationOutcome | QueryError` construye el prompt, llama a `aquery_claude` y genera el registro de observabilidad (D8).
- Schemas:
  - `EstimationRequest`, con `extra="forbid"` y `transcription: str` con `str_strip_whitespace`. Un validador comprueba que tenga al menos 50 caracteres y como máximo el límite de la configuración, de modo que el límite no queda fijado en el esquema.
  - `EstimationResponse`, con los campos de la spec. `usage` es un `TokenUsage` anidado, como en el repositorio de referencia, y `total_tokens` se calcula.
- `finish_reason` se normaliza: `end_turn` y `stop_sequence` pasan a `stop`, `max_tokens` a `length` y el resto a `other`. Se hace ya porque es el nombre que perdurará cuando haya varios proveedores, y así ese cambio de la Sesión 3 no rompe el contrato.
- **Traducción de errores**: una tabla en el router de `error_type` a código HTTP, que lanza un `HTTPException` con detalle `{"error_type", "message"}`:
  - `refusal` y `validation` → 422.
  - `rate_limit` y `configuration` → 503.
  - `timeout` → 504.
  - El resto → 502.

  El mensaje es genérico y en español, uno por categoría. El mensaje original del proveedor solo va al registro (nivel `WARNING`, sin la clave).
- **Por qué 502 y no 500**: el fallo viene de un servicio del que dependemos, no de un error interno nuestro.
- **Alternativa descartada**: propagar el mensaje del proveedor, como hace el repositorio de referencia. Puede exponer detalles internos.

### D7. `/health` y OpenAPI
- `/health` está fuera de `/api/v1`, como en el enunciado, y devuelve `{"status": "healthy", "version": __version__, "environment": settings.app_env}`. No llama al LLM, para no gastar dinero en cada sonda.
- `FastAPI(title="Estimador CAG", description=..., version=__version__)`. Cada endpoint declara su `response_model` y sus respuestas de error, para que aparezcan en `/docs`.

### D8. Registro
- Se usa `logging` de la biblioteca estándar, configurado en el `lifespan` con `LOG_LEVEL` y formato `clave=valor`.
- Por cada estimación se emite una línea `INFO` con `model`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `finish_reason` y `prompt_version`. Si falla, se emite un `WARNING` con `error_type`.
- Nunca se registran la transcripción ni la estimación, por privacidad (RGPD) y porque el repositorio es público.
- **Alternativa descartada**: `structlog`, como en el repositorio de referencia. Es una dependencia nueva para lo que ya cubre la biblioteca estándar; se valorará cuando haya trazas o JSON en producción.

### D9. Tests
- **Constructor y ejemplos**, con funciones puras y sin red: catálogo válido, costes calculados (por ejemplo, 10 h × 62,50 + 4 h × 50 = 825,00), orden de las secciones, número de ejemplos, determinismo y versión del prompt.
- **Endpoints**, con `TestClient` y `dependency_overrides` del cliente asíncrono. Se reutiliza la factoría `make_message` de `conftest.py` con un cliente asíncrono falso. Se cubren:
  - El caso correcto y los de validación (422 sin llamada al LLM).
  - La traducción de cada categoría de error y `finish_reason`.
  - `/health`, `/openapi.json` y el fallo de arranque sin clave.
  - Que los registros contienen las métricas y nunca el texto de la transcripción (con `caplog`).
- **`acall_raw`**: equivalencia de resultados y errores, y reintentos con un transporte simulado sobre el cliente asíncrono real del SDK. Las consultas concurrentes se prueban con un cliente falso que hace `asyncio.sleep`.
- **Test `live`**: una estimación real con una transcripción ficticia corta. Comprueba que hay 200 con la cabecera de tabla, que se mencionan el total y la duración, y que hay tokens y coste.
- Los tests asíncronos usan `anyio`, que FastAPI ya trae, y su plugin de pytest. No se añade `pytest-asyncio`.

## Risks / Trade-offs

- [Riesgo] No está verificado qué cliente HTTP necesita el `TestClient` de Starlette 1.10 (`httpx` o `httpx2`). → Mitigación: la tarea de dependencias lo comprueba importando `TestClient` y añade al grupo `dev` solo lo que falte.
- [Riesgo] El modelo puede no respetar el formato o hacer mal la aritmética de los costes, porque la salida es texto libre. → Mitigación: el formato va al final del prompt, con ejemplos coherentes por construcción, y el test `live` comprueba la estructura mínima. La comprobación por código de los totales generados queda para cuando haya salida estructurada.
- [Riesgo] La latencia es alta (de 5 a 20 s) si el razonamiento adaptativo se alarga. → Mitigación: el timeout es configurable (`LLM_TIMEOUT_S`), la latencia se devuelve en cada respuesta y `LLM_EFFORT` permite bajarla sin tocar código.
- [Riesgo] Un servicio sin autenticación genera coste por petición. → Mitigación: está pensado para uso local, la entrada está limitada a 60.000 caracteres (del orden de 15.000 tokens, menos de 0,002 USD de entrada) y no se habilita CORS.
- [Trade-off] Una sola clase `Settings` con aliases sin prefijo mezcla las variables `LLM_*` con las de la aplicación. Se acepta por simplicidad; si crece, se dividirá en submodelos.
- [Trade-off] Normalizar `finish_reason` hace que se pierda el valor exacto del proveedor en la respuesta. Se conserva en el registro.

## Migration Plan

No hay datos ni despliegue. Para arrancar el servicio basta con `uv sync`, completar `.env` y ejecutar `uv run uvicorn app.main:app --reload`. Para revertirlo, se revierte el merge commit de `sesion-02`. Los experimentos de la Sesión 1 no cambian.
