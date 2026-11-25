# Sesión 02 · Primeros pasos de arquitectura CAG

## Enunciado resumido

La sesión introduce CAG (Cache-Augmented Generation): en vez de recuperar documentos en cada consulta (RAG), el conocimiento acotado y estable se precarga en el contexto del modelo. También cubre la arquitectura por capas de un servicio de IA generativa (`config`, `routers`, `services`, `schemas`, `context` y `main.py` como pegamento), la gestión del contexto y el diseño de conversaciones sin estado.

El ejercicio es el **scaffolding del Proyecto 1**: un servicio FastAPI que recibe la transcripción de una reunión con un cliente y devuelve una estimación de software generada por un LLM con ejemplos precargados:
- `POST /api/v1/estimate` con `{"transcription"}` → `{"estimation", "model", "provider"}`.
- `GET /health`.
- Documentación en `/docs`.
- Configuración desde `.env`.
- Al menos dos estimaciones de ejemplo como few-shot.

Se evalúa el flujo completo (texto → contexto → LLM → respuesta), no la calidad de la estimación.

## Qué se ha hecho

El servicio se integra en el paquete `app/` de la Sesión 01: la estructura crece añadiendo ficheros, sin mover nada.

| Pieza | Dónde | Qué hace |
|---|---|---|
| Aplicación | `app/main.py` | FastAPI con `lifespan`: valida la configuración y no arranca sin `ANTHROPIC_API_KEY`, configura el registro y crea un único cliente asíncrono, que cierra al apagar. Expone `/health` y monta el router con el prefijo `/api/v1`. |
| Endpoint | `app/routers/estimations.py` | `POST /api/v1/estimate`, un endpoint fino que valida, delega en el servicio y traduce los errores del proveedor a 422, 502, 503 o 504 con un mensaje genérico. |
| Contratos | `app/schemas/estimation.py` | Petición con `transcription` (entre 50 y `ESTIMATION_MAX_TRANSCRIPTION_CHARS` caracteres, sin campos extra). Respuesta con `estimation`, `model`, `provider`, `usage{input_tokens, output_tokens, total_tokens}`, `finish_reason`, `latency_ms`, `cost_usd` y `created_at`. |
| Contexto CAG | `app/context/examples.py` | 5 estimaciones ficticias en español con tareas, rol y horas. Los costes y los totales se calculan por código con las tarifas configuradas, de modo que los ejemplos no pueden quedar incoherentes. |
| Prompt | `app/prompts/estimation_system.v1.md` | System prompt versionado con el orden de la lección: rol y tarea, uso del contexto, tarifas, ejemplos, formato de salida y restricciones. |
| Servicio | `app/services/estimation_service.py` | Construye el prompt de forma determinista (número de ejemplos ajustable), llama al LLM y registra modelo, tokens, latencia, coste, `finish_reason` y versión del prompt. Nunca registra la transcripción ni la estimación. |
| Cliente LLM | `app/services/llm_service.py` | Nuevas `acall_raw` y `aquery_claude`, con el mismo contrato que las síncronas de la Sesión 01 y la construcción de la petición compartida. Sigue siendo el único módulo de la aplicación que importa el SDK. |
| Configuración | `app/config.py`, `.env.example` | `LLM_PROVIDER` (solo `anthropic`), `APP_ENV`, `LOG_LEVEL`, `ESTIMATION_HOURLY_RATES` y `ESTIMATION_MAX_TRANSCRIPTION_CHARS`. |
| Tests | `tests/unit`, `tests/live` | 182 tests sin red (87 nuevos): configuración, consulta asíncrona, ejemplos, prompt, schemas, endpoint, aplicación y registro. Además, un test `live` de la estimación de extremo a extremo. |

El diseño se especificó antes con OpenSpec: `openspec/changes/add-estimation-api/` (propuesta, specs `estimation-api`, `estimation-context` y delta de `llm-client`, diseño y tareas).

## Decisiones

### Desviaciones respecto al enunciado

- **Dentro de `app/`, no en una carpeta `estimador-cag/`**: el repositorio es una única aplicación que evoluciona. Un proyecto paralelo duplicaría la configuración y el cliente de la Sesión 01.
- **Solo Anthropic, con `claude-haiku-5-5`**: el enunciado propone `gpt-4o-mini` o `claude-haiku-4-5`, y este último es legacy (ver la memoria de la Sesión 01). `LLM_PROVIDER` ya existe, pero solo admite `anthropic`: la abstracción de proveedores y el fallback llegan en la Sesión 3, y añadir OpenAI ahora sería construir esa capa dos veces.
- **Sin `python-dotenv`**: pydantic-settings ya lee `.env`.
- **`LOG_LEVEL` por defecto `INFO`**, en lugar de `DEBUG`.

### Desviaciones respecto al repositorio de referencia del programa

Contrato compatible: misma ruta y mismos campos `transcription`, `estimation`, `model` y `provider`, y los tokens agrupados en `usage`. Las diferencias:

- **Cliente asíncrono** (`AsyncAnthropic`): un cliente síncrono dentro de un `async def` bloquea el event loop.
- **Errores tipados con 422, 502, 503 o 504 y mensaje genérico**, en lugar de un 500 con el mensaje del proveedor, que puede exponer detalles internos.
- **El servicio no arranca sin clave**, y la clave se guarda como `SecretStr`.
- **Prompt en un fichero versionado**, no en un string del código.
- **Ejemplos estructurados con costes calculados por código**, en lugar de Markdown escrito a mano.
- **`finish_reason` normalizado** (`stop`, `length` u `other`), que no cambiará cuando haya varios proveedores. Además se devuelven `latency_ms`, `cost_usd` y `created_at`.
- **Sin CORS**: no hay frontend en el navegador, y una interfaz Streamlit llama desde el servidor.
- **`logging` estándar en lugar de structlog** y **sin Docker**: no aportan nada hasta que haya despliegue o base de datos.

### Privacidad y seguridad

- **Las transcripciones no se registran ni se guardan**: pueden contener datos personales (RGPD).
- **Registro del SDK limitado a `WARNING` con cualquier `LOG_LEVEL`**: a nivel `DEBUG`, el SDK de Anthropic y el cliente HTTP registran el cuerpo de las peticiones, con la transcripción incluida.
- **Prompt injection**: la transcripción viaja delimitada (`<transcripcion>…</transcripcion>`) en el mensaje de usuario, y el system prompt indica que sus instrucciones no cambian la tarea. Una etiqueta de cierre dentro del texto se neutraliza.
- **Coste por petición sin autenticación**: el servicio está pensado para uso local. La longitud de la transcripción está limitada (60.000 caracteres, del orden de 15.000 tokens).

## Cómo probarlo

```bash
uv sync
cp .env.example .env                 # rellenar ANTHROPIC_API_KEY

# Sin coste: tests, lint y tipos
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy app experiments

# Servicio (documentación interactiva en http://127.0.0.1:8000/docs)
uv run uvicorn app.main:app --reload
```

Con el servicio levantado (cada estimación cuesta menos de 0,003 USD):

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{"transcription": "Comercial: Gracias por la reunión. Resumo lo que necesitáis. Cliente: Somos una escuela de música. Queremos una landing para la campaña de matrícula con un formulario que cree el contacto en HubSpot, y un blog sencillo para publicar dos noticias al mes. Tenemos logotipo pero no diseño web. Comercial: ¿Plazo? Cliente: Que esté lista en un mes."}'
```

Pruebas con la API real (con coste): `uv run pytest -m live`.

## Verificación

- **Sin red**: 182 tests unitarios en verde, sin regresiones en los de la Sesión 01. `ruff check`, `ruff format --check` y `mypy --strict` sin errores.
- **Servicio levantado con una clave falsa** (sin coste):
  - Sin clave, el arranque falla nombrando `ANTHROPIC_API_KEY`.
  - `/health` devuelve 200 con `{"status": "healthy", "version": "0.2.0", "environment": "development"}`.
  - `/docs` devuelve 200.
  - Una transcripción corta devuelve 422.
  - El curl de estimación llega a Anthropic y devuelve 502 `authentication` con mensaje genérico.
  - El registro muestra la categoría del error sin la transcripción.
- **Con la API real**: pendiente de ejecutar con autorización del autor.
