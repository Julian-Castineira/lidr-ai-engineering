# Spec Delta

## Purpose

Expone el estimador de proyectos de software como un servicio HTTP: recibe la transcripción de una reunión y devuelve una estimación generada por un LLM con contexto precargado (CAG), junto con sus métricas de uso, o un error tipado.

## ADDED Requirements

### Requirement: Estimación a partir de una transcripción
El servicio SHALL exponer `POST /api/v1/estimate`, que acepta un cuerpo JSON `{"transcription": <texto>}`, construye el contexto del estimador, consulta al LLM configurado y responde 200 con la estimación generada.

#### Scenario: Estimación correcta
- **GIVEN** un servicio configurado y un LLM que responde con una estimación en Markdown
- **WHEN** se envía `POST /api/v1/estimate` con una transcripción válida
- **THEN** la respuesta es 200 y `estimation` contiene el texto devuelto por el LLM

#### Scenario: La transcripción llega al LLM como mensaje de usuario
- **WHEN** se envía una transcripción válida
- **THEN** el LLM recibe la transcripción en un mensaje de usuario, separada de las instrucciones del system prompt

### Requirement: Validación de la entrada
El servicio MUST rechazar con 422, sin consultar al LLM, un cuerpo sin `transcription`, con campos desconocidos, con una transcripción de menos de 50 caracteres sin contar los espacios de los extremos o con una que supere el máximo configurado.

#### Scenario: Transcripción demasiado corta
- **WHEN** se envía una transcripción de 49 caracteres o formada solo por espacios
- **THEN** la respuesta es 422 y no se realiza ninguna llamada al LLM

#### Scenario: Transcripción demasiado larga
- **GIVEN** un máximo configurado de 60.000 caracteres
- **WHEN** se envía una transcripción de 60.001 caracteres
- **THEN** la respuesta es 422 y no se realiza ninguna llamada al LLM

#### Scenario: Cuerpo inválido
- **WHEN** se envía un cuerpo sin `transcription`, con un campo adicional o con JSON mal formado
- **THEN** la respuesta es 422 y no se realiza ninguna llamada al LLM

#### Scenario: Cuerpo con codificación inválida
- **WHEN** se envía un cuerpo que no es UTF-8 válido
- **THEN** la respuesta es 400 y no se realiza ninguna llamada al LLM

### Requirement: Contrato de la respuesta de estimación
La respuesta 200 SHALL contener `estimation`, `model` (el modelo exacto que sirvió la respuesta), `provider`, `usage` con `input_tokens`, `output_tokens` y `total_tokens`, `finish_reason`, `latency_ms`, `cost_usd` (nulo si el modelo no tiene precio configurado) y `created_at` en ISO 8601 con zona horaria UTC.

#### Scenario: Campos y métricas
- **GIVEN** un LLM que informa 4.000 tokens de entrada y 1.000 de salida con el modelo `claude-haiku-5-5`
- **WHEN** se obtiene una estimación
- **THEN** la respuesta incluye `model` `claude-haiku-5-5`, `provider` `anthropic`, `usage.total_tokens` 5.000, `latency_ms` no negativa, `cost_usd` 0,0009 y `created_at` en UTC

#### Scenario: Modelo sin precio configurado
- **GIVEN** un LLM que responde con un modelo ausente de la tabla de precios
- **WHEN** se obtiene una estimación
- **THEN** la respuesta es 200 con `cost_usd` nulo

### Requirement: Motivo de finalización independiente del proveedor
La respuesta SHALL informar `finish_reason` con un valor independiente del proveedor: `stop` cuando el modelo termina de forma natural o por secuencia de parada, `length` cuando alcanza el límite de tokens y `other` en cualquier otro caso.

#### Scenario: Finalización natural
- **WHEN** el LLM termina con `end_turn`
- **THEN** `finish_reason` es `stop`

#### Scenario: Estimación truncada
- **WHEN** el LLM se detiene por alcanzar el límite de tokens
- **THEN** la respuesta es 200 con el texto parcial y `finish_reason` `length`
- **AND** se registra un aviso de truncado

### Requirement: Traducción de errores del proveedor a HTTP
El servicio SHALL responder a los fallos del LLM con un código HTTP según su categoría y un cuerpo `{"detail": {"error_type", "message"}}`, cuyo mensaje es genérico y MUST NOT incluir la API key, trazas ni el mensaje literal del proveedor.

#### Scenario: Negativa del modelo
- **WHEN** el LLM declina la petición
- **THEN** la respuesta es 422 con `error_type` `refusal`

#### Scenario: Límite de peticiones o configuración inválida
- **WHEN** el LLM devuelve un error de categoría `rate_limit` o `configuration`
- **THEN** la respuesta es 503 con esa categoría en `error_type`

#### Scenario: Timeout del proveedor
- **WHEN** el LLM no responde dentro del timeout configurado
- **THEN** la respuesta es 504 con `error_type` `timeout`

#### Scenario: Fallo del proveedor
- **WHEN** el LLM devuelve un error de categoría `authentication`, `permission`, `not_found`, `bad_request`, `server`, `connection` o `api`
- **THEN** la respuesta es 502 con esa categoría en `error_type` y sin el mensaje literal del proveedor

### Requirement: Salud del servicio
El servicio SHALL exponer `GET /health`, que responde 200 con `status` `healthy`, la versión de la aplicación y el entorno configurado, sin consultar al LLM.

#### Scenario: Servicio en marcha
- **GIVEN** un servicio arrancado con `APP_ENV` `development`
- **WHEN** se consulta `GET /health`
- **THEN** la respuesta es 200 con `status` `healthy`, `version` y `environment` `development`, y no se realiza ninguna llamada al LLM

### Requirement: Documentación interactiva de la API
El servicio SHALL publicar su esquema OpenAPI y una interfaz interactiva en `/docs`, con título, descripción, versión y los esquemas de petición y respuesta del endpoint de estimación.

#### Scenario: Consulta de la documentación
- **WHEN** se consulta `/docs` o `/openapi.json`
- **THEN** la respuesta es 200 y el esquema incluye `POST /api/v1/estimate` con sus modelos de petición y respuesta y `GET /health`

### Requirement: Validación de la configuración al arrancar
El servicio MUST negarse a arrancar, con un error que nombre la variable afectada y sin revelar valores secretos, si falta `ANTHROPIC_API_KEY` o si alguna variable de configuración es inválida.

#### Scenario: API key ausente
- **GIVEN** un entorno sin `ANTHROPIC_API_KEY`
- **WHEN** se arranca el servicio
- **THEN** el arranque falla con un error que nombra `ANTHROPIC_API_KEY`

#### Scenario: Proveedor no soportado
- **GIVEN** un entorno con `LLM_PROVIDER` `openai`
- **WHEN** se arranca el servicio
- **THEN** el arranque falla con un error de validación que nombra `LLM_PROVIDER`

### Requirement: Registro por estimación sin datos de la transcripción
El servicio SHALL registrar una línea por cada estimación con el modelo, los tokens, la latencia, el coste, el motivo de finalización y la versión del prompt (o la categoría del error si falla), y MUST NOT registrar el contenido de la transcripción ni de la estimación.

#### Scenario: Estimación registrada
- **WHEN** se completa una estimación
- **THEN** se emite un registro con modelo, tokens, latencia, coste, `finish_reason` y versión del prompt, y ningún registro contiene el texto de la transcripción

#### Scenario: Error registrado
- **WHEN** una estimación falla por un error del proveedor
- **THEN** se emite un registro con la categoría del error, sin el texto de la transcripción

### Requirement: Nivel de registro configurable
El servicio SHALL aplicar el nivel de registro de `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL`) al arrancar.

#### Scenario: Nivel informativo
- **GIVEN** `LOG_LEVEL` `WARNING`
- **WHEN** se completa una estimación sin incidencias
- **THEN** no se emite el registro informativo de la estimación
