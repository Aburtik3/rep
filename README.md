# DOMAIN HUNTER PRO

Browser dashboard and SQLite CRM for collecting, cleaning, categorizing, checking, monitoring, and exporting domains.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn domain_hunter.backend.app:app --host 127.0.0.1 --port 5000
```

Open http://127.0.0.1:5000.

## CLI examples

```bash
python -m domain_hunter.backend.cli collect crypto 1000
python -m domain_hunter.backend.cli check all
python -m domain_hunter.backend.cli export csv
```

The system does not run scheduled automatic checks; collection and rechecks are user-triggered only.
