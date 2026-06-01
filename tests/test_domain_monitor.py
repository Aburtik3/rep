import datetime as dt
import unittest

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
        self.assertEqual(domain_monitor.date_to_text(domain_monitor.parse_whois_expiry(text)), "2026-10-26T21:00:00Z")

    def test_classify_thresholds(self):
        now = dt.datetime.now(dt.timezone.utc)
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=3), False)[0], "critical")
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=20), False)[0], "danger")
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=90), False)[0], "warning")
        self.assertEqual(domain_monitor.classify(now + dt.timedelta(days=220), False)[0], "safe")


if __name__ == "__main__":
    unittest.main()
