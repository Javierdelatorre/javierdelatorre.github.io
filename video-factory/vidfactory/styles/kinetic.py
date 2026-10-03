from __future__ import annotations

from PIL import Image, ImageDraw

from ..fonts import load_font
from ..models import Scene
from .base import ACCENT, STYLES, WHITE, Style, ease_out, wrap_lines


@STYLES.register("kinetic")
class Kinetic(Style):
    name = "kinetic"
    description = "Texto animado palabra por palabra sobre fondo degradado (ideal para Shorts)."
    script_hint = "frases cortas y contundentes; cada una se muestra palabra por palabra."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._layouts: dict[tuple[int, str], tuple] = {}

    def text_box(self) -> tuple[float, float, float, float]:
        return (self.w * 0.08, self.h * 0.15, self.w * 0.92, self.h * 0.85)

    def layout(self, index: int, scene: Scene):
        key = (index, scene.text)
        if key in self._layouts:
            return self._layouts[key]
        x0, y0, x1, y1 = self.text_box()
        max_w, max_h = x1 - x0, y1 - y0
        words = scene.text.split()
        size = int(110 * self.u)
        while True:
            font = load_font(size, self.font_path)
            space = font.getlength(" ")
            lines = wrap_lines(words, font, max_w, space)
            line_h = int(size * 1.25)
            if len(lines) * line_h <= max_h or size <= int(38 * self.u):
                break
            size = int(size * 0.92)
        top = y0 + (max_h - len(lines) * line_h) / 2
        placed = []
        for row, idxs in enumerate(lines):
            width = sum(font.getlength(words[i]) for i in idxs) + space * (len(idxs) - 1)
            x = x0 + (max_w - width) / 2
            for i in idxs:
                placed.append((i, words[i], x, top + row * line_h))
                x += font.getlength(words[i]) + space
        self._layouts[key] = (font, placed)
        return self._layouts[key]

    def decorate(self, img: Image.Image, index: int, scene: Scene, t: float) -> None:
        """Elementos extra de cada estilo derivado (insignias, títulos...)."""

    def frame(self, index: int, scene: Scene, t: float) -> Image.Image:
        img = self.background(index).copy()
        self.decorate(img, index, scene, t)
        font, placed = self.layout(index, scene)
        draw = ImageDraw.Draw(img)
        stroke = max(2, int(5 * self.u))
        for i, word, x, y in placed:
            timing = scene.words[i] if i < len(scene.words) else None
            start = timing.start if timing else 0.0
            if t < start:
                continue
            rise = (1 - ease_out(min((t - start) / 0.18, 1))) * 34 * self.u
            active = timing is not None and timing.start <= t < timing.end
            draw.text(
                (x, y + rise),
                word,
                font=font,
                fill=ACCENT if active else WHITE,
                stroke_width=stroke,
                stroke_fill=(0, 0, 0),
            )
        return img
