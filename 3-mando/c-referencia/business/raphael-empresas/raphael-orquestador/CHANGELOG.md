# Changelog — raphael-orquestador

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico:
MAYOR = cambia el contrato con el harness · MENOR = funciones nuevas · PARCHE = arreglos.

## [0.3.0] - 2026-11-19
### Agregado
- El secretario ahora **hace lo que le pedís**: «aprobá la 2», «rechazá la 3», «respondele a la 1: …», «pasá el encargo 4 a listo».
  Funciona con reglas, sin IA. Todo cambio pide un «sí» antes de ejecutarse (y cualquier otra frase lo cancela).
- Con IA entiende frases libres («mandale el precio a Lola y avisale que va con seña») y organiza el día: el modelo recibe las
  tareas reales y contesta con un JSON; solo puede proponer acciones que existan sobre tareas reales, nunca inventa ni ejecuta solo.
- Memoria corta de la charla (últimos turnos) para que «y esa?» o «dale con la otra» tengan sentido.
### Cambia
- Requiere raphael-harness >= 0.4 (`ContextoDuena`).

## [0.2.0] - 2026-11-19
### Agregado
- Modo secretario: la dueña le habla al orquestador («¿qué tareas tenemos hoy?», «¿cuál hago primero?», «contame la 2»).
  Junta lo pendiente de todas las brigadas activas y lo ordena por urgencia con reglas (sin IA).
- Cuando algo requiere a la dueña, le da el contexto de la conversación y las salidas posibles, con una recomendada.
- Si el plan tiene IA: resume conversaciones (rol `resumen`) y contesta frases libres (rol `secretaria`) usando solo la lista del día.
### Cambia
- Requiere raphael-harness 0.3 (`Orquestador.atender_duena`, `Charla`).

## [0.1.0] - 2026-11-18
### Agregado
- Primera versión: orquestador de Raphael: decide qué brigada atiende cada mensaje.
