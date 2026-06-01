from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import extract_domains_from_text, fetch_json, fetch_text


class Source:
    name = "commoncrawl"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        indexes = fetch_json("https://index.commoncrawl.org/collinfo.json", timeout=5)
        if not indexes:
            return []
        index_id = indexes[0]["id"]
        results: list[str] = []
        for keyword in keywords[:2]:
            if len(results) >= limit:
                break
            url = f"https://index.commoncrawl.org/{index_id}-index?url=*{quote_plus(keyword)}*&output=json&fl=url&filter=status:200&limit={min(limit, 100)}"
            text = fetch_text(url, timeout=8)
            results.extend(extract_domains_from_text(text))
        return results[:limit]
