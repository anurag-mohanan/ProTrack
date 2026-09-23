"""Required / optional dependencies for Finance document PDF import."""

from __future__ import annotations

from typing import Any


# Required for layout-aware Prosohm quote/invoice import (pdfplumber word geometry).
REQUIRED_DOCUMENT_IMPORT_MODULES = ("pdfplumber", "pypdf")
# Optional extras — OCR path; missing is supported.
OPTIONAL_DOCUMENT_IMPORT_MODULES = ("pdf2image", "pytesseract")


def probe_document_import_dependencies() -> dict[str, Any]:
    """Return availability of PDF import dependencies for startup/health."""
    required: dict[str, dict[str, Any]] = {}
    missing_required: list[str] = []
    for name in REQUIRED_DOCUMENT_IMPORT_MODULES:
        try:
            mod = __import__(name)
            required[name] = {
                "available": True,
                "version": getattr(mod, "__version__", None),
            }
        except ImportError as exc:
            required[name] = {"available": False, "error": str(exc)}
            missing_required.append(name)

    optional: dict[str, dict[str, Any]] = {}
    for name in OPTIONAL_DOCUMENT_IMPORT_MODULES:
        try:
            mod = __import__(name)
            optional[name] = {
                "available": True,
                "version": getattr(mod, "__version__", None),
            }
        except ImportError:
            optional[name] = {"available": False}

    available = not missing_required
    return {
        "available": available,
        "pdf_parser": "pdfplumber" if required.get("pdfplumber", {}).get("available") else None,
        "required": required,
        "optional": optional,
        "missing_required": missing_required,
        "install_hint": (
            "On the API host: python -m pip install -r requirements.txt "
            "(or .\\scripts\\install_pdf_deps.ps1), then restart the API."
            if missing_required
            else None
        ),
    }


def log_document_import_dependency_status(logger) -> dict[str, Any]:
    """Log clear startup warnings when required PDF import deps are missing."""
    status = probe_document_import_dependencies()
    if status["available"]:
        logger.info(
            "Finance PDF Import: dependencies OK (pdfplumber=%s, pypdf=%s)",
            status["required"].get("pdfplumber", {}).get("version"),
            status["required"].get("pypdf", {}).get("version"),
        )
    else:
        missing = ", ".join(status["missing_required"])
        logger.error(
            "Finance PDF Import: MISSING DEPENDENCY: %s — %s",
            missing,
            status["install_hint"],
        )
    return status
