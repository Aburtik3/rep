from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

DOMAIN_RE = re.compile(r"(?:https?://|www\.)([^/'\"\s<>?#]+)", re.I)
HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)

BLOCKED_DOMAINS = {
    "github.com", "www.github.com", "producthunt.com", "www.producthunt.com", "google.com",
    "www.google.com", "duckduckgo.com", "www.duckduckgo.com", "bing.com", "www.bing.com",
    "twitter.com", "x.com", "facebook.com", "linkedin.com", "youtube.com", "youtu.be",
    "instagram.com", "reddit.com", "medium.com", "t.co", "bit.ly", "schema.org", "w3.org",
}


def fetch_text(url: str, timeout: int = 3) -> str:
    request = Request(url, headers={"User-Agent": "DomainHunterPro/1.0 (+manual domain research)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_json(url: str, timeout: int = 4) -> dict:
    return json.loads(fetch_text(url, timeout=timeout))


def _unwrap_url(value: str) -> str:
    value = unescape(value)
    parsed = urlparse(value)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(uddg) if uddg else value
    return value


def extract_domains_from_text(text: str) -> list[str]:
    domains: list[str] = []
    for match in DOMAIN_RE.finditer(text):
        domains.append(match.group(1))
    for href in HREF_RE.findall(text):
        url = _unwrap_url(href)
        parsed = urlparse(url if "://" in url else "https://" + url.lstrip("/"))
        if parsed.netloc:
            domains.append(parsed.netloc)
    return [domain for domain in domains if domain.lower().strip(".") not in BLOCKED_DOMAINS]
