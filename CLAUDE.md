# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito del repositorio

Repositorio **público** de entregas del Máster AI Engineering de LIDR: ejercicios y proyectos, uno por carpeta. No es un único producto, sino una colección de entregas independientes.

## Estructura y convenciones

- Cada entrega vive en su propia carpeta, siguiendo el patrón del README: `modulo-NN-<nombre>/ejercicio-NN/` y `proyecto-final/`. La estructura puede ajustarse a medida que avance el programa.
- Cada entrega es autocontenida: tiene su propio `README.md` con requisitos, instalación y ejecución, y sus propias dependencias. Los comandos de build, test y lint se definen por entrega, no a nivel de raíz; consulta el README de la carpeta antes de ejecutar nada.
- Al añadir o cerrar una entrega, actualiza la tabla «Índice de entregas» del `README.md` raíz.
- Variables de entorno: documentadas en un `.env.example` por entrega, sin valores reales. Al ser un repo público, nada de claves, `.env`, credenciales ni datos o nombres de clientes.

## Git

- Mensajes de commit en español (prevalece sobre la regla global de commits en inglés).

## OpenSpec

El repo usa OpenSpec (`openspec/`, schema `spec-driven`) para los cambios no triviales: las specs vigentes en `openspec/specs/`, los cambios en curso en `openspec/changes/` y los cerrados en `openspec/changes/archive/`. Usa las skills `openspec-*` instaladas en lugar de un proceso paralelo.

`openspec/config.yaml` está aún sin `context` ni `rules`: complétalo con el stack real cuando exista la primera entrega con código.
