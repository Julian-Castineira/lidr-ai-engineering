# Spec Delta

## Purpose

Ofrece experimentos ejecutables desde la línea de comandos que muestran, con llamadas reales a Claude, el efecto de cada parámetro de la Messages API y la forma de su respuesta, como material de aprendizaje y de demostración de la entrega.

## ADDED Requirements

### Requirement: Experimentos ejecutables con métricas
Cada experimento SHALL poder lanzarse con un único comando, usar la capa de acceso a Claude de la aplicación e imprimir para cada llamada el contenido, el modelo, `stop_reason`, los tokens, la latencia y el coste.

#### Scenario: Ejecución de un experimento
- **GIVEN** una API key válida configurada
- **WHEN** se ejecuta el experimento de llamada básica
- **THEN** se imprime la respuesta y sus métricas, y el proceso termina con código 0

#### Scenario: Sin API key
- **GIVEN** un entorno sin API key
- **WHEN** se ejecuta cualquier experimento
- **THEN** se imprime un mensaje que explica cómo configurar `.env`, no se llama al proveedor y el proceso termina con código distinto de 0

#### Scenario: Error del proveedor durante un experimento
- **GIVEN** un proveedor que devuelve un error en una de las llamadas
- **WHEN** se ejecuta el experimento
- **THEN** se imprime la categoría y el mensaje del error de esa llamada y el experimento continúa con las demás

### Requirement: Cobertura de parámetros de la lección
El conjunto de experimentos SHALL cubrir: llamada básica con system prompt, conversación multiturno, variación de `temperature`, `top_p` y `top_k`, truncado por `max_tokens`, `stop_sequences` y razonamiento extendido. Los experimentos usan el modelo por defecto salvo los de muestreo y `budget_tokens`, que usan el modelo legacy configurado con la versión de API legacy.

#### Scenario: Variación de temperatura
- **WHEN** se ejecuta el experimento de temperatura
- **THEN** se lanza el mismo prompt varias veces en el modelo legacy, con la versión de API legacy, con al menos dos valores de `temperature` (0 y 1) y se imprimen las respuestas agrupadas por valor
- **AND** se muestra el rechazo `bad_request` del modelo por defecto con `temperature` 0 y la versión de API vigente

#### Scenario: Modelo legacy no disponible
- **GIVEN** un modelo legacy retirado o inexistente
- **WHEN** se ejecuta un experimento que lo usa
- **THEN** la salida muestra el error `not_found`, indica que el modelo legacy ya no está disponible y el proceso termina con código 0

#### Scenario: Truncado por límite de tokens
- **WHEN** se ejecuta el experimento de `max_tokens` con un límite bajo
- **THEN** la salida muestra `stop_reason` `max_tokens` y el aviso de truncado

#### Scenario: Secuencia de parada
- **WHEN** se ejecuta el experimento de `stop_sequences`
- **THEN** la salida muestra `stop_reason` `stop_sequence` y la secuencia que detuvo la generación

#### Scenario: Razonamiento adaptativo con niveles de esfuerzo
- **WHEN** se ejecuta el experimento de razonamiento sobre el modelo por defecto con al menos dos niveles de `effort` (`low` y `high`) y resumen de razonamiento visible
- **THEN** la salida separa el resumen de razonamiento de la respuesta final y muestra, por nivel, los tokens de salida, la latencia y el coste

#### Scenario: Razonamiento con presupuesto fijo
- **WHEN** se ejecuta la parte del experimento de razonamiento sobre el modelo legacy con un presupuesto de al menos 1.024 tokens menor que `max_tokens`
- **THEN** la salida separa el razonamiento de la respuesta final y muestra los tokens de salida consumidos
- **AND** se muestra el rechazo `bad_request` del mismo presupuesto fijo en el modelo por defecto

#### Scenario: Combinación de parámetros no admitida
- **WHEN** un experimento envía una combinación que el modelo rechaza (por ejemplo, `temperature` y `top_p` a la vez, o razonamiento con `temperature` distinta de 1)
- **THEN** la salida muestra el error `bad_request` devuelto como resultado esperado del experimento, no como fallo del script

### Requirement: Comparación entre generaciones de modelo
El sistema SHALL incluir un experimento que ejecute el mismo prompt en el modelo por defecto y en el modelo legacy configurado y muestre las diferencias observables de parámetros admitidos, bloques de respuesta, tokens y coste.

#### Scenario: Mismo prompt en ambas generaciones
- **WHEN** se ejecuta el experimento de comparación
- **THEN** la salida muestra, para cada modelo, los tipos de bloque recibidos, los tokens de entrada y salida, la latencia y el coste

#### Scenario: Parámetro de muestreo no admitido
- **WHEN** el experimento envía `temperature` distinta de 1 a ambos modelos
- **THEN** el modelo legacy responde con normalidad y el modelo por defecto muestra el rechazo `bad_request`, seguido de la misma consulta sin ese parámetro con su respuesta y su coste

### Requirement: Coste acotado de los experimentos
Cada llamada de los experimentos MUST usar `max_tokens` ≤ 2.048 y cada experimento SHALL imprimir al final el coste total acumulado de sus llamadas.

#### Scenario: Resumen de coste
- **WHEN** termina un experimento
- **THEN** se imprime el número de llamadas, los tokens totales y el coste total en USD
