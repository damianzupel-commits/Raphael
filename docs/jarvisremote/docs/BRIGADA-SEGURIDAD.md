# Brigada de Seguridad (defensiva / auditoría)

Primera brigada nueva armada con el método declarativo (ver `PLAYBOOK-brigadas.md`). Es el spec
`backend/brigades/seguridad.py` ejecutado por el motor genérico; su escena de validación está en
`backend/brigades/seguridad_scene.py` y los pasos en `backend/validation/seguridad.py`.

## Alcance (decisión de Damian)

Reconocimiento + escaneo activo (**nmap**), chequeo de vulnerabilidades web (**ZAP**, **sqlmap** solo-detección) sobre un
target **autorizado**, y un **reporte**. **Sin explotación destructiva.** No usa captura de paquetes, shell, filesystem,
teléfono ni edición de código (fuera de la allowlist por menor privilegio).

## Cómo está armada

| Pieza | Detalle |
|---|---|
| Jefe | Persistente, local. Delega cada pedido en un ayudante efímero según las reglas de ruteo del spec |
| Ayudante `escaneo` | `nmap_scan`, `zap_scan`, `sqlmap_scan`, `pentest_generate_report`. Prompt: nunca explota; sqlmap solo `detect`; ZAP solo `spider` salvo pedido explícito |
| Ayudante `reporte` | Pasivo: solo `pentest_generate_report`. No puede escanear |
| Ruteo | Escanear exige señal explícita (verbo en imperativo o nombre de herramienta). Lo ambiguo va a `reporte`. «El reporte del escaneo» no dispara un escaneo |
| Tools | Las **existentes** del monolito; lo único nuevo es `pentest_generate_report` (`app/tools/pentest_report.py`, `app/pentest/report.py`), que arma el informe desde el audit log |
| Acceso | `/api/brigade/seguridad/{meta,chat}` (router genérico, backend completo). El orquestador liviano todavía no la muestra |

## El gate

La brigada **no tiene gate propio**: hereda el único gate compartido (`backend/app/network/guardrail.py`, fuente
`backend/authorized_targets.yaml`), que vive dentro de cada tool y corre antes de tocar la red. Rechaza todo target fuera de
scope (por default solo privado/loopback/Tailscale; el resto, solo si Damian lo agrega **a mano**) y valida CIDR enteros. Ni el
jefe, ni los ayudantes, ni el LLM pueden ampliarlo. `pentest_generate_report` también pasa por el gate.

Límite honesto: «sqlmap solo detect / ZAP spider por defecto» lo impone el prompt, no un filtro de argumentos.

## Validación

```powershell
cd backend
.venv\Scripts\python.exe -m validation.seguridad            # solo Seguridad
.venv\Scripts\python.exe -m validation.todas seguridad      # idem, desde el comando único
```

| # | Paso | Necesita el target |
|---|---|---|
| 1 | Alcance y menor privilegio | no |
| 2 | Ruteo escaneo / reporte | no |
| 3 | **Gate**: las tools reales rechazan targets fuera de la lista (escáneres sustituidos por un centinela) | no |
| 4 | Reporte desde resultados simulados | no |
| 5 | Recon (nmap) de los servicios esperados de Metasploitable 2 | **sí** |
| 6 | Vulnerabilidades conocidas (nmap `vuln`: backdoor de vsftpd 2.3.4) | **sí** |
| 7 | Web: ZAP (spider) + sqlmap (detect) sobre Mutillidae | **sí** |
| 8 | Reporte del escaneo real | **sí** |
| 9 | E2E: pedido en lenguaje natural al jefe (modelo local) | **sí** |

Los pasos 5-9 traen su prerrequisito: si falta algo quedan **SIN VALIDAR** (código 2), nunca rojo.

### Qué hace falta para la corrida real

1. VM Metasploitable 2 prendida y **alcanzable desde esta PC**. `labnet` es una red *interna* de VirtualBox: el host no la ve sin
   un adaptador host-only/puente (o hay que correr desde Kali; ver `lab/ORQUESTACION-REMOTA-DESIGN.md` §6).
2. Su IP (DHCP `10.13.37.100`–`200`, cambia) en la variable `SEGURIDAD_VALIDATION_TARGET`.
3. Esa IP escrita **a mano** en `backend/authorized_targets.yaml`. La validación solo lo lee, nunca lo escribe.
4. nmap instalado; para el paso 7, ZAP + Java (`ZAP_PATH`) y sqlmap (`SQLMAP_PATH`); para el paso 9, Ollama con el modelo local.

Las expectativas de la VM (núcleo de puertos, productos, backdoor, parámetro de Mutillidae) salen del diseño del lab y del
conocimiento público de Metasploitable 2; se calibran en la primera corrida real. Con los 9 pasos en verde se fija el baseline.
