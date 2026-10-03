"""Propuesta de temas virales."""
from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import Config
from .models import Topic, VidFactoryError
from .registry import Registry

PROVIDERS: Registry = Registry("proveedor de temas")

TRENDS_URL = "https://trends.google.com/trending/rss?geo={geo}"
TRENDS_NS = {"ht": "https://trends.google.com/trending/rss"}


def parse_traffic(text: str | None) -> float:
    """'200+' -> 200, '50K+' -> 50_000, '2M+' -> 2_000_000."""
    if not text:
        return 0.0
    raw = text.strip().rstrip("+").replace(",", "").upper()
    factor = 1.0
    if raw.endswith("K"):
        factor, raw = 1e3, raw[:-1]
    elif raw.endswith("M"):
        factor, raw = 1e6, raw[:-1]
    try:
        return float(raw) * factor
    except ValueError:
        return 0.0


def parse_trends_rss(xml_text: str) -> list[Topic]:
    root = ET.fromstring(xml_text)
    topics = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if title:
            traffic = item.findtext("ht:approx_traffic", namespaces=TRENDS_NS)
            topics.append(Topic(title, "google-trends", parse_traffic(traffic)))
    return topics


@PROVIDERS.register("trends")
def trends_provider(cfg: Config) -> list[Topic]:
    url = TRENDS_URL.format(geo=cfg["topics"]["geo"])
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return parse_trends_rss(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
        raise VidFactoryError(
            f"No pude leer las tendencias de Google ({exc}). "
            "Usa --topic o el proveedor 'file' (topics.txt)."
        ) from exc


@PROVIDERS.register("file")
def file_provider(cfg: Config) -> list[Topic]:
    file = cfg.path(cfg["topics"]["file"])
    if not file.is_file():
        raise VidFactoryError(f"No existe {file}: escribe un tema por línea.")
    lines = [l.strip() for l in file.read_text(encoding="utf-8").splitlines()]
    lines = [l for l in lines if l and not l.startswith("#")]
    return [Topic(l, "file", float(len(lines) - i)) for i, l in enumerate(lines)]


def suggest(cfg: Config, limit: int = 10, provider: str | None = None) -> list[Topic]:
    fetch = PROVIDERS.get(provider or cfg["topics"]["provider"])
    topics = sorted(fetch(cfg), key=lambda t: t.score, reverse=True)
    return topics[:limit]
