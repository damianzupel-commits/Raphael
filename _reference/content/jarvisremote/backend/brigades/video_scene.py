"""Escena de validación de la brigada de VIDEO (declarada como dato; ver BrigadeSpec.validation).

Criterio de éxito: la brigada está bien cableada y con menor privilegio, rutea cada pedido al ayudante que corresponde, sus
tools NUNCA salen de la carpeta fija ni tocan el original, y las operaciones dejan un archivo nuevo con las propiedades
esperadas. Cinco pasos:

  Sin modelo ni red (corren siempre):
    1. ALCANCE       registrada, declarativa, menor privilegio (solo tools `video_*`), ayudantes efímeros.
    2. RUTEO         cada pedido va a su ayudante; lo ambiguo va al ayudante PASIVO (`info`, que solo lee).
  REQUIEREN ffmpeg en esta PC (si falta, quedan SIN VALIDAR; nunca rojo):
    3. CARPETA       las tools reales rechazan todo archivo fuera de la carpeta fija, y el original queda intacto.
    4. OPERACIONES   sobre un video SINTÉTICO generado en el momento: recortar, unir, transición, vertical, texto, audio.
  REQUIERE además el modelo de la brigada:
    5. E2E           un pedido en lenguaje natural recorta el tramo pedido y la respuesta nombra el archivo nuevo.

Toda la validación trabaja en una carpeta TEMPORAL (`VIDEO_EDIT_DIR` aislado): nunca toca los videos de Damian.
El orden y los textos de `scene` no se tocan sin motivo: su hash versiona el baseline.
"""

from __future__ import annotations

from .spec import Criterion, StepSpec, ValidationSpec

ROUTING = {
    "montaje": ["Recortá charla.mp4 del 1:00 al 2:30", "Uní intro.mp4 y charla.mp4 con una transición", "Poné el video en cámara lenta"],
    "imagen": ["Ponele un título que diga Bienvenidos", "Agregale el logo abajo a la derecha", "Pasalo a blanco y negro"],
    "sonido": ["Normalizá el volumen de charla.mp4", "Agregale música de fondo"],
    "subtitulos": ["Subtitulá charla.mp4", "Transcribí el video"],
    "clips": ["Sacame clips para redes de charla.mp4", "Hacé un reel vertical con los mejores momentos"],
    "info": ["¿Qué videos tengo?", "Necesito ayuda con una cosa"],
}
FUERA_DE_CARPETA = ["../afuera.mp4", "../../etc/passwd", "/etc/hostname", "C:\\Windows\\win.ini", "entrada/../../afuera.mp4"]

_V = "validation.video"

VALIDATION = ValidationSpec(
    title="VALIDACION DE VIDEO — carpeta fija, original intacto, operaciones sobre un video sintético",
    scene={"routing": ROUTING, "fuera_de_carpeta": FUERA_DE_CARPETA, "pedido_e2e": "Recortá prueba.mp4 desde el segundo 2 hasta el segundo 6"},
    facts={"duracion": 12, "ancho": 640, "alto": 360},
    steps=(
        StepSpec("alcance", "Alcance y menor privilegio", f"{_V}:step_alcance"),
        StepSpec("ruteo", "Ruteo a cada ayudante", f"{_V}:step_ruteo"),
        StepSpec("carpeta", "Carpeta fija y original intacto", f"{_V}:step_carpeta", prereq=f"{_V}:prereq_ffmpeg"),
        StepSpec("operaciones", "Operaciones de edición", f"{_V}:step_operaciones", prereq=f"{_V}:prereq_ffmpeg"),
        StepSpec("e2e", "Pedido en lenguaje natural", f"{_V}:step_e2e", prereq=f"{_V}:prereq_e2e"),
    ),
    criterion=Criterion(
        "PASA si la brigada está bien cableada, rutea cada pedido a su ayudante, ninguna tool sale de la carpeta fija ni toca el "
        "original, y las operaciones dejan archivos nuevos con las propiedades esperadas. Sin ffmpeg (o sin el modelo, para el "
        "e2e) esos pasos quedan SIN VALIDAR (corrida INCOMPLETA, código 2)."
    ),
    baseline_keys=("routing", "carpeta", "operaciones"),
    prerequisites=(),
    isolate_env={"VIDEO_EDIT_DIR": "videos"},
    base_metrics=f"{_V}:base_metrics",
    banner=f"{_V}:banner",
)
