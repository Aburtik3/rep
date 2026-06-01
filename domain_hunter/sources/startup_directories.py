from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import extract_domains_from_text, fetch_text

STARTUP_SEARCHES = [
    "https://www.ycombinator.com/companies?query={keyword}",
    "https://betalist.com/search?query={keyword}",
    "https://www.crunchbase.com/discover/organization.companies/field/organizations/categories/{keyword}",
]


class Source:
    name = "startup_directories"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords[:1]:
            for template in STARTUP_SEARCHES[:2]:
                if len(results) >= limit:
                    break
                html = fetch_text(template.format(keyword=quote_plus(keyword)))
                results.extend(extract_domains_from_text(html))
        return results[:limit]
