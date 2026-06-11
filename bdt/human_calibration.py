"""
Human calibration — derive BDT validation thresholds from Book1 review data.

Parses Youssef's human PM review, auto validation export, and source BDT
files to extract per-site features and propose accept/revise/reject bands.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from alarm_app.bdt.evidence_metrics import (
        discharge_trend_metrics,
        max_reached_discharge_minutes,
        worst_r3_evidence,
    )
    from alarm_app.bdt.parser import BDTData, parse_bdt_file
except ImportError:
    from bdt.evidence_metrics import (
        discharge_trend_metrics,
        max_reached_discharge_minutes,
        worst_r3_evidence,
    )
    from bdt.parser import BDTData, parse_bdt_file


@dataclass
class HumanReviewRow:
    site_name: str
    site_code: str
    test_date: str
    test_type: str
    human_verdict: str
    human_reason: str
    severity: str


@dataclass
class SiteCalibrationRow:
    site_code: str
    test_date: str
    human_verdict: str
    human_reason: str
    severity: str
    test_type: str
    bdt_path: str = ""
    parse_error: str = ""
    r3_max_pos_delta: float | None = None
    r3_max_neg_delta: float | None = None
    r3_worst_string_imbalance: float | None = None
    r9_max_delta: float | None = None
    r9_late_delta: float | None = None
    bus_amp_slope: float | None = None
    discharge_minutes_reached: float | None = None
    auto_verdict: str = ""
    auto_r3: str = ""
    auto_r9: str = ""
    proposed_verdict: str = ""


def parse_book1(path: str | Path) -> list[HumanReviewRow]:
    """Parse Book1 human review workbook (May 2026 PM batch)."""
    df = pd.read_excel(path, header=None)
    rows: list[HumanReviewRow] = []
    for _, raw in df.iterrows():
        if str(raw.iloc[0]).strip() != "PM Site":
            continue
        site_code = str(raw.iloc[7]).strip()
        if not site_code or site_code.lower() in ("site code", "nan"):
            continue
        verdict = str(raw.iloc[8]).strip()
        if verdict not in ("Accepted", "Rejected"):
            continue
        test_date = _normalize_date(raw.iloc[6])
        rows.append(
            HumanReviewRow(
                site_name=str(raw.iloc[1]).strip(),
                site_code=site_code,
                test_date=test_date,
                test_type=str(raw.iloc[4]).strip(),
                human_verdict=verdict,
                human_reason=str(raw.iloc[9] if pd.notna(raw.iloc[9]) else "").strip(),
                severity=str(raw.iloc[10] if pd.notna(raw.iloc[10]) else "").strip(),
            )
        )
    return rows


def _normalize_date(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        return pd.Timestamp(text).strftime("%Y-%m-%d")
    except Exception:
        return text[:10]


def find_bdt_file(folder: str | Path, site_code: str) -> Path | None:
    """Locate a BDT xlsx whose filename contains the site code."""
    root = Path(folder)
    if not root.exists():
        return None
    code = site_code.upper()
    matches: list[Path] = []
    for pattern in ("*.xlsx", "*.XLSX"):
        for path in root.rglob(pattern):
            if path.name.startswith("._"):
                continue
            if code in path.name.upper():
                matches.append(path)
    if not matches:
        return None
    return sorted(matches, key=lambda p: len(p.name))[0]


def extract_site_features(bdt: BDTData) -> dict[str, float | None]:
    """Extract calibration features from parsed BDT data."""
    r3 = worst_r3_evidence(bdt)
    r9 = discharge_trend_metrics(bdt)
    reached = max_reached_discharge_minutes(bdt)
    out: dict[str, float | None] = {
        "discharge_minutes_reached": reached,
    }
    if r3 is not None:
        out.update({
            "r3_max_pos_delta": r3.max_pos_delta,
            "r3_max_neg_delta": r3.max_neg_delta,
            "r3_worst_string_imbalance": r3.worst_imbalance_ratio,
            "r3_checked_points": float(r3.checked_points),
        })
    if r9 is not None:
        out.update({
            "r9_max_delta": r9.max_delta,
            "r9_late_delta": r9.late_delta,
            "bus_amp_slope": r9.bus_amp_slope,
        })
    return out


def load_auto_export_index(path: str | Path) -> dict[tuple[str, str], dict[str, str]]:
    """Index auto validation export by (site_code, test_date)."""
    df = pd.read_excel(path)
    index: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in df.iterrows():
        site = str(row.get("Site Code", "")).strip()
        date = _normalize_date(row.get("Test Date"))
        if not site or not date:
            continue
        index[(site.upper(), date)] = {
            "auto_verdict": str(row.get("Verdict", "")).strip(),
            "auto_r3": str(row.get("R3 - String vs Bus Bar Ampere", "")).strip(),
            "auto_r9": str(row.get("R9 - Discharge Current Tolerance", "")).strip(),
        }
    return index


def _metric_stats(
    rows: list[SiteCalibrationRow],
    metric: str,
    *,
    verdict: str | None = None,
    reason_contains: str | None = None,
) -> dict[str, float | None]:
    values: list[float] = []
    for row in rows:
        if verdict and row.human_verdict != verdict:
            continue
        if reason_contains and reason_contains.lower() not in row.human_reason.lower():
            continue
        raw = getattr(row, metric, None)
        if raw is None:
            continue
        values.append(float(raw))
    if not values:
        return {"count": 0, "min": None, "max": None}
    return {"count": len(values), "min": min(values), "max": max(values)}


def build_human_aligned_profile(rows: list[SiteCalibrationRow]) -> dict[str, Any]:
    """Derive proposed tolerance bands from labeled rows."""
    accepted = [r for r in rows if r.human_verdict == "Accepted"]
    rejected = [r for r in rows if r.human_verdict == "Rejected"]

    def accept_max(metric: str) -> float | None:
        stats = _metric_stats(accepted, metric)
        return stats["max"]

    def reject_min(metric: str, reason: str | None = None) -> float | None:
        stats = _metric_stats(rejected, metric, reason_contains=reason)
        return stats["min"]

    profile = {
        "version": 3,
        "sample_count": len(rows),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "thresholds": {
            "string_ampere_pos_accept_a": _round_or(
                accept_max("r3_max_pos_delta"), 1.5),
            "string_ampere_pos_revise_a": max(
                5.0,
                _round_or(accept_max("r3_max_pos_delta"), 5.0) + 0.5,
            ),
            "string_ampere_a": 3.0,
            "string_imbalance_reject_ratio": 0.85,
            "string_imbalance_revise_ratio": 0.70,
            "discharge_current_accept_a": _round_or(
                accept_max("r9_max_delta"), 15.0),
            "discharge_slope_accept_a_per_min": _round_or(
                accept_max("bus_amp_slope"), 0.12),
            "discharge_slope_reject_a_per_min": _round_or(
                reject_min("bus_amp_slope", "fluctuat"), 0.25),
            "discharge_spike_reject_a": 10.0,
            "incomplete_reject_minutes": 30.0,
            "incomplete_revise_minutes": 90.0,
            "overall_ignore_na_rules": ["R11", "R5", "R7"],
        },
        "stats": {
            "accepted_r3_pos_max": _metric_stats(accepted, "r3_max_pos_delta"),
            "rejected_r3_pos_min": _metric_stats(rejected, "r3_max_pos_delta"),
            "accepted_slope_max": _metric_stats(accepted, "bus_amp_slope"),
            "rejected_slope_min": _metric_stats(
                rejected, "bus_amp_slope", reason_contains="fluctuat"),
            "accepted_imbalance_max": _metric_stats(
                accepted, "r3_worst_string_imbalance"),
            "rejected_imbalance_min": _metric_stats(
                rejected, "r3_worst_string_imbalance"),
        },
    }
    slope_reject = profile["thresholds"]["discharge_slope_reject_a_per_min"]
    if slope_reject is not None and slope_reject < 0.20:
        profile["thresholds"]["discharge_slope_reject_a_per_min"] = 0.20
    return profile


def _round_or(value: float | None, default: float) -> float:
    if value is None:
        return default
    return round(float(value), 2)


def build_calibration_rows(
    human_rows: list[HumanReviewRow],
    bdt_folder: str | Path,
    auto_index: dict[tuple[str, str], dict[str, str]] | None = None,
) -> list[SiteCalibrationRow]:
    """Join human labels with BDT features and optional auto export."""
    out: list[SiteCalibrationRow] = []
    for human in human_rows:
        row = SiteCalibrationRow(
            site_code=human.site_code,
            test_date=human.test_date,
            human_verdict=human.human_verdict,
            human_reason=human.human_reason,
            severity=human.severity,
            test_type=human.test_type,
        )
        key = (human.site_code.upper(), human.test_date)
        if auto_index and key in auto_index:
            auto = auto_index[key]
            row.auto_verdict = auto.get("auto_verdict", "")
            row.auto_r3 = auto.get("auto_r3", "")
            row.auto_r9 = auto.get("auto_r9", "")

        bdt_path = find_bdt_file(bdt_folder, human.site_code)
        if bdt_path is None:
            row.parse_error = "BDT file not found"
            out.append(row)
            continue
        row.bdt_path = str(bdt_path)
        try:
            bdt = parse_bdt_file(str(bdt_path), skip_photos=True)
            feats = extract_site_features(bdt)
            row.r3_max_pos_delta = _as_float(feats.get("r3_max_pos_delta"))
            row.r3_max_neg_delta = _as_float(feats.get("r3_max_neg_delta"))
            row.r3_worst_string_imbalance = _as_float(
                feats.get("r3_worst_string_imbalance"))
            row.r9_max_delta = _as_float(feats.get("r9_max_delta"))
            row.r9_late_delta = _as_float(feats.get("r9_late_delta"))
            row.bus_amp_slope = _as_float(feats.get("bus_amp_slope"))
            row.discharge_minutes_reached = _as_float(
                feats.get("discharge_minutes_reached"))
        except Exception as exc:
            row.parse_error = str(exc)
        out.append(row)
    return out


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def render_report_markdown(
    rows: list[SiteCalibrationRow],
    profile: dict[str, Any],
) -> str:
    """Build a human-readable calibration report."""
    lines = [
        "# Human BDT Calibration Report",
        "",
        f"Sites analyzed: **{len(rows)}** "
        f"({profile.get('accepted_count', 0)} accepted, "
        f"{profile.get('rejected_count', 0)} rejected)",
        "",
        "## Proposed thresholds",
        "",
        "```json",
        json.dumps(profile.get("thresholds", {}), indent=2),
        "```",
        "",
        "## Deep-dive cases",
        "",
        "### 0161CA — string imbalance (human Rejected, amp not matched)",
        _case_block(rows, "0161CA"),
        "",
        "### 0307RE vs 3565CA — same R3 Δ≈0.9A at 10 min, different slope",
        _case_block(rows, "0307RE"),
        _case_block(rows, "3565CA"),
        "",
        "## Human-rejected sites",
        "",
        "| Site | Reason | Severity | R3+ | R3- | Imbalance | R9 Δ | Slope | Discharge min |",
        "|------|--------|----------|-----|-----|-----------|------|-------|---------------|",
    ]
    for row in rows:
        if row.human_verdict != "Rejected":
            continue
        lines.append(
            f"| {row.site_code} | {row.human_reason or '—'} | {row.severity or '—'} "
            f"| {_fmt(row.r3_max_pos_delta)} | {_fmt(row.r3_max_neg_delta)} "
            f"| {_fmt(row.r3_worst_string_imbalance)} | {_fmt(row.r9_max_delta)} "
            f"| {_fmt(row.bus_amp_slope)} | {_fmt(row.discharge_minutes_reached)} |"
        )

    lines.extend([
        "",
        "## Overlap analysis (accepted vs rejected)",
        "",
        "```json",
        json.dumps(profile.get("stats", {}), indent=2),
        "```",
        "",
        "## All rows",
        "",
        "| Site | Date | Human | R3+ | Slope | Imb | Disch min | Auto | BDT |",
        "|------|------|-------|-----|-------|-----|-----------|------|-----|",
    ])
    for row in rows:
        lines.append(
            f"| {row.site_code} | {row.test_date} | {row.human_verdict} "
            f"| {_fmt(row.r3_max_pos_delta)} | {_fmt(row.bus_amp_slope)} "
            f"| {_fmt(row.r3_worst_string_imbalance)} "
            f"| {_fmt(row.discharge_minutes_reached)} "
            f"| {row.auto_verdict or '—'} | "
            f"{'OK' if row.bdt_path and not row.parse_error else row.parse_error or 'missing'} |"
        )
    return "\n".join(lines) + "\n"


def _case_block(rows: list[SiteCalibrationRow], site_code: str) -> str:
    for row in rows:
        if row.site_code.upper() == site_code.upper():
            return (
                f"- **{row.site_code}** ({row.human_verdict}): "
                f"R3+={_fmt(row.r3_max_pos_delta)}A, "
                f"imbalance={_fmt(row.r3_worst_string_imbalance)}, "
                f"R9 Δ={_fmt(row.r9_max_delta)}A, "
                f"slope={_fmt(row.bus_amp_slope)} A/min, "
                f"discharge={_fmt(row.discharge_minutes_reached)} min — "
                f"{row.human_reason or 'no reason'}"
            )
    return f"- **{site_code}**: not found in calibration batch"


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def run_calibration(
    book1_path: str | Path,
    bdt_folder: str | Path,
    auto_export_path: str | Path | None = None,
) -> tuple[list[SiteCalibrationRow], dict[str, Any]]:
    """Full calibration pipeline."""
    human_rows = parse_book1(book1_path)
    auto_index = (
        load_auto_export_index(auto_export_path) if auto_export_path else None
    )
    rows = build_calibration_rows(human_rows, bdt_folder, auto_index)
    profile = build_human_aligned_profile(rows)
    return rows, profile
