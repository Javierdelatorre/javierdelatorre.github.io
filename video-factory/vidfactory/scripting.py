"""Guionistas: convierten un tema en escenas. Cada uno es intercambiable."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .config import Config
from .models import Script, VidFactoryError
from .registry import Registry
from .styles.base import Style

WRITERS: Registry = Registry("guionista")

TEMPLATES = {
    "es": [
        "¿Ya viste lo que pasa con {t}? Esto está dando mucho que hablar.",
        "Primero: por qué {t} se volvió tendencia justo ahora.",
        "Segundo: lo que casi nadie está notando sobre {t}.",
        "Tercero: lo que esto puede cambiar para ti.",
        "Y lo más importante: no te quedes con la primera versión que escuchaste.",
        "Si te sirvió, sígueme para no perderte lo próximo.",
    ],
    "en": [
        "Have you seen what's happening with {t}? Everyone is talking about it.",
        "First: why {t} is trending right now.",
        "Second: what almost nobody notices about {t}.",
        "Third: what this could change for you.",
        "Most important: don't settle for the first version you heard.",
        "If this helped, follow me so you don't miss the next one.",
    ],
}


def build_prompt(topic: str, style: type[Style], cfg: Config) -> str:
    sc = cfg["script"]
    labels = (
        'Cada escena lleva "label" con el número del top, en orden descendente '
        "(p. ej. 3, 2, 1). "
        if style.needs_labels
        else 'Deja "label" vacío. '
    )
    return (
        f"Eres guionista de videos cortos virales para YouTube. Idioma: {sc['language']}.\n"
        f"Tema: {topic}\n"
        f"Estilo de animación: {style.name} — {style.script_hint}\n"
        f"Escribe {sc['scenes']} escenas. La primera es un gancho que retiene en 3 segundos; "
        "la última es un cierre con llamada a la acción. Cada escena: 1-2 frases cortas "
        "(máx. 200 caracteres), hechas para leerse en voz alta, sin emojis ni "
        "datos inventados: si no estás seguro de un dato, no lo afirmes.\n"
        f"{labels}"
        '"visual" es opcional: una palabra clave o el nombre de una imagen.\n'
        'Responde SOLO con JSON: {"title": str, "scenes": [{"text": str, "label": str, "visual": str}]}'
    )


def extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise VidFactoryError("El guionista no devolvió un JSON válido. Intenta de nuevo.")


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 300) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise VidFactoryError(f"{url} respondió {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise VidFactoryError(f"No pude conectar con {url}: {exc}") from exc


@WRITERS.register("template")
def template_writer(topic: str, style: type[Style], cfg: Config) -> dict:
    """Esqueleto genérico, SOLO para probar el flujo. Para contenido real usa ollama o claude."""
    sc = cfg["script"]
    lines = TEMPLATES.get(sc["language"], TEMPLATES["es"])[: sc["scenes"]]
    return {"title": topic, "scenes": [{"text": l.format(t=topic)} for l in lines]}


@WRITERS.register("ollama")
def ollama_writer(topic: str, style: type[Style], cfg: Config) -> dict:
    """Modelo local y gratis (https://ollama.com). Nada sale de tu PC."""
    opts = cfg["script"]["ollama"]
    reply = _post_json(
        f"{opts['host']}/api/generate",
        {
            "model": opts["model"],
            "prompt": build_prompt(topic, style, cfg),
            "stream": False,
            "format": "json",
        },
        {},
    )
    return extract_json(reply.get("response", ""))


@WRITERS.register("claude")
def claude_writer(topic: str, style: type[Style], cfg: Config) -> dict:
    """API de Anthropic. Envía solo el tema y las instrucciones; nunca tu voz."""
    opts = cfg["script"]["claude"]
    key = os.environ.get(opts["api_key_env"], "")
    if not key:
        raise VidFactoryError(f"Falta la variable de entorno {opts['api_key_env']}.")
    reply = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": opts["model"],
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": build_prompt(topic, style, cfg)}],
        },
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    text = "".join(b.get("text", "") for b in reply.get("content", []))
    return extract_json(text)


def finalize(data: dict, style: type[Style], language: str) -> Script:
    data = {"language": language, **data}
    script = Script.from_dict(data)
    if style.needs_labels:
        total = len(script.scenes)
        for i, scene in enumerate(script.scenes):
            scene.label = scene.label or str(total - i)
    return script


def write_script(topic: str, style: type[Style], cfg: Config) -> Script:
    writer = WRITERS.get(cfg["script"]["writer"])
    return finalize(writer(topic, style, cfg), style, cfg["script"]["language"])


def load_script_file(path: str | Path, style: type[Style], cfg: Config) -> Script:
    """Guion escrito a mano (o pegado desde un chat): JSON con title y scenes."""
    file = Path(path)
    if not file.is_file():
        raise VidFactoryError(f"No existe el guion: {file}")
    return finalize(extract_json(file.read_text(encoding="utf-8")), style, cfg["script"]["language"])
