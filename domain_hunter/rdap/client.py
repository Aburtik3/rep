from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

BOOTSTRAP = "https://data.iana.org/rdap/dns.json"


def _event(events: list[dict[str, Any]], names: set[str]) -> str | None:
    for item in events or []:
        if item.get("eventAction") in names:
            return item.get("eventDate")
    return None


def _registrar(data: dict[str, Any]) -> str | None:
    for entity in data.get("entities", []) or []:
        roles = entity.get("roles", []) or []
        if "registrar" in roles:
            vcard = entity.get("vcardArray", [])
            if len(vcard) > 1:
                for field in vcard[1]:
                    if field and field[0] == "fn":
                        return field[3]
            return entity.get("handle")
    return None


def _status(statuses: list[str] | None) -> str:
    text = " ".join(statuses or []).lower()
    if "pendingdelete" in text or "pending delete" in text:
        return "pendingDelete"
    if "redemption" in text:
        return "redemptionPeriod"
    if "client hold" in text or "clienthold" in text:
        return "clientHold"
    if "inactive" in text:
        return "inactive"
    return "active" if statuses else "inactive"


class RDAPClient:
    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self._bootstrap: dict[str, str] | None = None

    def _servers(self) -> dict[str, str]:
        if self._bootstrap is not None:
            return self._bootstrap
        data = requests.get(BOOTSTRAP, timeout=self.timeout).json()
        servers: dict[str, str] = {}
        for services in data.get("services", []):
            tlds, urls = services
            if urls:
                for tld in tlds:
                    servers[tld.lower()] = urls[0].rstrip("/")
        self._bootstrap = servers
        return servers

    def lookup(self, domain: str) -> dict[str, Any]:
        tld = domain.rsplit(".", 1)[-1].lower()
        base = self._servers().get(tld, f"https://rdap.org/domain")
        url = f"{base}/domain/{domain}"
        response = requests.get(url, timeout=self.timeout, headers={"Accept": "application/rdap+json, application/json"})
        response.raise_for_status()
        data = response.json()
        events = data.get("events", [])
        return {
            "domain": domain,
            "registrar": _registrar(data),
            "status": _status(data.get("status")),
            "creation_date": _event(events, {"registration"}),
            "updated_date": _event(events, {"last changed", "last update of RDAP database"}),
            "expiration_date": _event(events, {"expiration"}),
            "last_check": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "raw": response.text[:5000],
        }
