from __future__ import annotations

from dataclasses import dataclass, field


class VidFactoryError(Exception):
    """Error esperado (configuración, red, backend) con mensaje para el usuario."""


@dataclass
class Topic:
    title: str
    source: str = "manual"
    score: float = 0.0


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


@dataclass
class Scene:
    text: str
    label: str = ""  # p. ej. el número de un top ("3")
    visual: str = ""  # imagen o palabra clave que el estilo puede usar
    duration: float = 0.0  # la fija la etapa de voz
    words: list[WordTiming] = field(default_factory=list)


@dataclass
class Script:
    title: str
    scenes: list[Scene]
    language: str = "es"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "language": self.language,
            "scenes": [
                {"text": s.text, "label": s.label, "visual": s.visual}
                for s in self.scenes
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Script:
        raw = data.get("scenes") if isinstance(data, dict) else None
        if not raw:
            raise VidFactoryError("El guion no tiene escenas.")
        scenes = []
        for item in raw:
            if isinstance(item, str):
                item = {"text": item}
            text = str(item.get("text", "")).strip()
            if not text:
                raise VidFactoryError("Hay una escena sin texto en el guion.")
            scenes.append(
                Scene(
                    text=text,
                    label=str(item.get("label", "") or ""),
                    visual=str(item.get("visual", "") or ""),
                )
            )
        title = str(data.get("title") or scenes[0].text[:60]).strip()
        return cls(title=title, scenes=scenes, language=str(data.get("language", "es")))
