"""PDF text quality scoring — reject binary/stdlib scrape garbage."""

from __future__ import annotations

import re


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    return printable / max(len(text), 1)


def letter_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for ch in text if ch.isalpha())
    return letters / max(len(text), 1)


def is_usable_pdf_text(text: str | None, *, min_chars: int = 40) -> bool:
    """True when extracted text looks like readable document content.

    The stdlib PDF literal scrape often returns thousands of binary-noise
    characters that pass a simple length check but contain no invoice/quote
    labels. Reject those so pdfplumber/pypdf/OCR can be preferred.
    """
    body = (text or "").strip()
    if len(body) < min_chars:
        return False
    if printable_ratio(body) < 0.85:
        return False
    if letter_ratio(body) < 0.25:
        return False
    # At least a few word-like tokens
    words = re.findall(r"[A-Za-z]{3,}", body)
    if len(words) < 5:
        return False
    return True


def finance_text_signal_score(text: str | None) -> float:
    """Higher score = more likely a Prosohm invoice/quote text layer."""
    body = text or ""
    if not is_usable_pdf_text(body, min_chars=20):
        return 0.0
    score = 10.0
    upper = body.upper()
    checks = (
        (r"\bINVOICE\b", 25),
        (r"Invoice\s*#", 30),
        (r"\bQUOTE\b", 25),
        (r"Quote\s*#", 30),
        (r"Customer\s+Project\s*#", 20),
        (r"Balance\s+Due", 15),
        (r"Bill\s+To", 10),
        (r"Prepared\s+For", 10),
        (r"INV-\d", 15),
        (r"QT-\d", 15),
    )
    for pattern, points in checks:
        if re.search(pattern, body, re.IGNORECASE):
            score += points
    # Prefer denser readable text slightly
    score += min(letter_ratio(body) * 20, 20)
    return score


__all__ = [
    "finance_text_signal_score",
    "is_usable_pdf_text",
    "letter_ratio",
    "printable_ratio",
]
