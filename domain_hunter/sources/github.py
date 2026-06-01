from __future__ import annotations

from urllib.parse import quote_plus

from domain_hunter.sources.utils import fetch_json


class Source:
    name = "github"

    def collect(self, keywords: list[str], limit: int) -> list[str]:
        results: list[str] = []
        for keyword in keywords[:1]:
            if len(results) >= limit:
                break
            query = quote_plus(f"{keyword} company OR startup")
            data = fetch_json(f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=50")
            for item in data.get("items", []):
                homepage = (item.get("homepage") or "").strip()
                if homepage:
                    results.append(homepage)
                owner_url = item.get("owner", {}).get("html_url")
                if owner_url:
                    results.append(owner_url)
                if len(results) >= limit:
                    break
        return results[:limit]
