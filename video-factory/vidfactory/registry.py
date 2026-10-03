from __future__ import annotations

from typing import Callable, Generic, TypeVar

from .models import VidFactoryError

T = TypeVar("T")


class Registry(Generic[T]):
    """Catálogo de piezas intercambiables (estilos, voces, guionistas, temas)."""

    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str) -> Callable[[T], T]:
        def decorator(obj: T) -> T:
            self._items[name] = obj
            return obj

        return decorator

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            options = ", ".join(self.names())
            raise VidFactoryError(
                f"{self.kind} desconocido: '{name}'. Disponibles: {options}"
            ) from None

    def names(self) -> list[str]:
        return sorted(self._items)
