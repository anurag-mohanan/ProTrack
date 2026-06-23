import os

SECRET_KEY = os.getenv("PROTRACK_SECRET_KEY", "dev-only-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480
