from __future__ import annotations

from pathlib import Path


class Source:
    name = "custom"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        path = Path("domain_hunter/config/custom_domains.txt")
        if not path.exists():
            return []
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][:limit]
