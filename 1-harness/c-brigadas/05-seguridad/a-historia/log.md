# Registro · 05-seguridad · Seguridad

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 2026-11-25 · Resumen de cierre (hilo "Construir pieza 05 Seguridad")
- Se portó la brigada al harness v2 como `seguridad` 2.0.0: auditor (E1 a E7: secretos, dependencias, configuración, triage, convergencia, reporte), pentest activo (nmap, ZAP, sqlmap) y vigilancia defensiva (logins fallidos, tokens, certificado, servicio, backups). Se reescribió en vez de copiar: el código viejo dependía de la config de JarvisRemote.
- Autonomía: `pentest_corrida` y `purgar_historial` con aprobación; no hay acciones automáticas. Pentest solo en la PC (tools `active_scan` + el cocinero se niega en la nube); alcance solo desde `authorized_targets.yaml`, que la brigada únicamente lee.
- Enchufable: adaptadores real y simulado para dependencias (OSV), pentest y vigilancia; sin clave o sin programa avisa y no inventa. Sin modelo de IA (decisión de Damián: lo sensible, local). Plantillas: `b-codigo/seguridad.env.plantilla` y `authorized_targets.yaml.plantilla`.
- 62 tests y contrato en verde (personal y nube), ruff limpio. **Sin probar contra nmap, ZAP, sqlmap ni OSV reales.**
- Quedó afuera: el reporte de pentest en PDF/HTML, captura de paquetes (tshark), el escaneo desde el celular (Termux) y el índice de código (`codebase`) del JarvisRemote viejo; calidad (ruff/mypy de terceros) tampoco. Pendiente para 03: publicar `acceso.fallido` desde el servidor. Pendiente para 00/orquestador: convertir `seguridad.alerta` en aviso y poner `seguridad` en la lista `private` de `modelos.yaml`.
