from domain_hunter.categorizer.categorizer import categorize
from domain_hunter.categorizer.rating import rate_domain
from domain_hunter.cleaner.domain_cleaner import clean_domains, normalize_domain
from domain_hunter.export.exporter import export_domains
from domain_hunter.database.db import upsert_domain


def test_cleaner_strips_subdomains_and_deduplicates():
    assert clean_domains(["https://www.Example.com/a", "api.example.com", "bad value"]) == ["example.com"]


def test_categorizer_and_rating():
    assert categorize("coinbase.com") == "crypto"
    assert categorize("hostinger.com") == "hosting"
    assert 0 <= rate_domain("coin.com", "2010-01-01") <= 100


def test_export_txt(tmp_path):
    upsert_domain({"domain": "pytest-example.com", "category": "other", "source": "test", "rating": 42})
    path = export_domains("txt", {"q": "pytest-example"}, tmp_path)
    assert path.read_text(encoding="utf-8").strip() == "pytest-example.com"
