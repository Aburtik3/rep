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


def test_template_responses_use_request_keyword():
    source = __import__("pathlib").Path("domain_hunter/backend/app.py").read_text(encoding="utf-8")
    assert 'TemplateResponse("dashboard.html"' not in source
    assert "TemplateResponse(request=request" in source


def test_catalog_source_returns_many_crypto_domains_fast():
    from domain_hunter.sources.catalog import Source

    domains = clean_domains(Source().collect(["crypto"], 50))
    assert len(domains) >= 50
    assert "coinbase.com" in domains
    assert "cryptohub.com" not in domains
    assert "hubcrypto.com" not in domains


def test_delete_domain_removes_row():
    from domain_hunter.database.db import connect, delete_domain

    domain_id = upsert_domain({"domain": "delete-me-example.com", "category": "other", "source": "test"})
    assert delete_domain(domain_id) is True
    with connect() as conn:
        assert conn.execute("SELECT id FROM domains WHERE id = ?", (domain_id,)).fetchone() is None


def test_empty_numeric_filters_are_not_typed_as_int_query_params():
    source = __import__("pathlib").Path("domain_hunter/backend/app.py").read_text(encoding="utf-8")
    assert 'month: str = ""' in source
    assert 'rating_min: str = ""' in source
    assert "parse_optional_int(month)" in source


def test_collect_crypto_saves_real_catalog_domains_without_generation(monkeypatch):
    from domain_hunter.collector import collector
    from domain_hunter.sources.catalog import Source

    monkeypatch.setattr(collector, "load_sources", lambda: [Source()])
    result = collector.collect_domains("crypto", 25)
    assert result.saved == 25
    assert len(result.domains) == 25
    assert all(not domain.startswith("cryptohub") for domain in result.domains)


def test_hosting_catalog_has_many_real_domains_and_russian_alias():
    from domain_hunter.sources.catalog import Source

    domains = clean_domains(Source().collect(["хостинги"], 100))
    assert len(domains) >= 60
    assert "hostinger.com" in domains
    assert all("хост" not in domain for domain in domains)


def test_compact_table_keeps_only_required_columns():
    source = __import__("pathlib").Path("domain_hunter/frontend/templates/_table.html").read_text(encoding="utf-8")
    assert "<th>Дата окончания</th>" in source
    assert "<th>Возраст</th>" in source
    assert "<th>Регистратор</th>" not in source
    assert "<th>Рейтинг</th>" not in source


def test_dashboard_has_only_requested_period_blocks():
    source = __import__("pathlib").Path("domain_hunter/frontend/templates/dashboard.html").read_text(encoding="utf-8")
    assert "Избранные" not in source
    assert "Последние добавленные" not in source
    assert "Полгода" in source
    assert "Год" in source
