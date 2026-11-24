# Raphael

Repo único de Raphael personal y Raphael Empresas. Empezá por `CONTEXT.md`.

## El árbol (patrón a/b/c, de a tres)
Cada nivel tiene tres partes: **a** para saber, **b** para hacer y **c** para lo que cuelga de él.

```
raphael/
├─ 1-harness/                 la base: sin harness no corre nada
│  ├─ a-conocimiento/         todo para entender el harness a fondo
│  ├─ b-codigo/               el harness funcionando (+ panel de escritorio)
│  └─ c-brigadas/             todas las brigadas, montadas sobre el harness
│     ├─ 00-orquestador/      el que habla con la persona y reparte
│     ├─ 05-seguridad/ … 16-legales/
│     │  ├─ a-historia/       qué es, cocineros, decisiones, log
│     │  ├─ b-codigo/         manifest.yaml, src/
│     │  └─ c-salud/          pruebas/  monitoreo/  mantenimiento/
├─ 2-entrega/                 lo que llega a la gente
│  ├─ a-conocimiento/         spec y log del servidor, la app y el instalador
│  ├─ b-codigo/               servidor/  android/  panel-escritorio/
│  └─ c-despliegue/           vps/  instalacion-clienta/  cuentas-y-apis/
└─ 3-mando/                   cómo se dirige el proyecto
   ├─ a-conocimiento/         ESTADO, PLAN-MAESTRO, PIEZAS, log del mando
   ├─ b-herramientas/         la puerta (gate.bat) y pruebas que cruzan piezas
   └─ c-referencia/           código viejo de JarvisRemote y Empresas, solo lectura
```
Cada carpeta tiene su README: qué es y cómo debe funcionar.

## Puerta
`3-mando\b-herramientas\gate.bat` corre los 821 tests y ruff. Sale con 0 si todo pasa y con 2 si algo falla.

## Datos locales (fuera de git)
`.venv/` y `.data/` en la raíz; `1-harness/b-codigo/.venv` y `.datos` son el entorno y los datos del panel. No se leen ni se suben.

## Historia
- 24 nov 2026, madrugada: todo pasó a un monorepo (`apps`, `packages`, `brigades`, ...). Lo anterior quedó en `D:\Raphael Ultimate\_archivo\`.
- 24 nov 2026, tarde: el monorepo pasó a este árbol a/b/c para el repo único `damianzupel-commits/Raphael`. Los archivos se movieron con `git mv` (conservan su historial).

## Panel
Acceso directo "Raphael Harness v2" del escritorio: abre `1-harness/b-codigo/panel/abrir-panel.bat`.
