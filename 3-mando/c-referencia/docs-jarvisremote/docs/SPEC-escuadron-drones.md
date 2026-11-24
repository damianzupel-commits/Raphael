# SPEC — Escuadrón heterogéneo aire+tierra comandado por Raphael

> Estado: **SPEC COMPLETO** (todas las decisiones resueltas, 2026-09-28). Creado el
> 2026-09-28. Nace de un divague de
> Damian sobre robótica que decantó en algo concreto: un **escuadrón de robots
> aéreos y terrestres** que lo **siguen** y lo asisten, con Raphael de comandante
> (no de piloto). Empezó como "un dron que me siga"; evolucionó a una pareja
> aire+tierra, y a una topología nave-nodriza (2 aéreos + 1 terrestre pesado).
>
> Se elicita por preguntas, igual que los otros specs. Decisiones abiertas 🟡, con
> recomendación; cerradas ✅.

---

## 1. Objetivo y encuadre
Un **escuadrón multi-robot heterogéneo** (aire + tierra) cuya misión primaria es
**seguir y asistir a Damian**, comandado por Raphael en lenguaje natural. NO es un
show de coreografía (ese fue el ejemplo que disparó la idea); es un sistema
funcional.

La visión estética de Damian para los aéreos: **livianos, ágiles y veloces, como
colibríes** — moviéndose livianos por el aire. Esto tiene una consecuencia técnica
real (§7): cuanto más liviano, más colibrí, pero menos autonomía/carga/aguante
afuera. La topología de 2 aéreos que se alternan (§3) es justamente cómo se tiene
agilidad de colibrí Y persistencia al mismo tiempo.

---

## 2. Principio de mando (lo más importante) ✅ [DECISIÓN 1 — resuelta]
**Raphael es el general, no el piloto.** Da intención y reparte tareas; cada
unidad es **autónoma** a bajo nivel (navega y esquiva sola). Raphael NUNCA está en
el loop rápido de vuelo/manejo — tira objetivos cada varios segundos ("seguime",
"adelantate a la esquina", "dron, subí y filmá") y cada robot resuelve el *cómo*.
Esto lo hace seguro ante latencia y cortes de señal: si Raphael calla, cada unidad
sostiene su última orden o entra en su failsafe.

Es el mismo split de tres capas del divague:
1. **Comandante (Raphael):** intención + asignación de tareas + memoria. Segundos.
2. **Autonomía por unidad:** localización, percepción, planificación local,
   evitación de obstáculos. Onboard, tiempo real.
3. **Control de bajo nivel:** actitud/motores (aéreo) o tracción (terrestre), a
   cientos de Hz, en el firmware de cada robot.

---

## 3. Topología escalable ✅ [DECISIÓN 2 — resuelta]
La arquitectura NO cambia entre tamaños; solo se agrega el planificador de turnos.
Se crece sin rediseñar:
- **v1 — pareja 1+1:** 1 terrestre + 1 aéreo. Clava el "seguime" y el hand-off.
- **v2 — nave nodriza 2+1 pesado:** 2 aéreos + 1 terrestre grande. Los aéreos se
  **alternan** (uno vuela mientras el otro carga en el rover) → **cobertura aérea
  continua**, sin el hueco que deja un solo dron al recargar.

El terrestre pesado se gana el peso: carga las plataformas de aterrizaje +
cargadores de los dos drones, una batería grande (es la base de energía del
grupo), la compu de a bordo, y puede hacer de **repetidor de señal** que le
extiende el rango a los aéreos. Es una base móvil real, no un changuito.

---

## 4. "Seguime" — el corazón técnico 🟡 [DECISIÓN 3]
El robot tiene que saber **dónde está Damian** relativo a él. Opciones:
- **Tag UWB que Damian lleva encima** (ancla): ~10cm, robusto, anda aunque lo
  pierda de vista (esquina, contraluz). La respuesta más confiable.
- **Visión** (cámara + seguimiento/re-ID de persona): sin tag, pero lo pierde en
  la esquina, de noche o entre gente.
- **GPS del celular:** seguimiento grueso (metros), sirve para el aéreo afuera.

✅ [DECISIÓN 3 — resuelta] **Fusión de las tres, cada una para lo suyo:**
- **Tag UWB** = ancla fina (~10cm), la base robusta del "seguime" de cerca, aguanta
  perder la vista.
- **GPS del celular de Damian** = posición gruesa (metros), sobre todo para el aéreo
  **afuera** y para arranque/rango largo.
- **Visión** = complemento para que el dron te **encuadre** bien en el video.

Se fusionan (sensor fusion): GPS-cel para el "por dónde anda Damian" grueso, UWB para
el "exactamente acá relativo a mí" fino, visión para el encuadre. Ninguna sola; juntas
cubren cerca/lejos y adentro/afuera.

---

## 5. Hand-off dron↔rover (el ciclo de turnos) 🟡 [DECISIÓN 4]
La coordinación que hace que "dos" sea más que dos seguidores:
- El dron se **posa** en el rover cuando no hace falta ojo arriba, y se **recarga**.
- Cuando Raphael (o un evento) pide ojos, **despega**.
- Con 2 aéreos: A vuela, B carga; swap antes de que A se agote → siempre cobertura.
- El rover mantiene a los aéreos **en rango de comms** y de recarga.

Esto es un problema de scheduling con restricción de energía (hay literatura real:
UGV que recarga a un UAV con energía limitada). Es exactamente una **Brigada** —
orquestar el relevo es lo que Raphael ya hace.
✅ [DECISIÓN 4 — resuelta] Recarga **por contactos** en la plataforma del rover
pesado (simple y probado, no inductiva). El dron se posa y hace contacto físico con
los pads de carga del rover.

---

## 6. Posicionamiento y comms (la infra que todo cuelga de acá) 🟡 [DECISIÓN 5]
- **Aéreo afuera:** RTK-GPS (centímetros) + VIO (odometría visual-inercial) para
  cuando el GPS falla o adentro.
- **Terrestre:** SLAM con LiDAR/visión + odometría de ruedas; comparte mapa con el
  aéreo (el aire mapea desde arriba, la tierra ejecuta).
- **"Seguime" fino:** el tag UWB (§4) sobre todo eso.
- **Comms:** red robusta de campo (no un dongle en una sala). Radio con rango +
  mesh; cada unidad con failsafe si pierde el enlace (retorno/hold). El terrestre
  pesado como repetidor.
✅ [DECISIÓN 5 — resuelta] **Outdoor desde el arranque**, en el espacio verde cerca
de la casa de Damian. Robot terrestre en propiedad propia = bajo riesgo, no regulado.
Sin etapa de simulación/chico previa: se va directo al hardware real pesado. El
"seguime" se valida ahí; el dron se suma después a baja altura y con vista.

---

## 7. Plataformas reales (sin humo — chequeadas 2026-09-28)

### Aéreos — "colibrí": liviano, ágil, programable, autónomo
- **ModalAI Starling 2** (280 g): drone de desarrollo con VOXL 2 (compu IA +
  autopiloto en 16 g), hasta 5 cámaras, ~40+ min de navegación **indoor**, VIO +
  evitación de obstáculos + mapeo 3D pre-cargados, corre **PX4 + ROS 2**. Es lo más
  cercano a tu "colibrí programable" listo para autonomía. NDAA-compliant.
- **ModalAI Starling 2 Max** (500 g): la versión **outdoor**, ~55+ min y **500 g de
  carga útil**. Para cuando salgas al campo.
- **Crazyflie 2.1 Brushless** (29 g, Bitcraze): el más "colibrí" de todos, nano,
  ideal para enjambre indoor (Crazyswarm voló 49 con 3 radios). *Contra:* muy chico
  para cámara/carga seria afuera. Bueno para prototipar el mando y el enjambre en tu
  pieza, barato.
- **DIY (máximo control):** frame FPV chico + **Pixhawk 6X + NVIDIA Jetson Orin NX**
  (Holybro Jetson Baseboard) corriendo PX4/ArduPilot + ROS 2. Hay un framework
  abierto para esto (`aerial-autonomy-stack`: PX4/ArduPilot + ROS2 + YOLO + LiDAR +
  Jetson). Más laburo, pero es tuyo de punta a punta.

#### Airframe elegido por Damian para el camino DIY (2026-09-28): GEPRC TriPro LR60
Damian identificó este como su "colibrí" (mandó capturas del canal @colibrifpv).
Specs reales: **383 g**, 6", cruise **26-28 min**, cámara **DJI O4 Air Unit Pro**
(4K/120fps, sensor 1/1.3" — cubre percepción + video aceptable sin gimbal, como se
decidió), enlace hasta **15 km** (ELRS 915/2.4GHz), módulo **GPS GEP-M10**, FC
TAKER F722. Liviano, veloz, larguísimo alcance = colibrí de verdad.
- **La trampa para el escuadrón:** de fábrica es un FPV **manual** (Betaflight +
  goggles + radio), NO autónomo. Para meterlo en la escuadra follow-me hay que
  sumarle la pila de autonomía: FC con ArduPilot/PX4 + compañera Jetson + el
  posicionamiento. O sea: excelente AIRFRAME (motores, alcance, cámara), el CEREBRO
  autónomo lo ponés vos = es el camino DIY. Como FPV manual para volar y filmar,
  está listo ya.

#### El ideal de referencia (no comprable): Teledyne FLIR Black Hornet 4 PRS
Damian también mandó el Black Hornet — y es LITERALMENTE el norte de esta idea:
**70 g**, 16 cm, **>30 min**, >2 km, cámara **térmica 640×512 + EO 12MP**,
navegación **sin GPS** (VIO), casi silencioso. El dron-colibrí de reconocimiento
perfecto. PERO: **militar/gubernamental, US$80.000–195.000 por unidad, sin venta a
civiles** (proceso de vetting). Es el ideal de referencia, NO una opción de compra.
La aproximación real y alcanzable a ese ideal = un airframe clase TriPro (o el
Starling 2) + la pila de autonomía + cámara térmica si la querés.

#### El peso de "los ojos" (cámara vs agilidad)
Distinción clave: hay dos tipos de ojos y pesan re distinto.
- **Ojos de percepción** (cámara fija, para navegar/seguir/detectar): unos gramos,
  peso despreciable. Integrados en el diseño, no cuelgan nada. NO sacrifican agilidad.
- **Ojos de cine** (cámara + gimbal mecánico de 3 ejes, para video estabilizado
  lindo): 100-300 g+, colgando abajo del centro → mata la agilidad (baja el
  empuje/peso Y sube la inercia de giro, se pone lento para rotar).

Física de la agilidad: depende del **empuje/peso** (queré ≥2:1) y de tener la masa
**cerca del centro**. Regla práctica: carga agregada por debajo del ~10-15% del peso
total y no colgada lejos. → Por eso, para agilidad de colibrí, se quiere cámara
**integrada y liviana**, no un gimbal atornillado.

**El mejor para tu caso (ojos sin sacrificar agilidad): ModalAI Starling 2.** No
carga una cámara — *es* una plataforma de cámaras: trae hasta 5 sensores integrados
y livianos, pensados justo para visión autónoma (seguir, mapear, esquivar). Los ojos
son parte de los 280 g, no un extra, así que no pagás penalidad de agilidad.

✅ [DECISIÓN 7 — resuelta] **Percepción + video ACEPTABLE, sin cine.** Damian no
necesita video cinematográfico → **NO hace falta gimbal en ningún dron.** Se usa
**estabilización electrónica (EIS)** por software sobre la cámara fija: da video
usable con peso ~cero. Consecuencia buena: **los DOS aéreos quedan colibrí livianos**
(ninguno carga gimbal), agilidad plena en ambos, y aun así sacás video mirable para
seguirte/mostrar la esquina. Un gimbal solo se agregaría si algún día querés cine.

### Terrestre — el rover PESADO (nave nodriza desde el arranque) ✅ [DECISIÓN 6b]
Damian quiere el **más pesado desde el vamos**. Elección: **Clearpath Warthog** —
**276 kg de carga**, anfibio, todoterreno, ROS2. Bestia total: le sobra para cargar
los dos pads + cargadores, una batería enorme (nodriza de energía real), compu,
repetidor, y lo que se te ocurra sumar. Es su hábitat el verde/campo abierto.
- **Realidad honesta:** el Warthog es un UGV **industrial** (grande, ~clase de
  decenas de miles de USD, no un rover de hobby). Para "seguime" es sobrado — pero es
  a prueba de futuro y aguanta cualquier misión que le agregues. Si en algún momento
  resulta demasiado, el escalón abajo es el **AgileX UMR** (80 kg, 8 h, mucho más
  manejable y barato) — mismo software, no hay que rediseñar nada.

### Software (el pegamento)
- **ROS 2** como idioma común de toda la flota.
- **Open-RMF** como capa de gestión de flota **heterogénea** (literal, es para esto).
- **PX4 / ArduPilot** en cada aéreo (PX4 = baja latencia/precisión; ArduPilot =
  fiabilidad/misiones largas/swarm).
- Raphael se sienta ARRIBA de Open-RMF como el comandante en lenguaje natural + memoria.

✅ [DECISIÓN 6 — resuelta] Camino **producto** para arrancar y aprender: **Starling 2
(aéreo) + Clearpath Warthog (tierra, el más pesado)**. DIY (Pixhawk+Jetson + frame
propio) queda como evolución cuando quieras control/costo total. Rover el más pesado
desde el inicio (Decisión 6b).

---

## 8. Integración con Raphael (reuso de lo que ya existe)
- **Brigada/harness** → el comandante que reparte tareas y orquesta el hand-off
  (multi-robot task allocation + scheduling de turnos).
- **`target="phone"` sobre WebSocket** → un `target` por unidad (drone_1, drone_2,
  rover). Mismo patrón de despacho.
- **Memoria episódica** (ver `SPEC-memoria-episodica.md`) → recuerda recorridos,
  terreno, misiones, el estado de cada unidad, tus preferencias de comando.
- **Gates** → la seguridad (e-stop por unidad, geofence, retorno automático,
  aterrizaje de emergencia si se cae el posicionamiento). Mismo ethos que
  `authorized_targets.yaml` / dry-run→confirm.

---

## 9. Seguridad y legal (bandera honesta, no negociable)
- **Terrestre = bajo riesgo** y no regulado en tu propiedad. Por eso va primero.
- **Aéreo autónomo = regulado** (espacio aéreo, registro, línea de vista, altura).
  Va lícito, en tu terreno, a baja altura, con vos mirando. No se salta esto.
- **Nada de armar ni de vigilar a terceros.** Escuadrón personal, para lo tuyo.
- Failsafes duros: cada unidad segura ante pérdida de enlace/posición/batería.

---

## 10. Fases
- **Fase 1 — un solo seguidor:** el **terrestre** te sigue (base ROS2 + tag UWB),
  indoor. Bajo riesgo, sin espacio aéreo. Clavás "seguime".
- **Fase 2 — la pareja 1+1:** sumás un aéreo (Starling 2) + el hand-off posarse/
  recargar en el rover.
- **Fase 3 — nave nodriza 2+1 pesado:** segundo aéreo + planificador de turnos →
  cobertura aérea continua; rover grande de nodriza/repetidor.
- **Fase 4 — comandante rico:** Raphael con voz + memoria dirigiendo misiones
  ("patrullá el perímetro", "adelantate y mostrame la esquina"), no solo "seguime".

---

## 10-bis. Diseño 3D y planos de fabricación (2026-09-28)
Se modeló el escuadrón en 3D paramétrico (trimesh) y se generaron **planos de
fabricación** por pieza. Todo en `C:\Users\dam\Desktop\Damian\Proyectos\`:
- `NanoHornet-3D/` — el frame del colibrí nano (STL imprimible + fuente paramétrica
  + ficha con BOM y parámetros de impresión).
- `Escuadron-3D/` — los componentes **individuales** (STL + planos):
  - **Tractor oruga** = concentra la energía: panel solar, banco de baterías,
    mecanismo de carga visible, mástil LiDAR + domo GPS, bahías de mini-humanoides.
  - **Acoplado modular** = lo útil: pads de aterrizaje + carga (los remolques llevan
    la carga, la energía va en el tractor).
  - **Colibrí** a tamaño Hornet (nano): cuerpo alargado + 4 ductos + nacela de cámara.
  - **Mini-humanoide** desplegable con muchos grados de libertad (juntas esféricas),
    sale del tractor cuando llega a posición segura.
  - Scripts: `escuadron_v2.py` (modelos), `planos_taller.py` (vistas + cotas de
    feature), `planos_fabricacion.py` (cotas por pieza individual, notación Ø/×N).

Decisiones de este diseño: quad de 4 ductos (estable), percepción + video aceptable
con EIS (sin gimbal), **sin winch/malacate** (descartado por Damian), y **unidades
relativas** — la escala real se fija después (multiplicar por un factor → mm reales).

> **NOTA (Damian, 2026-09-28):** el diseño actual es suficiente por ahora. **Cuando
> se pase a fabricar de verdad, se empiezan a sumar detalles** (tolerancias ±, notas
> de material por pieza, vistas de corte, cotas en mm a escala real, refinamiento de
> holguras tras la primera impresión). No es un plano final: es la base que crece en
> el momento de fabricar.

## 11. Estado de las decisiones
Resueltas: 1 (Raphael general, unidades autónomas), 2 (topología escalable 1+1→2+1),
3 (seguime = fusión GPS-cel + UWB + visión), 4 (recarga por contactos en el rover),
6 (camino producto: Starling 2 + AgileX UMR), 6b (rover pesado desde el arranque),
7 (percepción + video aceptable con EIS, sin gimbal → los dos aéreos livianos).
Resueltas (cont.): 5 (outdoor desde el arranque, sin simulación previa).

**TODAS LAS DECISIONES RESUELTAS — spec completo.**

## Fuente
- Divague Damian 2026-09-28. Plataformas verificadas por búsqueda web (ModalAI
  Starling 2 / VOXL 2, Bitcraze Crazyflie, AgileX, Clearpath, Open-RMF,
  aerial-autonomy-stack). Relacionado: `SPEC-memoria-episodica.md`,
  `SPEC-capa-navegacion-de-agente.md`, `harness/` (Brigada), `phone_link.py`
  (patrón WebSocket por unidad).
