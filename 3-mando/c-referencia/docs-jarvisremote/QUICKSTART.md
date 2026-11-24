# 🚀 QUICKSTART — Corré tu propio Raphael de cero

Guía para poner Raphael (JarvisRemote) andando en tu PC desde cero. Un asistente
que corre **100% local** en tu máquina: tu chat, tus archivos y tu control de PC
no salen a ningún servidor de terceros. Está pensada para alguien que sabe usar
una terminal pero llega nuevo a este repo.

> Por ahora Raphael corre en **Windows 10/11** (varias capacidades usan APIs
> propias de Windows). Mac/Linux está en la lista, todavía no.

---

## 1. Requisitos previos

Antes de empezar, tené instalado:

- **Windows 10 u 11.**
- **Python 3.12** (o 3.10+). Bajalo de [python.org](https://www.python.org/downloads/)
  y en el instalador **tildá "Add Python to PATH"**. Verificá con `python --version`.
- **Git.** De [git-scm.com](https://git-scm.com/download/win). Verificá con `git --version`.
- **~25 GB de disco libre** si vas a usar el modelo grande (menos para el chico — ver abajo).
- **Conexión a internet** (para bajar Ollama y el modelo, que pesa varios GB).

Sobre el modelo, el instalador elige solo según tu hardware, pero para que sepas:
- **Tier `lite`** (Qwen3-8B, ~5 GB): anda cómodo con ~8 GB de RAM.
- **Tier `v2`** (Qwen3-30B, ~18 GB): conviene ~24 GB entre RAM + VRAM.

---

## 2. Cloná el repo

```powershell
git clone https://github.com/damianzupel-commits/JarvisRemote.git
cd JarvisRemote
```

---

## 3. Corré el instalador

⚠️ **Esto es lo que frena a casi todos:** por seguridad, Windows no deja correr
scripts de PowerShell por default. Si hacés `.\install.ps1` a secas, te va a decir
*"la ejecución de scripts está deshabilitada en este sistema"*. La forma limpia de
correrlo sin cambiar la config de tu sistema es esta:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador es **idempotente** (podés correrlo de nuevo sin miedo) y hace todo esto:
1. Detecta tu CPU/RAM/GPU y **recomienda un tier** de modelo (te deja elegir).
2. Instala **Ollama** si no lo tenés — te va a pedir **un click** en su instalador, una vez.
3. Baja el modelo base y arma el modelo de Raphael (esto tarda; son varios GB).
4. Crea los entornos de Python (`backend\.venv`, `tray-app\.venv`) e instala dependencias.
5. Genera `backend\.env` con una API key propia y el modelo local ya configurado.

Al terminar te muestra el comando para arrancar.

---

## 4. Arrancá Raphael

```powershell
cd tray-app
.\.venv\Scripts\pythonw.exe tray.py
```

Se abre la ventana de escritorio (pestañas Codebase / Obsidian) y levanta el
backend como subproceso. Listo: ya tenés a Raphael corriendo.

---

## 5. Verificá que anda

En otra terminal:

```powershell
curl http://localhost:8000/api/health
```

Si responde OK, el backend está vivo. Después probá un mensaje desde la ventana
de la tray, o por API:

```powershell
curl -X POST http://localhost:8000/api/chat `
  -H "Authorization: Bearer TU_API_KEY" -H "Content-Type: application/json" `
  -d '{\"message\": \"Listame los archivos de mi escritorio\"}'
```

(La API key está en `backend\.env`, campo `API_KEY`.)

---

## 6. (Opcional) Búsqueda semántica del vault

Raphael puede buscar en un vault de notas por significado, no solo por palabra.
Eso necesita un servidor de **embeddings** aparte, que el instalador NO monta:

- Instalá [LM Studio](https://lmstudio.ai/), descargá el modelo
  `nomic-embed-text-v1.5`, cargalo y arrancá su servidor local (queda en `:1234`).
- El `backend\.env` ya viene apuntando ahí (`EMBEDDING_BASE_URL`).

Sin esto, el chat y el control de PC andan igual; solo la **búsqueda semántica**
del vault queda en modo degradado (cae a búsqueda por palabra clave).

---

## 7. Qué NO cubre el instalador (a propósito)

Estas cosas dependen de decisiones o hardware tuyo y se hacen aparte:
- **Generación de imágenes/video** (ComfyUI) — ver `backend/README.md`.
- **La app de Android** — ver `android-app/README.md`.
- **Termux (control del celular), TLS, Tailscale** — pasos manuales en `backend/README.md` (sección de seguridad).

---

## Problemas comunes

- **"la ejecución de scripts está deshabilitada"** → usá el comando del paso 3 con `-ExecutionPolicy Bypass`.
- **"python no se reconoce" / no crea el venv** → Python no está en el PATH. Reinstalá Python tildando "Add to PATH", abrí una terminal nueva y reintentá.
- **"Ollama no respondió"** → abrí Ollama a mano (buscalo en el menú de inicio) y volvé a correr el instalador.
- **El modelo tarda una eternidad** → es normal la primera vez (varios GB). Si se corta, volvé a correr el instalador: retoma donde quedó.
- **Poca RAM/VRAM** → elegí el tier `lite` cuando te pregunte.

---

¿Lo pusiste a andar? Si algo se trabó en un paso que acá no está, es un hueco de
esta guía — avisá así lo arreglamos. La idea es que **cualquiera como vos** pueda
tener su propio asistente, sin entregarle sus datos a nadie.
