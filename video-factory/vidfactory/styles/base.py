from __future__ import annotations

from PIL import Image, ImageOps

from ..models import Scene, Script
from ..registry import Registry

STYLES: Registry = Registry("estilo")

PALETTES = [
    ((20, 24, 60), (120, 40, 160)),
    ((10, 40, 70), (0, 140, 150)),
    ((60, 15, 30), (200, 70, 50)),
    ((15, 15, 15), (70, 70, 90)),
]
ACCENT = (255, 214, 10)
WHITE = (255, 255, 255)


def gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    ramp = Image.linear_gradient("L").resize(size)
    return ImageOps.colorize(ramp, black=top, white=bottom).convert("RGB")


def ease_out(x: float) -> float:
    return 1 - (1 - x) ** 3


def ease_out_back(x: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def wrap_lines(words: list[str], font, max_width: float, space: float) -> list[list[int]]:
    """Reparte índices de palabras en líneas que caben en max_width."""
    lines: list[list[int]] = [[]]
    used = 0.0
    for i, word in enumerate(words):
        width = font.getlength(word)
        if lines[-1] and used + space + width > max_width:
            lines.append([i])
            used = width
        else:
            used += width if not lines[-1] else space + width
            lines[-1].append(i)
    return lines


class Style:
    """Un tipo de animación. Para crear uno nuevo: hereda, define `frame` y regístralo en STYLES."""

    name = ""
    description = ""
    script_hint = ""  # indicación para el guionista (qué forma debe tener el guion)
    needs_labels = False  # True si cada escena necesita un número/etiqueta

    def __init__(self, size: tuple[int, int], fps: int, options: dict, assets_dir):
        self.w, self.h = size
        self.size = size
        self.fps = fps
        self.options = options
        self.assets_dir = assets_dir
        self.u = min(size) / 1080  # escala: todo se dimensiona respecto a 1080 px
        self.font_path = options.get("font", "")
        self.script: Script | None = None
        self._backgrounds: dict[int, Image.Image] = {}

    def prepare(self, script: Script) -> None:
        self.script = script

    def background(self, index: int) -> Image.Image:
        key = index % len(PALETTES)
        if key not in self._backgrounds:
            top, bottom = PALETTES[key]
            self._backgrounds[key] = gradient(self.size, top, bottom)
        return self._backgrounds[key]

    def frame(self, index: int, scene: Scene, t: float) -> Image.Image:
        """Imagen RGB del tamaño del video para el instante t (s) dentro de la escena."""
        raise NotImplementedError
