# SPEC-MIGRACION-LINUX-2026-10-19 — Pasar la PC a Linux y portar Raphael

> Spec de migración completo. Lo pidió Damian el 2026-10-19 tras decidir dejar de
> jugar LoL/TFT y usar **un solo sistema operativo** como base de todo trabajo real.
> Norte explícito: *"que Raphael se levante apenas prenda la PC y poder iniciar mi
> trabajo directamente con él como si de un compañero de trabajo se tratase, mientras
> él puede manipular el sistema entero y yo lo uso como extensión de mí."*
>
> Este spec NO toca el sistema de 5 tiers ni debilita ningún gate de seguridad.
> Es un plan de ejecución por fases; no se ejecuta nada hasta que Damian dé el OK
> fase por fase. **No commitea nada** (sigue la regla vigente del repo).

---

## 0. TL;DR — leé esto primero

- **¿Linux le da a Raphael más control y más fluidez?** Sí, en casi todo, y en varias
  cosas mucho más (shell real, sandbox de verdad, autostart con systemd, pentest/
  antimalware nativos, modelos locales más rápidos, se arregla el bug de Playwright).
  **Un solo asterisco:** el control de la GUI de otras apps (`desktop_*`) depende del
  servidor gráfico. Se resuelve eligiendo **sesión X11** (ver §2).
- **Distro recomendada:** **Kubuntu LTS** (KDE Plasma). Razón: base Ubuntu LTS = el
  stack mejor soportado para ROCm/Ollama/Docker, estable por años (ideal "base de
  trabajo"), y KDE **conserva sesión X11** (GNOME ya la eliminó en 2026).
- **Sesión gráfica:** **X11/Xorg**, NO Wayland. Es la decisión más importante del
  plan: sin X11, el control total del escritorio que querés queda a medias.
- **GPU (AMD, a confirmar modelo exacto):** aceleración de modelos locales por ROCm
  con `HSA_OVERRIDE_GFX_VERSION` **o** backend Vulkan. Ojo con una regresión de ROCm
  reciente en gfx1031 (ver §2.3) — hay plan B.
- **Porteo de Raphael:** la mayoría de los módulos tienen equivalente Linux limpio y
  varios quedan **mejor**. El único delicado es `desktop.py` (automatización de GUI).
- **Red de seguridad durante la transición:** mantener Windows en un segundo disco/
  partición unas semanas (dual-boot temporal) hasta que Raphael corra 100% en Linux;
  recién ahí se borra. El estado final sí es un solo SO.

---

## 1. Veredicto honesto: control y fluidez en Linux

### 1.1 Dónde Raphael GANA (y por qué)

| Capacidad | Hoy en Windows | En Linux | Veredicto |
|---|---|---|---|
| Shell / `pc_run_command` | blocklist de patrones, sin sandbox real | shell POSIX + **sandbox real** (namespaces/cgroups/seccomp, bubblewrap/firejail) | **Mucho mejor** |
| Autostart "compañero" | tarea de inicio frágil | **systemd user service** limpio y supervisado | **Mucho mejor** |
| Modelos locales (Ollama/llama.cpp) | overhead de Windows | menos overhead, mejor control de GPU/driver | **Mejor fluidez** |
| Pentest (nmap/sqlmap/ZAP/scapy) | quirks de Windows | ciudadanos de primera (Kali-grade) | **Mejor** |
| Antimalware (YARA/ClamAV + FIM) | ClamAV/YARA andan, Defender/Sysmon pesados | ClamAV/YARA nativos, FIM con **inotify**, auditd/eBPF/AppArmor | **Mejor y más abierto** |
| Browser tool (Playwright) | workaround `msedge` por el antivirus | Chromium propio de Playwright sin drama | **Se arregla un bug** |
| Monitoreo de procesos (watchdog) | taskkill | señales POSIX, `/proc`, cgroups | **Mejor** |

### 1.2 El único asterisco: control de GUI de otras apps

`desktop.py` (mover mouse, tipear, manejar ventanas de OTRAS apps) es lo único que
puede quedar peor — y SOLO si se usa Wayland. En **X11** hay herramientas maduras
(xdotool + wmctrl + AT-SPI) y queda tan fluido como Windows, o mejor (AT-SPI da
targeting semántico de elementos, parecido al Accessibility Service del celular).
Wayland, por diseño de seguridad, **bloquea que una app controle a otra** y restringe
la inyección de input; se puede sortear con ydotool (daemon uinput) + portales, pero
con fricción y permisos por captura. Conclusión: **usamos X11** y el asterisco
desaparece. (Fuentes en §12.)

---

## 2. Decisiones base (definen todo el resto)

### 2.1 Distro: Kubuntu LTS (KDE Plasma)

- **Por qué Kubuntu:** base Ubuntu LTS → ROCm, Ollama, Docker y PyTorch documentan y
  validan primero contra Ubuntu LTS; soporte largo (una LTS da ~3-5 años) = base de
  trabajo estable, no un SO que se rompe cada 6 meses. KDE Plasma es el sabor oficial
  KDE de Ubuntu.
- **Por qué KDE y no GNOME:** GNOME 50 (marzo 2026) **eliminó la sesión X11**; Fedora
  GNOME ya es Wayland-only. KDE Plasma **sigue ofreciendo sesión X11** (su retiro se
  estima recién ~2027). Como necesitamos X11 para el control total, GNOME queda
  descartado.
- **Alternativa (si querés lo más fresco para la GPU):** **Fedora KDE** — kernels y
  Mesa más nuevos (mejor para GPU AMD recién salida), pero se mueve más rápido y
  empuja fuerte Wayland. Para "base de todo trabajo real" priorizo estabilidad →
  Kubuntu. Fedora KDE es plan B válido si la GPU necesita Mesa de punta.
- **Nota:** el escritorio por default en Plasma reciente arranca en Wayland. En la
  pantalla de login hay que elegir **"Plasma (X11)"** y dejarlo fijo (§5).

### 2.2 Sesión gráfica: X11/Xorg (NO Wayland) — la decisión clave

Todo el control de escritorio de Raphael depende de esto. En X11: xdotool/wmctrl
(input + ventanas) y AT-SPI (elementos) funcionan. En Wayland: no, sin workarounds
frágiles. **Instalamos y dejamos fija la sesión X11.** Si en el futuro KDE retira
X11, para entonces AT-SPI + portal RemoteDesktop + ydotool ya serán el camino maduro;
lo evaluamos cuando llegue, no ahora.

### 2.3 GPU AMD — aceleración de modelos locales

(El modelo exacto se confirma en Fase 0 con `lspci`/`lshw`; el plan vale para la
familia RDNA2/gfx103x que es lo que venís usando.)

- **Camino principal:** ROCm + `HSA_OVERRIDE_GFX_VERSION=10.3.0` (para gfx1031 tipo
  RX 6700/6750 XT, que no tiene soporte ROCm oficial). Se setea como drop-in de
  systemd en el servicio de Ollama.
- **⚠️ Regresión conocida:** en gfx1031/gfx1032, ROCm 6.4.3+ ha shippeado builds donde
  el override carga el modelo y **crashea al recibir el primer prompt**. Plan B:
  **pinear ROCm 6.4.1**, o usar el **backend Vulkan** de Ollama, o CPU como último
  recurso. Lo validamos en Fase 1 ANTES de depender de la GPU.
- **Gaming (bonus):** las GPU AMD tienen drivers abiertos (Mesa) excelentes en Linux;
  si algún día querés un juego no-Riot, Steam + Proton anda muy bien. No es el
  objetivo, pero no perdés nada.

---

## 3. Fase 0 — Preparación (sin tocar Windows todavía)

**Objetivo:** llegar a la instalación sin sorpresas y con red de seguridad.

1. **Backup completo** de lo que no está en git: `Vault-Fenix`, `backend/obsidian_vault*`,
   `.env` de backend y tray, `authorized_targets.yaml`, credenciales DPAPI (hay que
   re-cifrarlas, no se migran tal cual), `content/`, y cualquier cosa fuera del repo.
2. **Inventario de hardware:** correr en Windows `Get-CimInstance Win32_VideoController`
   y anotar GPU + VRAM exactas; CPU, RAM, discos. (En Linux después: `lspci -nnk | grep -A3 VGA`,
   `lscpu`, `free -h`, `lsblk`.) Esto fija el override de GPU y el tier de modelo local.
3. **Inventario de apps** que usás además de Raphael (Obsidian, navegador, editor,
   Voicemod/co-host, etc.) → mapear equivalente Linux (§6.9).
4. **Probar en vivo sin instalar:** USB booteable de Kubuntu (Ventoy o Rufus) → arrancar
   en "live", elegir sesión **X11**, verificar que la GPU, WiFi, audio y pantalla andan.
   Cero riesgo para Windows.
5. **Plan de particionado:** segundo disco o partición para Linux. **Mantener Windows**
   como dual-boot temporal (red de seguridad). El objetivo final es borrarlo, pero
   recién cuando Raphael corra 100% en Linux.
6. **Baseline de Raphael en Windows:** confirmar que todo lo que hoy funciona está
   anotado (qué tools, qué flags, qué endpoints) para comparar después de portar.

**Criterio de salida:** backup verificado + live USB que arranca en X11 con hardware OK.

---

## 4. Fase 1 — Instalación base del sistema

1. Instalar **Kubuntu LTS** en el disco/partición de Linux (junto a Windows para el
   dual-boot temporal). Zona horaria, usuario, cifrado de disco (LUKS) si querés.
2. **Fijar sesión X11** en el login (SDDM) y dejarla por default (§5).
3. **Drivers AMD:** Mesa viene de fábrica (no instalar el blob propietario). Verificar
   con `glxinfo`/`vulkaninfo`.
4. **Stack de IA local:**
   - **Ollama** nativo. Configurar el drop-in de systemd con `HSA_OVERRIDE_GFX_VERSION`
     (o Vulkan). **Validar inferencia real con un prompt** antes de seguir (chequear la
     regresión de §2.3).
   - **Embeddings:** hoy usás LM Studio (:1234) para `text-embedding-nomic-embed-text-v1.5`.
     LM Studio tiene build Linux; alternativa: servir el embedding por `llama.cpp` o
     por el propio Ollama si cargás un modelo de embeddings ahí (ajustando
     `EMBEDDING_BASE_URL`/`EMBEDDING_MODEL`). Decidir en esta fase.
5. **Herramientas base:** Docker + docker compose, Python 3 + venv, git (con
   `core.autocrlf=input`, que en Linux es natural), build-essential, nmap, clamav,
   yara. Editor (VS Code / tu preferido). Obsidian (AppImage/Flatpak).
6. **Automatización de escritorio:** `xdotool`, `wmctrl`, `at-spi2-core` + bindings
   Python (`python-atspi`/`pyatspi`), y `ydotool` instalado por si algún día hace falta.

**Criterio de salida:** SO en X11, Ollama acelerando (o Vulkan/CPU decidido), Docker y
venvs listos, herramientas de automatización instaladas.

---

## 5. Fase 3 — El "compañero que arranca con la PC" (la visión)

> Se diseña temprano porque es el norte; se activa al final (depende del porteo).

- **Autostart con systemd:** el backend FastAPI y la tray-app corren como **servicios
  de usuario systemd** (`~/.config/systemd/user/raphael-backend.service`,
  `raphael-tray.service`), con `WantedBy=default.target` → arrancan al iniciar sesión,
  con restart automático y logs en journald. Mucho más robusto que el inicio de Windows.
- **Autologin opcional:** si es tu máquina personal, SDDM con autologin → prendés la PC
  y entrás directo a la sesión X11 con Raphael ya levantado. (Cifrado de disco LUKS
  sigue pidiendo passphrase al boot; eso no se automatiza, es la protección real.)
- **Voz (compañero de verdad):** `tray-app/voice_listener.py` + TTS. En Linux:
  captura por **PipeWire**, STT con **whisper.cpp** local, TTS con **Piper** (local,
  rápido). Es el M7 del SPEC-MEJORAS, acá encaja natural. Push-to-talk o wake word.
- **Control del sistema como "extensión tuya":** Raphael corre con TU usuario, así que
  puede manejar tu escritorio (X11), tu shell, tus archivos y tus apps — **con los
  gates intactos** (ver §10). Para acciones que necesiten root (algunas de pentest/
  antimalware/FIM a nivel sistema) se usa una regla sudo acotada a comandos
  específicos, nunca sudo abierto.
- **Panel siempre a mano:** el Centro de Mando (HTML servido por el backend) abre al
  inicio en una ventana/tab fija; el grafo de memoria y el globo quedan a un click.

**Criterio de salida:** prendés la PC → Raphael levantado, escuchándote, con panel
abierto, capaz de actuar sobre el sistema, sin que toques una terminal.

---

## 6. Fase 2 — Porteo de Raphael, módulo por módulo

El corazón del trabajo. Orden sugerido: primero lo que desbloquea el uso diario
(shell, browser, auth), después desktop/voz, al final antimalware a nivel sistema.

### 6.1 Cifrado de secretos — DPAPI → Secret Service / `keyring`
- **Hoy:** DPAPI (Windows) cifra device tokens (`device_tokens.py`), credential store
  de `forms/`, y protege las claves Ed25519 de `investigation/`.
- **Linux:** API **Secret Service** vía `libsecret` (KWallet en KDE) usando la lib
  `keyring` de Python; o `age`/`gpg` para blobs en disco. Crear una capa
  `secrets_backend` con implementación Windows/Linux detrás de la misma interfaz.
- **Migración:** los secretos NO se copian cifrados (DPAPI es irreversible fuera de
  Windows) → se **re-generan/re-ingresan** una vez en Linux. Los device tokens del
  celular se re-vinculan por QR (ya tenés ese flujo).
- **Esfuerzo:** medio. **Riesgo:** bajo (hay equivalente directo). **Gate:** ninguno nuevo.

### 6.2 Control de escritorio — `desktop.py` (pywinauto) → xdotool + AT-SPI
- **Hoy:** pywinauto + control de mouse/teclado/ventanas (Windows UIAutomation).
- **Linux (X11):** input con **xdotool**, ventanas con **wmctrl**, y targeting semántico
  de elementos con **AT-SPI** (pyatspi) — el reemplazo natural de UIAutomation.
  Screenshots con `scrot`/`import` o API de KDE.
- **Esfuerzo:** **alto** (es el módulo más grande de reescribir). **Riesgo:** medio →
  mitigado por usar X11. **Gate:** mantiene el patrón dry-run→confirm donde ya lo tiene.

### 6.3 Shell — `pc_command.py` / `shell_exec.py` → shell POSIX (+ sandbox real)
- **Hoy:** ejecuta comandos reales con blocklist de patrones destructivos; auditoría
  persistente. No es sandbox real.
- **Linux:** casi directo (cambia `cmd`/PowerShell por bash). **Mejora grande:**
  envolver la ejecución en sandbox real (**bubblewrap**/firejail/`systemd-run` con
  cgroups+seccomp). Esto es el M6 del SPEC-MEJORAS, que en Linux es nativo y barato.
- **Esfuerzo:** bajo (port) + medio (sandbox opcional). **Riesgo:** bajo. **Gate:**
  la blocklist se mantiene; el sandbox la refuerza, no la reemplaza.

### 6.4 Matar procesos colgados — taskkill → señales POSIX
- **Hoy:** `taskkill` (Windows) en el watchdog.
- **Linux:** `os.kill`/`signal`/`pkill`, `psutil` (ya lo usás) multiplataforma.
- **Esfuerzo:** trivial. **Riesgo:** nulo.

### 6.5 Browser tool — `browser.py` (Playwright vía msedge) → Chromium nativo
- **Hoy:** Playwright apuntado al Edge del sistema como workaround del antivirus.
- **Linux:** Playwright usa su **Chromium propio** sin el workaround → se elimina el
  bug. `playwright install chromium`.
- **Esfuerzo:** bajo. **Riesgo:** nulo. **Mejora neta.**

### 6.6 Celular — `phone_link.py` / `phone.py` (Termux/adb) → igual o más fácil
- **Hoy:** link con Termux + adb + cámara, por WebSocket.
- **Linux:** `adb` y el WebSocket funcionan igual; `android-tools-adb` del repo. Udev
  rules para el dispositivo. Nada Windows-específico salvo rutas.
- **Esfuerzo:** bajo. **Riesgo:** bajo.

### 6.7 Antimalware — `malware/` → nativo y más potente
- **Hoy:** YARA + ClamAV (clamd) + heurística (watchdog/psutil) + FIM + monitor propio
  + Sysmon (experimental, off). Cuarentena reversible.
- **Linux:** YARA y ClamAV son **nativos** (ClamAV nació en Linux). FIM con **inotify**
  (mejor que en Windows). Heurística con psutil igual. El rol de Defender ASR/Sysmon/ETW
  lo cubren **auditd / eBPF / AppArmor / falco** (más abiertos y potentes). Cuarentena:
  mover a dir con permisos restringidos (igual patrón).
- **Esfuerzo:** medio (reescribir la capa "features de kernel de Windows"). **Riesgo:**
  bajo. **Gate:** cuarentena sigue dry-run→confirm; borrado definitivo solo con confirm.

### 6.8 Grabación — `recording.py` (ffmpeg) → ffmpeg nativo
- **Hoy:** ffmpeg para grabar pantalla alrededor de las tools.
- **Linux (X11):** `ffmpeg -f x11grab` directo. (En Wayland haría falta portal; otra
  razón para X11.)
- **Esfuerzo:** bajo. **Riesgo:** nulo.

### 6.9 Voz / co-host — voice_listener + Voicemod → PipeWire + Piper/whisper
- **Hoy:** entrada por voz en la tray; Voicemod (Windows-only) para el co-host/cambio
  de voz.
- **Linux:** captura PipeWire, STT whisper.cpp local, TTS Piper local. **Voicemod no
  existe en Linux** → alternativa: cadena PipeWire + filtros (RNNoise para ruido,
  módulos de pitch/efectos) o un voice-changer Linux. Es el cambio con más "pérdida"
  directa; hay reemplazo pero no 1:1.
- **Esfuerzo:** medio-alto (sobre todo el co-host). **Riesgo:** medio (depende de cuánto
  dependas de Voicemod exacto).

### 6.10 Tray-app — pystray/PySide6 → corre en Linux, re-empaquetar
- **Hoy:** PySide6 + pystray + ventana de pestañas; lanza el backend como subproceso.
- **Linux:** PySide6 corre nativo; el icono de bandeja usa **AppIndicator**/StatusNotifier
  (KDE lo soporta bien). `process_manager.py` cambia detalles de subproceso (señales,
  rutas). El selector de modelo escribe el mismo `.env`.
- **Esfuerzo:** medio. **Riesgo:** bajo.

### 6.11 Config y rutas — `config.py` → rutas XDG
- **Hoy:** rutas estilo Windows, `FS_ALLOWED_ROOT=Path.home()`.
- **Linux:** `~/.config/raphael`, `~/.local/share/raphael`, `~/.cache/raphael` (XDG).
  Buen momento para la mitigación pendiente de `FS_ALLOWED_ROOT` (acotar por debajo de
  HOME) que ya figura en ESTADO.md.
- **Esfuerzo:** bajo. **Riesgo:** bajo. **Mejora de seguridad de paso.**

---

## 7. Fase 4 — Migración de datos

| Dato | Cómo migra |
|---|---|
| Repos (JarvisRemote, etc.) | `git clone` del remoto público; el working tree sin commitear se copia a mano (recordá: hay cambios sin commitear) |
| Vault Obsidian (`Vault-Fenix`, `backend/obsidian_vault*`) | copiar las carpetas tal cual (son .md); re-indexar embeddings en Linux |
| Modelos Ollama | `ollama pull <modelo>` de nuevo (recomendado) o copiar `~/.ollama/models` |
| Embedding model | re-descargar en LM Studio Linux o servirlo por Ollama/llama.cpp |
| `.env` backend + tray | portar a rutas XDG; **secretos re-ingresados** (DPAPI no migra) |
| `authorized_targets.yaml` | **recrear a mano** (no está en git por seguridad; solo lo editás vos) |
| Claves Ed25519 de investigación | re-generar y re-cifrar con el backend Secret Service nuevo |
| `content/` (grabaciones, etc.) | copiar (está gitignoreado) |

---

## 8. Qué queda IGUAL / MEJOR / requiere trabajo (resumen)

- **Mejor en Linux:** shell + sandbox, autostart (systemd), modelos locales, pentest,
  antimalware, browser (bug resuelto), FIM (inotify), FS sandbox (de paso se mejora).
- **Igual (port casi directo):** celular/adb, taskkill→señales, grabación (en X11),
  config/rutas, tray (re-empaquetar).
- **Requiere trabajo real:** `desktop.py` (X11/AT-SPI), DPAPI→keyring, voz/Voicemod.
- **Única "pérdida" sin 1:1:** Voicemod exacto (hay alternativa, no idéntica).

---

## 9. Orden y timeline sugerido

- **Finde 1:** Fase 0 (backup + live USB) y Fase 1 (instalar Kubuntu X11, drivers,
  Ollama validado, Docker, apps). Migrar datos (Fase 4). Dual-boot con Windows intacto.
- **Semana 1-2:** porteo core que desbloquea uso diario — shell (6.3), browser (6.5),
  auth/DPAPI→keyring (6.1), celular (6.6), config/rutas (6.11), taskkill (6.4).
  Raphael ya usable para la mayoría del trabajo.
- **Semana 2-3:** `desktop.py` sobre X11 (6.2), tray (6.10), antimalware nativo (6.7),
  grabación (6.8).
- **Semana 3-4:** voz + co-host (6.9), autostart systemd + autologin + panel al inicio
  (Fase 5). El "compañero que arranca con la PC" queda vivo.
- **Después:** correr en Linux como SO principal 1-2 semanas con Windows como respaldo;
  cuando todo funcione, **borrar Windows** → un solo SO.

*(Esfuerzo total realista: unas 2-4 semanas de trabajo a ritmo tranquilo, la mayor
parte en `desktop.py` y la voz. Nada bloqueante.)*

---

## 10. Gates que NO se tocan (reafirmado)

- **Sistema de 5 tiers (0-4): intacto.** Este plan no lo modifica.
- **Scope de pentest** contra `authorized_targets.yaml` (solo lo editás vos): igual.
- **Patrón dry-run→confirm** para todo lo destructivo: igual (cuarentena, fixes, forms).
- **Self-repair con `proposal_id`:** igual.
- **Flags default-OFF** para cada capacidad invasiva: igual (y se suman flags para lo
  nuevo: sandbox de shell, backend de secretos, voz).
- **Sandbox de FS (`FS_ALLOWED_ROOT`):** se mantiene y **mejora** (rutas XDG + acotar
  bajo HOME, pendiente que ya estaba anotado).
- **sudo:** NUNCA abierto. Solo reglas sudoers acotadas a comandos puntuales que lo
  necesiten (algunas de pentest/antimalware a nivel sistema).

---

## 11. Riesgos y rollback

- **Arrancar en Wayland por error** → `desktop_*` falla. Mitigación: fijar sesión X11
  en SDDM y verificar con `echo $XDG_SESSION_TYPE` (debe decir `x11`).
- **Regresión ROCm gfx1031** (§2.3) → crash al primer prompt. Mitigación: pinear ROCm
  6.4.1 o usar Vulkan; validar en Fase 1 antes de depender de la GPU.
- **Porteo de `desktop.py` incompleto** → mitigación: AT-SPI primero (semántico, más
  robusto), xdotool como fallback; se puede ir migrando tool por tool.
- **Voicemod sin reemplazo 1:1** → mitigación: evaluar la cadena PipeWire temprano; si
  el co-host depende mucho de Voicemod, decidir si vale un paso extra.
- **Rollback global:** Windows en dual-boot durante toda la transición. Si algo crítico
  no funciona, seguís trabajando en Windows mientras se resuelve. Borrás Windows recién
  al final.

---

## 12. Fuentes (verificadas 2026-10-19)

- GNOME 50 elimina la sesión X11 (Wayland-only): ghacks, xda-developers (2026-03).
- Fedora GNOME Wayland-only / spins con X11: Phoronix, Fedora Project Wiki, Neowin, itsfoss.
- KDE conserva X11 (~hasta 2027): TechHut.
- Distros para LLM local + AMD + KDE (Kubuntu / Fedora KDE): opensourcefeed, tecmint, makeuseof.
- ROCm override gfx1031 (10.3.0) + regresión 6.4.3 / Vulkan fallback: localaimaster, conroyp, major.io.
- Automatización Linux X11 vs Wayland (xdotool/wmctrl/AT-SPI/ydotool): proyectos MCP de
  desktop Linux, computer-use-linux (2026-09).

*(Los enlaces completos van en el mensaje de entrega; varias son fuentes secundarias,
los puntos de versión conviene re-verificarlos al momento de instalar.)*

---

## 13. Próximo paso

Confirmar modelo exacto de GPU (Fase 0, paso 2) y decidir Kubuntu vs Fedora KDE.
Con eso, arrancamos por Fase 0 + Fase 1. El porteo de Raphael se puede hacer módulo
por módulo sin perder el Windows de respaldo, así nunca quedás sin máquina de trabajo.
