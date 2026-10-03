from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

BOLD_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def find_font(custom: str = "") -> str | None:
    for candidate in ([custom] if custom else []) + BOLD_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


@lru_cache(maxsize=128)
def load_font(size: int, custom: str = "") -> ImageFont.FreeTypeFont:
    path = find_font(custom)
    size = max(8, int(size))
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)
