import datetime as dt
import unittest
from unittest import mock

import domain_monitor


class DomainMonitorTests(unittest.TestCase):
    def test_normalize_idn(self):
        self.assertEqual(domain_monitor.normalize_domain("https://пример.рф/path"), ("xn--e1afmkfd.xn--p1ai", "пример.рф"))

    def test_parse_russian_paid_until(self):
        text = """
        Зарегистрирован:             2007-10-26T20:00:00Z
        Оплачен до:                  2026-10-26T21:00:00Z
        Дата окончания периода\nпреимущественного продления: 2026-11-27
        """
        parsed = domain_monitor.parse_whois_expiry(text)
        self.assertEqual(domain_monitor.date_to_text(parsed), "2026-10-26T21:00:00Z")
        self.assertEqual(domain_monitor.date_part(parsed), "2026-10-26")
        self.assertEqual(domain_monitor.time_part_utc(parsed), "21:00:00")

    def test_check_rdap_timeout_is_source_error(self):
        with mock.patch("domain_monitor.rdap_base_for_tld", side_effect=TimeoutError("The read operation timed out")):
            result = domain_monitor.check_rdap("example.test")
        self.assertEqual(result.source, "RDAP")
        self.assertIn("read operation timed out", result.error)

    def test_combine_results_exposes_date_and_hour(self):
        result = domain_monitor.combine_results(
            "example.com",
            "example.com",
            [domain_monitor.SourceResult(source="test", expires_at="2026-10-26T21:00:00Z", available=False)],
        )
        self.assertEqual(result.expires_date, "2026-10-26")
        self.assertEqual(result.expires_time_utc, "21:00:00")

    def test_classify_thresholds(self):
        now = dt.datetime.now(dt.timezone.utc)
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=3), False)[0], "critical")
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=20), False)[0], "danger")
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=90), False)[0], "warning")
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=220), False)[0], "safe")


if __name__ == "__main__":
    unittest.main()
