from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import extract_domains_from_text, fetch_json


class Source:
    name = "hackernews"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords[:2]:
            if len(results) >= limit:
                break
            data = fetch_json(f"https://hn.algolia.com/api/v1/search?query={quote_plus(keyword)}&tags=story&hitsPerPage=50", timeout=5)
            for hit in data.get("hits", []):
                if hit.get("url"):
                    results.append(hit["url"])
                if hit.get("story_text"):
                    results.extend(extract_domains_from_text(hit["story_text"]))
                if len(results) >= limit:
                    break
        return results[:limit]
