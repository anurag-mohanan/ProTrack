import os
from pathlib import Path

SECRET_KEY = os.getenv("PROTRACK_SECRET_KEY", "dev-only-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = Path(os.getenv("PROTRACK_UPLOAD_DIR", BASE_DIR / "uploads"))
COMPANY_LOGO_DIR = UPLOAD_DIR / "company"

# Demo design-team users are for local development only; keep disabled for production imports.
ENABLE_DEMO_SEED = os.getenv("PROTRACK_ENABLE_DEMO_SEED", "").lower() in ("1", "true", "yes")
