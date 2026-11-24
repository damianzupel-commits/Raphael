# Changelog — raphael-servidor

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [0.4.0] - 2026-11-19
### Agregado
- Estado → **Inteligencia artificial**: la dueña elige NVIDIA, Ollama, LM Studio u otro servicio compatible con OpenAI, carga modelo y clave,
  prueba la conexión y la deja activa sin reiniciar (`/api/ia`, `/api/ia/probar`, `/api/ia/quitar`). Se guarda en `datos/ia.json`; la clave
  nunca vuelve a salir por la API. Un solo proveedor atiende todos los roles de todos los planes.
- El recuadro «Modelo del orquestador» de la cabecera lleva a esa configuración.
### Cambia
- Requiere raphael-harness >= 0.4 y raphael-orquestador >= 0.3.

## [0.2.0] - 2026-11-18
### Agregado
- Tienda de brigadas (`tienda.py`, `catalogo.yaml`): cada brigada aparece bloqueada, descargada o activa.
  Descargar clona su repo (GitHub o copia local, solo lo del catálogo); activar/desactivar edita el perfil
  y recarga el harness sin reiniciar. Respeta dependencias (Cobros y Avisos necesitan Encargos).
- Panel: pestaña Brigadas; las pestañas Encargos, Agenda y Dudas aparecen solo con su brigada activa.

## [0.1.0] - 2026-11-18
### Agregado
- Primera versión: servidor de Raphael para el equipo del cliente: panel de la dueña, WhatsApp/Instagram, licencia, backups e instalador.
