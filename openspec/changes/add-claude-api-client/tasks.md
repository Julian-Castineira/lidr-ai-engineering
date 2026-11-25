# Tasks

## 1. Setup del proyecto

- [x] 1.1 Crear `pyproject.toml` (Python ≥3.11, aplicación sin build backend), `.python-version` y paquetes vacíos `app/`, `app/services/`, `experiments/`, `tests/unit/`, `tests/live/`; verificar con `uv sync` sin errores
- [x] 1.2 Añadir dependencias aprobadas con `uv add anthropic pydantic-settings` y `uv add --dev pytest ruff mypy`; verificar que `uv.lock` existe y `uv run python -c "import anthropic, pydantic_settings"` funciona
- [x] 1.3 Configurar pytest (`pythonpath`, marcador `live`, `addopts = "-m 'not live'"`), ruff y mypy en `pyproject.toml`; verificar que `uv run pytest`, `uv run ruff check .` y `uv run mypy app` se ejecutan sobre el proyecto vacío sin errores de configuración

## 2. Configuración

- [x] 2.1 Escribir tests de `Settings`: valores por defecto (`claude-haiku-5-5`, `max_tokens` 4096, temperatura y `effort` sin fijar, modelo legacy `claude-haiku-4-5-20251001`), override por entorno, validación de rango de temperatura, valores de `effort` y `max_tokens`, API key enmascarada en `repr`/`str`; verificar que fallan (rojo)
- [x] 2.2 Implementar `app/config.py` con `pydantic-settings` (`ANTHROPIC_API_KEY` como `SecretStr | None`, variables `LLM_*` incluidas `LLM_EFFORT` y `LLM_LEGACY_MODEL`) y verificar que los tests de 2.1 pasan
- [x] 2.3 Crear `.env.example` con todas las variables, valores por defecto, sin clave real y con notas sobre `LLM_TEMPERATURE` (el modelo por defecto la rechaza), `LLM_EFFORT` y `LLM_LEGACY_MODEL` (solo experimentos); verificar que coincide con los campos de `Settings` (test que compara nombres)

## 3. Precios y coste

- [x] 3.1 Escribir tests de coste: caso 10.000/2.000 tokens con Haiku 5.5 = 0,002 USD, caso 1.000/200 tokens con Haiku 4.5 = 0,002 USD, tokens de caché, tramo superior de Haiku 5.5 por encima de 100.000 tokens de prompt, modelo desconocido → `None` con aviso, override por `LLM_PRICING_JSON`; verificar rojo
- [x] 3.2 Implementar `app/services/pricing.py` (tabla con fecha de verificación 2026-11-25 para `claude-haiku-4-5-20251001`, `claude-haiku-4-5` y `claude-haiku-5-5`, cálculo con `Decimal`) y verificar que los tests de 3.1 pasan

## 4. Servicio de LLM: llamada única

- [x] 4.1 Definir `QueryResult` y `QueryError` en `app/services/schemas.py` y crear en `tests/conftest.py` el cliente falso y las factorías de `Message` y de excepciones del SDK; verificar con un test que las factorías construyen objetos del SDK válidos
- [x] 4.2 Escribir tests de `query_claude`: respuesta correcta (system de primer nivel, `max_tokens` enviado, modelo/id/tokens/latencia/coste), `temperature` y `effort` ausentes de la petición si no se fijan y presentes tal cual si se fijan, bloque `thinking` vacío antes del texto, mensaje vacío, API key ausente, truncado con aviso (`caplog`), negativa `refusal` con categoría y con `stop_details` nulo; verificar rojo
- [x] 4.3 Implementar `query_claude` y `call_raw` en `app/services/llm_service.py` (parámetros opcionales solo si se fijan, `effort` en `output_config`, comprobación de `stop_reason` antes de leer `content`, extracción por tipo de bloque, medición de latencia, coste por `response.model`) y verificar que los tests de 4.2 pasan

## 5. Servicio de LLM: errores y reintentos

- [x] 5.1 Escribir tests de mapeo de errores (401, 403, 404, 400, 429, 500, 529, timeout, conexión) y de que el mensaje de error no contiene la API key; verificar rojo
- [x] 5.2 Implementar el mapeo de excepciones del SDK a `QueryError` y verificar que los tests de 5.1 pasan
- [x] 5.3 Escribir y pasar tests de reintentos con `httpx.MockTransport` y cliente real del SDK: 401 → una sola petición; 529 seguido de 200 con `max_retries=2` → resultado correcto y dos peticiones

## 6. Conversación multiturno

- [x] 6.1 Escribir tests de `Conversation` y de la validación de historial: segundo turno envía `user/assistant/user`, historial que empieza por `assistant` o repite rol → error `validation` sin llamada, turno fallido no modifica el historial; verificar rojo
- [x] 6.2 Implementar `Conversation` y la función de validación en `llm_service.py` y verificar que los tests de 6.1 pasan

## 7. Smoke test real

- [x] 7.1 Crear `tests/live/test_smoke.py` (marcador `live`, `skip` sin `ANTHROPIC_API_KEY`, una llamada al modelo por defecto con `effort` `low` y `max_tokens` ≤ 256) y verificar que `uv run pytest` lo muestra como deseleccionado y `uv run pytest -m live` sin clave lo omite
- [x] 7.2 Con autorización explícita del autor para gastar crédito, ejecutar `uv run pytest -m live` con clave real y verificar que pasa (texto no vacío, tokens > 0, coste no nulo); si no se autoriza, dejarlo anotado como no verificado

## 8. Experimentos

- [x] 8.1 Implementar `experiments/_common.py` (impresión de resultado/error, acumulador de llamadas, tokens y coste, y aviso de modelo legacy no disponible ante `not_found`) con tests unitarios del acumulador, del mensaje sin API key (código de salida ≠ 0) y del aviso de legacy retirado (código de salida 0), y verificar que pasan
- [x] 8.2 Implementar `01_basic.py` y `02_multiturn.py`; verificar con un test que ejecuta su `main()` con el cliente falso y comprueba la salida impresa
- [x] 8.3 Implementar `03_temperature.py` (0 y 1, varias repeticiones en el modelo legacy y 400 esperado en el modelo por defecto) y `04_sampling.py` (`top_p`, `top_k` en el modelo legacy, 400 esperado al combinar `temperature` y `top_p` y 400 en el modelo por defecto); verificar con tests sobre cliente falso que se usa el modelo correcto en cada llamada
- [x] 8.4 Implementar `05_max_tokens.py` (truncado en el modelo por defecto, incluido el caso de corte en mitad del razonamiento sin texto) y `06_stop_sequences.py`; verificar con tests sobre cliente falso que se imprime `max_tokens`/aviso y `stop_sequence`/secuencia
- [x] 8.5 Implementar `07_thinking.py` (modelo por defecto: adaptativo con `effort` `low` y `high` y `display: "summarized"`; modelo legacy: `budget_tokens=1024`, `max_tokens=2048`, 400 esperado con `temperature`≠1; 400 esperado de `budget_tokens` en el modelo por defecto) y `08_model_comparison.py` (modelo por defecto frente a legacy: tipos de bloque, tokens, latencia y coste; rechazo de `temperature` en el por defecto y repetición sin ella); verificar con tests sobre cliente falso
- [x] 8.6 Con autorización explícita para gastar crédito (< 0,10 USD estimado), ejecutar los ocho experimentos con clave real y guardar un extracto de la salida para la memoria; si no se autoriza, anotarlo como no verificado

- [x] 8.7 Añadir `api_version` a `call_raw`/`query_claude` y `LLM_LEGACY_API_VERSION` a la configuración y a `.env.example` (D10), con tests de la cabecera enviada y del valor por defecto; verificar que pasan
- [x] 8.8 Hacer que los experimentos 03, 04, 07 y 08 envíen la versión de API legacy en todas las llamadas al modelo legacy y que el proveedor simulado de los tests rechace muestreo sin `2023-06-01`; verificar con tests y repitiendo la ejecución real de esos cuatro experimentos sin errores no esperados

## 9. Documentación

- [x] 9.1 Actualizar `README.md`: estructura del repo con `app/`, `experiments/`, `tests/`; sección «Cómo ejecutar» (`uv sync`, `.env`, tests, experimentos, smoke test); verificar que los comandos documentados se ejecutan tal cual
- [x] 9.2 Actualizar `context` en `openspec/config.yaml` (stack, modelos y proveedor, testing) y verificar con `openspec validate add-claude-api-client --strict`
- [x] 9.3 Escribir `docs/sesiones/sesion-01.md` (enunciado resumido incluido el alta de cuentas, qué se hizo, decisión de usar `claude-haiku-5-5` en lugar del modelo de los apuntes y sus consecuencias, precios verificados, cómo probarlo, coste observado, lo no verificado) y actualizar la fila de la Sesión 01 en el «Índice de entregas»; verificar enlaces y que no contiene claves ni datos reales

## 10. Verificación final

- [x] 10.1 Ejecutar `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy app`, todo en verde sin red ni API key
- [x] 10.2 Comprobar con `git status` y una búsqueda de `sk-ant-` que no hay `.env` ni claves en el árbol versionado
- [x] 10.3 Definition of Done: tests nuevos en verde sin regresiones, documentación (README, `.env.example`, memoria, `config.yaml`) actualizada, specs coherentes con el código (`openspec validate --strict`) e informe de lo hecho, lo omitido, lo pendiente y cómo se verificó

## Workflow follow-up

- Commits atómicos en español en la rama `sesion-01`; push y PR `sesion-01 → main` solo con confirmación del autor.
- Archivar el cambio con `openspec-archive-change` antes de fusionar, para que `openspec/specs/` describa la aplicación.
- Al entregar: tag anotado `entrega-sesion-01` y merge con `--no-ff`, previa confirmación.
