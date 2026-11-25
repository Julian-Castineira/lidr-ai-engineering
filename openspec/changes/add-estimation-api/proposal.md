# Proposal

## Why

La Sesión 2 del Máster («Primeros pasos de arquitectura CAG») pide el scaffolding del Proyecto 1: un servicio FastAPI que recibe la transcripción de una reunión y devuelve una estimación de software generada por un LLM con arquitectura CAG (conocimiento precargado en el contexto, sin base de datos ni retrieval). Se evalúa el flujo completo texto → contexto → LLM → respuesta, y hay que llegar a la sesión en vivo con el servicio funcionando para iterar sobre ejemplos, prompt y parámetros.

Para quién: el profesor, que evalúa la entrega de forma aislada, y el propio autor, que hará evolucionar este servicio en las sesiones siguientes (abstracción de proveedores, fallback y una interfaz en Streamlit en la Sesión 3; RAG después). Objetivo: exponer la capa de acceso a Claude de la Sesión 1 como una API HTTP observable, con un contexto CAG versionado y verificable, sin reestructurar lo existente.

## What Changes

- **API HTTP** (FastAPI) en el paquete `app/` existente, no en un proyecto paralelo `estimador-cag/` como sugiere el enunciado:
  - `POST /api/v1/estimate`: recibe `{"transcription": "..."}` (mínimo 50 caracteres y un máximo configurable) y devuelve `{estimation, model, provider, usage{input_tokens, output_tokens, total_tokens}, finish_reason, latency_ms, cost_usd, created_at}`. Los cinco primeros campos coinciden con el contrato del repositorio de referencia del programa; el resto añade observabilidad sin romperlo.
  - `GET /health`: `{status, version, environment}`.
  - Documentación OpenAPI en `/docs` con título y descripción.
  - Errores del proveedor traducidos a códigos HTTP (422, 502, 503, 504) con un cuerpo uniforme y un mensaje genérico, sin filtrar detalles internos.
  - Validación de la configuración al arrancar: sin `ANTHROPIC_API_KEY` el servicio no arranca.
- **Contexto CAG**:
  - 5 estimaciones de ejemplo ficticias, en español y estructuradas (tareas con rol y horas, equipo y duración). Al construir el prompt, los costes y los totales se calculan por código a partir de las tarifas configuradas, de modo que los ejemplos son coherentes por construcción.
  - System prompt versionado en un fichero, con el orden que recomienda la lección: rol y tarea, ejemplos con separadores, formato y restricciones, y la transcripción como mensaje de usuario.
  - Formato de salida fijado: título, tabla `Tarea | Rol | Horas | Coste (EUR)`, total de horas, coste total, equipo recomendado y duración en semanas.
  - Constructor de prompt parametrizable (número de ejemplos, con o sin ejemplos), para iterar en la sesión en vivo sin cambiar el contrato HTTP.
- **Servicio de LLM**: variante asíncrona de la consulta, para que el endpoint no bloquee el event loop, que comparte con la síncrona la construcción de la petición, las métricas y el mapeo de errores. Los experimentos de la Sesión 1 siguen siendo síncronos.
- **Configuración**: nuevas variables `LLM_PROVIDER` (solo `anthropic` en esta sesión), `APP_ENV`, `LOG_LEVEL`, tarifas por rol y límite de longitud de la transcripción, documentadas en `.env.example`.
- **Observabilidad**: un registro por estimación con modelo, tokens, latencia, coste, `finish_reason` y versión del prompt. Nunca se registra el contenido de la transcripción.
- **Tests**: unitarios sin red (constructor de prompt, ejemplos y endpoints con el LLM simulado) y un test `live` opt-in del endpoint contra la API real.
- **Documentación**: memoria `docs/sesiones/sesion-02.md` (con el curl de ejemplo landing + HubSpot + blog), README (cómo arrancar el servicio, estructura e índice de entregas), `CLAUDE.md` (estructura) y `context` de `openspec/config.yaml`.

### Fuera de alcance

- OpenAI y la abstracción multiproveedor con fallback: llegan en la Sesión 3. `LLM_PROVIDER` se introduce ya con un único valor válido para fijar el contrato de configuración.
- Parámetros por petición (modelo, `max_tokens`, razonamiento, preprocesado, número de ejemplos) en la API: se ensayan en la sesión en vivo. El constructor de prompt ya los admite internamente.
- Salida estructurada (JSON validado) y recálculo por código de los costes de la estimación generada: el contrato del ejercicio devuelve Markdown.
- Docker y Compose, CORS, interfaz de usuario, autenticación, persistencia, streaming y prompt caching activo.
- Dataset formal de evaluación de calidad: el ejercicio evalúa el flujo, no la calidad de la estimación.

## Capabilities

### New Capabilities

- `estimation-api`: contrato HTTP del estimador — endpoint de estimación, validación de la entrada, forma de la respuesta, traducción de errores, salud del servicio, documentación OpenAPI, validación de la configuración al arrancar y registro por petición.
- `estimation-context`: contexto CAG del estimador — ejemplos de estimación, tarifas, construcción del system prompt y del mensaje de usuario, formato de salida exigido y límites de tamaño de la entrada.

### Modified Capabilities

- `llm-client`: se añaden la consulta asíncrona, con el mismo contrato de resultado y errores que la síncrona, y la selección de proveedor por configuración, limitada a `anthropic`. Los requisitos existentes no cambian.

## Impact

- **Ficheros nuevos**:
  - `app/main.py`, `app/routers/__init__.py`, `app/routers/estimations.py`, `app/schemas/__init__.py`, `app/schemas/estimation.py`, `app/context/__init__.py`, `app/context/examples.py`, `app/prompts/estimation_system.v1.md` y `app/services/estimation_service.py`.
  - Tests nuevos en `tests/unit/` y `tests/live/`, y la memoria `docs/sesiones/sesion-02.md`.
- **Ficheros modificados**: `app/config.py`, `app/services/llm_service.py`, `.env.example`, `pyproject.toml`, `uv.lock`, `README.md`, `CLAUDE.md` y `openspec/config.yaml`.
- **Endpoints nuevos**: `POST /api/v1/estimate`, `GET /health`, `/docs` y `/openapi.json`. No hay modelo de datos ni migraciones.
- **Dependencias nuevas**, aprobadas por el autor en el plan:
  - Runtime: `fastapi` y `uvicorn[standard]`. Versiones vigentes en PyPI el 2026-11-25: FastAPI 0.165.0 (Python ≥ 3.11) y uvicorn 0.54.0, fijadas en `uv.lock`.
  - Desarrollo: el cliente HTTP que requiera `TestClient` (`httpx` o `httpx2`, según la versión de Starlette), solo si no llega ya como dependencia transitiva.
  - No se añaden `python-dotenv` (pydantic-settings ya lee `.env`), `structlog` ni el SDK de OpenAI.
- **LLM: modelo, coste y latencia**:
  - Modelo `claude-haiku-5-5` (configuración vigente de la Sesión 1; el `claude-haiku-4-5` del enunciado es legacy). `max_tokens` 4096 por defecto, incluido el razonamiento adaptativo, y `effort` por defecto del modelo.
  - Coste estimado por estimación: unos 3.000–6.000 tokens de entrada (instrucciones, 5 ejemplos y la transcripción) y hasta 4.096 de salida. A 0,10/0,50 USD/MTok, cuesta menos de 0,003 USD por llamada.
  - Latencia esperada: del orden de 5–20 s por estimación, por la longitud de la salida y el razonamiento. Se mide y se devuelve en cada respuesta, sin objetivo contractual.
  - Evaluación:
    - Del flujo, con tests deterministas (prompt construido, contrato HTTP, traducción de errores) y un test `live` que comprueba que la estimación real contiene la tabla y los totales exigidos.
    - De la calidad, de forma manual con transcripciones ficticias de distinto tamaño; el dataset formal queda para cuando se compare entre prompts o modelos.
- **Riesgos**:
  - Exposición del servicio: no hay autenticación y cada petición cuesta dinero. Mitigación: es un servicio local de desarrollo, la transcripción tiene un límite de longitud y no se habilita CORS. La autenticación se añadirá antes de cualquier despliegue.
  - Prompt injection en la transcripción: el texto del usuario va como mensaje `user`, separado de las instrucciones. La salida es Markdown que no se ejecuta ni se interpola en ningún sitio.
  - Privacidad (RGPD): las transcripciones pueden contener datos personales. No se registran ni se persisten, y los ejemplos y fixtures son ficticios.
  - El contrato puede cambiar en sesiones posteriores (el repositorio de referencia lo reescribe en la Sesión 4). Mitigación: endpoints finos y lógica en servicios, de modo que el cambio sea local.
- **Rollback**: el cambio solo añade o modifica ficheros en la rama `sesion-02`. Para revertirlo basta con no fusionar el PR o revertir el merge commit. Los experimentos y la API síncrona de la Sesión 1 no cambian de contrato.
