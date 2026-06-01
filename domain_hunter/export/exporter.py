from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

try:
    from openpyxl import Workbook
except ModuleNotFoundError:  # XLSX export reports a clear error if optional dependency is absent.
    Workbook = None

from domain_hunter.database.db import query_domains

COLUMNS = ["domain", "category", "source", "registrar", "status", "creation_date", "updated_date", "expiration_date", "last_check", "rating", "notes", "interest"]


def export_domains(fmt: str, filters: dict | None = None, output_dir: Path = Path("domain_hunter/results/exports")) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = query_domains(filters or {}, limit=1_000_000)
    fmt = fmt.lower()
    target = output_dir / f"domains.{fmt}"
    if fmt == "txt":
        target.write_text("\n".join(row["domain"] for row in rows), encoding="utf-8")
    elif fmt == "csv":
        with target.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows({key: row.get(key) for key in COLUMNS} for row in rows)
    elif fmt == "xlsx":
        if Workbook is None:
            raise RuntimeError("openpyxl is required for XLSX export")
        wb = Workbook()
        ws = wb.active
        ws.title = "Domains"
        ws.append(COLUMNS)
        for row in rows:
            ws.append([row.get(key) for key in COLUMNS])
        wb.save(target)
    else:
        raise ValueError("Format must be txt, csv, or xlsx")
    return target
