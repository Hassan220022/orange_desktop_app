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
_INTEGER_COLUMNS = {
    "# of BSC",
    "# of BTS",
    "# of GSM/MRFU/RF",
    "# of DSC/MRFU/RF",
    "# of MW",
    "# of SDH",
    "# of ADM",
    "# of Routers",
    "No. Of 3G RF",
    "No. Of 4G RF",
    "# of Modules",
    "No of String",
    "No of Batteries",
}
_STRICT_NUMERIC_COLUMNS = _INTEGER_COLUMNS | {
    "PLD Value",
}
_NUMERIC_WITH_UNITS_COLUMNS = {
    "Battery Volt",
    "Battery Ampere Hour",
    "Discharge time( Mins)",
    "Start Volt",
    "Start Amp",
    "Charging current",
    "End Volt",
    "End Amp",
}
_TEXT_ONLY_COLUMNS = {
    "BSC Type",
    "BTS Type",
    "MW Type",
    "AC1 Type",
    "AC2 Type",
    "3G Type",
    "4G Type",
}
_NUMERIC_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


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


def _numeric_from_strict_text(text: str) -> float | None:
    val = text.strip().replace(",", ".")
    if not _NUMERIC_RE.fullmatch(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _numeric_from_text_with_units(text: str) -> float | None:
    val = text.strip().lower().replace(",", ".")
    val = re.sub(r"\s+", "", val)
    for suffix in ("minutes", "minute", "mins", "min", "vdc", "ah", "am", "v", "a"):
        if val.endswith(suffix):
            val = val[: -len(suffix)]
            break
    return _numeric_from_strict_text(val)


def _format_numeric(num: float, *, integer: bool) -> str:
    if integer and abs(num - round(num)) < 1e-9:
        return str(int(round(num)))
    return f"{num:.2f}".rstrip("0").rstrip(".")


def _normalize_numeric_column(column: str, value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    if column in _STRICT_NUMERIC_COLUMNS:
        num = _numeric_from_strict_text(text)
    elif column in _NUMERIC_WITH_UNITS_COLUMNS:
        num = _numeric_from_text_with_units(text)
    else:
        num = None
    if num is None:
        return ""
    return _format_numeric(num, integer=(column in _INTEGER_COLUMNS))


def _parse_date(value: Any):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)

    text = _clean_text(value)
    if not text:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%b-%y",
        "%d-%b-%Y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    for day_first in (False, True):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=day_first)
        if not pd.isna(parsed):
            return parsed.to_pydatetime()
    return None


def _normalize_date_text(value: Any) -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return _clean_text(value)
    return parsed.strftime("%Y-%m-%d")


def _normalize_week(value: str, test_date: str) -> str:
    text = _clean_text(value)
    if text:
        m = re.match(r"^\s*[wW]\s*(\d{1,2})\s*$", text)
        if m:
            week_no = int(m.group(1))
            if week_no > 0:
                return f"W{week_no:02d}"
        n = _numeric_from_strict_text(text)
        if n is not None and n > 0:
            return f"W{int(round(n)):02d}"

    parsed = _parse_date(test_date)
    if parsed is None:
        return text
    return f"W{int(parsed.isocalendar().week):02d}"


def _normalize_site_category(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    key = _normalize_key(text)
    if key in {"od", "outdoor"}:
        return "OUTDOOR"
    if key in {"shelter", "indoor"}:
        return "SHELTER"
    return text.upper()


def _normalize_type(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    key = _normalize_key(text)
    if key in {"bronze", "silver", "gold", "platinum"}:
        return text.upper()
    return text


def _normalize_power_source(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    upper = text.upper().replace(" ", "")
    if upper in {"ECDG", "EC+DG"}:
        return "EC+DG"
    if upper in {"ETDG", "ET+DG"}:
        return "ET+DG"
    if upper in {"EC", "DG", "ET"}:
        return upper
    return text.upper()


def _blank_if_numeric(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    return "" if _numeric_from_strict_text(text) is not None else text


def _normalize_canonical_row(row: dict[str, str], row_index: int) -> None:
    row["Short Code"] = _clean_text(row.get("Short Code", "")).upper()
    row["On Air Date"] = _normalize_date_text(row.get("On Air Date", ""))
    row["Test Date"] = _normalize_date_text(row.get("Test Date", ""))
    row["Week"] = _normalize_week(row.get("Week", ""), row.get("Test Date", ""))
    row["Ser"] = str(row_index + 1)
    row["Type"] = _normalize_type(row.get("Type", ""))
    row["Site Category"] = _normalize_site_category(row.get("Site Category", ""))
    row["Power Source"] = _normalize_power_source(row.get("Power Source", ""))

    reason_repeat = _clean_text(row.get("Reason for Repeated BDT", ""))
    if _normalize_key(reason_repeat) == "cycle":
        row["Reason for Repeated BDT"] = "Cycle"
    else:
        row["Reason for Repeated BDT"] = reason_repeat

    for col in _STRICT_NUMERIC_COLUMNS | _NUMERIC_WITH_UNITS_COLUMNS:
        row[col] = _normalize_numeric_column(col, row.get(col, ""))

    for col in _TEXT_ONLY_COLUMNS:
        row[col] = _blank_if_numeric(row.get(col, ""))


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
    for row_index, res in enumerate(results):
        bdt = getattr(res, "bdt_data", None)
        summary_data = getattr(bdt, "summary_data", None) if bdt is not None else None
        exact, ordered = _normalize_summary_data(summary_data)

        canonical_row = {
            col: _summary_value_for_column(col, exact, ordered)
            for col in BDT_PM_SUMMARY_HEADERS
        }
        _apply_ac_hp_split_fallback(canonical_row, exact, ordered)
        _apply_bdt_fallbacks(canonical_row, bdt)
        _normalize_canonical_row(canonical_row, row_index)
        rows.append(_to_export_row(canonical_row))
    return rows


def build_bdt_export_sheets(results, health_pct: float | None = None) -> dict[str, pd.DataFrame]:
    pm_rows = build_pm_summary_rows(results, health_pct=health_pct)
    return {BDT_SUMMARY_SHEET_NAME: pd.DataFrame(pm_rows, columns=BDT_SUMMARY_EXPORT_HEADERS)}
