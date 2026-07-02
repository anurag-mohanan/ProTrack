import os
from pathlib import Path

SECRET_KEY = os.getenv("PROTRACK_SECRET_KEY", "dev-only-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

APP_VERSION = os.getenv("PROTRACK_APP_VERSION", "1.0.0")
RELEASE_CANDIDATE = os.getenv("PROTRACK_RELEASE_CANDIDATE", "RC3")

FRONTEND_URL = os.getenv("PROTRACK_FRONTEND_URL", "https://protrack.prosohm.com")
API_PUBLIC_URL = os.getenv("PROTRACK_API_URL", "https://api.protrack.prosohm.com")

_default_cors = ",".join(
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        FRONTEND_URL,
    ]
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("PROTRACK_CORS_ORIGINS", _default_cors).split(",")
    if origin.strip()
]

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = Path(os.getenv("PROTRACK_UPLOAD_DIR", BASE_DIR / "uploads"))
COMPANY_LOGO_DIR = UPLOAD_DIR / "company"

# Demo design-team users are for local development only; keep disabled for production imports.
ENABLE_DEMO_SEED = os.getenv("PROTRACK_ENABLE_DEMO_SEED", "").lower() in ("1", "true", "yes")
