from __future__ import annotations

from domain_hunter.config.settings import CATEGORIES

KEYWORDS = {
    "crypto": ["coin", "crypto", "chain", "ledger", "wallet", "token", "bitcoin", "block"],
    "finance": ["bank", "pay", "wise", "capital", "loan", "fund", "fin", "money", "invest"],
    "hosting": ["host", "server", "vps", "domain", "dns"],
    "vpn": ["vpn", "proxy", "privacy"],
    "ai": ["ai", "gpt", "bot", "neural", "model", "ml"],
    "education": ["edu", "learn", "course", "school", "academy", "udemy"],
    "health": ["health", "med", "care", "clinic", "doctor"],
    "shopping": ["shop", "store", "cart", "market", "buy"],
    "sport": ["sport", "fit", "gym", "run", "game"],
    "travel": ["travel", "trip", "hotel", "flight", "tour"],
    "business": ["business", "corp", "company", "crm", "office"],
    "email": ["mail", "email", "smtp", "inbox"],
    "cloud": ["cloud", "saas", "compute", "storage"],
    "marketing": ["seo", "ads", "marketing", "brand", "lead"],
    "social": ["social", "chat", "community", "media"],
}


def categorize(domain: str, hint: str | None = None) -> str:
    text = f"{domain} {hint or ''}".lower()
    for category, words in KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return hint if hint in CATEGORIES else "other"
