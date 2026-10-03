from __future__ import annotations

import argparse
import os
import shutil
import urllib.error
import urllib.request

from . import topics, voice
from .config import Config, load_config
from .fonts import find_font
from .models import VidFactoryError
from .pipeline import Result, make_video
from .render import ffmpeg_exe, nvenc_works
from .styles import STYLES


def _add_make_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--style", help="Tipo de animación (ver: vidfactory styles)")
    parser.add_argument("--writer", help="Guionista: template | ollama | claude")
    parser.add_argument("--voice", help="Voz: silent | piper | command")
    parser.add_argument("--draft", action="store_true", help="Borrador: mitad de resolución, render rápido")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vidfactory", description="Tema viral -> guion -> voz -> animación -> mp4")
    parser.add_argument("--config", help="Ruta a config.toml (por defecto el de la carpeta actual)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="Revisa que todo esté listo (ffmpeg, GPU, voz, guionista)")
    sub.add_parser("styles", help="Lista los tipos de animación")

    p = sub.add_parser("topics", help="Propone temas virales")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--provider", help="trends | file")

    p = sub.add_parser("make", help="Genera un video de un tema")
    p.add_argument("--topic", help="Tema del video")
    p.add_argument("--script", help="Guion ya escrito (JSON) en vez de generarlo")
    _add_make_options(p)

    p = sub.add_parser("auto", help="Toma un tema viral propuesto y genera el video")
    p.add_argument("--pick", type=int, default=1, help="Posición del tema en la lista (1 = el más viral)")
    p.add_argument("--provider", help="trends | file")
    _add_make_options(p)

    p = sub.add_parser("batch", help="Genera un video por cada línea de un archivo de temas")
    p.add_argument("file")
    _add_make_options(p)
    return parser


def _apply_overrides(cfg: Config, args: argparse.Namespace) -> None:
    if getattr(args, "style", None):
        cfg["style"]["name"] = args.style
    if getattr(args, "writer", None):
        cfg["script"]["writer"] = args.writer
    if getattr(args, "voice", None):
        cfg["voice"]["backend"] = args.voice


def _report(result: Result) -> None:
    render = result.timings.get("render", 0.0)
    ratio = render / result.seconds if result.seconds else 0.0
    steps = " | ".join(f"{k} {v:.1f}s" for k, v in result.timings.items())
    print(f"\n✔ Video listo: {result.video}")
    print(f"  duración {result.seconds:.1f}s · codificador {result.encoder} · render {ratio:.2f}× tiempo real")
    print(f"  tiempos: {steps}")


def _warn_placeholders(cfg: Config) -> None:
    if cfg["voice"]["backend"] == "silent":
        print("⚠ Voz 'silent': el video saldrá SIN voz (modo prueba). Configura [voice] en config.toml.")
    if cfg["script"]["writer"] == "template":
        print("⚠ Guionista 'template': guion genérico de prueba. Usa --writer ollama, --writer claude o --script.")


def cmd_doctor(cfg: Config) -> int:
    ok = True

    def line(good: bool | None, text: str) -> None:
        nonlocal ok
        mark = {True: "✔", False: "✘", None: "·"}[good]
        ok = ok and good is not False
        print(f" {mark} {text}")

    try:
        ffmpeg = ffmpeg_exe()
        line(True, f"ffmpeg: {ffmpeg}")
        gpu = nvenc_works(ffmpeg)
        line(None, "codificación por GPU NVIDIA: " + ("disponible (h264_nvenc)" if gpu else "no disponible, se usa CPU (libx264)"))
    except VidFactoryError as exc:
        line(False, str(exc))
    line(None, "nvidia-smi: " + ("encontrado" if shutil.which("nvidia-smi") else "no encontrado (sin GPU NVIDIA o sin drivers)"))
    font = find_font(cfg["style"]["font"])
    line(font is not None, f"fuente: {font or 'no encontré ninguna; se usará la de Pillow (más fea). Define style.font'}")

    backend = cfg["voice"]["backend"]
    try:
        problem = voice.BACKENDS.get(backend)(cfg).check()
        if backend == "silent":
            line(None, "voz: 'silent' (solo pruebas; sin audio real)")
        else:
            line(problem is None, f"voz '{backend}': " + (problem or "lista"))
    except VidFactoryError as exc:
        line(False, str(exc))

    writer = cfg["script"]["writer"]
    if writer == "ollama":
        host = cfg["script"]["ollama"]["host"]
        try:
            urllib.request.urlopen(f"{host}/api/tags", timeout=3)
            line(True, f"guionista ollama responde en {host}")
        except (urllib.error.URLError, OSError):
            line(False, f"guionista ollama: no responde en {host} (¿está abierto?)")
    elif writer == "claude":
        env = cfg["script"]["claude"]["api_key_env"]
        line(bool(os.environ.get(env)), f"guionista claude: variable {env} " + ("definida" if os.environ.get(env) else "no definida"))
    else:
        line(None, f"guionista '{writer}'")

    images = cfg.path(cfg["style"]["assets_dir"])
    count = len([p for p in images.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]) if images.is_dir() else 0
    line(None, f"imágenes en {images}: {count} (las usa el estilo slideshow)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        _apply_overrides(cfg, args)

        if args.cmd == "doctor":
            return cmd_doctor(cfg)
        if args.cmd == "styles":
            for name in STYLES.names():
                print(f"{name:10} {STYLES.get(name).description}")
            return 0
        if args.cmd == "topics":
            for i, t in enumerate(topics.suggest(cfg, args.limit, args.provider), 1):
                traffic = f"  (~{t.score:,.0f} búsquedas)" if t.score else ""
                print(f"{i:2}. {t.title}{traffic}")
            return 0

        _warn_placeholders(cfg)
        if args.cmd == "make":
            _report(make_video(cfg, args.topic or "", args.style, args.script, args.draft))
        elif args.cmd == "auto":
            found = topics.suggest(cfg, max(args.pick, 10), args.provider)
            if args.pick > len(found):
                raise VidFactoryError(f"Solo hay {len(found)} temas propuestos.")
            chosen = found[args.pick - 1]
            print(f"Tema elegido: {chosen.title}")
            _report(make_video(cfg, chosen.title, args.style, None, args.draft))
        elif args.cmd == "batch":
            lines = [l.strip() for l in open(args.file, encoding="utf-8")]
            for topic in (l for l in lines if l and not l.startswith("#")):
                print(f"\n=== {topic} ===")
                _report(make_video(cfg, topic, args.style, None, args.draft))
        return 0
    except VidFactoryError as exc:
        print(f"Error: {exc}")
        return 1
