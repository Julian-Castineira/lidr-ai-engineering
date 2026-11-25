# llm-client Specification

## Purpose

Proporciona a la aplicación un acceso configurable, observable y tolerante a fallos a los modelos Claude a través de la Messages API de Anthropic, para que las capas superiores pidan una respuesta y reciban contenido, métricas o un error tipado.

## Requirements

### Requirement: Configuración desde el entorno
El sistema SHALL leer la API key, el modelo por defecto, la temperatura y el nivel de `effort` opcionales, `max_tokens`, el timeout, el número de reintentos, el modelo legacy de los experimentos y la tabla de precios de variables de entorno o de un fichero `.env`, con valores por defecto documentados en `.env.example` salvo la API key.

#### Scenario: Configuración válida
- **GIVEN** un entorno con `ANTHROPIC_API_KEY` definida y el resto de variables ausentes
- **WHEN** la aplicación carga la configuración
- **THEN** usa la API key del entorno y los valores por defecto documentados: modelo `claude-haiku-5-5`, `max_tokens` 4096, sin temperatura ni `effort` fijados, modelo legacy `claude-haiku-4-5-20251001` y versión de API legacy `2023-06-01`

#### Scenario: Valor de configuración inválido
- **GIVEN** un entorno con una temperatura fuera del rango 0–1, un `effort` distinto de `low`, `medium`, `high`, `xhigh` o `max`, o un `max_tokens` menor que 1
- **WHEN** la aplicación carga la configuración
- **THEN** la carga falla con un error de validación que nombra la variable incorrecta, sin realizar ninguna llamada al proveedor

### Requirement: Protección de la API key
El sistema MUST NOT incluir la API key en logs, mensajes de error, resultados ni en la representación textual de la configuración.

#### Scenario: Representación de la configuración
- **GIVEN** una configuración cargada con una API key
- **WHEN** se imprime o registra la configuración
- **THEN** la API key aparece enmascarada y su valor no figura en la salida

#### Scenario: API key ausente
- **GIVEN** un entorno sin `ANTHROPIC_API_KEY`
- **WHEN** se solicita una consulta al modelo
- **THEN** el sistema devuelve un error tipado de configuración que indica que falta la variable, sin llamar al proveedor

### Requirement: Consulta de un solo turno
El sistema SHALL aceptar un mensaje de usuario, un system prompt opcional y overrides opcionales de modelo y temperatura, enviar la petición a la Messages API con `max_tokens` siempre informado y devolver el texto concatenado de los bloques de tipo texto de la respuesta.

#### Scenario: Parámetros opcionales no fijados
- **GIVEN** una configuración sin temperatura ni `effort` y una consulta sin override de temperatura
- **WHEN** se consulta al modelo por defecto
- **THEN** la petición no incluye `temperature` ni `effort`, y el modelo aplica sus valores por defecto

#### Scenario: Parámetros opcionales fijados
- **GIVEN** una configuración con `effort` `low`
- **WHEN** se consulta con temperatura 0,3
- **THEN** la petición incluye `temperature` 0,3 y `effort` `low` tal cual, sin que el sistema decida si el modelo los admite

#### Scenario: Respuesta correcta
- **GIVEN** un proveedor que responde con un bloque de texto y `stop_reason` `end_turn`
- **WHEN** se consulta «¿Qué es un LLM?» con un system prompt
- **THEN** el resultado contiene el texto devuelto, el modelo exacto que indica la respuesta, el `id` del mensaje y `stop_reason` `end_turn`
- **AND** el system prompt se envió como parámetro de primer nivel, no como mensaje

#### Scenario: Respuesta con bloques de razonamiento antes del texto
- **GIVEN** un proveedor que responde con un bloque `thinking` seguido de un bloque de texto
- **WHEN** se consulta al modelo
- **THEN** el contenido del resultado es solo el texto del bloque de texto

#### Scenario: Mensaje vacío
- **WHEN** se consulta con un mensaje vacío o formado solo por espacios
- **THEN** el sistema devuelve un error tipado de validación sin llamar al proveedor

### Requirement: Métricas por llamada
Cada resultado correcto SHALL incluir tokens de entrada y de salida, tokens de escritura y lectura de caché cuando el proveedor los informe, latencia en milisegundos medida alrededor de la llamada y coste en USD calculado de forma determinista a partir de la tabla de precios configurada.

#### Scenario: Coste calculado
- **GIVEN** un modelo con precio configurado de 0,10 USD/MTok de entrada y 0,50 USD/MTok de salida hasta 100.000 tokens de prompt
- **WHEN** una respuesta informa 10.000 tokens de entrada y 2.000 de salida
- **THEN** `cost_usd` es 0,002 y `latency_ms` es un número no negativo

#### Scenario: Precio por tramos según longitud del prompt
- **GIVEN** un modelo con precio por tramos (hasta 100.000 tokens de prompt y por encima)
- **WHEN** una respuesta informa más de 100.000 tokens de prompt, contando los de caché
- **THEN** el coste usa los precios del tramo superior para toda la petición

#### Scenario: Modelo sin precio configurado
- **GIVEN** un modelo que no figura en la tabla de precios
- **WHEN** se completa una consulta con ese modelo
- **THEN** el resultado se devuelve con `cost_usd` nulo y se emite un aviso, sin estimar un coste

### Requirement: Aviso de respuesta truncada
El sistema SHALL emitir un aviso y conservar `stop_reason` `max_tokens` en el resultado cuando la respuesta se corte por alcanzar el límite de tokens.

#### Scenario: Respuesta truncada
- **GIVEN** un proveedor que responde con `stop_reason` `max_tokens`
- **WHEN** se consulta al modelo
- **THEN** el resultado contiene el texto parcial y `stop_reason` `max_tokens`
- **AND** se registra un aviso de truncado

### Requirement: Versión de API por petición
El sistema SHALL permitir fijar la versión de API (`anthropic-version`) de una petición concreta; sin ese override, la petición usa la versión por defecto del SDK.

#### Scenario: Versión fijada
- **WHEN** se consulta con la versión de API `2023-06-01`
- **THEN** la petición se envía con la cabecera `anthropic-version: 2023-06-01`

#### Scenario: Versión por defecto
- **WHEN** se consulta sin fijar versión de API
- **THEN** la petición no sobrescribe la cabecera `anthropic-version` del SDK

### Requirement: Negativa del modelo
El sistema SHALL devolver un error tipado de categoría `refusal` cuando la respuesta tenga `stop_reason` `refusal`, incluyendo la categoría de la negativa si el proveedor la informa, y MUST NOT presentar como respuesta válida el texto parcial que pudiera acompañarla.

#### Scenario: Petición declinada
- **GIVEN** un proveedor que responde con `stop_reason` `refusal` y categoría `cyber`
- **WHEN** se consulta al modelo
- **THEN** el resultado es un error de categoría `refusal` cuyo mensaje incluye `cyber`, sin código HTTP
- **AND** se registra un aviso

### Requirement: Conversación multiturno sin estado en el proveedor
El sistema SHALL mantener el historial de la conversación en el cliente y reenviarlo completo en cada turno, empezando por un mensaje `user` y alternando estrictamente `user` y `assistant`.

#### Scenario: Segundo turno con contexto
- **GIVEN** una conversación con un turno previo de usuario y su respuesta
- **WHEN** el usuario envía un segundo mensaje
- **THEN** la petición incluye los tres mensajes en orden `user`, `assistant`, `user`
- **AND** la respuesta se añade al historial como mensaje `assistant`

#### Scenario: Historial inválido
- **WHEN** se intenta enviar un historial que empieza por `assistant` o con dos mensajes seguidos del mismo rol
- **THEN** el sistema devuelve un error tipado de validación sin llamar al proveedor

#### Scenario: Turno fallido
- **GIVEN** una conversación en curso
- **WHEN** la llamada del nuevo turno falla
- **THEN** el historial queda como estaba antes del turno fallido

### Requirement: Errores del proveedor tipados
El sistema SHALL convertir los fallos del proveedor en un resultado de error con categoría, mensaje legible y código HTTP cuando exista, en lugar de propagar la excepción.

#### Scenario: Clave inválida
- **GIVEN** un proveedor que responde 401
- **WHEN** se consulta al modelo
- **THEN** el resultado es un error de categoría `authentication` con código 401

#### Scenario: Petición inválida o sin crédito
- **GIVEN** un proveedor que responde 400
- **WHEN** se consulta al modelo
- **THEN** el resultado es un error de categoría `bad_request` con el mensaje del proveedor

#### Scenario: Límite de peticiones
- **GIVEN** un proveedor que responde 429 tras agotar los reintentos
- **WHEN** se consulta al modelo
- **THEN** el resultado es un error de categoría `rate_limit` con código 429

#### Scenario: Proveedor sobrecargado o caído
- **GIVEN** un proveedor que responde 500 o 529 tras agotar los reintentos
- **WHEN** se consulta al modelo
- **THEN** el resultado es un error de categoría `server` con el código recibido

#### Scenario: Fallo de red o timeout
- **GIVEN** un proveedor inalcanzable o que no responde dentro del timeout configurado
- **WHEN** se consulta al modelo
- **THEN** el resultado es un error de categoría `connection` o `timeout`, sin código HTTP

### Requirement: Reintentos acotados
El sistema SHALL reintentar únicamente errores transitorios (conexión, timeout, 408, 409, 429 y 5xx) con el número de reintentos configurado, y MUST NOT reintentar errores 400, 401, 403 ni 404.

#### Scenario: Error no transitorio
- **GIVEN** un proveedor que responde 401
- **WHEN** se consulta al modelo
- **THEN** se realiza una única petición

#### Scenario: Error transitorio recuperado
- **GIVEN** un proveedor que responde 529 una vez y después responde correctamente, con reintentos configurados a 2
- **WHEN** se consulta al modelo
- **THEN** el resultado es correcto

### Requirement: Verificación sin coste ni red
La suite de tests por defecto MUST ejecutarse sin red ni API key, y la prueba contra el proveedor real SHALL ejecutarse solo cuando se active de forma explícita.

#### Scenario: Ejecución por defecto
- **GIVEN** un entorno sin API key ni acceso a red
- **WHEN** se ejecuta la suite de tests por defecto
- **THEN** todos los tests pasan y la prueba real aparece como omitida

#### Scenario: Prueba real activada
- **GIVEN** una API key válida y la prueba real activada explícitamente
- **WHEN** se ejecuta la prueba real
- **THEN** se realiza una única llamada al modelo por defecto con `max_tokens` ≤ 256 y `effort` `low`, y el resultado contiene texto, tokens mayores que cero y coste no nulo
