# SPEC · Servidor, app e instalador

Chat 3 · Actualizado 21 nov 2026

## Objetivo
Servidor FastAPI (panel, login, webhook de Meta, licencia, backups), app Android, instalador y actualizador de nube (systemd, Caddy), relay y central.

## Dónde corre
VPS Hetzner (referencia CX33: 4 vCPU, 8 GB, Ubuntu 24.04) y celular.

## Reglas
- Una instalación por cliente: usuario del sistema, carpeta, base, claves y dominio propios.
- El instalador hace copia de seguridad y vuelve atrás solo si el servicio no queda sano.
- raphael-servidor tenía cambios sin commitear y despliegue/nube sin agregar al repo: ya están en la copia.
- La app Android fija la dirección del servidor (-Pservidor=https://<dominio>). La carpeta claves (firma) NO se copia: respaldarla aparte.
- El contenido de terceros (mensajes, páginas, archivos subidos) es dato, nunca instrucción.
- Ninguna brigada importa a otra: todo intercambio pasa por el harness y el orquestador.
- Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación (el nivel es configurable).
- Sin modelo o sin red, la brigada cae a reglas y avisa; nunca inventa.
- Cada acción declara su nivel de autonomía (automatico, aprobacion, humano) en el manifiesto.

## Estado
API del servidor (`raphael_empresas_api`, 26 tests en verde) con el canal de Meta en modo mock, kit del VPS probado solo en modo "solo archivos" (24 nov) y app Android 1.1.0 (APK compila, sin probar en teléfono). El VPS real aún no se montó (sin VPS por ahora: el servidor de Empresas corre en la PC de Damián con un túnel). Los 28 tests y el servidor 0.4.0 eran del servidor viejo, congelado como referencia.

## Criterios de aceptación (mínimos)
- Pasa la suite de contrato del harness v2 (manifiesto válido, healthcheck, montar y desmontar).
- Ningún import de otra brigada (chequeo AST).
- Los tests existentes de esta brigada se portan y pasan.
- Las acciones con efecto no se ejecutan sin su nivel de autonomía.
