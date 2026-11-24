# Arquitectura de Raphael

## Un núcleo, muchas empresas

El código es el mismo para todos los clientes. Lo que cambia es el **perfil de empresa**
(`perfil.yaml`): datos del negocio, reglas, brigadas contratadas y plan. Nunca se escribe código
para un cliente en particular.

## Un repo por pieza, un punto de reunión

| Repo | Responsabilidad | Depende de |
|---|---|---|
| raphael-harness | Contrato, perfil, políticas, modelos, eventos, almacén, uso, supervisión, CLI | pydantic, pyyaml, httpx |
| raphael-orquestador | Ordenar qué brigada atiende cada mensaje | harness |
| raphael-atencion | Responder con lo cargado, anotar dudas, derivar reclamos | harness |
| raphael-encargos | Tomar pedidos, sugerir presupuesto, estados | harness |
| raphael-cobros | Avisos de pago de seña | harness |
| raphael-agenda | Turnos y recordatorios | harness |
| raphael-avisos | Avisos de cambio de estado | harness |
| raphael-servidor | Equipo del cliente: API + panel PWA, Meta, licencia, latido, backups, Docker | harness + brigadas (instaladas) |
| raphael-relay | Nube: webhooks de Meta → cola por instalación | — |
| raphael-central | Damián: licencias + panel de soporte | — |

Ninguna brigada depende de otra. Si una no está instalada, las demás siguen: Encargos sin
Atención retoma su pregunta sin responder la duda; sin Agenda, el pedido de turno queda en las
notas del encargo; sin Avisos, la dueña avisa a mano.

## Recorrido de un mensaje

1. Llega un mensaje (canal, contacto, texto) → `Harness.recibir`.
2. Se cuenta para el registro de uso (y el tope del plan).
3. El **orquestador** ordena las brigadas (reclamo → conversación abierta → interés → Atención como red).
4. La primera brigada que devuelve una `Respuesta` atiende; su texto va al cliente.
5. Cada `Accion` pasa por el **Policy Engine**: automática (se ejecuta), aprobación (queda en el
   panel) o humana (el bot se retira).
6. Lo que ejecutan las brigadas se comunica por **eventos** (ej. pago confirmado → encargo
   confirmado → aviso al cliente).
7. Todo queda en el **registro de supervisión**; el panel de soporte ve versiones, uso y avisos,
   nunca conversaciones.

## Despliegue

```
Meta ──► raphael-relay (nube) ◄── cola ── raphael-servidor (mini PC del cliente) ──► API de Meta
                                               │  latido + licencia
                                               ▼
                                         raphael-central (Damián)
```

## Lo que falta para lanzar

- App de Meta aprobada (App Review) y plantillas de WhatsApp para avisos fuera de 24 h.
- Elegir modelos concretos por plan (`modelos.yaml`) y el mini PC.
- Contrato y política de privacidad revisados por un abogado (Ley 25.326).
- Desplegar relay y central con HTTPS en un dominio propio.
