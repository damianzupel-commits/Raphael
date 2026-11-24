from fastapi import Header, HTTPException, status

from .config import settings


def _scope_for(token: str) -> str | None:
    """Scope del token: 'master' (API_KEY maestra) / 'full' / 'read' (device token), o None.
    La key maestra sigue valiendo para todo — no rompe setups viejos (tray, etc.)."""
    if token and token == settings.api_key:
        return "master"
    try:
        from . import device_tokens

        return device_tokens.verify(token)  # 'full' | 'read' | None
    except Exception:  # noqa: BLE001 -- si el store falla, solo vale la maestra
        return None


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


async def verify_api_key(authorization: str | None = Header(default=None)) -> None:
    """Endpoints de control (chat, tools, config): exige la key maestra o un device token
    con scope 'full'. Un token 'read' NO alcanza acá."""
    scope = _scope_for(_bearer(authorization))
    if scope not in ("master", "full"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or insufficient token")


async def verify_read(authorization: str | None = Header(default=None)) -> None:
    """Endpoints de SOLO LECTURA (panel/mission-control): acepta maestra, 'full' o 'read'."""
    scope = _scope_for(_bearer(authorization))
    if scope not in ("master", "full", "read"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
