from __future__ import annotations

from PIL import Image, ImageDraw

from ..fonts import load_font
from ..models import Scene
from .base import STYLES, WHITE, ease_out_back
from .kinetic import Kinetic


@STYLES.register("countdown")
class Countdown(Kinetic):
    name = "countdown"
    description = "Top / cuenta regresiva: un número grande aparece por escena y debajo el texto."
    script_hint = "un top o lista numerada (3, 2, 1): cada escena es un elemento de la lista."
    needs_labels = True

    def text_box(self) -> tuple[float, float, float, float]:
        return (self.w * 0.08, self.h * 0.42, self.w * 0.92, self.h * 0.90)

    def decorate(self, img: Image.Image, index: int, scene: Scene, t: float) -> None:
        draw = ImageDraw.Draw(img)
        if self.script and self.script.title:
            font = load_font(int(44 * self.u), self.font_path)
            title = self.script.title
            while font.getlength(title) > self.w * 0.9 and len(title) > 8:
                title = title[:-2].rstrip() + "…"
            draw.text((self.w / 2, self.h * 0.07), title, font=font, fill=WHITE, anchor="mm")
        if not scene.label:
            return
        side = int(380 * self.u * ease_out_back(min(t / 0.35, 1)))
        if side < 20:
            return
        cx, cy = self.w / 2, self.h * 0.24
        draw.rounded_rectangle(
            (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2),
            radius=int(side * 0.18),
            fill=(220, 30, 40),
            outline=WHITE,
            width=max(2, int(8 * self.u)),
        )
        font = load_font(int(side * 0.6), self.font_path)
        draw.text((cx, cy), scene.label, font=font, fill=WHITE, anchor="mm")
