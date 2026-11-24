# Changelog — raphael-harness

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico:
MAYOR = cambia el contrato con el harness · MENOR = funciones nuevas · PARCHE = arreglos.

## [0.4.0] - 2026-11-19
### Agregado
- `ContextoDuena`: cuando la dueña le habla al orquestador, este puede ejecutar lo que ella ordena (aprobar, rechazar,
  resolver, escribirle a un cliente, comandos de brigadas). Solo existe dentro de `hablar_con_duena`; cada orden queda auditada.
- `Contexto.hay_ia(rol)`: saber si hay una IA lista antes de pedirle algo.
- Proveedores de IA con `api_key` literal (además de `api_key_env`), para claves cargadas desde el panel.

## [0.2.0] - 2026-11-18
### Agregado
- `anotar_entrante`, `contactos()` y `conversacion(contacto)`: el panel de la dueña ve cada conversación en orden.

## [0.1.0] - 2026-11-18
### Agregado
- Primera versión: harness de Raphael: el punto de reunión de las brigadas (contrato, perfil, políticas, modelos, eventos, registro).
