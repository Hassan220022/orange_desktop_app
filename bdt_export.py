"""
Helpers to build BDT export payloads.

Export format intentionally matches the weekly summary workbook layout.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

import pandas as pd

try:
    from .constants import (
        BDT_PM_SUMMARY_HEADERS,
        BDT_SUMMARY_EXPORT_HEADERS,
        BDT_SUMMARY_SHEET_NAME,
    )
except ImportError:
    from constants import (
        BDT_PM_SUMMARY_HEADERS,
        BDT_SUMMARY_EXPORT_HEADERS,
        BDT_SUMMARY_SHEET_NAME,
    )


_EMPTY_VALUES = {"", "none", "nan", "null", "-", "--", "unknown"}
_SUMMARY_EMPTY_VALUES = _EMPTY_VALUES | {"na", "n/a"}
_EXPORT_TO_CANONICAL_HEADER = {
    "No of Batteries ": "No of Batteries",
    "CAP request ": "CAP request",
}


_SUMMARY_KEY_VARIANTS: dict[str, tuple[str, ...]] = {
    "PLD Value": ("PLVD Value", "PLVD Set Point", "LVD Disconnect Value"),
    "Linked sites name codes": ("Linked sites name code", "Linked sites name/codes"),
    "Site Category": ("Site Category Type", "Site Category / Type", "Site Category and Type"),
    "BTS Type": ("Type2", "Type 2"),
    "No. Of 3G RF": ("No of 3G RF", "# of 3G RF"),
    "No. Of 4G RF": ("No of 4G RF", "# of 4G RF"),
    "# of Modules": ("No of Modules", "Number of Modules"),
    "No of String": ("No of Strings", "# of String", "# of Strings", "Number of Strings"),
    "No of Batteries": ("No. of Batteries", "# of Batteries", "Number of Batteries"),
    "Charging current": (
        "Batteries Charnging current limit",
        "Batteries Charging current limit",
        "Battery Charging current limit",
        "Charging current limit",
    ),
    "Reason for Stop BDT": ("Reason for Test stop",),
    "CAP request": ("Cap request #", "CAP request no", "CAP request number"),
    "AC1 HP": ("AC HP", "AC HP1"),
    "AC2 HP": ("AC HP2", "AC HP3"),
}

_CORE_BDT_FALLBACKS: dict[str, str] = {
    "Short Code": "site_code",
    "Site Name": "site_name",
    "Test Date": "test_date",
    "Rectifier Brand": "rectifier_brand",
    "# of Modules": "num_modules",
    "Battery Brand": "battery_brand",
    "Battery Volt": "battery_voltage",
    "Battery Ampere Hour": "battery_ah",
    "No of String": "num_strings",
    "No of Batteries": "num_batteries",
    "Start Volt": "start_voltage",
    "Start Amp": "start_ampere",
    "End Volt": "end_voltage",
    "End Amp": "end_ampere",
    "Discharge time( Mins)": "discharge_minutes",
    "PLD Value": "pld_value",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() in _EMPTY_VALUES:
        return ""
    return text


def _clean_summary_value(value: Any) -> str:
    text = _clean_text(value)
    if text.lower() in _SUMMARY_EMPTY_VALUES:
        return ""
    return text


def _normalize_key(key: Any) -> str:
    text = _clean_text(key).lower().replace("\u00a0", " ")
    return re.sub(r"[^a-z0-9]+", "", text)


def _normalize_summary_data(summary_data: dict[str, str] | None) -> tuple[dict[str, str], list[tuple[str, str]]]:
    exact: dict[str, str] = {}
    ordered: list[tuple[str, str]] = []
    if not summary_data:
        return exact, ordered

    for key, value in summary_data.items():
        normalized_key = _normalize_key(key)
        if not normalized_key:
            continue
        clean_value = _clean_summary_value(value)
        if normalized_key not in exact or (not exact[normalized_key] and clean_value):
            exact[normalized_key] = clean_value
        ordered.append((normalized_key, clean_value))
    return exact, ordered


def _find_summary_value(
    exact: dict[str, str],
    ordered: list[tuple[str, str]],
    aliases: tuple[str, ...],
) -> str:
    normalized_aliases = tuple(a for a in (_normalize_key(alias) for alias in aliases) if a)

    for alias in normalized_aliases:
        if alias in exact:
            return exact[alias]

    for alias in normalized_aliases:
        if len(alias) < 5:
            continue
        for key_norm, value in ordered:
            if not value:
                continue
            if alias in key_norm or key_norm in alias:
                return value
    return ""


def _summary_value_for_column(
    column: str,
    exact: dict[str, str],
    ordered: list[tuple[str, str]],
) -> str:
    aliases = (column,) + _SUMMARY_KEY_VARIANTS.get(column, ())
    return _find_summary_value(exact, ordered, aliases)


def _format_bdt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).strftime("%Y-%m-%d")
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return _clean_text(value)


def _apply_bdt_fallbacks(row: dict[str, str], bdt) -> None:
    if bdt is None:
        return
    for column, attr in _CORE_BDT_FALLBACKS.items():
        if row.get(column):
            continue
        row[column] = _format_bdt_value(getattr(bdt, attr, None))


def _apply_ac_hp_split_fallback(
    row: dict[str, str],
    exact: dict[str, str],
    ordered: list[tuple[str, str]],
) -> None:
    if row.get("AC1 HP") and row.get("AC2 HP"):
        return
    pair_value = _find_summary_value(exact, ordered, ("AC HP/AC HP3", "AC HP3/AC HP"))
    if not pair_value:
        return

    parts = [p.strip() for p in re.split(r"[/|,;]", pair_value) if p.strip()]
    if not parts:
        return

    if not row.get("AC1 HP"):
        row["AC1 HP"] = parts[0]
    if not row.get("AC2 HP"):
        row["AC2 HP"] = parts[1] if len(parts) > 1 else parts[0]


def _to_export_row(canonical_row: dict[str, str]) -> dict[str, str]:
    return {
        export_col: canonical_row.get(
            _EXPORT_TO_CANONICAL_HEADER.get(export_col, export_col), ""
        )
        for export_col in BDT_SUMMARY_EXPORT_HEADERS
    }


def build_pm_summary_rows(results, health_pct: float | None = None) -> list[dict[str, str]]:
    del health_pct  # Kept in signature for call-site compatibility.
    rows: list[dict[str, str]] = []
    for res in results:
        bdt = getattr(res, "bdt_data", None)
        summary_data = getattr(bdt, "summary_data", None) if bdt is not None else None
        exact, ordered = _normalize_summary_data(summary_data)

        canonical_row = {
            col: _summary_value_for_column(col, exact, ordered)
            for col in BDT_PM_SUMMARY_HEADERS
        }
        _apply_ac_hp_split_fallback(canonical_row, exact, ordered)
        _apply_bdt_fallbacks(canonical_row, bdt)
        rows.append(_to_export_row(canonical_row))
    return rows


def build_bdt_export_sheets(results, health_pct: float | None = None) -> dict[str, pd.DataFrame]:
    pm_rows = build_pm_summary_rows(results, health_pct=health_pct)
    return {BDT_SUMMARY_SHEET_NAME: pd.DataFrame(pm_rows, columns=BDT_SUMMARY_EXPORT_HEADERS)}
