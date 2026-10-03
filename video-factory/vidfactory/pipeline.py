"""Orquesta las etapas: guion -> voz -> render, midiendo cuánto tarda cada una."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import scripting, voice
from .config import Config
from .models import Script, VidFactoryError
from .render import ffmpeg_exe, open_sink, pick_encoder, video_size
from .styles import STYLES, Style


@dataclass
class Result:
    video: Path
    script_path: Path
    seconds: float  # duración del video
    timings: dict[str, float] = field(default_factory=dict)
    encoder: str = ""


def slugify(text: str, limit: int = 40) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:limit] or "video"


def render_video(script: Script, style: Style, audio: Path, out: Path, ffmpeg: str,
                 encoder: str, draft: bool, log=print) -> None:
    style.prepare(script)
    fps = style.fps
    total = round(sum(s.duration for s in script.scenes) * fps)
    elapsed = 0.0
    written = 0
    next_report = 25
    with open_sink(ffmpeg, out, style.size, fps, audio, encoder, draft) as stdin:
        for index, scene in enumerate(script.scenes):
            first = round(elapsed * fps)
            elapsed += scene.duration
            for f in range(first, round(elapsed * fps)):
                image = style.frame(index, scene, (f - first) / fps)
                if image.size != style.size:
                    raise VidFactoryError(f"El estilo '{style.name}' devolvió {image.size}, se esperaba {style.size}.")
                stdin.write(image.convert("RGB").tobytes())
                written += 1
                if total and written * 100 // total >= next_report:
                    log(f"  render {next_report}%")
                    next_report += 25


@contextmanager
def _timed(timings: dict[str, float], name: str):
    start = time.perf_counter()
    yield
    timings[name] = time.perf_counter() - start


def make_video(cfg: Config, topic: str = "", style_name: str | None = None,
               script_path: str | None = None, draft: bool = False, log=print) -> Result:
    style_cls = STYLES.get(style_name or cfg["style"]["name"])
    fps = int(cfg["video"]["fps"])
    size = video_size(cfg["video"]["format"], draft)
    ffmpeg = ffmpeg_exe()
    timings: dict[str, float] = {}

    with _timed(timings, "guion"):
        if script_path:
            script = scripting.load_script_file(script_path, style_cls, cfg)
        elif topic:
            script = scripting.write_script(topic, style_cls, cfg)
        else:
            raise VidFactoryError("Indica un tema (--topic) o un guion (--script).")
    log(f"Guion: «{script.title}» · {len(script.scenes)} escenas · estilo {style_cls.name}")

    run_dir = cfg.path(cfg["paths"]["output"]) / f"{datetime.now():%Y%m%d-%H%M%S}-{slugify(script.title)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    script_file = run_dir / "script.json"
    script_file.write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    with _timed(timings, "voz"):
        audio = voice.synthesize(script, cfg, run_dir, ffmpeg, log)

    style = style_cls(size, fps, cfg["style"], cfg.path(cfg["style"]["assets_dir"]))
    encoder = pick_encoder(cfg["render"]["encoder"], ffmpeg)
    out = run_dir / "video.mp4"
    with _timed(timings, "render"):
        render_video(script, style, audio, out, ffmpeg, encoder, draft, log)

    seconds = sum(s.duration for s in script.scenes)
    (run_dir / "timings.json").write_text(
        json.dumps({"video_seconds": seconds, "encoder": encoder, **timings}, indent=2), encoding="utf-8"
    )
    return Result(out, script_file, seconds, timings, encoder)
