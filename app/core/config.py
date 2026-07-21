import os
from pathlib import Path


def _flag(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- Deployment environment -------------------------------------------------
# PROTRACK_ENV: "development" (default) or "production". Production enables the
# secret/config guard in app.main and turns on stricter transport defaults.
ENVIRONMENT = os.getenv("PROTRACK_ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT in ("production", "prod")
# When true, production refuses to start on insecure config (missing secrets).
# Default false so upgrades never take a running deployment offline; enable it
# once real secrets are provisioned.
STRICT_SECURITY = _flag("PROTRACK_STRICT_SECURITY", "false")

# --- Signing / encryption secrets -------------------------------------------
DEV_DEFAULT_SECRET_KEY = "dev-only-change-me-in-production"
SECRET_KEY = os.getenv("PROTRACK_SECRET_KEY", DEV_DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _int("PROTRACK_ACCESS_TOKEN_EXPIRE_MINUTES", 480)

# Fernet key (urlsafe base64, 32 bytes) used for symmetric encryption of stored
# secrets (e.g. SMTP passwords). When unset in development we derive a stable key
# from SECRET_KEY so the app keeps working; production must set a real key.
ENCRYPTION_KEY = os.getenv("PROTRACK_ENCRYPTION_KEY", "").strip()

APP_VERSION = os.getenv("PROTRACK_APP_VERSION", "1.0.0")
RELEASE_CANDIDATE = os.getenv("PROTRACK_RELEASE_CANDIDATE", "RC5")

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

# --- Transport / edge hardening ---------------------------------------------
# HSTS should only be enabled when the app is genuinely served over HTTPS.
ENABLE_HSTS = _flag("PROTRACK_ENABLE_HSTS", "true" if IS_PRODUCTION else "false")
# Comma-separated Host allowlist for TrustedHostMiddleware; empty disables it.
TRUSTED_HOSTS = [
    host.strip()
    for host in os.getenv("PROTRACK_TRUSTED_HOSTS", "").split(",")
    if host.strip()
]
# Hard cap on request body size (bytes) to blunt memory-exhaustion DoS.
MAX_REQUEST_BODY_BYTES = _int("PROTRACK_MAX_REQUEST_BODY_BYTES", 50 * 1024 * 1024)
# Per-file upload cap for import/attachment endpoints (bytes).
MAX_UPLOAD_BYTES = _int("PROTRACK_MAX_UPLOAD_BYTES", 25 * 1024 * 1024)

# --- Rate limiting ----------------------------------------------------------
RATE_LIMIT_ENABLED = _flag("PROTRACK_RATE_LIMIT_ENABLED", "true")
# Applied to authentication endpoints (login / token / change-password).
AUTH_RATE_LIMIT = os.getenv("PROTRACK_AUTH_RATE_LIMIT", "10/minute")

# --- Authentication policy defaults -----------------------------------------
# These are defaults; the effective values can be overridden at runtime via the
# security policy settings store (see governance workstream).
LOCKOUT_MAX_FAILED_ATTEMPTS = _int("PROTRACK_LOCKOUT_MAX_FAILED_ATTEMPTS", 5)
LOCKOUT_WINDOW_MINUTES = _int("PROTRACK_LOCKOUT_WINDOW_MINUTES", 15)
LOCKOUT_DURATION_MINUTES = _int("PROTRACK_LOCKOUT_DURATION_MINUTES", 30)
PASSWORD_EXPIRY_DAYS = _int("PROTRACK_PASSWORD_EXPIRY_DAYS", 0)  # 0 disables expiry
PASSWORD_HISTORY_COUNT = _int("PROTRACK_PASSWORD_HISTORY_COUNT", 5)
SESSION_IDLE_TIMEOUT_MINUTES = _int("PROTRACK_SESSION_IDLE_TIMEOUT_MINUTES", 0)  # 0 disables idle timeout

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = Path(os.getenv("PROTRACK_UPLOAD_DIR", BASE_DIR / "uploads"))
COMPANY_LOGO_DIR = UPLOAD_DIR / "company"

# Filesystem sandbox roots. Server-side path inputs (email attachments, folder
# imports) must resolve inside one of these directories.
_default_import_root = str(BASE_DIR / "import_sources")
IMPORT_SOURCE_ROOTS = [
    Path(p.strip()).expanduser().resolve()
    for p in os.getenv("PROTRACK_IMPORT_SOURCE_ROOTS", _default_import_root).split(os.pathsep)
    if p.strip()
]
_default_attachment_root = str(BASE_DIR / "uploads")
ATTACHMENT_ROOTS = [
    Path(p.strip()).expanduser().resolve()
    for p in os.getenv("PROTRACK_ATTACHMENT_ROOTS", _default_attachment_root).split(os.pathsep)
    if p.strip()
]

# Demo design-team users are for local development only; keep disabled for production imports.
ENABLE_DEMO_SEED = os.getenv("PROTRACK_ENABLE_DEMO_SEED", "").lower() in ("1", "true", "yes")

# Internal Release (soft launch): skip forced password change redirects while testing.
# Set INTERNAL_RELEASE=false before production deployment.
INTERNAL_RELEASE = os.getenv("INTERNAL_RELEASE", "true").lower() in ("1", "true", "yes")


def security_config_problems() -> list[str]:
    """Production-blocking security misconfigurations (hard startup blockers).

    Only true secrets belong here — items whose absence makes the deployment
    genuinely insecure. Operational flags (e.g. INTERNAL_RELEASE) are advisory
    and must never prevent the service from starting.
    """
    problems: list[str] = []
    if SECRET_KEY == DEV_DEFAULT_SECRET_KEY:
        problems.append(
            "PROTRACK_SECRET_KEY is unset or using the insecure development default."
        )
    if not ENCRYPTION_KEY:
        problems.append(
            "PROTRACK_ENCRYPTION_KEY is not set (required to encrypt stored secrets)."
        )
    return problems


def security_config_warnings() -> list[str]:
    """Non-blocking advisories surfaced at startup (never prevent boot)."""
    warnings: list[str] = []
    if INTERNAL_RELEASE:
        warnings.append(
            "INTERNAL_RELEASE is true (forced password change is bypassed)."
        )
    return warnings


def assert_production_security() -> list[str]:
    """Surface security misconfigurations at startup.

    By default the app always boots (insecure config is logged loudly) so an
    upgrade can never take a live deployment offline. Set
    ``PROTRACK_STRICT_SECURITY=true`` to make production *refuse* to start on
    missing secrets once you are ready to enforce it.

    Returns the combined list of problems + warnings so callers can log them.
    """
    problems = security_config_problems()
    if problems and IS_PRODUCTION and STRICT_SECURITY:
        raise RuntimeError(
            "Refusing to start in production with insecure configuration:\n  - "
            + "\n  - ".join(problems)
        )
    return problems + security_config_warnings()
