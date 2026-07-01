import os

SECRET_KEY = os.getenv("PROTRACK_SECRET_KEY", "dev-only-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

# Demo design-team users are for local development only; keep disabled for production imports.
ENABLE_DEMO_SEED = os.getenv("PROTRACK_ENABLE_DEMO_SEED", "").lower() in ("1", "true", "yes")
