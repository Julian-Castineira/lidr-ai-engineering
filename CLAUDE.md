# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito del repositorio

Repositorio **público** de entregas del Máster AI Engineering de LIDR. Es **una única aplicación que evoluciona sesión a sesión**: cada sesión construye sobre la anterior y puede añadir funcionalidades o refactorizar a fondo el código existente. `main` contiene siempre la versión acumulada.

## Estructura

- La aplicación vive en una sola estructura evolutiva, no en carpetas por sesión: paquete `app/` en la raíz con `main.py` (FastAPI, `lifespan` y `/health`), `config.py`, `routers/` (endpoints finos bajo `/api/v1`), `schemas/` (contratos HTTP), `context/` (conocimiento precargado, CAG), `prompts/` (prompts versionados `nombre.vN.md`) y la lógica en `services/` (`llm_service.py` es el único módulo de `app/` que importa el SDK de Anthropic). Scripts de experimentación en `experiments/` y tests en `tests/unit` (sin red) y `tests/live` (API real, opt-in).
- `docs/sesiones/sesion-NN.md`: memoria de cada entrega (enunciado resumido, qué se hizo, decisiones y cómo probarlo). Es lo primero que lee el profesor.
- `ejercicios/sesion-NN/`: solo para ejercicios independientes que no formen parte de la aplicación.
- Stack: Python 3.11+ con uv. Comandos: `uv sync`, `uv run pytest` (excluye los tests `live`), `uv run pytest -m live` (con coste), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app experiments` y `uv run uvicorn app.main:app --reload` (servicio, documentación en `/docs`).

## Flujo de entrega por sesión

El profesor evalúa cada sesión por separado, así que este flujo no debe romperse:

1. Rama `sesion-NN` (dos dígitos) creada desde `main` actualizado, con la sesión anterior ya fusionada.
2. Pull request `sesion-NN → main` con la descripción de la entrega.
3. Al entregar, tag anotado `entrega-sesion-NN` sobre el último commit entregado.
4. Fusión en `main` en el momento de la entrega, sin esperar a la corrección, con **merge commit** (`--no-ff`); nunca squash ni rebase.
5. Las ramas `sesion-NN` no se borran, y ni ellas ni los tags `entrega-sesion-NN` se reescriben tras la entrega. Las correcciones por feedback van en una rama nueva o en la sesión siguiente.
6. Al cerrar cada sesión, añade su memoria en `docs/sesiones/` y su fila en el «Índice de entregas» del `README.md` (rama, PR, tag, memoria y estado). La actualización final de la fila (tag y estado «Entregada») se commitea en `sesion-NN` antes de crear el tag, para que la entrega la incluya y no haga falta un commit directo en `main`.

Los cambios que no son de una sesión (configuración, documentación general) van en ramas `chore/<descripción>`.

## Git

- Mensajes de commit en español (prevalece sobre la regla global de commits en inglés).

## OpenSpec

El repo usa OpenSpec (`openspec/`, schema `spec-driven`) para los cambios no triviales: las specs vigentes en `openspec/specs/`, los cambios en curso en `openspec/changes/` y los cerrados en `openspec/changes/archive/`. Usa las skills `openspec-*` instaladas en lugar de un proceso paralelo. Cada funcionalidad de una sesión es un cambio de OpenSpec que se verifica con `openspec-verify-change` y se archiva antes de fusionar, de modo que `openspec/specs/` describe la aplicación completa.

`openspec/config.yaml` define el `context` del repo y las `rules` por artefacto (proposal, specs, design, tasks) que OpenSpec inyecta al generar cada artefacto. Mantén su `context` al día cuando cambien el stack, los modelos o la estructura.

## Seguridad

Repo público: nada de claves, `.env`, credenciales, datos reales ni nombres de clientes. Variables de entorno documentadas en `.env.example` sin valores reales.
