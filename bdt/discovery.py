"""Helpers for deciding which workbooks are raw BDT inputs."""

from __future__ import annotations

from pathlib import Path


BDT_WORKBOOK_SUFFIXES = frozenset({".xlsx", ".xlsm", ".xls"})

NON_RAW_BDT_WORKBOOK_HINTS = (
    "acceptance",
    "accepted",
    "summary",
    "stolen",
    "not installed",
    "solar",
)


def normalize_workbook_label(value: str) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").lower()
    return " ".join(text.split())


def is_non_raw_bdt_label(value: str) -> bool:
    """True for human registers, summaries, and asset lists, not raw BDTs."""
    label = normalize_workbook_label(value)
    return any(hint in label for hint in NON_RAW_BDT_WORKBOOK_HINTS)


def is_raw_bdt_workbook_filename(path_or_name: str | Path) -> bool:
    """Return whether a workbook filename should be treated as a raw BDT file."""
    path = Path(path_or_name)
    name = path.name
    if not name or name.startswith(("~$", "._")):
        return False
    if path.suffix.lower() not in BDT_WORKBOOK_SUFFIXES:
        return False
    label = normalize_workbook_label(path.stem)
    if "bdt" not in label:
        return False
    return not is_non_raw_bdt_label(label)
