from __future__ import annotations

from typing import Protocol


class DomainSource(Protocol):
    name: str

    def collect(self, keywords: list[str], limit: int) -> list[str]: ...
