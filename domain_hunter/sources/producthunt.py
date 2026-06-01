from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import extract_domains_from_text, fetch_text


class Source:
    name = "producthunt"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords[:1]:
            if len(results) >= limit:
                break
            html = fetch_text(f"https://www.producthunt.com/search?q={quote_plus(keyword)}")
            results.extend(extract_domains_from_text(html))
        return results[:limit]
