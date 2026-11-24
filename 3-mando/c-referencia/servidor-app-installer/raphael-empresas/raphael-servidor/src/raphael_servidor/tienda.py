"""Tienda de brigadas: lo que el cliente puede sumar a su Raphael.

Cada brigada del catálogo está en uno de tres estados:
    bloqueada   no está en este equipo
    descargada  el código está en la carpeta de piezas, pero no trabaja
    activa      está en el perfil: el harness la carga y el orquestador la usa

Descargar = clonar su repo (de GitHub o de una copia local). Activar/desactivar = agregarla o
sacarla de `brigadas:` en el perfil y recargar el harness, sin reiniciar el servidor.
Solo se puede descargar lo que está en el catálogo: nunca una URL que mande el panel.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

CATALOGO_POR_DEFECTO = Path(__file__).with_name("catalogo.yaml")


class ErrorTienda(RuntimeError):
    pass


def cargar_catalogo(ruta: str | Path | None = None) -> list[dict]:
    return yaml.safe_load(Path(ruta or CATALOGO_POR_DEFECTO).read_text(encoding="utf-8")) or []


def _version(repo: Path) -> str | None:
    for init in (repo / "src").glob("raphael_*/__init__.py"):
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return None


def _borrar(carpeta: Path) -> None:
    """rmtree que también borra los archivos de solo lectura que deja git en Windows."""
    def quitar_solo_lectura(fn, ruta, _):
        os.chmod(ruta, 0o700)
        fn(ruta)
    if carpeta.exists():
        shutil.rmtree(carpeta, onerror=quitar_solo_lectura)


class Tienda:
    def __init__(self, piezas: Path, perfil: Path, catalogo: list[dict], fuente_repos: str = "", fuente_local: str = "",
                 git: str = "git") -> None:
        self.piezas, self.perfil, self.catalogo = piezas, perfil, {b["nombre"]: b for b in catalogo}
        self.fuente_repos, self.fuente_local, self.git = fuente_repos.rstrip("/"), fuente_local, git

    def _item(self, nombre: str) -> dict:
        if nombre not in self.catalogo:
            raise ErrorTienda(f"'{nombre}' no está en el catálogo")
        return self.catalogo[nombre]

    def _carpeta(self, nombre: str) -> Path:
        return self.piezas / self._item(nombre)["repo"]

    def _perfil(self) -> dict:
        return yaml.safe_load(self.perfil.read_text(encoding="utf-8")) or {}

    def activas(self) -> list[str]:
        return list(self._perfil().get("brigadas") or [])

    def estado(self) -> list[dict]:
        activas = set(self.activas())
        out = []
        for n, b in self.catalogo.items():
            carpeta = self._carpeta(n)
            descargada = (carpeta / "src").is_dir()
            out.append({"nombre": n, "titulo": b.get("titulo", n), "descripcion": b.get("descripcion", ""),
                        "necesita": b.get("necesita", []), "version": _version(carpeta) if descargada else None,
                        "estado": "activa" if n in activas and descargada else "descargada" if descargada else "bloqueada"})
        return out

    def descargar(self, nombre: str) -> dict:
        repo = self._item(nombre)["repo"]
        destino = self._carpeta(nombre)
        if (destino / "src").is_dir():
            return {"estado": "descargada", "nota": "ya estaba"}
        self.piezas.mkdir(parents=True, exist_ok=True)
        errores = []
        fuentes = []
        if self.fuente_repos:
            fuentes.append(f"{self.fuente_repos}/{repo}.git")
        if self.fuente_local and (Path(self.fuente_local) / repo).is_dir():
            fuentes.append(str(Path(self.fuente_local) / repo))
        for origen in fuentes:
            r = subprocess.run([self.git, "clone", "--depth", "1", origen, str(destino)], capture_output=True, text=True,
                               timeout=180, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
            if r.returncode == 0 and (destino / "src").is_dir():
                return {"estado": "descargada", "desde": origen, "version": _version(destino)}
            errores.append(f"{origen}: {(r.stderr or r.stdout).strip()[-200:]}")
            _borrar(destino)
        raise ErrorTienda("no se pudo descargar: " + (" | ".join(errores) or "no hay fuente configurada"))

    def _guardar_activas(self, activas: list[str]) -> None:
        datos = self._perfil()
        datos["brigadas"] = activas
        self.perfil.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def activar(self, nombre: str) -> list[str]:
        if not (self._carpeta(nombre) / "src").is_dir():
            raise ErrorTienda(f"primero hay que descargar '{nombre}'")
        activas = self.activas()
        faltan = [n for n in self._item(nombre).get("necesita", []) if n not in activas]
        if faltan:
            raise ErrorTienda(f"'{nombre}' necesita que actives antes: {', '.join(faltan)}")
        if nombre not in activas:
            activas.append(nombre)
            self._guardar_activas(activas)
        return activas

    def desactivar(self, nombre: str) -> list[str]:
        self._item(nombre)
        activas = self.activas()
        dependen = [n for n in activas if nombre in self.catalogo.get(n, {}).get("necesita", [])]
        if dependen:
            raise ErrorTienda(f"no se puede: {', '.join(dependen)} la necesita")
        if nombre in activas:
            activas.remove(nombre)
            self._guardar_activas(activas)
        return activas
