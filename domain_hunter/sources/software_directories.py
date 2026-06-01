from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import extract_domains_from_text, fetch_text

SOFTWARE_DIRECTORIES = [
    "https://www.saashub.com/search?q={keyword}",
    "https://stackshare.io/search/q={keyword}",
    "https://alternativeto.net/browse/search/?q={keyword}",
]


class Source:
    name = "software_directories"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords[:2]:
            for template in SOFTWARE_DIRECTORIES:
                if len(results) >= limit:
                    break
                html = fetch_text(template.format(keyword=quote_plus(keyword)))
                results.extend(extract_domains_from_text(html))
        return results[:limit]
