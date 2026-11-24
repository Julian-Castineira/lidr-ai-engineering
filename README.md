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
├── README.md
├── docs/
│   └── sesiones/          # Memoria de cada entrega (sesion-NN.md)
├── ejercicios/            # Solo ejercicios independientes de la aplicación (sesion-NN/)
└── openspec/              # Specs de la aplicación y cambios por sesión
```

> La estructura de la aplicación se definirá con el stack de la primera sesión.

## Índice de entregas

| Sesión | Descripción | Rama | PR | Tag | Memoria | Estado |
|--------|-------------|------|----|-----|---------|--------|
| 01 | [Resumen breve] | `sesion-01` | — | — | — | Pendiente |

## Cómo ejecutar

Las instrucciones de instalación y ejecución de la aplicación se documentarán aquí a partir de la primera sesión. La memoria de cada entrega indica cómo probar lo añadido en esa sesión.

## Seguridad

- Este repositorio es público: no se suben claves de API, archivos `.env`, credenciales ni datos de clientes.
- Las variables de entorno se documentan en un archivo `.env.example` sin valores reales.
