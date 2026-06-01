from __future__ import annotations

import shutil
from pathlib import Path

from domain_hunter.config.settings import CATEGORIES, MONTHS, RESULTS_DIR
from domain_hunter.database.db import query_domains

STATUS_DIRS = {
    "active": "active",
    "pendingDelete": "pending_delete",
    "redemptionPeriod": "redemption",
    "inactive": "inactive",
    "clientHold": "inactive",
}


def rebuild_results(results_dir: Path = RESULTS_DIR) -> None:
    if results_dir.exists():
        shutil.rmtree(results_dir)
    for month in MONTHS:
        for status_dir in sorted(set(STATUS_DIRS.values())):
            (results_dir / month / status_dir).mkdir(parents=True, exist_ok=True)
    for row in query_domains(limit=1_000_000):
        if not row.get("expiration_date"):
            continue
        month = MONTHS[int(row["expiration_date"][5:7]) - 1]
        category = row.get("category") if row.get("category") in CATEGORIES else "other"
        status_dir = STATUS_DIRS.get(row.get("status"), "inactive")
        target = results_dir / month / status_dir / f"{category}.txt"
        with target.open("a", encoding="utf-8") as fh:
            fh.write(row["domain"] + "\n")
