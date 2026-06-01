from __future__ import annotations

import importlib
import importlib.util
import re
from urllib.parse import urlparse

tldextract = importlib.import_module("tldextract") if importlib.util.find_spec("tldextract") else None

from domain_hunter.config.settings import TECHNICAL_LABELS

DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$", re.I)


def normalize_domain(value: str) -> str | None:
    raw = (value or "").strip().lower()
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").strip(".")
    if not host or host.replace(".", "").isdigit():
        return None
    if tldextract is not None:
        ext = tldextract.extract(host)
        if not ext.domain or not ext.suffix:
            return None
        registered = f"{ext.domain}.{ext.suffix}".lower()
    else:
        parts = [p for p in host.split(".") if p]
        if len(parts) < 2:
            return None
        # Fallback covers common domains when tldextract data is unavailable.
        registered = ".".join(parts[-2:])
    return registered if is_valid_domain(registered) else None


def is_valid_domain(domain: str) -> bool:
    return bool(domain and len(domain) <= 253 and DOMAIN_RE.match(domain) and ".." not in domain)


def clean_domains(values: list[str] | set[str]) -> list[str]:
    cleaned = {d for v in values if (d := normalize_domain(v))}
    return sorted(cleaned)
