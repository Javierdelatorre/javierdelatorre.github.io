"""Voces. Por defecto todo es local: tu voz nunca sale de tu PC."""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import wave
from pathlib import Path

from .config import Config
from .models import VidFactoryError, WordTiming
from .registry import Registry

BACKENDS: Registry = Registry("voz")


def write_silence(path: Path, seconds: float, rate: int = 22050) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


class Voice:
    name = ""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def synth(self, text: str, out_wav: Path) -> None:
        raise NotImplementedError

    def fingerprint(self) -> str:
        """Cambia cuando cambia la configuración, para invalidar la caché."""
        return json.dumps(self.cfg["voice"].get(self.name, {}), sort_keys=True)

    def check(self) -> str | None:
        """None si está listo; si no, el motivo."""
        return None


@BACKENDS.register("silent")
class SilentVoice(Voice):
    """Audio en silencio con la duración de una lectura normal. Solo para probar y ajustar estilos."""

    name = "silent"

    def synth(self, text: str, out_wav: Path) -> None:
        write_silence(out_wav, max(1.0, len(text.split()) / 2.5))


@BACKENDS.register("piper")
class PiperVoice(Voice):
    """Piper (https://github.com/rhasspy/piper): TTS local muy rápido en CPU."""

    name = "piper"

    def check(self) -> str | None:
        opts = self.cfg["voice"]["piper"]
        if not opts["model"]:
            return "falta voice.piper.model (ruta al .onnx)"
        if not Path(opts["model"]).expanduser().is_file() and not self.cfg.path(opts["model"]).is_file():
            return f"no existe el modelo {opts['model']}"
        return None

    def synth(self, text: str, out_wav: Path) -> None:
        opts = self.cfg["voice"]["piper"]
        problem = self.check()
        if problem:
            raise VidFactoryError(f"Piper: {problem}")
        model = self.cfg.path(opts["model"])
        try:
            subprocess.run(
                [opts["binary"], "--model", str(model), "--output_file", str(out_wav)],
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            raise VidFactoryError(f"No encuentro '{opts['binary']}'. Instala piper (pip install piper-tts).") from None
        except subprocess.CalledProcessError as exc:
            raise VidFactoryError(f"Piper falló: {exc.stderr.decode(errors='replace')[-300:]}") from exc


@BACKENDS.register("command")
class CommandVoice(Voice):
    """Cualquier TTS local (XTTS, F5-TTS, tu propio script) llamado como comando.

    En config.toml: args = ["python", "mi_tts.py", "--text-file", "{text_file}",
    "--speaker", "{speaker_wav}", "--out", "{out}"]. Debe escribir un .wav en {out}.
    """

    name = "command"

    def check(self) -> str | None:
        opts = self.cfg["voice"]["command"]
        if not opts["args"]:
            return "falta voice.command.args"
        if "{out}" not in " ".join(opts["args"]):
            return "args debe incluir {out}"
        return None

    def fingerprint(self) -> str:
        opts = self.cfg["voice"]["command"]
        speaker = self.cfg.path(opts["speaker_wav"])
        stamp = f"{speaker.stat().st_size}:{speaker.stat().st_mtime_ns}" if speaker.is_file() else "sin-muestra"
        return json.dumps(opts, sort_keys=True) + stamp

    def synth(self, text: str, out_wav: Path) -> None:
        problem = self.check()
        if problem:
            raise VidFactoryError(f"Voz 'command': {problem}")
        opts = self.cfg["voice"]["command"]
        text_file = out_wav.with_suffix(".txt")
        text_file.write_text(text, encoding="utf-8")
        values = {
            "text_file": str(text_file),
            "out": str(out_wav),
            "speaker_wav": str(self.cfg.path(opts["speaker_wav"])),
            "language": self.cfg["script"]["language"],
        }
        cmd = [a.format(**values) for a in opts["args"]]
        try:
            subprocess.run(cmd, check=True, capture_output=True, cwd=self.cfg.base_dir)
        except FileNotFoundError:
            raise VidFactoryError(f"No encuentro el programa '{cmd[0]}'.") from None
        except subprocess.CalledProcessError as exc:
            tail = (exc.stderr or b"").decode(errors="replace")[-400:]
            raise VidFactoryError(f"Tu comando de voz falló:\n{tail}") from exc
        finally:
            text_file.unlink(missing_ok=True)
        if not out_wav.is_file():
            raise VidFactoryError("Tu comando de voz terminó pero no creó el .wav en {out}.")


def distribute_words(text: str, speech_seconds: float) -> list[WordTiming]:
    """Reparte la duración entre palabras según su largo (aproximación sin reconocimiento de voz)."""
    words = text.split()
    weights = [len(w.strip(".,;:!?¿¡")) + 2 for w in words]
    total = sum(weights) or 1
    out, cursor = [], 0.0
    for word, weight in zip(words, weights):
        span = speech_seconds * weight / total
        out.append(WordTiming(word, cursor, cursor + span))
        cursor += span
    return out


def _normalize(ffmpeg: str, src: Path, dst: Path) -> None:
    proc = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-ar", "44100", "-ac", "1", "-sample_fmt", "s16", str(dst)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise VidFactoryError(f"ffmpeg no pudo leer el audio: {proc.stderr.decode(errors='replace')[-300:]}")


def synthesize(script, cfg: Config, run_dir: Path, ffmpeg: str, log=print) -> Path:
    """Genera la voz de cada escena (con caché), fija duraciones y arma audio.wav."""
    voice = BACKENDS.get(cfg["voice"]["backend"])(cfg)
    cache = cfg.path(cfg["paths"]["cache"]) / "voice"
    cache.mkdir(parents=True, exist_ok=True)
    pause = float(cfg["video"]["pause"])
    rate = 44100
    out_path = run_dir / "audio.wav"

    with wave.open(str(out_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        for i, scene in enumerate(script.scenes, 1):
            key = hashlib.sha1(f"{voice.name}|{voice.fingerprint()}|{scene.text}".encode()).hexdigest()[:20]
            norm = cache / f"{key}.n.wav"
            if norm.is_file():
                hit = " (caché)"
            else:
                hit = ""
                raw = cache / f"{key}.wav"
                voice.synth(scene.text, raw)
                _normalize(ffmpeg, raw, norm)
                raw.unlink(missing_ok=True)
            speech = wav_duration(norm)
            scene.duration = speech + pause
            scene.words = distribute_words(scene.text, speech)
            with wave.open(str(norm), "rb") as src:
                out.writeframes(src.readframes(src.getnframes()))
            out.writeframes(struct.pack("<h", 0) * int(pause * rate))
            log(f"  voz {i}/{len(script.scenes)}: {speech:.1f}s{hit}")
    return out_path
