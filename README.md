# AI Engineering · Máster de Ingeniería de IA (LIDR)

Repositorio de entregas del programa **AI Engineering**: una única aplicación que se construye y evoluciona sesión a sesión.

**Autor:** Julián Castiñeira
**GitHub:** [@Julian-Castineira](https://github.com/Julian-Castineira)
**LinkedIn:** [Julián Castiñeira](https://www.linkedin.com/in/juliancastineira/)

## Descripción

Cada sesión del máster amplía o modifica la aplicación anterior. La rama `main` contiene siempre la versión acumulada; cada entrega se puede revisar por separado a través de su rama, su pull request y su tag.

## Cómo revisar una entrega

| Qué revisar | Dónde |
|-------------|-------|
| Solo los cambios de la sesión | Pull request `sesion-NN → main` |
| La aplicación completa tal como se entregó | Tag `entrega-sesion-NN` |
| El trabajo realizado durante la sesión | Rama `sesion-NN` |
| La memoria de la entrega | `docs/sesiones/sesion-NN.md` |

## Estructura

```
.
├── app/                   # Aplicación (paquete Python)
│   ├── config.py          # Configuración desde variables de entorno / .env
│   └── services/          # Lógica de negocio; llm_service.py es el acceso a Claude
├── experiments/           # Scripts de experimentación con la API (NN_tema.py)
├── tests/
│   ├── unit/              # Tests sin red ni API key (LLM simulado)
│   └── live/              # Smoke test contra la API real (opt-in, con coste)
├── docs/
│   └── sesiones/          # Memoria de cada entrega (sesion-NN.md)
├── ejercicios/            # Solo ejercicios independientes de la aplicación (sesion-NN/)
├── openspec/              # Specs de la aplicación y cambios por sesión
├── pyproject.toml         # Proyecto y dependencias (uv)
└── .env.example           # Variables de entorno documentadas, sin valores reales
```

Stack: Python 3.11+ con [uv](https://docs.astral.sh/uv/), SDK oficial `anthropic` 2.x (API `2026-10-21`), Pydantic Settings, pytest, ruff y mypy. Modelo por defecto: `claude-haiku-5-5`.

## Índice de entregas

| Sesión | Descripción | Rama | PR | Tag | Memoria | Estado |
|--------|-------------|------|----|-----|---------|--------|
| 01 | LLMs y setup: cliente de la Messages API de Anthropic con métricas, errores tipados y experimentos de parámetros | `sesion-01` | [#2](https://github.com/Julian-Castineira/lidr-ai-engineering/pull/2) | — | [sesion-01.md](docs/sesiones/sesion-01.md) | En revisión |

## Cómo ejecutar

Requisitos: [uv](https://docs.astral.sh/uv/getting-started/installation/) (instala Python 3.12 si hace falta) y una API key de Anthropic.

```bash
uv sync                      # crea .venv e instala dependencias desde uv.lock
cp .env.example .env         # y rellena ANTHROPIC_API_KEY en .env
```

Calidad (sin red ni API key):

```bash
uv run pytest                # tests unitarios; el smoke test real queda excluido
uv run ruff check .
uv run ruff format --check .
uv run mypy app experiments
```

Llamadas reales a la API (tienen coste, del orden de céntimos):

```bash
uv run pytest -m live                         # smoke test: una llamada
uv run python -m experiments.01_basic         # ver experiments/ para el resto (01 a 08)
```

La memoria de cada entrega indica cómo probar lo añadido en esa sesión.

## Seguridad

- Este repositorio es público: no se suben claves de API, archivos `.env`, credenciales ni datos de clientes.
- Las variables de entorno se documentan en un archivo `.env.example` sin valores reales.
