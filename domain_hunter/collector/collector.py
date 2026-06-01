from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass

import domain_hunter.sources as sources_pkg
from domain_hunter.categorizer.categorizer import categorize
from domain_hunter.categorizer.rating import rate_domain
from domain_hunter.cleaner.domain_cleaner import clean_domains
from domain_hunter.database.db import upsert_domain


@dataclass
class CollectionResult:
    requested: int
    collected_raw: int
    saved: int
    domains: list[str]


def load_sources():
    plugins = []
    for module_info in pkgutil.iter_modules(sources_pkg.__path__):
        if module_info.name in {"base"} or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"domain_hunter.sources.{module_info.name}")
        source_cls = getattr(module, "Source", None)
        if source_cls:
            plugins.append(source_cls())
    return plugins


def collect_domains(topic: str, count: int) -> CollectionResult:
    keywords = [part.strip().lower() for part in topic.replace(",", " ").split() if part.strip()]
    raw: list[tuple[str, str]] = []
    remaining = count
    for source in load_sources():
        if remaining <= 0:
            break
        found = source.collect(keywords, remaining)
        raw.extend((item, source.name) for item in found)
        remaining = max(0, count - len({item for item, _ in raw}))
    cleaned = clean_domains([item for item, _ in raw])
    source_by_domain = {}
    for item, source in raw:
        for domain in clean_domains([item]):
            source_by_domain.setdefault(domain, source)
    saved = 0
    for domain in cleaned[:count]:
        category = categorize(domain, keywords[0] if keywords else None)
        upsert_domain({"domain": domain, "category": category, "source": source_by_domain.get(domain, "collector"), "rating": rate_domain(domain)})
        saved += 1
    return CollectionResult(count, len(raw), saved, cleaned[:count])
