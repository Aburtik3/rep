from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from domain_hunter.backend.services import domain_age_years, recheck, upcoming
from domain_hunter.categorizer.categorizer import categorize
from domain_hunter.categorizer.rating import rate_domain
from domain_hunter.cleaner.domain_cleaner import normalize_domain
from domain_hunter.collector.collector import collect_domains
from domain_hunter.config.settings import BASE_DIR, CATEGORIES, CATEGORY_LABELS_RU, MONTH_LABELS_RU, MONTHS, STATUSES, STATUS_LABELS_RU
from domain_hunter.database.db import connect, delete_domain, init_db, query_domains, row_to_dict, stats, upsert_domain
from domain_hunter.export.exporter import export_domains

app = FastAPI(title="DOMAIN HUNTER PRO")
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)
templates.env.globals["age_years"] = domain_age_years
templates.env.globals["category_label"] = lambda value: CATEGORY_LABELS_RU.get(value, value or "—")
templates.env.globals["status_label"] = lambda value: STATUS_LABELS_RU.get(value, value or "неизвестно")


def parse_optional_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    today = date.today()
    data = {
        "request": request,
        "stats": stats(),
        "categories": CATEGORIES,
        "today": today,
        "today_domains": upcoming(0, today),
        "tomorrow_domains": [r for r in upcoming(1, today + timedelta(days=1)) if r.get("expiration_date", "")[:10] == (today + timedelta(days=1)).isoformat()],
        "week_domains": upcoming(7, today),
        "month_domains": upcoming(30, today),
        "top_domains": query_domains({"rating_min": 80}, limit=10),
        "favorites": query_domains({"q": ""}, limit=10),
        "latest": query_domains(limit=10),
        "notes": [r for r in query_domains(limit=100) if r.get("notes")][:10],
    }
    data["favorites"] = [r for r in query_domains(limit=100) if r.get("interest") in {"star", "fire"}][:10]
    return templates.TemplateResponse(request=request, name="dashboard.html", context=data)


@app.get("/domains", response_class=HTMLResponse)
def domains_page(request: Request, q: str = "", category: str = "", status: str = "", month: str = "", rating_min: str = ""):
    month_value = parse_optional_int(month)
    rating_value = parse_optional_int(rating_min)
    filters = {k: v for k, v in {"q": q, "category": category, "status": status, "month": month_value, "rating_min": rating_value}.items() if v not in (None, "")}
    return templates.TemplateResponse(
        request=request,
        name="domains.html",
        context={"domains": query_domains(filters, limit=500), "filters": filters, "categories": CATEGORIES, "statuses": STATUSES, "months": MONTHS, "month_labels": MONTH_LABELS_RU},
    )


@app.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request, year: int | None = None, month: int | None = None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    rows = query_domains({"month": month}, limit=10000)
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("expiration_date") and row["expiration_date"].startswith(f"{year}-{month:02d}"):
            by_day.setdefault(row["expiration_date"][:10], []).append(row)
    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={"year": year, "month": month, "month_name": MONTH_LABELS_RU[month - 1], "by_day": by_day},
    )


@app.get("/domains/{domain_id}", response_class=HTMLResponse)
def domain_detail(request: Request, domain_id: int):
    with connect() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM domains WHERE id = ?", (domain_id,)).fetchone())
        history = [dict(r) for r in conn.execute("SELECT * FROM check_history WHERE domain_id = ? ORDER BY checked_at DESC", (domain_id,)).fetchall()]
    if not row:
        raise HTTPException(404, "Domain not found")
    return templates.TemplateResponse(request=request, name="domain_detail.html", context={"domain": row, "history": history})


@app.post("/domains/{domain_id}/notes")
def update_notes(domain_id: int, notes: str = Form(""), interest: str = Form("")):
    with connect() as conn:
        conn.execute("UPDATE domains SET notes = ?, interest = ? WHERE id = ?", (notes, interest, domain_id))
    return RedirectResponse(f"/domains/{domain_id}", status_code=303)




@app.post("/domains/{domain_id}/delete")
def delete_domain_route(domain_id: int):
    delete_domain(domain_id)
    return RedirectResponse("/domains", status_code=303)


@app.post("/collect")
def collect(topic: str = Form(...), count: int = Form(100)):
    collect_domains(topic, count)
    return RedirectResponse("/domains", status_code=303)


@app.post("/manual")
def manual_add(domain: str = Form(...), category: str = Form("other"), source: str = Form("manual"), expiration_date: str = Form("")):
    normalized = normalize_domain(domain)
    if not normalized:
        raise HTTPException(400, "Invalid domain")
    upsert_domain({"domain": normalized, "category": category or categorize(normalized), "source": source, "expiration_date": expiration_date or None, "rating": rate_domain(normalized)})
    return RedirectResponse("/domains", status_code=303)


@app.post("/recheck")
def recheck_route(group: str = Form("all")):
    filters: dict[str, Any] = {}
    g = group.lower()
    if g in CATEGORIES:
        filters["category"] = g
    elif g in {"pendingdelete", "pending_delete"}:
        filters["status"] = "pendingDelete"
    elif g in [m.lower() for m in MONTHS]:
        filters["month"] = [m.lower() for m in MONTHS].index(g) + 1
    recheck(filters)
    return RedirectResponse("/domains", status_code=303)


@app.get("/export/{fmt}")
def export_route(fmt: str, category: str = "", status: str = "", month: str = "", q: str = ""):
    filters = {k: v for k, v in {"category": category, "status": status, "month": parse_optional_int(month), "q": q}.items() if v not in (None, "")}
    path = export_domains(fmt, filters)
    return FileResponse(path, filename=path.name)


@app.get("/api/domains")
def api_domains(q: str = "", category: str = "", status: str = "", limit: int = Query(100, le=1000)):
    return query_domains({k: v for k, v in {"q": q, "category": category, "status": status}.items() if v}, limit=limit)


@app.get("/api/stats")
def api_stats():
    return stats()
