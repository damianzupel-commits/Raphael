"""Almacén de brigadas creadas (borradores y activas) y el GATE «borrador -> activa». Portado de JarvisRemote
(`brigades/draft_store.py`).

LA LÍNEA ROJA: una brigada creada nace BORRADOR y no es operativa (el cargador no la ve, no se monta, no corre) hasta
que una persona la ACTIVA con una acción explícita. Cómo se hace cumplir:

  1. LA APROBACIÓN ES SOBRE UN CONTENIDO EXACTO: activar exige el hash del borrador tal como se revisó. Si el contenido
     cambió entre la revisión y el OK, el hash no coincide y no se activa.
  2. LA APROBACIÓN ESTÁ FIRMADA (`signing.Signer`) sobre «id + hash». «Activa» solo vale si la firma verifica Y el
     contenido guardado sigue teniendo ese hash. Escribir "state": "activa" a mano en el almacén no activa nada.
  3. SE REVALIDA EN CADA USO contra el registro de tools y las brigadas de HOY: si una tool desaparece o se vuelve
     peligrosa, o aparece una brigada con su id, deja de estar activa (falla cerrado).
  4. ANTES DE ACTIVAR se corren sus casos de ruteo (deterministas): una brigada cuyo propio ruteo no pasa no se activa.
  5. SOLO CÓDIGO DETERMINISTA ACTIVA: `activate()` no es una tool de ningún efímero; la llama el panel o el
     orquestador cuando la persona lo pide.

Los registros viven en el Store (espacio `_drafts`); la clave de firma, en un archivo aparte (`signing.py`).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from ..engine import BrigadeSpec
from ..store import Space
from . import factory
from .signing import Signer

DRAFT, ACTIVE = "borrador", "activa"
MAX_VERSIONS = 5
COLLECTION = "drafts"


class DraftError(Exception):
    """Operación no permitida sobre el borrador (no existe, estado incorrecto, hash que no coincide...)."""


class DraftInvalid(DraftError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def approval_message(brigade_id: str, h: str) -> bytes:
    return f"raphael-brigada-activacion-v2|{brigade_id}|{h}".encode()


class DraftStore:
    def __init__(self, space: Space, signer: Signer, *, catalog: Callable[[], Mapping[str, Any]],
                 taken_ids: Callable[[], set[str]] = set, clock: Callable[[], datetime] | None = None) -> None:
        """`catalog`: el registro de tools de HOY (nombre -> Tool). `taken_ids`: ids de las brigadas que no son
        borradores (instaladas o encontradas por el cargador): un borrador no puede tomarlos."""
        self.space = space
        self.signer = signer
        self._catalog = catalog
        self._taken = taken_ids
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[str, BrigadeSpec]] = {}

    # --- utilidades -------------------------------------------------------------------------------------------------------
    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    def _read(self, brigade_id: str) -> dict | None:
        if not isinstance(brigade_id, str) or not factory.ID_RE.match(brigade_id):
            return None
        return self.space.get(COLLECTION, brigade_id)

    def _validate(self, draft: Any, own_id: str | None = None) -> tuple[dict | None, list[str]]:
        taken = set(self._taken()) | {r["draft"]["id"] for r in self._raw_records() if self.verified_active(r)
                                      and r["draft"]["id"] != own_id}
        taken.discard(own_id or "")
        return factory.validate_draft(draft, self._catalog(), taken)

    def _raw_records(self) -> list[dict]:
        return [r for r in self.space.list(COLLECTION) if isinstance(r.get("draft"), dict)]

    # --- la verificación ---------------------------------------------------------------------------------------------------
    def verified_active(self, rec: dict | None) -> bool:
        """¿Este registro es una brigada ACTIVA de verdad? Estado + firma + hash + borrador válido HOY."""
        try:
            if not rec or rec.get("state") != ACTIVE:
                return False
            ap = rec.get("approval") or {}
            draft = rec["draft"]
            h = factory.draft_hash(draft)
            if not (rec.get("hash") == ap.get("hash") == h):
                return False
            if not self.signer.verify(approval_message(draft["id"], h), ap.get("signature", "")):
                return False
            taken = set(self._taken()) - {draft["id"]}
            clean, errors = factory.validate_draft(draft, self._catalog(), taken)
            return not errors and clean is not None and factory.draft_hash(clean) == h
        except Exception:  # noqa: BLE001 - ante cualquier duda, NO está activa
            return False

    def _normalize(self, rec: dict) -> dict:
        out = dict(rec)
        if rec.get("state") == ACTIVE and not self.verified_active(rec):
            out["state"] = DRAFT
            out["invalid_approval"] = True
        return out

    # --- crear, listar, versiones -------------------------------------------------------------------------------------------
    def create(self, raw: Any, origin: str = "json", description: str | None = None) -> dict:
        """Valida y guarda un BORRADOR (nunca activo). Reemplaza un borrador previo con el mismo id (el anterior queda en
        `versions`); rechaza si hay una ACTIVA con ese id."""
        with self._lock:
            bid = raw.get("id") if isinstance(raw, dict) else None
            prior = self._read(bid) if isinstance(bid, str) else None
            if prior and self.verified_active(prior):
                raise DraftError(f"Ya hay una brigada ACTIVA con el id '{bid}': desactivala primero o usá otro id.")
            clean, errors = self._validate(raw, own_id=None)
            if errors or clean is None:
                raise DraftInvalid(errors)
            rec = {"state": DRAFT, "draft": clean, "hash": factory.draft_hash(clean), "origin": origin,
                   "description": description, "created": self._now(), "approval": None, "versions": []}
            if prior and isinstance(prior.get("draft"), dict):
                versions = [v for v in prior.get("versions", []) if isinstance(v, dict)]
                if prior.get("hash") != rec["hash"]:
                    versions.append({"hash": prior.get("hash"), "created": prior.get("created"),
                                     "origin": prior.get("origin"), "draft": prior["draft"]})
                rec["versions"] = versions[-MAX_VERSIONS:]
            self.space.put(COLLECTION, clean["id"], rec)
            self._cache.pop(clean["id"], None)
            return rec

    def versions(self, brigade_id: str) -> list[dict]:
        rec = self._read(brigade_id) or {}
        return [{"hash": v.get("hash"), "short_hash": str(v.get("hash") or "")[:12], "created": v.get("created"),
                 "origin": v.get("origin")} for v in rec.get("versions", []) if isinstance(v, dict)]

    def restore_version(self, brigade_id: str, ref: str) -> dict:
        ref = (ref or "").strip().lower()
        rec = self._read(brigade_id)
        if rec is None:
            raise DraftError(f"No existe la brigada '{brigade_id}'.")
        if len(ref) < 12:
            raise DraftError("Indicá el hash de la versión (al menos 12 caracteres).")
        hit = [v for v in rec.get("versions", []) if isinstance(v, dict) and str(v.get("hash") or "").startswith(ref)]
        if len(hit) != 1:
            raise DraftError(f"No hay una versión de '{brigade_id}' con el hash {ref[:12]}.")
        return self.create(hit[0]["draft"], origin="version", description=rec.get("description"))

    def get(self, brigade_id: str) -> dict | None:
        rec = self._read(brigade_id)
        return self._normalize(rec) if rec else None

    def list(self) -> list[dict]:
        return sorted((self._normalize(r) for r in self._raw_records() if factory.ID_RE.match(r["draft"].get("id", ""))),
                      key=lambda r: r["draft"]["id"])

    def active_ids(self) -> list[str]:
        return [r["draft"]["id"] for r in self.list() if r["state"] == ACTIVE]

    def review(self, brigade_id: str) -> dict:
        rec = self.get(brigade_id)
        if rec is None:
            raise DraftError(f"No existe la brigada '{brigade_id}'.")
        _, errors = self._validate(rec["draft"], own_id=brigade_id)
        rv = factory.review(rec["draft"], self._catalog())   # sobre el contenido GUARDADO, recalculando el hash
        rv.update(state=rec["state"], current_errors=errors, routing_failures=factory.check_routing(rec["draft"]),
                  draft=rec["draft"], versions=self.versions(brigade_id))
        return rv

    # --- el GATE ------------------------------------------------------------------------------------------------------------
    def activate(self, brigade_id: str, approved_hash: str, by: str = "damian") -> dict:
        """ACTIVA un borrador. `approved_hash`: el hash (o su prefijo de >= 12) del contenido que la persona revisó."""
        with self._lock:
            rec = self._read(brigade_id)
            if rec is None:
                raise DraftError(f"No existe la brigada '{brigade_id}'.")
            if self.verified_active(rec):
                raise DraftError(f"'{brigade_id}' ya está activa.")
            draft = rec.get("draft") or {}
            h = factory.draft_hash(draft)
            if rec.get("hash") != h:
                raise DraftError("El contenido guardado no coincide con su hash (alguien lo editó): descartalo y creá el "
                                 "borrador de nuevo.")
            ref = (approved_hash or "").strip().lower()
            if len(ref) < 12 or not h.startswith(ref):
                raise DraftError("El hash no coincide con el contenido guardado: lo que estás aprobando NO es lo que está "
                                 "en el borrador. Volvé a revisarlo y aprobá su hash actual.")
            _, errors = self._validate(draft, own_id=brigade_id)
            if errors:
                raise DraftInvalid(errors)
            failing = factory.check_routing(draft)
            if failing:
                raise DraftInvalid(["su propia validación de ruteo no pasa: " + "; ".join(failing)])
            signature = self.signer.sign(approval_message(brigade_id, h))
            rec.update(state=ACTIVE, approval={"signature": signature, "hash": h, "at": self._now(), "by": by})
            self.space.put(COLLECTION, brigade_id, rec)
            self._cache.pop(brigade_id, None)
            return rec

    def deactivate(self, brigade_id: str) -> dict:
        """Vuelve a BORRADOR (revoca la aprobación). Reversible."""
        with self._lock:
            rec = self._read(brigade_id)
            if rec is None:
                raise DraftError(f"No existe la brigada '{brigade_id}'.")
            rec.update(state=DRAFT, approval=None)
            self.space.put(COLLECTION, brigade_id, rec)
            self._cache.pop(brigade_id, None)
            return rec

    def discard(self, brigade_id: str) -> None:
        """Borra un BORRADOR. Una activa no se borra: se desactiva primero."""
        with self._lock:
            rec = self._read(brigade_id)
            if rec is None:
                raise DraftError(f"No existe la brigada '{brigade_id}'.")
            if self.verified_active(rec):
                raise DraftError("Está ACTIVA: desactivala antes de descartarla.")
            self.space.delete(COLLECTION, brigade_id)
            self._cache.pop(brigade_id, None)

    def active_spec(self, brigade_id: str) -> BrigadeSpec:
        """BrigadeSpec de una brigada ACTIVA y verificada. KeyError si es borrador, no existe o su aprobación no vale."""
        rec = self._read(brigade_id)
        if not self.verified_active(rec):
            self._cache.pop(brigade_id, None)
            raise KeyError(f"brigada no activa: {brigade_id}")
        assert rec is not None
        h = rec["hash"]
        cached = self._cache.get(brigade_id)
        if cached and cached[0] == h:
            return cached[1]
        spec = factory.compile_spec(rec["draft"])
        self._cache[brigade_id] = (h, spec)
        return spec
