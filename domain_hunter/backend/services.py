from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from domain_hunter.categorizer.rating import parse_date, rate_domain
from domain_hunter.database.db import add_history, query_domains, upsert_domain
from domain_hunter.rdap.client import RDAPClient
from domain_hunter.results.sorter import rebuild_results


def upcoming(days: int, start: date | None = None) -> list[dict[str, Any]]:
    start = start or date.today()
    end = start + timedelta(days=days)
    rows = query_domains(limit=1_000_000)
    return [r for r in rows if r.get("expiration_date") and start <= parse_date(r["expiration_date"]) <= end]


def recheck(filters: dict[str, Any] | None = None, limit: int = 1000) -> dict[str, int]:
    client = RDAPClient()
    rows = query_domains(filters or {}, limit=limit)
    checked = failed = 0
    for row in rows:
        try:
            data = client.lookup(row["domain"])
            data["category"] = row["category"]
            data["source"] = row["source"]
            data["rating"] = rate_domain(row["domain"], data.get("creation_date"))
            domain_id = upsert_domain(data)
            add_history(domain_id, data)
            checked += 1
        except Exception:
            failed += 1
    rebuild_results()
    return {"checked": checked, "failed": failed}


def domain_age_years(creation_date: str | None) -> int | None:
    created = parse_date(creation_date)
    if not created:
        return None
    return max(0, (date.today() - created).days // 365)
