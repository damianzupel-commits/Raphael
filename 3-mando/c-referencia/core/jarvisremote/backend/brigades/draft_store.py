"""Almacén de brigadas creadas (borradores y activas) + el GATE «borrador -> activa» (Etapa 2).

LA LÍNEA ROJA: una brigada creada nace en estado BORRADOR y NO es operativa (no se rutea, no corre, no aparece como
activa, el router HTTP responde 404) hasta que Damian la ACTIVA con una acción explícita. Nada se vuelve operativo sin
su confirmación.

Cómo se hace cumplir (no es solo un campo «estado» que cualquiera pueda cambiar):

  1. LA APROBACIÓN ES SOBRE UN CONTENIDO EXACTO. Activar exige el hash (sha256) del borrador tal como Damian lo revisó.
     Si el contenido cambió entre la revisión y el OK (otro borrador con el mismo id, edición del archivo), el hash no
     coincide y no se activa. Nunca se aprueba «lo que haya guardado».
  2. LA APROBACIÓN ESTÁ FIRMADA. Al activar se firma (Ed25519, clave privada protegida con DPAPI: la infraestructura que ya
     usa el log de investigación, con una clave PROPIA de este almacén) el mensaje «id + hash». «Activa» solo vale si la
     firma verifica contra la clave pública Y el contenido guardado sigue teniendo ese hash. Escribir `"estado": "activa"`
     a mano, o desde una tool de filesystem de un jefe manipulado por prompt-injection, no sirve: sin la firma, la
     brigada sigue siendo un borrador. Editar el borrador después de activar también la desactiva (el hash ya no coincide).
  3. SE REVALIDA EN CADA USO. Una brigada activa vuelve a pasar por `validate_draft` cada vez que se la consulta: si la
     política de tools se endurece o aparece una brigada con su mismo id, deja de estar activa (falla cerrado).
  4. SOLO CÓDIGO DETERMINÍSTICO ACTIVA. `activate()` no está expuesta como tool de ningún jefe ni del LLM: la llaman los
     endpoints del orquestador (token efímero, solo 127.0.0.1) y el comando de chat que escribe Damian.

Límite honesto: DPAPI ata la clave a la cuenta de Windows, no al proceso. Un agente con shell sin restricciones (el
`pc_run_command` del Raphael completo, que no es un sandbox) podría, en teoría, firmar. El gate protege contra edición
de archivos y contra los jefes de brigada (que no tienen shell); no contra un atacante con ejecución arbitraria como el
usuario. Defensa en profundidad opcional: agregar la carpeta del almacén a FS_DENIED_PATHS.
"""

from __future__ import annotations

import json
import time
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import factory

BORRADOR, ACTIVA = "borrador", "activa"
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "brigades_creadas"
_lock = threading.RLock()
_spec_cache: dict[str, tuple[str, object]] = {}  # id -> (hash, BrigadeSpec)


MAX_VERSIONES = 5  # cuántas versiones anteriores de un borrador se conservan


class DraftError(Exception):
    """Operación no permitida sobre el borrador (no existe, estado incorrecto, hash que no coincide...)."""


class DraftInvalid(DraftError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def store_dir() -> Path:
    override = os.getenv("BRIGADAS_CREADAS_DIR", "").strip()
    return Path(override) if override else _DEFAULT_DIR


def keys_dir() -> Path:
    return store_dir() / "_claves"


def _path(brigade_id: str) -> Path:
    if not factory.ID_RE.match(brigade_id or ""):
        raise DraftError(f"id inválido: {brigade_id!r}")
    return store_dir() / f"{brigade_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(brigade_id: str) -> dict | None:
    try:
        return json.loads(_path(brigade_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, DraftError):
        return None


def _write(brigade_id: str, rec: dict) -> None:
    path = _path(brigade_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    # atómico: nunca queda un JSON a medias. En Windows el replace puede fallar un instante con WinError 32/5 si un
    # antivirus/indexador tiene el archivo abierto (visto en la prueba real del diseñador): se reintenta con backoff.
    for intento in range(8):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if intento == 7:
                raise
            time.sleep(0.1 * (intento + 1))


def _static_ids() -> set[str]:
    from .registry import _BRIGADES, _SPECS  # ids de las brigadas del sistema

    return set(_BRIGADES) | set(_SPECS)


def _approval_message(brigade_id: str, h: str) -> bytes:
    return f"raphael-brigada-activacion-v1|{brigade_id}|{h}".encode("utf-8")


def _signature_ok(brigade_id: str, h: str, firma: str) -> bool:
    try:
        from app.investigation import keys

        pub = keys.load_public_key(keys_dir())
        return keys.verify(pub, _approval_message(brigade_id, h), firma)
    except Exception:  # noqa: BLE001 — sin clave, firma ilegible o malformada: NO es una aprobación válida
        return False


def verified_active(rec: dict | None) -> bool:
    """¿Este registro es una brigada ACTIVA de verdad? Estado + firma + hash del contenido + borrador aún válido."""
    try:
        if not rec or rec.get("estado") != ACTIVA:
            return False
        ap = rec.get("aprobacion") or {}
        draft = rec["draft"]
        h = factory.draft_hash(draft)
        if not (rec.get("hash") == ap.get("hash") == h):
            return False  # el contenido cambió después de la aprobación
        if not _signature_ok(draft["id"], h, ap.get("firma", "")):
            return False
        clean, errors = factory.validate_draft(draft, _static_ids())  # la política vigente de hoy también tiene que aceptarla
        return not errors and clean is not None and factory.draft_hash(clean) == h
    except Exception:  # noqa: BLE001 — ante cualquier duda, NO activa
        return False


# --- crear / listar ------------------------------------------------------------------------------------------------
def create_draft(raw: object, origen: str = "json", descripcion: str | None = None) -> dict:
    """Valida y guarda un BORRADOR (nunca activo). Reemplaza un borrador previo con el mismo id; rechaza si ya hay una
    activa con ese id (hay que desactivarla antes: una brigada activa no se pisa con otro contenido)."""
    with _lock:
        bid = raw.get("id") if isinstance(raw, dict) else None
        prior = _read(bid) if isinstance(bid, str) and factory.ID_RE.match(bid) else None
        if prior and prior.get("estado") == ACTIVA:
            raise DraftError(f"Ya hay una brigada ACTIVA con el id '{bid}': desactivala primero o usá otro id.")
        existing = _static_ids() | {r["draft"]["id"] for r in list_records() if r["estado"] == ACTIVA}
        clean, errors = factory.validate_draft(raw, existing)
        if errors or clean is None:
            raise DraftInvalid(errors)
        rec = {"estado": BORRADOR, "draft": clean, "hash": factory.draft_hash(clean), "origen": origen,
               "descripcion_original": descripcion, "creado": _now(), "aprobacion": None}
        # Versionado (O-9): editar un borrador = guardar otro con el mismo id. La versión anterior no se pierde: queda en
        # `versiones` (las últimas MAX_VERSIONES, con su hash y su contenido) y se puede volver a ella con `restore_version`.
        # Es solo historial: nunca cuenta como aprobación de nada (la aprobación es SIEMPRE sobre el hash vigente).
        if prior and isinstance(prior.get("draft"), dict):
            versiones = [v for v in prior.get("versiones", []) if isinstance(v, dict)]
            if prior.get("hash") != rec["hash"]:
                versiones.append({"hash": prior.get("hash"), "creado": prior.get("creado"), "origen": prior.get("origen"), "draft": prior["draft"]})
            rec["versiones"] = versiones[-MAX_VERSIONES:]
        _write(clean["id"], rec)
        return rec


def versions(brigade_id: str) -> list[dict]:
    """Las versiones anteriores de un borrador (sin su contenido): [{hash, hash_corto, creado, origen}], la más nueva al final."""
    rec = _read(brigade_id) or {}
    return [{"hash": v.get("hash"), "hash_corto": str(v.get("hash") or "")[:12], "creado": v.get("creado"), "origen": v.get("origen")}
            for v in rec.get("versiones", []) if isinstance(v, dict)]


def restore_version(brigade_id: str, ref: str) -> dict:
    """Vuelve un BORRADOR a una versión anterior (por su hash o prefijo de >= 12). Pasa por `create_draft`: se valida de nuevo y
    la versión que se reemplaza queda a su vez en el historial. Una brigada activa no se toca: hay que desactivarla antes."""
    ref = (ref or "").strip().lower()
    rec = _read(brigade_id)
    if rec is None:
        raise DraftError(f"No existe la brigada '{brigade_id}'.")
    if len(ref) < 12:
        raise DraftError("Indicá el hash de la versión (al menos 12 caracteres).")
    hit = [v for v in rec.get("versiones", []) if isinstance(v, dict) and str(v.get("hash") or "").startswith(ref)]
    if len(hit) != 1:
        raise DraftError(f"No hay una versión de '{brigade_id}' con el hash {ref[:12]}.")
    return create_draft(hit[0]["draft"], origen="version", descripcion=rec.get("descripcion_original"))


def get_record(brigade_id: str) -> dict | None:
    rec = _read(brigade_id)
    return _normalize(rec) if rec else None


def _normalize(rec: dict) -> dict:
    """El estado que se MUESTRA: una 'activa' sin aprobación válida se informa como borrador (y se marca)."""
    out = dict(rec)
    if rec.get("estado") == ACTIVA and not verified_active(rec):
        out["estado"] = BORRADOR
        out["aprobacion_invalida"] = True
    return out


def list_records() -> list[dict]:
    d = store_dir()
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        if not factory.ID_RE.match(p.stem):
            continue  # un archivo con nombre que no es un id válido no es una brigada (y nunca llega a la UI)
        rec = _read(p.stem)
        if rec and isinstance(rec.get("draft"), dict) and rec["draft"].get("id") == p.stem:
            out.append(_normalize(rec))
    return out


def active_ids() -> list[str]:
    return [r["draft"]["id"] for r in list_records() if r["estado"] == ACTIVA]


def review_for(brigade_id: str) -> dict:
    rec = get_record(brigade_id)
    if rec is None:
        raise DraftError(f"No existe la brigada '{brigade_id}'.")
    clean, errors = factory.validate_draft(rec["draft"], _static_ids() - {brigade_id})
    rv = factory.review(rec["draft"])  # siempre sobre el contenido GUARDADO, recalculando el hash
    rv["estado"] = rec["estado"]
    rv["errores_vigentes"] = errors
    rv["draft"] = rec["draft"]            # el JSON del borrador, para poder editarlo desde la UI (O-9)
    rv["versiones"] = versions(brigade_id)  # historial (sin contenido): se vuelve a una con restore_version
    return rv


# --- el GATE ---------------------------------------------------------------------------------------------------------
def activate(brigade_id: str, approved_hash: str, por: str = "damian") -> dict:
    """ACTIVA un borrador. `approved_hash` es el hash (completo o su prefijo de >= 12 caracteres) del contenido que Damian
    revisó. Solo la llaman los endpoints/comandos del orquestador: no es una tool de ningún jefe."""
    from app.investigation import keys

    with _lock:
        rec = _read(brigade_id)
        if rec is None:
            raise DraftError(f"No existe la brigada '{brigade_id}'.")
        if rec.get("estado") == ACTIVA and verified_active(rec):
            raise DraftError(f"'{brigade_id}' ya está activa.")
        draft = rec.get("draft") or {}
        h = factory.draft_hash(draft)
        if rec.get("hash") != h:
            raise DraftError("El contenido guardado no coincide con su hash (alguien lo editó): descartalo y creá el borrador de nuevo.")
        ref = (approved_hash or "").strip().lower()
        if len(ref) < 12 or not h.startswith(ref):
            raise DraftError("El hash no coincide con el contenido guardado: lo que estás aprobando NO es lo que está en el "
                             "borrador (¿se modificó después de revisarlo?). Volvé a revisarlo y aprobá su hash actual.")
        clean, errors = factory.validate_draft(draft, _static_ids() - {brigade_id})
        if errors:
            raise DraftInvalid(errors)
        keys.ensure_keypair(keys_dir())
        firma = keys.sign(keys.load_private_key(keys_dir()), _approval_message(brigade_id, h))
        rec.update({"estado": ACTIVA, "aprobacion": {"firma": firma, "hash": h, "ts": _now(), "por": por}})
        _write(brigade_id, rec)
        _spec_cache.pop(brigade_id, None)
        return rec


def deactivate(brigade_id: str) -> dict:
    """Vuelve a BORRADOR (revoca la aprobación). Reversible: se puede revisar y activar de nuevo."""
    with _lock:
        rec = _read(brigade_id)
        if rec is None:
            raise DraftError(f"No existe la brigada '{brigade_id}'.")
        rec.update({"estado": BORRADOR, "aprobacion": None})
        _write(brigade_id, rec)
        _spec_cache.pop(brigade_id, None)
        return rec


def discard(brigade_id: str) -> None:
    """Borra un BORRADOR. Una brigada activa no se borra: se desactiva primero."""
    with _lock:
        rec = _read(brigade_id)
        if rec is None:
            raise DraftError(f"No existe la brigada '{brigade_id}'.")
        if verified_active(rec):
            raise DraftError("Está ACTIVA: desactivala antes de descartarla.")
        _path(brigade_id).unlink(missing_ok=True)
        _spec_cache.pop(brigade_id, None)


# --- el spec de una brigada ACTIVA ----------------------------------------------------------------------------------
def active_spec(brigade_id: str):
    """BrigadeSpec de una brigada ACTIVA y verificada. KeyError si es borrador, no existe o su aprobación no vale."""
    rec = _read(brigade_id)
    if not verified_active(rec):
        _spec_cache.pop(brigade_id, None)
        raise KeyError(f"brigada no activa: {brigade_id}")
    h = rec["hash"]
    cached = _spec_cache.get(brigade_id)
    if cached and cached[0] == h:
        return cached[1]
    spec = factory.compile_spec(rec["draft"])
    _spec_cache[brigade_id] = (h, spec)
    return spec
