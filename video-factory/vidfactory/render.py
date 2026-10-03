"""Salida de video con ffmpeg."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .models import VidFactoryError


def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise VidFactoryError(
            "No encuentro ffmpeg. Ejecuta: pip install imageio-ffmpeg (o instala ffmpeg)."
        ) from None


def nvenc_works(ffmpeg: str) -> bool:
    """True si la tarjeta NVIDIA puede codificar con h264_nvenc (no solo si ffmpeg lo lista)."""
    try:
        proc = subprocess.run(
            [ffmpeg, "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


def pick_encoder(preference: str, ffmpeg: str) -> str:
    if preference != "auto":
        return preference
    return "h264_nvenc" if nvenc_works(ffmpeg) else "libx264"


def encoder_args(encoder: str, draft: bool) -> list[str]:
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "28" if draft else "22"]
    if encoder == "libx264":
        return ["-c:v", "libx264", "-preset", "ultrafast" if draft else "veryfast", "-crf", "28" if draft else "20"]
    return ["-c:v", encoder]


def video_size(fmt: str, draft: bool) -> tuple[int, int]:
    if fmt not in ("vertical", "horizontal"):
        raise VidFactoryError("video.format debe ser 'vertical' u 'horizontal'.")
    size = (1080, 1920) if fmt == "vertical" else (1920, 1080)
    return (size[0] // 2, size[1] // 2) if draft else size


@contextmanager
def open_sink(ffmpeg: str, out: Path, size: tuple[int, int], fps: int, audio: Path, encoder: str, draft: bool):
    """Abre ffmpeg y entrega su stdin: escribe ahí cada fotograma RGB crudo."""
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-",
        "-i", str(audio),
        *encoder_args(encoder, draft),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
        str(out),
    ]
    with tempfile.TemporaryFile() as errlog:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errlog)
        broken = False
        try:
            yield proc.stdin
        except BrokenPipeError:
            broken = True
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        try:
            proc.stdin.close()
        except BrokenPipeError:
            broken = True
        code = proc.wait()
        if code != 0 or broken:
            errlog.seek(0)
            detail = errlog.read().decode(errors="replace")[-1500:]
            raise VidFactoryError(f"ffmpeg falló (codificador {encoder}):\n{detail}")
