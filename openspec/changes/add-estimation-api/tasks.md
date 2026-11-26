# Tasks

## 1. Dependencias

- [x] 1.1 Añadir `uv add fastapi "uvicorn[standard]"` y verificar que `uv.lock` se actualiza y que `uv run python -c "import fastapi, uvicorn"` funciona
- [x] 1.2 Comprobar qué cliente HTTP necesita `TestClient` (`uv run python -c "from fastapi.testclient import TestClient"`) y añadir al grupo `dev` solo lo que falte (`httpx` o `httpx2`); verificar que el import funciona y que `uv run pytest` sigue en verde (95 tests)

## 2. Configuración

- [x] 2.1 Escribir tests de `Settings`: `LLM_PROVIDER` por defecto `anthropic` y `openai` rechazado nombrando la variable, `APP_ENV` y `LOG_LEVEL` leídos sin prefijo con sus valores por defecto (`development`, `INFO`) y valores inválidos rechazados, tarifas por defecto, `ESTIMATION_HOURLY_RATES` en JSON con tarifas ≤ 0 rechazadas y `ESTIMATION_MAX_TRANSCRIPTION_CHARS` por defecto 60.000; verificar rojo
- [x] 2.2 Ampliar `app/config.py` (D3) y verificar que pasan los tests de 2.1 y los de configuración existentes
- [x] 2.3 Documentar en `.env.example` las variables nuevas, con su valor por defecto y una nota sobre `LLM_PROVIDER` (solo `anthropic` hasta la Sesión 3); verificar que el test que compara `.env.example` con los campos de `Settings` pasa

## 3. Servicio de LLM: consulta asíncrona y proveedor

- [x] 3.1 Añadir a `tests/conftest.py` un cliente asíncrono falso, con respuesta, excepción y retardo configurables, y escribir tests de `acall_raw`/`aquery_claude`:
  - Resultado equivalente, con un coste de 0,002 y `provider` `anthropic`.
  - Errores 401, 429 y 529 tras agotar los reintentos, y timeout.
  - Clave ausente → `configuration` y negativa → `refusal`.
  - Mensaje vacío → `validation`.
  - Dos consultas concurrentes de 200 ms que terminan en menos de 400 ms.
  - Reintento 529 → 200 con el `AsyncAnthropic` real sobre un transporte simulado.

  Verificar rojo.
- [x] 3.2 Extraer `_build_request` de `call_raw` e implementar `build_async_client`, `acall_raw` y `aquery_claude` (D2) y `QueryResult.provider` (D3); verificar que pasan los tests de 3.1 y todos los tests existentes de `llm_service`, sin cambiarlos

## 4. Contexto CAG

- [x] 4.1 Escribir tests de ejemplos:
  - Catálogo de 5 ejemplos válidos.
  - Cada rol con su tarifa configurada.
  - `render_example` con 10 h de desarrollo y 4 h de diseño da 625,00 + 200,00 = 825,00 EUR y 14 h.
  - Un rol sin tarifa da un `ValueError` que nombra el rol.

  Verificar rojo.
- [x] 4.2 Implementar `app/context/examples.py` (D4) con los 5 ejemplos ficticios en español y verificar que pasan los tests de 4.1
- [x] 4.3 Escribir tests de `build_estimation_prompt`:
  - Orden rol → tarifas → ejemplos → formato.
  - Cabecera `Tarea | Rol | Horas | Coste (EUR)` y petición de totales, equipo y semanas.
  - Transcripción ausente del system y delimitada en el mensaje de usuario, también con un intento de inyección.
  - 2 ejemplos, 0 ejemplos y desactivados, y 6 ejemplos rechazado.
  - Determinismo y `prompt_version` `v1`.

  Verificar rojo.
- [x] 4.4 Crear `app/prompts/estimation_system.v1.md` e implementar `build_estimation_prompt` en `app/services/estimation_service.py` (D5); verificar que pasan los tests de 4.3

## 5. API HTTP

- [x] 5.1 Escribir tests de los schemas: transcripción de 49 caracteres, solo espacios o por encima del máximo → error; campo adicional → error; `usage.total_tokens` calculado y `created_at` en UTC. Verificar rojo
- [x] 5.2 Implementar `app/schemas/estimation.py` (D6) y verificar que pasan los tests de 5.1
- [x] 5.3 Escribir tests del endpoint con `TestClient` y el cliente asíncrono falso inyectado:
  - 200 con todos los campos (4.000/1.000 tokens dan un coste de 0,0009 y `total_tokens` 5.000).
  - `cost_usd` nulo con un modelo sin precio.
  - `finish_reason` `stop`, `length` (con aviso) y `other`.
  - 422 de validación sin llamada al LLM.
  - Cada categoría de error con su código (422, 503, 504 y 502) y un mensaje sin el texto del proveedor.
  - Registro con las métricas, la versión del prompt o el `error_type`, y sin el texto de la transcripción (`caplog`).

  Verificar rojo.
- [x] 5.4 Implementar `estimate()` en `estimation_service.py` y `app/routers/estimations.py` con la tabla de errores (D6) y el registro (D8); verificar que pasan los tests de 5.3
- [x] 5.5 Escribir tests de la aplicación:
  - `GET /health` da 200 con `healthy`, la versión y el entorno, sin llamar al LLM.
  - `/openapi.json` incluye `POST /api/v1/estimate` (sin el prefijo duplicado) con sus modelos, y `/health`.
  - `/docs` da 200.
  - El arranque sin `ANTHROPIC_API_KEY` falla nombrando la variable.
  - `LOG_LEVEL` `WARNING` suprime el registro informativo.

  Verificar rojo.
- [x] 5.6 Implementar `app/main.py` (lifespan con fallo rápido, configuración del logging, cliente asíncrono en `app.state`, router con el prefijo `/api/v1` y `/health`) y `app/__init__.__version__`; verificar que pasan los tests de 5.5
- [x] 5.7 Añadir un test `live` en `tests/live/` con una transcripción ficticia corta contra `POST /api/v1/estimate`, que compruebe el 200, la cabecera de tabla, tokens > 0 y coste no nulo; verificar que `uv run pytest` lo muestra como deseleccionado y que `uv run pytest -m live` sin clave lo omite

## 6. Documentación

- [x] 6.1 Actualizar `README.md`:
  - Estructura, con `main.py`, `routers/`, `schemas/`, `context/` y `prompts/`.
  - «Cómo ejecutar», con `uv run uvicorn app.main:app --reload`, `/docs` y un ejemplo de curl.
  - Fila de la Sesión 02 en el índice, con estado «En curso».

  Verificar que los comandos documentados se ejecutan tal como están escritos.
- [x] 6.2 Escribir `docs/sesiones/sesion-02.md`:
  - Enunciado resumido, qué se ha hecho y decisiones.
  - Desviaciones respecto al enunciado y al repositorio de referencia, con su motivo.
  - Cómo probarlo, con el curl de ejemplo de una transcripción ficticia de landing + HubSpot + blog.
  - Verificación.

  Verificar que el curl documentado devuelve 200 con el servicio levantado.
- [x] 6.3 Actualizar la sección «Estructura» de `CLAUDE.md` y el `context` de `openspec/config.yaml` (FastAPI, uvicorn, capas, variables nuevas y `LLM_PROVIDER`); verificar que `openspec validate add-estimation-api --strict` sigue pasando

## 7. Verificación integral

- [x] 7.1 Ejecutar `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy app experiments`; verificar que todo está en verde, sin regresiones en los 95 tests de la Sesión 1
- [x] 7.2 Con autorización explícita del autor para gastar crédito:
  - Ejecutar `uv run pytest -m live`.
  - Levantar `uv run uvicorn app.main:app` y probar `/health`, `/docs` y el curl de la memoria.
  - Comprobar en el registro las métricas y la ausencia del texto de la transcripción.
  - Anotar en la memoria la latencia y el coste observados.

  Si no se autoriza, dejarlo anotado como no verificado.
- [ ] 7.3 Ejecutar `openspec-verify-change` sobre `add-estimation-api` y resolver o justificar todos sus hallazgos

## Workflow follow-up

- Archivar el cambio con `openspec-archive-change` antes de fusionar, de modo que `openspec/specs/` incluya `estimation-api`, `estimation-context` y el delta de `llm-client`.
- Push de `sesion-02` y PR `sesion-02 → main`, con la confirmación del autor.
- Al entregar: actualizar la fila del índice (tag y estado «Entregada») en `sesion-02`, crear el tag anotado `entrega-sesion-02` y fusionar con merge commit (`--no-ff`).
