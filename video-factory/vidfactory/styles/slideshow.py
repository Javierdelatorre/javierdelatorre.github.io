from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from ..fonts import load_font
from ..models import Scene, Script
from .base import STYLES, WHITE, Style, wrap_lines

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
OVERSCAN = 1.2  # la imagen base es 20 % mayor que el cuadro: margen para el zoom


@STYLES.register("slideshow")
class Slideshow(Style):
    name = "slideshow"
    description = "Imágenes de tu carpeta assets/ con zoom suave y subtítulo abajo."
    script_hint = "narración descriptiva; 'visual' puede ser el nombre de un archivo de assets/."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files: list[Path] = []
        self._loaded: dict[Path, Image.Image] = {}

    def prepare(self, script: Script) -> None:
        super().prepare(script)
        folder = Path(self.assets_dir)
        self._files = (
            sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
            if folder.is_dir()
            else []
        )

    def _image_for(self, index: int, scene: Scene) -> Image.Image | None:
        if not self._files:
            return None
        chosen = next(
            (p for p in self._files if scene.visual and scene.visual.lower() in (p.name.lower(), p.stem.lower())),
            self._files[index % len(self._files)],
        )
        if chosen not in self._loaded:
            base = Image.open(chosen).convert("RGB")
            target = (int(self.w * OVERSCAN), int(self.h * OVERSCAN))
            scale = max(target[0] / base.width, target[1] / base.height)
            base = base.resize((round(base.width * scale), round(base.height * scale)), Image.LANCZOS)
            left, top = (base.width - target[0]) // 2, (base.height - target[1]) // 2
            self._loaded[chosen] = base.crop((left, top, left + target[0], top + target[1]))
        return self._loaded[chosen]

    def frame(self, index: int, scene: Scene, t: float) -> Image.Image:
        base = self._image_for(index, scene)
        if base is None:
            img = self.background(index).copy()
        else:
            progress = min(t / scene.duration, 1.0) if scene.duration else 0.0
            if index % 2:
                progress = 1 - progress
            zoom = 1 + (OVERSCAN - 1) * progress
            bw, bh = base.size
            vw, vh = bw / zoom, bh / zoom
            left, top = (bw - vw) / 2, (bh - vh) / 2
            img = base.resize(self.size, Image.BILINEAR, box=(left, top, left + vw, top + vh))
        self._caption(img, scene.text)
        return img

    def _caption(self, img: Image.Image, text: str) -> None:
        size = int(58 * self.u)
        font = load_font(size, self.font_path)
        words = text.split()
        lines = wrap_lines(words, font, self.w * 0.84, font.getlength(" "))
        line_h = int(size * 1.3)
        band_h = len(lines) * line_h + int(60 * self.u)
        box = (0, int(self.h * 0.88) - band_h, self.w, int(self.h * 0.88))
        region = img.crop(box)
        img.paste(Image.blend(region, Image.new("RGB", region.size, (0, 0, 0)), 0.6), box)
        draw = ImageDraw.Draw(img)
        y = box[1] + int(30 * self.u)
        for idxs in lines:
            draw.text((self.w / 2, y), " ".join(words[i] for i in idxs), font=font, fill=WHITE, anchor="ma")
            y += line_h
