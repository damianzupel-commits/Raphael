# Chats del proyecto Raphael (numeración de Damián)

Cada chat es el agente de UNA brigada o pieza. Edita solo lo suyo y anota su cierre en `docs/log/<pieza>.md` (un archivo por pieza; en Empresas va una sección por módulo). El chat 0 (Mando) consolida en ESTADO.md.
Nombre de la sesión: `0 · Mando`, `1 · Harness`, etc.

## Soporte
- **0 Mando**: decisiones, prioridades, estado. No escribe código.
- **1 Harness**: `raphael-harness` (contrato, bus, almacén, políticas, modelos) y `raphael-familia-core` (montar/desmontar, suite de contrato). Guardián de los repos de Empresas: corre la regresión; no los edita salvo orden.
- **2 Orquestador**: el maestro de Raphael personal y de la Familia (mando, voz, ruteo, reparto por DAG, modelos por rol).
- **3 Servidor, app e instalador**: servidor, app Android, instalar/actualizar, VPS Hetzner, Caddy, copias de seguridad, alertas.
- **4 Cuentas y APIs**: Meta, WhatsApp, Instagram de prueba, proveedor de IA, dominios. Nunca recibe claves.

## Brigadas de Raphael personal (JarvisRemote)
- **5 Seguridad**: auditoría y pentest (ataque/defensa) + defensa pasiva para el VPS.
- **6 Antimalware**
- **7 Investigación**: forense, Scout, y las ideas, prototipos y tendencias de Innovación.
- **8 Geolocalización pública**: mapa y OSINT.
- **9 Memoria · Cerebro**
- **10 Ingesta**
- **11 Trading**
- **12 Operaciones**: PC y celular.
- **13 Autorreparación**
- **14 Contenido**: imagen, video (ffmpeg, Whisper), Instagram, campañas, analítica.

## Raphael Empresas (una brigada adentro de Raphael personal)
- **15 Raphael Empresas**, con sus módulos adentro del mismo chat:
  - a) Secretaria (jefa; en el harness de Empresas ese rol es el orquestador)
  - b) Atención
  - c) Agenda
  - d) Cobros
  - e) Encargos
  - f) Avisos
  - g) Tienda (nuevo, conector de catálogo agnóstico)

## Brigada nueva
- **16 Legales**: documentos, cumplimiento, riesgos, archivo. Argentina.

## Control
- **17 Revisor**: contexto en blanco; revisa cada fase contra SPEC.md. No construye.

## Vida (no son piezas del producto)
Estudio · Divague · Rutina

## Reglas comunes
- Al empezar: leer `CONTEXT.md`, `docs/ESTADO.md`, el README de tu rama y tu log en `docs/log/`.
- Al cerrar: "Resumen de cierre" de 3 a 6 líneas en `docs/log/<pieza>.md`.
- Si algo toca otra brigada: anotarlo como "pendiente para <brigada>"; no resolverlo.
- Trabajar solo en `raphael\`; originales intactos. No leer .env ni claves. No hacer push.
