"""Firma de las aprobaciones de brigadas creadas por borrador.

JarvisRemote firmaba con Ed25519 (paquete `cryptography`) y protegía la clave privada con DPAPI. El núcleo v2 no suma
dependencias por esto: firma con HMAC-SHA256 (biblioteca estándar) con una clave de 32 bytes al azar.

  - En Windows la clave se guarda PROTEGIDA con DPAPI (CryptProtectData, vía ctypes): el archivo solo lo puede abrir la
    misma cuenta de Windows en la misma PC. Copiar el archivo a otra cuenta o PC no sirve para firmar.
  - En otros sistemas (la nube, tests) se guarda tal cual, con permisos 600. Ahí la protección es la del disco.

Qué protege y qué no (igual que en JarvisRemote, dicho sin vueltas): editar el almacén a mano o desde una tool de un
efímero manipulado no activa nada, porque sin la clave no hay firma válida. NO protege contra alguien que ya ejecuta
código como tu usuario: ese puede usar la clave igual que Raphael.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import os
import secrets
import sys
from pathlib import Path

KEY_FILE = "aprobaciones.key"


class SigningError(RuntimeError):
    pass


# --- DPAPI (solo Windows) -----------------------------------------------------------------------------------------------------
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:  # pragma: no cover - solo corre en Windows
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    desc = ctypes.c_wchar_p("raphael-aprobaciones") if protect else None
    ok = fn(ctypes.byref(blob_in), desc, None, None, None, 0x1, ctypes.byref(blob_out))   # 0x1 = sin interfaz
    if not ok:
        raise SigningError(f"DPAPI falló ({ctypes.GetLastError()})")  # type: ignore[attr-defined]
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


class Signer:
    def __init__(self, key_dir: str | Path, *, protect: bool | None = None) -> None:
        self.key_dir = Path(key_dir)
        self.protect = (sys.platform == "win32") if protect is None else protect

    @property
    def path(self) -> Path:
        return self.key_dir / KEY_FILE

    def has_key(self) -> bool:
        return self.path.is_file()

    def ensure_key(self) -> None:
        if self.has_key():
            return
        self.key_dir.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        raw = _dpapi(key, True) if self.protect else key
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.path)

    def _key(self) -> bytes:
        raw = self.path.read_bytes()
        key = _dpapi(raw, False) if self.protect else raw
        if len(key) != 32:
            raise SigningError("la clave de aprobaciones está dañada")
        return key

    def sign(self, message: bytes) -> str:
        self.ensure_key()
        return hmac.new(self._key(), message, hashlib.sha256).hexdigest()

    def verify(self, message: bytes, signature: str) -> bool:
        """False ante cualquier duda: sin clave, clave ilegible, firma mal formada o distinta."""
        try:
            if not self.has_key() or not isinstance(signature, str) or len(signature) != 64:
                return False
            expected = hmac.new(self._key(), message, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:  # noqa: BLE001
            return False
