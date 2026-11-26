# Spec Delta

## ADDED Requirements

### Requirement: Consulta asíncrona
El sistema SHALL ofrecer una variante asíncrona de la consulta a la Messages API que acepte los mismos parámetros que la consulta síncrona y devuelva el mismo contrato de resultado o de error tipado, sin bloquear el bucle de eventos durante la llamada al proveedor.

#### Scenario: Resultado equivalente
- **GIVEN** un proveedor que responde con un bloque de texto, 10.000 tokens de entrada y 2.000 de salida
- **WHEN** se consulta de forma asíncrona con un system prompt
- **THEN** el resultado contiene el texto, el modelo exacto, el `id`, `stop_reason`, los tokens, `latency_ms` no negativa y `cost_usd` 0,002, igual que la consulta síncrona

#### Scenario: Errores equivalentes
- **GIVEN** un proveedor que responde 401, 429, 529 tras agotar los reintentos o que no responde dentro del timeout
- **WHEN** se consulta de forma asíncrona
- **THEN** el resultado es el mismo error tipado que devolvería la consulta síncrona, sin propagar la excepción

#### Scenario: Negativa y API key ausente
- **WHEN** se consulta de forma asíncrona sin `ANTHROPIC_API_KEY` o el proveedor declina la petición
- **THEN** el resultado es un error tipado de categoría `configuration` o `refusal`, respectivamente

#### Scenario: Consultas concurrentes
- **GIVEN** un proveedor que tarda 200 ms en responder cada petición
- **WHEN** se lanzan dos consultas asíncronas a la vez
- **THEN** ambas terminan en menos de 400 ms en total

### Requirement: Selección de proveedor por configuración
El sistema SHALL leer el proveedor de LLM de `LLM_PROVIDER`, con `anthropic` como valor por defecto y único admitido, e incluirlo en la información que acompaña a cada resultado.

#### Scenario: Proveedor por defecto
- **GIVEN** un entorno sin `LLM_PROVIDER`
- **WHEN** se carga la configuración
- **THEN** el proveedor es `anthropic`

#### Scenario: Proveedor no soportado
- **GIVEN** un entorno con `LLM_PROVIDER` `openai`
- **WHEN** se carga la configuración
- **THEN** la carga falla con un error de validación que nombra `LLM_PROVIDER`
