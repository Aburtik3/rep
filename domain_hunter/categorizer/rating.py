from __future__ import annotations

from datetime import date, datetime

PREMIUM_TLDS = {"com", "net", "org", "io", "ai", "co"}
POPULAR_WORDS = {"pay", "coin", "host", "cloud", "shop", "ai", "data", "bank", "travel", "health"}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def rate_domain(domain: str, creation_date: str | None = None) -> int:
    name, _, tld = domain.partition(".")
    score = 50
    if len(name) <= 6:
        score += 15
    elif len(name) <= 10:
        score += 10
    elif len(name) > 18:
        score -= 10
    if "-" in name:
        score -= 10
    if any(ch.isdigit() for ch in name):
        score -= 8
    if tld in PREMIUM_TLDS:
        score += 10
    if any(word in name for word in POPULAR_WORDS):
        score += 8
    created = parse_date(creation_date)
    if created:
        age = max(0, (date.today() - created).days // 365)
        score += min(age * 2, 20)
    return max(0, min(100, score))
