"""Ensure required runtime packages for the running ProTrack API process.

This is server-side (program level) — never a per-browser install.
When the API host is missing pdfplumber/pypdf after a code sync, startup
attempts to install them into *this* interpreter so Finance PDF import works
for every user without local setup.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("protrack.startup")

# Critical for Finance invoice/quote PDF import on every API host.
CRITICAL_IMPORTS = ("pdfplumber", "pypdf")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _missing_modules(names: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for name in names:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    return missing


def _pip_install(args: list[str]) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pip", "install", *args]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    out = (proc.stdout or "")[-1500:]
    err = (proc.stderr or "")[-1500:]
    detail = (out + "\n" + err).strip()
    return proc.returncode == 0, detail


def ensure_critical_runtime_dependencies(*, auto_install: bool = True) -> dict[str, Any]:
    """Probe critical deps; optionally install into the running interpreter.

    Returns a status dict suitable for logs / health checks.
    """
    missing = _missing_modules(CRITICAL_IMPORTS)
    status: dict[str, Any] = {
        "python": sys.executable,
        "required": list(CRITICAL_IMPORTS),
        "missing_before": list(missing),
        "auto_install": auto_install,
        "installed": False,
        "ok": not missing,
        "detail": None,
    }
    if not missing:
        versions = {}
        for name in CRITICAL_IMPORTS:
            mod = __import__(name)
            versions[name] = getattr(mod, "__version__", None)
        status["versions"] = versions
        logger.info(
            "Runtime deps OK (pdfplumber=%s, pypdf=%s) via %s",
            versions.get("pdfplumber"),
            versions.get("pypdf"),
            sys.executable,
        )
        return status

    logger.error(
        "Finance PDF Import: MISSING DEPENDENCY on API host: %s (python=%s)",
        ", ".join(missing),
        sys.executable,
    )
    if not auto_install:
        status["detail"] = "auto_install disabled"
        return status

    requirements = _repo_root() / "requirements.txt"
    if requirements.is_file():
        logger.warning(
            "Installing missing runtime deps from %s into %s …",
            requirements,
            sys.executable,
        )
        ok, detail = _pip_install(["-r", str(requirements)])
    else:
        logger.warning("requirements.txt not found; installing %s directly", missing)
        ok, detail = _pip_install(list(missing))

    status["installed"] = ok
    status["detail"] = detail
    still_missing = _missing_modules(CRITICAL_IMPORTS)
    status["missing_after"] = still_missing
    status["ok"] = not still_missing

    if status["ok"]:
        logger.warning(
            "Runtime deps installed successfully into %s — Finance PDF import is ready for all users.",
            sys.executable,
        )
    else:
        logger.error(
            "Could not install runtime deps (%s). "
            "On the API host run: %s -m pip install -r requirements.txt "
            "then restart the ProTrack API service. Detail: %s",
            still_missing,
            sys.executable,
            (detail or "")[:500],
        )
    return status


__all__ = ["ensure_critical_runtime_dependencies"]
