from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "domains.sqlite3"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
CATEGORIES = [
    "finance", "crypto", "hosting", "vpn", "ai", "education", "health",
    "shopping", "sport", "travel", "business", "email", "cloud", "marketing",
    "social", "other",
]
STATUSES = ["active", "inactive", "clientHold", "redemptionPeriod", "pendingDelete"]
TECHNICAL_LABELS = {"www", "api", "mail", "cdn", "blog", "dev", "staging", "test", "app", "m"}
