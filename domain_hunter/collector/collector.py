from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass

import domain_hunter.sources as sources_pkg
from domain_hunter.categorizer.categorizer import categorize
from domain_hunter.categorizer.rating import rate_domain
from domain_hunter.cleaner.domain_cleaner import clean_domains
from domain_hunter.database.db import connect, now_iso


@dataclass
class CollectionResult:
    requested: int
    collected_raw: int
    saved: int
    domains: list[str]


def load_sources():
    preferred_order = {"custom": 0, "github": 1, "producthunt": 2, "company_directories": 3, "software_directories": 4, "startup_directories": 5, "hackernews": 6, "commoncrawl": 7, "search_engines": 8, "curated_company_catalog": 9}
    plugins = []
    for module_info in pkgutil.iter_modules(sources_pkg.__path__):
        if module_info.name in {"base"} or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"domain_hunter.sources.{module_info.name}")
        source_cls = getattr(module, "Source", None)
        if source_cls:
            plugins.append(source_cls())
    return sorted(plugins, key=lambda source: preferred_order.get(source.name, 100))


def collect_domains(topic: str, count: int) -> CollectionResult:
    keywords = [part.strip().lower() for part in topic.replace(",", " ").split() if part.strip()]
    raw: list[tuple[str, str]] = []
    for source in load_sources():
        cleaned_count = len(clean_domains([item for item, _ in raw]))
        remaining = max(0, count - cleaned_count)
        if remaining <= 0:
            break
        try:
            found = source.collect(keywords, remaining)
        except Exception:
            found = []
        raw.extend((item, source.name) for item in found)
    cleaned = clean_domains([item for item, _ in raw])
    source_by_domain = {}
    for item, source in raw:
        for domain in clean_domains([item]):
            source_by_domain.setdefault(domain, source)
    selected = cleaned[:count]
    created_at = now_iso()
    with connect() as conn:
        for domain in selected:
            conn.execute(
                """
                INSERT INTO domains (domain, category, source, rating, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    category=excluded.category,
                    source=COALESCE(excluded.source, domains.source),
                    rating=CASE WHEN excluded.rating > 0 THEN excluded.rating ELSE domains.rating END
                """,
                (domain, categorize(domain, keywords[0] if keywords else None), source_by_domain.get(domain, "collector"), rate_domain(domain), created_at),
            )
    return CollectionResult(count, len(raw), len(selected), selected)
