from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from domain_hunter.config.settings import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'other',
    source TEXT,
    registrar TEXT,
    status TEXT,
    creation_date TEXT,
    updated_date TEXT,
    expiration_date TEXT,
    last_check TEXT,
    rating INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    interest TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS check_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL,
    checked_at TEXT NOT NULL,
    registrar TEXT,
    status TEXT,
    creation_date TEXT,
    updated_date TEXT,
    expiration_date TEXT,
    raw TEXT,
    FOREIGN KEY(domain_id) REFERENCES domains(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_domains_category ON domains(category);
CREATE INDEX IF NOT EXISTS idx_domains_status ON domains(status);
CREATE INDEX IF NOT EXISTS idx_domains_expiration ON domains(expiration_date);
CREATE INDEX IF NOT EXISTS idx_domains_rating ON domains(rating);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def connect(path: Path = DB_PATH):
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def upsert_domain(data: dict[str, Any]) -> int:
    created_at = data.get("created_at") or now_iso()
    payload = {
        "domain": data["domain"],
        "category": data.get("category") or "other",
        "source": data.get("source") or "manual",
        "registrar": data.get("registrar"),
        "status": data.get("status"),
        "creation_date": data.get("creation_date"),
        "updated_date": data.get("updated_date"),
        "expiration_date": data.get("expiration_date"),
        "last_check": data.get("last_check"),
        "rating": int(data.get("rating") or 0),
        "notes": data.get("notes") or "",
        "interest": data.get("interest") or "",
        "created_at": created_at,
    }
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO domains (domain, category, source, registrar, status, creation_date,
                updated_date, expiration_date, last_check, rating, notes, interest, created_at)
            VALUES (:domain, :category, :source, :registrar, :status, :creation_date,
                :updated_date, :expiration_date, :last_check, :rating, :notes, :interest, :created_at)
            ON CONFLICT(domain) DO UPDATE SET
                category=excluded.category,
                source=COALESCE(excluded.source, domains.source),
                registrar=COALESCE(excluded.registrar, domains.registrar),
                status=COALESCE(excluded.status, domains.status),
                creation_date=COALESCE(excluded.creation_date, domains.creation_date),
                updated_date=COALESCE(excluded.updated_date, domains.updated_date),
                expiration_date=COALESCE(excluded.expiration_date, domains.expiration_date),
                last_check=COALESCE(excluded.last_check, domains.last_check),
                rating=CASE WHEN excluded.rating > 0 THEN excluded.rating ELSE domains.rating END
            """,
            payload,
        )
        row = conn.execute("SELECT id FROM domains WHERE domain = ?", (payload["domain"],)).fetchone()
        return int(row["id"] if row else cur.lastrowid)


def query_domains(filters: dict[str, Any] | None = None, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    filters = filters or {}
    clauses: list[str] = []
    params: list[Any] = []
    if q := filters.get("q"):
        clauses.append("(domain LIKE ? OR notes LIKE ? OR registrar LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    for key in ["category", "status", "registrar"]:
        if filters.get(key):
            clauses.append(f"{key} = ?")
            params.append(filters[key])
    if filters.get("month"):
        clauses.append("strftime('%m', expiration_date) = ?")
        params.append(f"{int(filters['month']):02d}")
    if filters.get("date"):
        clauses.append("date(expiration_date) = date(?)")
        params.append(filters["date"])
    if filters.get("rating_min") is not None:
        clauses.append("rating >= ?")
        params.append(int(filters["rating_min"]))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM domains{where} ORDER BY date(expiration_date) IS NULL, date(expiration_date), rating DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]


def stats() -> dict[str, int]:
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM domains").fetchone()["c"]
        rows = conn.execute("SELECT category, COUNT(*) c FROM domains GROUP BY category").fetchall()
        result = {r["category"]: r["c"] for r in rows}
        result["total"] = total
        return result


def add_history(domain_id: int, data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO check_history (domain_id, checked_at, registrar, status, creation_date, updated_date, expiration_date, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (domain_id, now_iso(), data.get("registrar"), data.get("status"), data.get("creation_date"), data.get("updated_date"), data.get("expiration_date"), data.get("raw")),
        )
