"""Small, explainable statistics in pure Python (no numeric libraries are installed)."""

from __future__ import annotations

import math
from statistics import median

MIN_SAMPLE = 5
MIN_RANGE_SAMPLE = 10
MIN_PATTERN_GROUP = 8
SIGNIFICANCE = 0.05


def quantile(values: list[float], q: float) -> float:
    """Linear interpolation between order statistics (same as the common 'type 7' definition)."""
    if not values:
        raise ValueError("quantile of an empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def central(values: list[float]) -> float:
    return float(median(values))


def mann_whitney_p(group: list[float], rest: list[float]) -> float | None:
    """Two-sided p-value of the Mann–Whitney U test, normal approximation with tie correction.

    Returns None when either side is smaller than the minimum sample, where the approximation
    is not trustworthy.
    """
    n1, n2 = len(group), len(rest)
    if n1 < MIN_SAMPLE or n2 < MIN_SAMPLE:
        return None
    combined = sorted([(v, 0) for v in group] + [(v, 1) for v in rest])
    ranks = [0.0] * len(combined)
    tie_term = 0.0
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = rank
        t = j - i + 1
        tie_term += t**3 - t
        i = j + 1
    r1 = sum(rank for rank, (_, side) in zip(ranks, combined) if side == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    n = n1 + n2
    variance = n1 * n2 / 12 * ((n + 1) - tie_term / (n * (n - 1)))
    if variance <= 0:
        return 1.0
    z = (u1 - n1 * n2 / 2) / math.sqrt(variance)
    return math.erfc(abs(z) / math.sqrt(2))


def share(values: list[float], predicate) -> float:
    return sum(1 for v in values if predicate(v)) / len(values) if values else 0.0
