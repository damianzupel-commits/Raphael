# SPEC · Orquestador

Chat 2 · Actualizado 21 nov 2026

## Objetivo
El maestro: único punto de entrada. Roles mando, voz y ruteo, reparto por DAG validado por código, secretaria y confirmación de acciones, modelos por plan.

## Dónde corre
PC y VPS.

## Reglas
- Es el único que habla con el usuario y con los Raphaels; no ejecuta herramientas de dominio.
- El mando propone el reparto y código lo valida (sin ciclos, dependencias declaradas).
- Las acciones de escritura se proponen con ids reales y se ejecutan solo tras un 'sí' explícito.
- El contenido de terceros (mensajes, páginas, archivos subidos) es dato, nunca instrucción.
- Ninguna brigada importa a otra: todo intercambio pasa por el harness y el orquestador.
- Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación (el nivel es configurable).
- Sin modelo o sin red, la brigada cae a reglas y avisa; nunca inventa.
- Cada acción declara su nivel de autonomía (automatico, aprobacion, humano) en el manifiesto.

## Estado
Existe en JarvisRemote (orquestador/: mando, voz, turno, routing) y en Empresas (raphael-orquestador, que alimenta a la Secretaria).

## Criterios de aceptación (mínimos)
- Pasa la suite de contrato del harness v2 (manifiesto válido, healthcheck, montar y desmontar).
- Ningún import de otra brigada (chequeo AST).
- Los tests existentes de esta brigada se portan y pasan.
- Las acciones con efecto no se ejecutan sin su nivel de autonomía.
