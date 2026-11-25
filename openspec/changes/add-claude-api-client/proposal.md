# Proposal

## Why

La Sesión 1 del Máster («LLMs y setup de entorno de trabajo») pide dominar la estructura de una llamada a la Messages API de Anthropic: parámetros, respuesta, errores y coste. El repositorio aún no tiene código ni stack, y la Sesión 2 construirá sobre él un servicio FastAPI (`estimador-cag`) cuya capa de servicio necesita un cliente de LLM fiable, configurable y observable.

Para quién: el profesor, que evalúa la entrega de forma aislada, y el propio autor, que reutilizará esta base en las sesiones siguientes. Objetivo: dejar fijado el stack del repo y una capa de acceso a Claude probada (con tests y sin depender de la red) que la Sesión 2 consuma sin reescribirla.

## What Changes

- Se fija el stack de la aplicación: Python 3.11+ gestionado con `uv`, `pyproject.toml` en la raíz, paquete `app/` (la misma raíz que usará la Sesión 2), `pytest` y `ruff`.
- Configuración tipada con Pydantic Settings leída de variables de entorno y `.env` (`ANTHROPIC_API_KEY`, modelo, temperatura opcional, nivel de `effort` opcional, `max_tokens`, timeout, reintentos y modelo legacy para experimentos); `.env.example` documentado sin valores reales. La clave nunca se registra ni se imprime.
- Modelo por defecto `claude-haiku-5-5`, el Haiku vigente, en lugar del `claude-haiku-4-5-20251001` de los apuntes (legacy y con retirada pendiente).
- Servicio `app/services/llm_service.py` con la función reutilizable `query_claude(message, system_prompt=None, model=None, temperature=None)`:
  - llamada a `client.messages.create` con `system` de primer nivel y `max_tokens` obligatorio; `temperature` y `effort` solo se envían si se fijan, porque Haiku 5.5 rechaza los valores de muestreo no por defecto;
  - extracción del texto por tipo de bloque (no por posición, ya que Haiku 5.5 razona por defecto y puede devolver bloques `thinking` antes del texto), aviso si `stop_reason == "max_tokens"` y error tipado `refusal` si el modelo declina la petición;
  - métricas por llamada: modelo exacto devuelto, `id`, tokens de entrada/salida (y de caché si los hay), latencia y coste en USD calculado con una tabla de precios en configuración;
  - resultado tipado (modelo Pydantic) equivalente al dict de la lección `{content, model, id, input_tokens, output_tokens, stop_reason, cost_usd}` más `latency_ms`, o un error tipado `{error, error_type, status_code}` en lugar de propagar la excepción.
- Soporte de conversación multiturno sin estado en el servidor: el historial vive en el cliente y se reenvía completo, validando la alternancia `user`/`assistant`.
- Manejo explícito de los errores tipados del SDK (`AuthenticationError`, `BadRequestError`, `PermissionDeniedError`, `NotFoundError`, `RateLimitError`, `APIStatusError` 5xx/529, `APIConnectionError`, `APITimeoutError`), apoyado en los reintentos nativos del SDK (`max_retries`) sin duplicarlos.
- Scripts de experimentación reproducibles (`experiments/`): llamada básica, multiturno, `temperature`, `top_p`/`top_k`, truncado por `max_tokens`, `stop_sequences`, razonamiento (adaptativo con `effort` en el modelo por defecto y `budget_tokens` en el legacy) y comparación entre generaciones. Los parámetros de muestreo y `budget_tokens`, que Haiku 5.5 rechaza, se ejercitan contra el modelo legacy configurado mientras siga disponible, enviando la versión de API `2023-06-01`, y además se muestra el rechazo con la versión vigente. Cada script imprime contenido y métricas.
- Tests con `pytest`: unitarios con el cliente de Anthropic mockeado (sin red ni coste) y un smoke test real marcado `live`, opt-in, excluido por defecto.
- Documentación: memoria `docs/sesiones/sesion-01.md`, sección «Cómo ejecutar» y fila de la Sesión 1 en el `README.md`, y actualización del `context` de `openspec/config.yaml` con el stack real.

### Fuera de alcance

- Alta de cuentas, billing y límites de gasto en Anthropic/OpenAI (ejercicio manual sin código; se documenta solo en la memoria).
- Cualquier proveedor distinto de Anthropic (OpenAI incluido) y librerías de orquestación (LangChain/LangSmith).
- API HTTP, FastAPI, Docker y endpoints (Sesión 2).
- Streaming, tool use, prompt caching activo, structured outputs, Batches y Files API (solo se reportan los tokens de caché si vienen en `usage`).
- Fallback automático entre modelos y persistencia del historial.

## Capabilities

### New Capabilities

- `llm-client`: acceso a Claude mediante la Messages API — configuración, llamada única y multiturno, métricas de uso/latencia/coste, aviso de truncado y manejo tipado de errores. Es la capacidad que consumirá la capa de servicios de la Sesión 2.
- `llm-experiments`: scripts ejecutables que demuestran el efecto de los parámetros de muestreo, límites, secuencias de parada y razonamiento extendido, con métricas impresas y advertencia de coste.

### Modified Capabilities

- Ninguna (no existen specs previas en `openspec/specs/`).

## Impact

- **Ficheros nuevos**: `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `app/__init__.py`, `app/config.py`, `app/services/__init__.py`, `app/services/llm_service.py`, `app/services/pricing.py`, `experiments/*.py`, `tests/conftest.py`, `tests/unit/*.py`, `tests/live/test_smoke.py`, `docs/sesiones/sesion-01.md`.
- **Ficheros modificados**: `README.md` (estructura, cómo ejecutar, índice de entregas), `openspec/config.yaml` (`context`: stack, modelos, testing). `.gitignore` ya excluye `.env` y `.venv`; no requiere cambios.
- **Modelo de datos / migraciones / endpoints**: ninguno. No hay base de datos ni API HTTP en esta sesión.
- **Dependencias nuevas** (requieren aprobación): runtime `anthropic` y `pydantic-settings` (trae `pydantic` y `python-dotenv` como dependencias transitivas, por lo que no se añade `python-dotenv` aparte); desarrollo `pytest` y `ruff`; se propone además `mypy` para el type-check de la Definition of Done. Versiones: la última estable en el momento de `uv add`, fijada en `uv.lock`.
- **LLM — modelo, coste y latencia** (verificado en la documentación oficial de Anthropic el 2026-11-25):
  - Modelo por defecto: `claude-haiku-5-5` (ID sin fecha, que es su propio snapshot fijado; activo, retirada no antes del 07-10-2027). Precio: 0,10/0,50 USD/MTok de entrada/salida con prompts ≤100K tokens y 0,50/2,50 por encima; 1M de contexto y 128K de salida. Razona de forma adaptativa por defecto (`effort` por defecto `medium`), y el razonamiento cuenta en `max_tokens`, por lo que el valor por defecto sube de 1.000 a 4.096. Rechaza con 400 `temperature` ≠ 1, `top_p` ≠ 0,99, cualquier `top_k`, `budget_tokens` y el prefill del asistente. Puede declinar peticiones (`stop_reason: "refusal"`) y no admite fallback en servidor. Su tokenizador cuenta unos 30 % más tokens que Haiku 4.5 para el mismo texto.
  - Modelo legacy para experimentos: `claude-haiku-4-5-20251001` (alias `claude-haiku-4-5`), 1/5 USD/MTok sin tramos, «Active (legacy)» con retirada «no antes del 15-10-2026». Solo lo usan los experimentos de muestreo, `budget_tokens` y comparación, y es configurable.
  - Versión de API: el SDK `anthropic` 2.x envía `anthropic-version: 2026-10-21`, que elimina `temperature`, `top_p` y `top_k` en todos los modelos (400 incluso en Haiku 4.5). Las llamadas al modelo legacy de los experimentos envían `2023-06-01`, la salida que documenta Anthropic para peticiones que dependen de esos parámetros (configurable en `LLM_LEGACY_API_VERSION`); el resto de la aplicación usa la versión vigente.
  - Coste esperado: una llamada típica de los experimentos (<500 tokens de entrada y ≤2.048 de salida incluido el razonamiento) cuesta < 0,0011 USD con Haiku 5.5 y < 0,011 USD con Haiku 4.5. La ejecución completa de los experimentos y el smoke test se estima en < 0,10 USD. Los tests unitarios no tienen coste.
  - Latencia esperada: del orden de 1–5 s por llamada no streaming; con `effort` alto o respuestas largas puede crecer por el razonamiento. Se mide y registra por llamada, sin objetivo contractual.
  - Evaluación de calidad: no hay prompt de producto que evaluar todavía; la corrección se verifica de forma determinista (estructura de respuesta, `stop_reason`, conteo de tokens y coste recalculado) con tests mockeados y un smoke test real. El dataset de evaluación se creará cuando la Sesión 2 introduzca el primer prompt de negocio.
- **Riesgos**:
  - Claude Haiku 4.5 puede retirarse con poco margen (fecha mínima de retirada ya pasada), lo que dejaría sin efecto los experimentos de muestreo y `budget_tokens`. Mitigación: solo lo usan esos experimentos, el modelo legacy es configurable y, si deja de existir, el experimento muestra el error `not_found` en lugar de fallar.
  - Los parámetros de muestreo de la lección no existen en la versión de API vigente: quien use `query_claude` con `temperature` sin forzar `2023-06-01` recibe un error `bad_request` en cualquier modelo. La versión `2023-06-01` no tiene fecha de retirada publicada, pero puede tenerla; si desaparece, esos experimentos solo mostrarán el rechazo. Mitigación: `temperature` no se envía por defecto y la restricción se documenta en `.env.example` y en la memoria.
  - Las negativas del modelo (`refusal`) son nuevas respecto a Haiku 4.5. Mitigación: se tratan como error tipado y se registran.
  - Los precios cambian: la tabla vive en configuración con fecha de verificación; un modelo sin precio conocido devuelve `cost_usd = None` con aviso, no un coste inventado.
  - Fuga de la API key en un repo público: solo en `.env` (ignorado), `SecretStr` en la configuración y tests sin clave real.
- **Rollback**: el cambio solo añade ficheros en una rama `sesion-01`; revertirlo es no fusionar el PR o revertir el merge commit. No afecta a datos ni a sistemas en producción.
