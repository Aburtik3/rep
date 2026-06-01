from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import extract_domains_from_text, fetch_text

DIRECTORY_SEARCHES = [
    "https://www.g2.com/search?query={keyword}",
    "https://www.capterra.com/search/?query={keyword}",
    "https://www.trustradius.com/search?query={keyword}",
]


class Source:
    name = "company_directories"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords[:1]:
            for template in DIRECTORY_SEARCHES[:2]:
                if len(results) >= limit:
                    break
                html = fetch_text(template.format(keyword=quote_plus(keyword)))
                results.extend(extract_domains_from_text(html))
        return results[:limit]
