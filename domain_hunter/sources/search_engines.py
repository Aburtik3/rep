from __future__ import annotations

import re
from urllib.parse import quote_plus

import requests

DOMAIN_RE = re.compile(r"https?://([^/'\"\s>]+)")


class Source:
    name = "search_engines"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        # Lightweight public HTML search endpoint; failures are ignored so manual workflow remains responsive.
        results: list[str] = []
        for keyword in keywords:
            if len(results) >= limit:
                break
            try:
                url = f"https://duckduckgo.com/html/?q={quote_plus(keyword + ' company website')}"
                html = requests.get(url, timeout=10, headers={"User-Agent": "DomainHunterPro/1.0"}).text
                results.extend(DOMAIN_RE.findall(html))
            except requests.RequestException:
                continue
        return results[:limit]
