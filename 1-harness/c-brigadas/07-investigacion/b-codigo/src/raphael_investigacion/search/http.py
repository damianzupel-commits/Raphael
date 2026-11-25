"""GET con urllib (sin dependencias). Las partes que buscan reciben una función con esta firma, así los tests inyectan una
simulada y nunca salen a la red: (url, params, headers) -> (status, texto)."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 2_000_000


def default_get(url: str, params: dict[str, str], headers: dict[str, str], timeout: float = 15.0) -> tuple[int, str]:
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(full, headers={"User-Agent": "Raphael-Investigacion/2.0", **headers})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - http(s) validado por quien llama
            return resp.status, resp.read(MAX_BYTES).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(type(exc).__name__) from None
