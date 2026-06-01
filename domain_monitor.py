#!/usr/bin/env python3
"""Small browser-based domain expiration monitor.

Runs a local HTTP server with an HTML UI. The backend checks domains through
free, captcha-less public protocols: RDAP first, then classic WHOIS fallback.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import http.server
import json
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

RDAP_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
USER_AGENT = "domain-expiration-monitor/1.0 (+local admin tool)"
REQUEST_TIMEOUT = 12
WHOIS_TIMEOUT = 12
MAX_DOMAINS_PER_REQUEST = 2000
MAX_WORKERS = 24

# Direct RDAP bases for common zones. This keeps checks useful even when the
# IANA bootstrap endpoint is slow or temporarily unavailable. Unknown TLDs still
# try the IANA bootstrap below.
RDAP_SERVERS: dict[str, str] = {
    "com": "https://rdap.verisign.com/com/v1/",
    "net": "https://rdap.verisign.com/net/v1/",
    "org": "https://rdap.publicinterestregistry.org/rdap/",
    "info": "https://rdap.identitydigital.services/rdap/",
    "biz": "https://rdap.identitydigital.services/rdap/",
    "ru": "https://rdap.tcinet.ru/",
    "рф": "https://rdap.tcinet.ru/",
    "xn--p1ai": "https://rdap.tcinet.ru/",
    "su": "https://rdap.tcinet.ru/",
}

# Helpful direct WHOIS servers for popular zones and zones where RDAP can be
# incomplete or unavailable. Unknown TLDs fall back to whois.iana.org referral.
WHOIS_SERVERS: dict[str, str] = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "info": "whois.afilias.net",
    "biz": "whois.biz",
    "ru": "whois.tcinet.ru",
    "рф": "whois.tcinet.ru",
    "xn--p1ai": "whois.tcinet.ru",
    "su": "whois.tcinet.ru",
    "ua": "whois.ua",
    "by": "whois.cctld.by",
    "kz": "whois.nic.kz",
    "io": "whois.nic.io",
    "co": "whois.nic.co",
    "me": "whois.nic.me",
    "tv": "whois.nic.tv",
    "cc": "ccwhois.verisign-grs.com",
}

EXPIRY_KEYS = (
    "registry expiry date",
    "registrar registration expiration date",
    "expiration date",
    "expiry date",
    "expires on",
    "expires",
    "expire",
    "paid-till",
    "paid till",
    "paid until",
    "paid through",
    "renewal date",
    "valid until",
    "validity",
    "оплачен до",
)

FREE_MARKERS = (
    "no match for",
    "not found",
    "no entries found",
    "no data found",
    "domain not found",
    "object does not exist",
    "status: free",
    "available for registration",
    "is available",
    "домен не найден",
    "domain name has not been registered",
)

STATUS_LABELS = {
    "safe": "ОК: больше 6 месяцев",
    "warning": "Скоро: 1–6 месяцев",
    "danger": "Срочно: 1 неделя–1 месяц",
    "critical": "Критично: свободен или ≤ 7 дней",
    "unknown": "Не удалось проверить",
}

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_rdap_bootstrap: list[dict[str, Any]] | None = None


@dataclass
class SourceResult:
    source: str
    expires_at: str | None = None
    available: bool | None = None
    error: str | None = None
    raw_hint: str | None = None


@dataclass
class DomainResult:
    domain: str
    unicode_domain: str
    status: str
    status_label: str
    expires_at: str | None
    expires_date: str | None
    expires_time_utc: str | None
    days_left: int | None
    available: bool | None
    confidence: str
    sources: list[SourceResult]
    notes: list[str]


def normalize_domain(value: str) -> tuple[str, str] | None:
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/", 1)[0].split(":", 1)[0].strip().strip(".")
    if not value or "." not in value:
        return None
    try:
        ascii_domain = value.encode("idna").decode("ascii")
        unicode_domain = ascii_domain.encode("ascii").decode("idna")
    except UnicodeError:
        return None
    if not re.fullmatch(r"[a-z0-9.-]+", ascii_domain) or ".." in ascii_domain:
        return None
    return ascii_domain, unicode_domain


def parse_datetime(value: str) -> dt.datetime | None:
    value = value.strip().strip(".;")
    value = re.sub(r"\s+\(.*?\)$", "", value)
    formats = (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d.%m.%Y",
        "%Y.%m.%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    )
    iso_value = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(iso_value)
        return parsed.astimezone(dt.timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        pass
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    match = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    if match:
        return parse_datetime(match.group(1))
    return None


def date_to_text(value: dt.datetime | None) -> str | None:
    if not value:
        return None
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def date_part(value: dt.datetime | None) -> str | None:
    if not value:
        return None
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")


def time_part_utc(value: dt.datetime | None) -> str | None:
    if not value:
        return None
    return value.astimezone(dt.timezone.utc).strftime("%H:%M:%S")


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def rdap_bootstrap() -> list[dict[str, Any]]:
    global _rdap_bootstrap
    if _rdap_bootstrap is None:
        data = fetch_json(RDAP_BOOTSTRAP_URL)
        _rdap_bootstrap = data.get("services", [])
    return _rdap_bootstrap


def rdap_base_for_tld(tld: str) -> str | None:
    tld = tld.lower().lstrip(".")
    if tld in RDAP_SERVERS:
        return RDAP_SERVERS[tld]
    for service in rdap_bootstrap():
        tlds, urls = service[0], service[1]
        if tld in [item.lower() for item in tlds] and urls:
            return urls[0]
    return None


def check_rdap(domain: str) -> SourceResult:
    tld = domain.rsplit(".", 1)[-1]
    try:
        base = rdap_base_for_tld(tld)
    except Exception as exc:  # noqa: BLE001 - RDAP bootstrap/network errors must not fail the whole batch.
        return SourceResult(source="RDAP", error=f"ошибка RDAP bootstrap: {exc}")
    if not base:
        return SourceResult(source="RDAP", error="RDAP для зоны не найден")
    url = urllib.parse.urljoin(base.rstrip("/") + "/", "domain/" + urllib.parse.quote(domain))
    try:
        data = fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return SourceResult(source="RDAP", available=True, raw_hint="RDAP 404")
        return SourceResult(source="RDAP", error=f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001 - show concise source-specific error in UI.
        return SourceResult(source="RDAP", error=str(exc))

    expiry: dt.datetime | None = None
    for event in data.get("events", []):
        action = str(event.get("eventAction", "")).lower()
        if "expir" in action:
            candidate = parse_datetime(str(event.get("eventDate", "")))
            if candidate and (expiry is None or candidate > expiry):
                expiry = candidate
    return SourceResult(source="RDAP", expires_at=date_to_text(expiry), available=False if expiry else None)


def whois_query(server: str, query: str) -> str:
    with socket.create_connection((server, 43), timeout=WHOIS_TIMEOUT) as sock:
        sock.settimeout(WHOIS_TIMEOUT)
        sock.sendall((query + "\r\n").encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if sum(len(chunk) for chunk in chunks) > 256_000:
                break
    return b"".join(chunks).decode("utf-8", errors="replace")


def iana_whois_server(tld: str) -> str | None:
    try:
        text = whois_query("whois.iana.org", tld)
    except Exception:
        return None
    match = re.search(r"(?im)^whois:\s*(\S+)", text)
    return match.group(1).strip() if match else None


def parse_whois_expiry(text: str) -> dt.datetime | None:
    best: dt.datetime | None = None
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = re.sub(r"\s+", " ", key.strip().lower())
        if any(token in normalized_key for token in EXPIRY_KEYS):
            parsed = parse_datetime(value)
            if parsed and (best is None or parsed > best):
                best = parsed
    return best


def check_whois(domain: str) -> SourceResult:
    tld = domain.rsplit(".", 1)[-1]
    server = WHOIS_SERVERS.get(tld) or iana_whois_server(tld)
    if not server:
        return SourceResult(source="WHOIS", error="WHOIS сервер для зоны не найден")
    try:
        query = "=" + domain if server == "whois.verisign-grs.com" else domain
        text = whois_query(server, query)
        lower = text.lower()
        if any(marker in lower for marker in FREE_MARKERS):
            return SourceResult(source=f"WHOIS ({server})", available=True)
        expiry = parse_whois_expiry(text)
        return SourceResult(source=f"WHOIS ({server})", expires_at=date_to_text(expiry), available=False if expiry else None)
    except Exception as exc:  # noqa: BLE001 - show concise source-specific error in UI.
        return SourceResult(source=f"WHOIS ({server})", error=str(exc))


def classify(expiry: dt.datetime | None, available: bool | None) -> tuple[str, int | None]:
    if available is True:
        return "critical", None
    if not expiry:
        return "unknown", None
    today = dt.datetime.now(dt.timezone.utc)
    days_left = (expiry - today).days
    if days_left <= 7:
        return "critical", days_left
    if days_left <= 30:
        return "danger", days_left
    if days_left <= 183:
        return "warning", days_left
    return "safe", days_left


def combine_results(domain: str, unicode_domain: str, sources: list[SourceResult]) -> DomainResult:
    expiries: list[dt.datetime] = []
    notes: list[str] = []
    available_votes = 0
    for source in sources:
        if source.available is True:
            available_votes += 1
        parsed = parse_datetime(source.expires_at) if source.expires_at else None
        if parsed:
            expiries.append(parsed)

    available = True if available_votes and not expiries else False if expiries else None
    expiry = min(expiries) if expiries else None
    if len(expiries) >= 2:
        spread = (max(expiries) - min(expiries)).days
        if spread > 2:
            notes.append(f"Источники расходятся по дате на {spread} дн.; показана ближайшая дата.")
    if available_votes and expiries:
        notes.append("Один источник считает домен свободным, другой нашёл дату — проверьте вручную.")
    if not expiries and not available_votes:
        notes.append("Нет достоверной даты: зона может скрывать expiry или временно не отвечать.")

    status, days_left = classify(expiry, available)
    successful = sum(1 for s in sources if s.expires_at or s.available is not None)
    confidence = "высокая" if successful >= 2 and not notes else "средняя" if successful else "низкая"
    return DomainResult(
        domain=domain,
        unicode_domain=unicode_domain,
        status=status,
        status_label=STATUS_LABELS[status],
        expires_at=date_to_text(expiry),
        expires_date=date_part(expiry),
        expires_time_utc=time_part_utc(expiry),
        days_left=days_left,
        available=available,
        confidence=confidence,
        sources=sources,
        notes=notes,
    )


def check_domain(domain: str, unicode_domain: str, force_refresh: bool = False) -> DomainResult:
    cache_key = domain
    now = time.time()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if not force_refresh and cached and now - cached[0] < 3600:
            return result_from_dict(cached[1])

    sources = [check_rdap(domain), check_whois(domain)]
    result = combine_results(domain, unicode_domain, sources)
    with _cache_lock:
        _cache[cache_key] = (now, result_to_dict(result))
    return result



def error_result(domain: str, unicode_domain: str, exc: Exception) -> DomainResult:
    source = SourceResult(source="internal", error=str(exc))
    return DomainResult(
        domain=domain,
        unicode_domain=unicode_domain,
        status="unknown",
        status_label=STATUS_LABELS["unknown"],
        expires_at=None,
        expires_date=None,
        expires_time_utc=None,
        days_left=None,
        available=None,
        confidence="низкая",
        sources=[source],
        notes=["Проверка этого домена упала по таймауту/ошибке, остальные домены не остановлены."],
    )

def result_to_dict(result: DomainResult) -> dict[str, Any]:
    data = asdict(result)
    data["sources"] = [asdict(source) for source in result.sources]
    return data


def result_from_dict(data: dict[str, Any]) -> DomainResult:
    copied = dict(data)
    copied["sources"] = [SourceResult(**source) for source in copied.get("sources", [])]
    return DomainResult(**copied)


INDEX_HTML = r"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Мониторинг сроков доменов</title>
  <style>
    :root { color-scheme: light; font-family: Inter, system-ui, -apple-system, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #f5f7fb; color: #172033; }
    header { background: linear-gradient(135deg, #172033, #3454d1); color: white; padding: 28px 36px; }
    main { padding: 24px 36px 48px; }
    textarea { width: 100%; min-height: 170px; border: 1px solid #c9d3e6; border-radius: 12px; padding: 14px; font: 15px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; box-sizing: border-box; }
    button { border: 0; border-radius: 10px; background: #3454d1; color: white; padding: 12px 18px; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    button.secondary { background: #eef3ff; color: #263a8b; }
    button.mini { padding: 7px 10px; font-size: 13px; }
    label.autoretry { display: inline-flex; align-items: center; gap: 6px; color: #5f6b7a; font-size: 14px; }
    .panel { background: white; border-radius: 16px; box-shadow: 0 10px 30px rgba(23, 32, 51, .08); padding: 20px; margin-bottom: 20px; }
    .controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 14px; }
    .legend { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
    .pill { border-radius: 999px; padding: 6px 10px; color: white; font-size: 13px; font-weight: 700; }
    .safe { background: #21a366; }
    .warning { background: #f4c430; color: #2b2400; }
    .danger { background: #ff1f1f; }
    .critical { background: #7f0000; }
    .unknown { background: #6b7280; }
    table { width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 14px; background: white; }
    th, td { padding: 11px 12px; border-bottom: 1px solid #e6ebf5; vertical-align: top; text-align: left; }
    th { position: sticky; top: 0; background: #eef3ff; z-index: 1; }
    tr.safe { background: #e9f8ef; }
    tr.warning { background: #fff6cf; }
    tr.danger { background: #ffe1e1; }
    tr.critical { background: #ffd1d1; color: #280000; }
    tr.unknown { background: #eef0f4; }
    .muted { color: #5f6b7a; font-size: 13px; }
    .nowrap { white-space: nowrap; }
    details { max-width: 520px; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
    .card { border-radius: 14px; color: white; padding: 14px; font-weight: 800; }
    .card small { display: block; opacity: .9; font-weight: 600; margin-top: 4px; }
  </style>
</head>
<body>
  <header>
    <h1>Мониторинг сроков продления доменов</h1>
    <p>Вставьте до 1000+ доменов списком. Проверка идёт через RDAP и WHOIS, без платных API и без капчи.</p>
  </header>
  <main>
    <section class="panel">
      <textarea id="domains" placeholder="example.com&#10;site.ru&#10;пример.рф"></textarea>
      <div class="controls">
        <button id="check">Проверить домены</button>
        <button id="retryFailed" class="secondary" disabled>Обновить неудачные</button>
        <button id="csv" disabled>Скачать CSV</button>
        <label class="autoretry"><input id="autoRetry" type="checkbox"> автообновлять неудачные каждые 5 минут</label>
        <span id="progress" class="muted">Ожидание списка доменов</span>
      </div>
      <div class="legend">
        <span class="pill safe">зелёный: &gt; 6 месяцев</span>
        <span class="pill warning">жёлтый: 1–6 месяцев</span>
        <span class="pill danger">ярко-красный: 1 неделя–1 месяц</span>
        <span class="pill critical">тёмно-красный: свободен или ≤ 7 дней</span>
      </div>
    </section>
    <section id="summary" class="summary" hidden></section>
    <section class="panel" style="padding:0; overflow:auto; max-height:70vh;">
      <table>
        <thead><tr><th>Домен</th><th>Дата окончания</th><th>Час окончания UTC</th><th>Оплачен до</th><th>Дней</th><th>Статус</th><th>Надёжность</th><th>Источники и заметки</th><th>Действие</th></tr></thead>
        <tbody id="rows"><tr><td colspan="9" class="muted">Результаты появятся здесь.</td></tr></tbody>
      </table>
    </section>
  </main>
<script>
const $ = (id) => document.getElementById(id);
let lastResults = [];
let autoRetryTimer = null;
function parseDomains(text) {
  return [...new Set(text.split(/[\s,;]+/).map(x => x.trim()).filter(Boolean))];
}
function fmtDate(value) {
  if (!value) return '—';
  return value.replace('T', ' ').replace('Z', ' UTC');
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function unknownResults() {
  return lastResults.filter(r => r.status === 'unknown');
}
function sortResults(results) {
  return results.sort((a, b) => {
    const ad = a.days_left ?? 999999;
    const bd = b.days_left ?? 999999;
    if (ad !== bd) return ad - bd;
    return a.domain.localeCompare(b.domain);
  });
}
async function checkDomains(domains, forceRefresh = false) {
  const response = await fetch('/api/check', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({domains, force_refresh: forceRefresh})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Ошибка проверки');
  return data.results;
}
function mergeResults(newResults) {
  const byDomain = new Map(lastResults.map(r => [r.domain, r]));
  for (const result of newResults) byDomain.set(result.domain, result);
  render(sortResults([...byDomain.values()]));
}
function updateControls() {
  const hasResults = lastResults.length > 0;
  const hasUnknown = unknownResults().length > 0;
  $('csv').disabled = !hasResults;
  $('retryFailed').disabled = !hasUnknown;
}
function render(results) {
  lastResults = results;
  updateControls();
  const counts = {safe:0, warning:0, danger:0, critical:0, unknown:0};
  for (const r of results) counts[r.status] = (counts[r.status] || 0) + 1;
  $('summary').hidden = false;
  $('summary').innerHTML = Object.entries({critical:'Критично', danger:'Срочно', warning:'Скоро', safe:'ОК', unknown:'Неизвестно'})
    .map(([key,label]) => `<div class="card ${key}">${counts[key] || 0}<small>${label}</small></div>`).join('');
  $('rows').innerHTML = results.map(r => {
    const sourceHtml = r.sources.map(s => `${escapeHtml(s.source)}: ${escapeHtml(s.expires_at || (s.available ? 'свободен' : s.error || 'нет даты'))}`).join('<br>');
    const notes = r.notes && r.notes.length ? `<div class="muted">${r.notes.map(escapeHtml).join('<br>')}</div>` : '';
    const retryHint = r.status === 'unknown' ? '<div class="muted">Можно обновить позже: публичный WHOIS/RDAP часто отвечает после паузы.</div>' : '';
    return `<tr class="${r.status}">
      <td><strong>${escapeHtml(r.unicode_domain)}</strong><div class="muted">${escapeHtml(r.domain)}</div></td>
      <td class="nowrap">${escapeHtml(r.expires_date || '—')}</td>
      <td class="nowrap"><strong>${escapeHtml(r.expires_time_utc || '—')}</strong></td>
      <td class="nowrap">${fmtDate(r.expires_at)}</td>
      <td class="nowrap">${r.days_left ?? '—'}</td>
      <td><span class="pill ${r.status}">${escapeHtml(r.status_label)}</span></td>
      <td>${escapeHtml(r.confidence)}</td>
      <td><details><summary>показать</summary>${sourceHtml}${notes}${retryHint}</details></td>
      <td><button class="mini secondary refresh-one" data-domain="${escapeHtml(r.domain)}">Обновить</button></td>
    </tr>`;
  }).join('') || '<tr><td colspan="9" class="muted">Нет результатов.</td></tr>';
}
async function runFullCheck() {
  const domains = parseDomains($('domains').value);
  if (!domains.length) { alert('Вставьте список доменов.'); return; }
  $('check').disabled = true;
  $('retryFailed').disabled = true;
  $('progress').textContent = `Проверяем ${domains.length} доменов...`;
  try {
    render(await checkDomains(domains));
    $('progress').textContent = `Готово: ${lastResults.length} доменов, не удалось проверить: ${unknownResults().length}, ${new Date().toLocaleString()}`;
  } catch (error) {
    $('progress').textContent = `Ошибка: ${error.message}`;
  } finally {
    $('check').disabled = false;
    updateControls();
  }
}
async function refreshDomains(domains, label = 'Обновляем') {
  if (!domains.length) return;
  $('retryFailed').disabled = true;
  $('progress').textContent = `${label}: ${domains.length}...`;
  try {
    mergeResults(await checkDomains(domains, true));
    $('progress').textContent = `Обновлено: ${domains.length}, осталось неудачных: ${unknownResults().length}, ${new Date().toLocaleString()}`;
  } catch (error) {
    $('progress').textContent = `Ошибка обновления: ${error.message}`;
  } finally {
    updateControls();
  }
}
$('check').addEventListener('click', runFullCheck);
$('retryFailed').addEventListener('click', () => refreshDomains(unknownResults().map(r => r.domain), 'Обновляем неудачные'));
$('rows').addEventListener('click', async (event) => {
  const button = event.target.closest('.refresh-one');
  if (!button) return;
  button.disabled = true;
  await refreshDomains([button.dataset.domain], `Обновляем ${button.dataset.domain}`);
  button.disabled = false;
});
$('autoRetry').addEventListener('change', () => {
  if (autoRetryTimer) {
    clearInterval(autoRetryTimer);
    autoRetryTimer = null;
  }
  if ($('autoRetry').checked) {
    autoRetryTimer = setInterval(() => {
      const domains = unknownResults().map(r => r.domain);
      if (domains.length) refreshDomains(domains, 'Автообновление неудачных');
    }, 5 * 60 * 1000);
    $('progress').textContent = 'Автообновление неудачных включено: каждые 5 минут.';
  }
});
$('csv').addEventListener('click', () => {
  const header = ['domain','expires_date','expires_time_utc','expires_at','days_left','status','confidence','notes'];
  const lines = [header.join(',')].concat(lastResults.map(r => header.map(k => '"' + String(k === 'notes' ? (r.notes||[]).join('; ') : (r[k] ?? '')).replace(/"/g, '""') + '"').join(',')));
  const blob = new Blob([lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'domains-expiration.csv';
  a.click();
  URL.revokeObjectURL(a.href);
});
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "DomainMonitor/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/api/check":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            raw_domains = payload.get("domains", [])
            force_refresh = bool(payload.get("force_refresh", False))
            if not isinstance(raw_domains, list):
                raise ValueError("domains должен быть списком")
            normalized: list[tuple[str, str]] = []
            seen: set[str] = set()
            for item in raw_domains[:MAX_DOMAINS_PER_REQUEST]:
                parsed = normalize_domain(str(item))
                if parsed and parsed[0] not in seen:
                    normalized.append(parsed)
                    seen.add(parsed[0])
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_domains = {
                    executor.submit(check_domain, domain, unicode_domain, force_refresh): (domain, unicode_domain)
                    for domain, unicode_domain in normalized
                }
                results = []
                for future in concurrent.futures.as_completed(future_domains):
                    domain, unicode_domain = future_domains[future]
                    try:
                        results.append(future.result())
                    except Exception as exc:  # noqa: BLE001 - one failed domain must not abort all results.
                        results.append(error_result(domain, unicode_domain, exc))
            results.sort(key=lambda r: (999999 if r.days_left is None else r.days_left, r.domain))
            self.send_json(200, {"results": [result_to_dict(result) for result in results]})
        except Exception as exc:  # noqa: BLE001 - return JSON error to UI.
            self.send_json(400, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local HTML domain expiration monitor")
    parser.add_argument("--host", default="127.0.0.1", help="host to bind, default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8080, help="port to bind, default: 8080")
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Open http://{args.host}:{args.port}/ in your browser", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
