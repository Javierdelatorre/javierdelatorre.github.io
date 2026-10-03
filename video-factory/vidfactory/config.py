from __future__ import annotations

import copy
import tomllib
from pathlib import Path

from .models import VidFactoryError

DEFAULTS: dict = {
    "video": {"format": "vertical", "fps": 30, "pause": 0.25},
    "topics": {"provider": "trends", "geo": "MX", "file": "topics.txt"},
    "script": {
        "writer": "template",
        "language": "es",
        "scenes": 6,
        "ollama": {"host": "http://localhost:11434", "model": "llama3.1"},
        "claude": {"model": "claude-sonnet-5", "api_key_env": "ANTHROPIC_API_KEY"},
    },
    "voice": {
        "backend": "silent",
        "piper": {"binary": "piper", "model": ""},
        "command": {"args": [], "speaker_wav": "voices/mi_voz.wav"},
    },
    "style": {"name": "kinetic", "assets_dir": "assets", "font": ""},
    "render": {"encoder": "auto"},
    "paths": {"output": "output", "cache": "cache"},
}


def deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Config:
    def __init__(self, data: dict, base_dir: Path):
        self.data = data
        self.base_dir = base_dir

    def __getitem__(self, key: str) -> dict:
        return self.data[key]

    def path(self, value: str) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else self.base_dir / p


def load_config(path: str | Path | None = None) -> Config:
    """Carga config.toml (el indicado, o el de la carpeta actual) sobre los valores por defecto."""
    if path:
        file = Path(path)
        if not file.is_file():
            raise VidFactoryError(f"No existe el archivo de configuración: {file}")
    else:
        candidate = Path.cwd() / "config.toml"
        file = candidate if candidate.is_file() else None

    if file is None:
        return Config(copy.deepcopy(DEFAULTS), Path.cwd())
    try:
        with file.open("rb") as fh:
            user = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise VidFactoryError(f"config.toml mal escrito: {exc}") from exc
    return Config(deep_merge(DEFAULTS, user), file.resolve().parent)
