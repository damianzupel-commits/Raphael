# Seguridad · b-codigo
Brigada `seguridad` 2.0.0 para el harness v2 (contrato 2.1). Portada y reescrita desde `3-mando/c-referencia/security/` (JarvisRemote).

- `manifest.yaml` (y su copia dentro del paquete, `scripts/sync_manifest.py`): 3 cocineros, 2 acciones (`pentest_corrida` y `purgar_historial`, las dos con aprobación), 4 tools y 10 comandos.
- `src/raphael_seguridad/`: `audit.py` (flujo E1 a E7), `secrets_scan.py`, `deps.py` (adaptadores OSV, simulado y apagado), `config_check.py`, `triage.py`, `report.py`, `guardrail.py`, `pentest.py` (adaptadores reales de nmap, ZAP y sqlmap, y uno simulado), `defensive.py` (vigilancia con sondas reales y simuladas), `cooks.py`, `health.py`, `tools.py`, `settings.py`.
- `seguridad.env.plantilla` y `authorized_targets.yaml.plantilla`: lo que tiene que completar Damián (también está en `3-mando/a-conocimiento/LIENZO-DAMIAN.md`).

## Reglas que cumple (y qué test las prueba)
- Pentest activo solo en la PC: las tools son `active_scan` (el harness no las carga en la nube) y el cocinero se niega igual (`test_gate`, `test_cooks`).
- Cada corrida pide aprobación; el alcance sale de `authorized_targets.yaml` que solo lee (`test_guardrail`).
- Nada se explota: nmap con presets cerrados, ZAP `spider` por defecto, sqlmap nivel 1 riesgo 1 sin volcar datos.
- Sin clave o sin programa: avisa y no inventa. Lo simulado sale marcado SIMULADO.
- Sin modelo de IA: todo es por reglas. Nada de código ni de hallazgos sale a un modelo (decisión de Damián: lo sensible, local).
- El contenido de terceros es dato: solo se le contesta a la persona dueña.

## Config de la brigada (en `installation.yaml`)
```yaml
brigades:
  seguridad:
    active: true
    config:
      repos: ["D:\\Raphael Ultimate\\raphael"]       # los únicos que se auditan
      targets_file: "D:\\Raphael Ultimate\\.data\\authorized_targets.yaml"
      watch:
        tls_hosts: ["damian.tail9381ba.ts.net:443"]
        services: ["http://127.0.0.1:8000/health"]
        backups: ["D:\\Raphael Ultimate\\.data\\backups"]
        tokens: [{name: "Token de Meta", expires: "2027-01-31"}]
        interval_minutes: 15
```

## Probado y no probado
Probado con tests (62): parsers, adaptadores con transportes y runners falsos, guardrail, cocineros montados por el cargador, contrato en edición personal y nube. **No probado contra los programas reales** (nmap, ZAP, sqlmap, OSV.dev, un certificado TLS real): los parsers se probaron con muestras de su salida y los flags de nmap/sqlmap/ZAP son los del código viejo de JarvisRemote.
