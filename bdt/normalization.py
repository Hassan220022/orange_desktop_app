"""Normalization helpers for section-first BDT parsing."""

import re


_CATEGORY_KEYWORDS = {
    "rectifier": (
        "rectifier",
        "module",
        "converter",
        "ac input",
        "dc output",
    ),
    "batteries": (
        "battery",
        "string",
        "ah",
        "capacity",
        "cell",
    ),
    "modules": (
        "module",
        "slot",
        "board",
        "unit",
    ),
    "load": (
        "load",
        "discharge",
        "current",
        "ampere",
        "amp",
    ),
    "charging": (
        "charge",
        "charging",
        "float",
        "equalize",
        "recharge",
    ),
    "alarms": (
        "alarm",
        "fault",
        "door",
        "warning",
        "event",
    ),
}


def normalize_header_text(text) -> str:
    """Return lowercase, de-punctuated, space-normalized header text."""

    if text is None:
        return ""
    value = str(text).strip().lower()
    if not value:
        return ""
    value = re.sub(r"[_\-/]+", " ", value)
    value = re.sub(r"[^a-z0-9\s]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def resolve_section_category(header_text, nearby_texts) -> str:
    """Infer section category from header and nearby text keywords."""

    haystack = [normalize_header_text(header_text)]
    haystack.extend(normalize_header_text(t) for t in (nearby_texts or []))
    merged = " ".join(v for v in haystack if v)
    if not merged:
        return "other"

    scores = {name: 0 for name in _CATEGORY_KEYWORDS}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in merged:
                scores[category] += 1

    winner = max(scores, key=scores.get)
    if scores[winner] <= 0:
        return "other"
    return winner
