"""
BDT Validator — run validation rules against parsed BDT data.

Cross-references BDT (Battery Discharge Test) reports against loaded alarm
data to detect fraudulent or incorrect test submissions.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
import re

import pandas as pd
import numpy as np

try:
    from .parser import BDTData
    from ..constants import (
        BDT_DEFAULT_TOLERANCE,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_REQUIRED_PHOTO_COUNT,
        BDT_POWER_TIMING_TOLERANCE_MIN,
        BDT_COMPLETION_MINUTES,
        BDT_SIZING_TOLERANCE_MINUTES,
        BDT_STRING_AMPERE_TOLERANCE_A,
    )
except ImportError:
    from alarm_app.bdt.parser import BDTData
    from alarm_app.constants import (
        BDT_DEFAULT_TOLERANCE,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_REQUIRED_PHOTO_COUNT,
        BDT_POWER_TIMING_TOLERANCE_MIN,
        BDT_COMPLETION_MINUTES,
        BDT_SIZING_TOLERANCE_MINUTES,
        BDT_STRING_AMPERE_TOLERANCE_A,
    )


@dataclass
class RuleResult:
    """Result of a single validation rule."""
    rule_id: str
    rule_name: str
    passed: bool | None  # None = cannot evaluate (missing data)
    verdict: str         # "Accepted", "Rejected", "Revise", "N/A"
    detail: str = ""     # Human-readable explanation


@dataclass
class ValidationResult:
    """Full validation result for one BDT file."""
    filename: str
    site_code: str
    test_date: str
    overall: str  # "Accepted", "Rejected", "Revise"
    rules: list[RuleResult] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    bdt_data: BDTData | None = None  # parsed source data for detail view


def validate_bdt(bdt: BDTData, alarm_df: pd.DataFrame | None,
                 tolerance: float = BDT_DEFAULT_TOLERANCE,
                 health_pct: float = BDT_DEFAULT_HEALTH_PCT,
                 power_timing_tol: float | None = None) -> ValidationResult:
    """Validate a parsed BDT file against alarm data.

    Args:
        bdt: Parsed BDT data from bdt_parser.
        alarm_df: Loaded alarm DataFrame (may be None if no alarms loaded).
        tolerance: Fractional tolerance for duration matching (0.15 = 15%).

    Returns:
        ValidationResult with per-rule verdicts and overall verdict.
    """
    result = ValidationResult(
        filename=bdt.filename,
        site_code=bdt.site_code,
        test_date=(bdt.test_date.strftime("%Y-%m-%d")
                   if bdt.test_date else "Unknown"),
        overall="Accepted",
        parse_errors=list(bdt.errors),
        bdt_data=bdt,
    )

    battery_skip_reason = _battery_skip_reason(bdt)

    result.rules.append(_rule_1_photos(bdt))
    if battery_skip_reason:
        result.rules.extend(_skipped_battery_rules(battery_skip_reason))
    else:
        result.rules.append(_rule_2_power_alarm_match(bdt, alarm_df, tol_override=power_timing_tol))
        result.rules.append(_rule_3_string_vs_busbar(bdt))
        result.rules.append(_rule_5_start_ampere(bdt))
        result.rules.append(_rule_6_end_voltage(bdt, health_pct))
        result.rules.append(_rule_7_inverse_relationship(bdt))
        result.rules.append(_rule_8_backup_time(bdt, health_pct, tolerance=tolerance))
        result.rules.append(_rule_9_discharge_current_tolerance(bdt))
    result.rules.append(_rule_10_door_alarm_match(bdt, alarm_df))
    result.rules.append(_rule_11_summary_checklist(bdt))

    # Overall verdict
    failed = [r for r in result.rules if r.verdict == "Rejected"]
    revise = [r for r in result.rules if r.verdict == "Revise"]
    no_alarm_data_na = any(
        r.verdict == "N/A" and "no alarm data" in str(r.detail).lower()
        for r in result.rules
    )

    if failed:
        result.overall = "Rejected"
    elif revise:
        result.overall = "Revise"
    elif no_alarm_data_na:
        # If alarm-dependent rules are not evaluable due to missing alarm data,
        # surface as Revise (incomplete evidence), not Accepted.
        result.overall = "Revise"
    else:
        result.overall = "Accepted"

    return result


# ── Rule implementations ──────────────────────────────────


def _clean_battery_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _battery_key(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _battery_skip_reason(bdt: BDTData) -> str:
    num_batteries = getattr(bdt, "num_batteries", None)
    if num_batteries == 0:
        return "No battery installed"

    summary_data = dict(getattr(bdt, "summary_data", {}) or {})
    battery_count_keys = {
        _battery_key(key)
        for key in ("No of Batteries", "No. of Batteries", "Number of Batteries", "# of Batteries")
    }
    for key, raw in summary_data.items():
        if _battery_key(key) not in battery_count_keys:
            continue
        try:
            if raw is not None and float(str(raw).strip().replace(",", ".")) == 0:
                return "No battery installed"
        except (TypeError, ValueError):
            pass

    texts = [
        getattr(bdt, "battery_brand", ""),
        getattr(bdt, "battery_model", ""),
        *summary_data.values(),
    ]
    for text in (_clean_battery_text(value) for value in texts):
        if not text:
            continue
        if re.search(r"\b(no|without|missing)\s+batter(?:y|ies)\b", text):
            return "No battery installed"
        if re.search(r"\bbatter(?:y|ies)\s+(missing|not installed|removed)\b", text):
            return "No battery installed"
        if "battery" in text or "batteries" in text:
            if re.search(r"\b(faulty|fault|bad|damaged|dead|defective)\b", text):
                return "Faulty battery reported"
    return ""


def bdt_battery_status(bdt: BDTData | None) -> str:
    if bdt is None:
        return "--"
    reason = _battery_skip_reason(bdt)
    if reason.startswith("No battery"):
        return "No Battery"
    if reason.startswith("Faulty battery"):
        return "Faulty Battery"
    return "Has Battery"


def _skipped_battery_rules(reason: str) -> list[RuleResult]:
    rules = (
        ("R2", "Power Alarm + Duration"),
        ("R3", "String vs Bus Bar Ampere"),
        ("R5", "Starting I-Battery ampere"),
        ("R6", "End Voltage Range"),
        ("R7", "V/A Inverse"),
        ("R8", "Sizing vs Actual"),
        ("R9", "Discharge Current Tolerance"),
    )
    return [
        RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            passed=None,
            verdict="Skipped",
            detail=f"{reason}; battery-dependent rule not considered",
        )
        for rule_id, rule_name in rules
    ]


def _rule_1_photos(bdt: BDTData) -> RuleResult:
    """R1: Photo completeness — category-based validation with count fallback.

    Decision tree:
    1. deferred + no slots  → count-based fallback
    2. low mapping confidence → N/A
    3. photo_categories_found populated → category-based path
    4. slots present but no categories → count-based path
    5. no slots → count-based fallback on photo_count integer
    """
    detection_mode = getattr(bdt, "photo_detection_mode", "") or ""
    photo_categories_found: list[str] = list(getattr(bdt, "photo_categories_found", []) or [])
    mapping_confidence: str = getattr(bdt, "photo_mapping_confidence", "") or ""
    required_photo_count = int(
        getattr(bdt, "required_photo_count", BDT_REQUIRED_PHOTO_COUNT)
        or BDT_REQUIRED_PHOTO_COUNT
    )
    ai_flagged_labels = [
        str(getattr(slot, "label", "") or getattr(slot, "category", "") or "photo")
        for slot in list(getattr(bdt, "photo_slots", []) or [])
        if getattr(slot, "image_data", None)
        and str(
            (
                dict(getattr(slot, "verification", {}) or {})
                .get("synthid", {})
                .get("status", "")
            )
            or ""
        ).strip().lower() == "detected"
    ]

    if ai_flagged_labels:
        sample = ", ".join(ai_flagged_labels[:3])
        if len(ai_flagged_labels) > 3:
            sample = f"{sample}, +{len(ai_flagged_labels) - 3} more"
        return RuleResult(
            rule_id="R1",
            rule_name="Photos",
            passed=False,
            verdict="Rejected",
            detail=f"AI-generated photo signal detected (SynthID): {sample}",
        )

    # ── Branch 1: deferred mode with no slots → count-based fallback ──────────
    if detection_mode == "deferred" and not bdt.photo_slots:
        count = int(bdt.photo_count or 0)
        if count == 0:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=False, verdict="Rejected",
                detail="No photos embedded in file",
            )
        if count >= required_photo_count:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=True, verdict="Accepted",
                detail=f"Photo count: {count}/{required_photo_count}",
            )
        missing_n = required_photo_count - count
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Revise",
            detail=f"Photo count: {count}/{required_photo_count} (missing {missing_n})",
        )

    # ── Branch 2: low confidence → N/A ────────────────────────────────────────
    if mapping_confidence == "low":
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=None, verdict="N/A",
            detail="Photo mapping confidence too low to evaluate categories",
        )

    # ── Branch 3: category-based path ─────────────────────────────────────────
    if photo_categories_found:
        required_cats: list[str] = list(
            getattr(bdt, "required_photo_categories", []) or ["rectifier", "batteries"]
        ) or ["rectifier", "batteries"]
        missing = [c for c in required_cats if c not in photo_categories_found]
        if not missing:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=True, verdict="Accepted",
                detail=f"Required categories present: {sorted(photo_categories_found)}",
            )
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Rejected",
            detail=(
                f"Missing required photo categories: {missing}; "
                f"found: {photo_categories_found}"
            ),
        )

    # ── Branch 4: slots present, no category metadata → count-based ───────────
    if bdt.photo_slots:
        total_slots = len(bdt.photo_slots)
        filled_slots = sum(
            1 for slot in bdt.photo_slots if bool(getattr(slot, "image_data", None))
        )
        if filled_slots == 0:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=False, verdict="Rejected",
                detail=f"No photos embedded in file (0/{total_slots} slots filled)",
            )
        if filled_slots >= required_photo_count:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=True, verdict="Accepted",
                detail=f"Photo count: {filled_slots}/{required_photo_count}",
            )
        missing_n = required_photo_count - filled_slots
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Revise",
            detail=f"Photo count: {filled_slots}/{required_photo_count} (missing {missing_n})",
        )

    # ── Branch 5: no slots at all → integer count fallback ────────────────────
    count = int(bdt.photo_count or 0)
    if count == 0:
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Rejected",
            detail="No photos embedded in file",
        )
    if count >= required_photo_count:
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=True, verdict="Accepted",
            detail=f"Photo count: {count}/{required_photo_count}",
        )
    missing_n = required_photo_count - count
    return RuleResult(
        rule_id="R1", rule_name="Photos",
        passed=False, verdict="Revise",
        detail=f"Photo count: {count}/{required_photo_count} (missing {missing_n})",
    )


def _normalize_alarm_datetimes(alarm_df: pd.DataFrame) -> pd.DataFrame:
    """Ensure occurred_on/cleared_on columns are datetime when present."""
    normalized = alarm_df
    for col in ("occurred_on", "cleared_on"):
        if col in normalized.columns and not pd.api.types.is_datetime64_any_dtype(normalized[col]):
            if normalized is alarm_df:
                normalized = normalized.copy()
            normalized[col] = pd.to_datetime(normalized[col], errors="coerce", format="mixed")
    return normalized


def _find_power_alarms(alarm_df: pd.DataFrame, site_code: str) -> pd.DataFrame:
    """Find Power alarms for a site, with file_source fallback if unconfigured."""
    required_cols = {"site_id", "occurred_on"}
    if not required_cols.issubset(alarm_df.columns):
        return alarm_df.iloc[0:0]

    alarm_df = _normalize_alarm_datetimes(alarm_df)
    site_mask = (
        alarm_df["site_id"].astype(str).str.strip().str.upper()
        == site_code.strip().upper()
    ) & (alarm_df["occurred_on"].notna())

    power = alarm_df.iloc[0:0]
    if "alarm_category" in alarm_df.columns:
        cat_mask = site_mask & (
            alarm_df["alarm_category"].astype(str).str.strip().str.lower() == "power"
        )
        power = alarm_df[cat_mask]
        if not power.empty:
            return power

    # Fallback: if no alarms classified as Power, use file_source keyword
    if "file_source" in alarm_df.columns:
        src_mask = site_mask & (
            alarm_df["file_source"].astype(str).str.contains(
                "power", case=False, na=False))
        return alarm_df[src_mask]

    return power


def _find_down_alarms(alarm_df: pd.DataFrame, site_code: str) -> pd.DataFrame:
    """Find Down alarms for a site using category/name/source signals."""
    required_cols = {"site_id", "occurred_on"}
    if not required_cols.issubset(alarm_df.columns):
        return alarm_df.iloc[0:0]

    alarm_df = _normalize_alarm_datetimes(alarm_df)
    site_mask = (
        alarm_df["site_id"].astype(str).str.strip().str.upper()
        == site_code.strip().upper()
    ) & (alarm_df["occurred_on"].notna())

    down_mask = pd.Series(False, index=alarm_df.index)
    if "alarm_category" in alarm_df.columns:
        down_mask = down_mask | (
            alarm_df["alarm_category"].astype(str).str.strip().str.lower() == "down"
        )
    if "alarm_name" in alarm_df.columns:
        down_mask = down_mask | (
            alarm_df["alarm_name"].astype(str).str.contains("down", case=False, na=False)
        )
    if "file_source" in alarm_df.columns:
        down_mask = down_mask | (
            alarm_df["file_source"].astype(str).str.contains("down", case=False, na=False)
        )
    return alarm_df[site_mask & down_mask]


def _parse_test_time(raw_time) -> time | None:
    """Parse BDT test time from HH:MM or HH:MM:SS formats."""
    if raw_time is None:
        return None
    try:
        if pd.isna(raw_time):
            return None
    except Exception:
        pass
    if isinstance(raw_time, datetime):
        return raw_time.time().replace(microsecond=0)
    if hasattr(raw_time, "hour") and hasattr(raw_time, "minute"):
        # datetime.time or pandas Timestamp-like
        try:
            return raw_time.replace(microsecond=0)
        except TypeError:
            return datetime(
                2000, 1, 1, raw_time.hour, raw_time.minute,
                getattr(raw_time, "second", 0)
            ).time()

    text = str(raw_time).strip()
    if not text or text.lower() == "nan":
        return None
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    text = re.sub(r"\s+", " ", text).strip()

    ampm_normalized = text.replace(".", "")

    for fmt in (
        "%H:%M:%S", "%H:%M",
        "%I:%M:%S%p", "%I:%M:%S %p",   # 12-hour with AM/PM (e.g. "12:31:10PM")
        "%I:%M%p", "%I:%M %p",          # 12-hour without seconds
    ):
        for candidate in (text, ampm_normalized):
            try:
                return datetime.strptime(candidate, fmt).time()
            except ValueError:
                continue

    # Excel sometimes serializes times as a datetime-like string.
    try:
        ts = pd.to_datetime(text, errors="coerce")
        if not pd.isna(ts):
            return ts.to_pydatetime().time().replace(microsecond=0)
    except Exception:
        pass

    # Excel numeric time fraction fallback (e.g. 0.583333 => 14:00:00).
    try:
        numeric = float(text)
        if 0.0 <= numeric < 1.0:
            secs = int(round(numeric * 24 * 60 * 60))
            return (datetime(2000, 1, 1) + timedelta(seconds=secs)).time()
    except (TypeError, ValueError):
        pass

    return None


def _build_test_window(bdt: BDTData) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if bdt.test_date is None:
        return None, None
    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return None, None

    start_time = _parse_test_time(getattr(bdt, "time_in", None))
    if start_time is None:
        return None, None

    start_ts = test_date + pd.Timedelta(
        hours=start_time.hour,
        minutes=start_time.minute,
        seconds=start_time.second,
    )

    end_time = _parse_test_time(getattr(bdt, "time_out", None))
    if end_time is not None:
        end_ts = test_date + pd.Timedelta(
            hours=end_time.hour,
            minutes=end_time.minute,
            seconds=end_time.second,
        )
        if end_ts < start_ts:
            end_ts += pd.Timedelta(days=1)
        return start_ts, end_ts

    discharge_minutes = _max_reached_discharge_minutes(bdt)
    if discharge_minutes is not None:
        return start_ts, start_ts + pd.Timedelta(minutes=discharge_minutes)

    return start_ts, None


def _max_reached_discharge_minutes(bdt: BDTData) -> float | None:
    """Return max discharge-minute label that has at least one real reading."""
    max_mins = 0.0
    for label, v, a in bdt.discharge_readings:
        if v is None and a is None:
            continue
        try:
            mins = _parse_discharge_minute_label(label)
        except (ValueError, TypeError, IndexError):
            continue
        if mins is None:
            continue
        if mins > max_mins:
            max_mins = mins
    return max_mins if max_mins > 0 else None


def _parse_discharge_minute_label(label) -> float | None:
    """Extract the minute value from a discharge row label."""
    if label is None:
        return None

    text = str(label).strip()
    if not text:
        return None

    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None

    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _lithium_cadence_violation(bdt: BDTData) -> str | None:
    """Return a lithium cadence violation message, or None when valid/not applicable."""
    readings: list[tuple[int, float, float | None, float | None]] = []
    threshold_idx: int | None = None

    for idx, (label, voltage, ampere) in enumerate(bdt.discharge_readings):
        minute = _parse_discharge_minute_label(label)
        if minute is None:
            continue

        has_reading = voltage is not None or ampere is not None
        if not has_reading:
            continue

        minute_i = int(round(minute))
        readings.append((idx, minute_i, voltage, ampere))
        if threshold_idx is None and voltage is not None and voltage <= 47.0:
            threshold_idx = len(readings) - 1

    if threshold_idx is None:
        return None

    threshold_minute = readings[threshold_idx][1]
    expected_minute = threshold_minute + 5

    for _, minute, _, _ in readings[threshold_idx + 1:]:
        if minute != expected_minute:
            return (
                f"Lithium cadence violation after 47V at {threshold_minute} min: "
                f"expected reading at {expected_minute} min, found {minute} min"
            )
        expected_minute += 5

    return None


def _rule_2_power_alarm_match(bdt: BDTData,
                               alarm_df: pd.DataFrame | None,
                               tol_override: float | None = None) -> RuleResult:
    """R2: Unified Power timing + duration check (Power→Cleared or Power→Down)."""
    tol_min = float(tol_override if tol_override is not None else BDT_POWER_TIMING_TOLERANCE_MIN)
    tol = pd.Timedelta(minutes=tol_min)

    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=None, verdict="N/A",
            detail="No alarm data loaded",
        )
    if bdt.test_date is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail="No test date found in BDT file",
        )

    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail=f"Invalid test date: {bdt.test_date!r}",
        )

    discharge_minutes = _max_reached_discharge_minutes(bdt)
    if discharge_minutes is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=("Cannot validate timing: no reached minute found in discharge table "
                    "(need at least one row with V or A reading)"),
        )

    start_time = _parse_test_time(bdt.time_in)
    if start_time is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=("Cannot validate alarm timing: invalid time_in "
                    "(expected HH:MM, HH:MM:SS, or AM/PM format)"),
        )

    start_ts = test_date + pd.Timedelta(
        hours=start_time.hour, minutes=start_time.minute, seconds=start_time.second
    )
    expected_end_ts = start_ts + pd.Timedelta(minutes=discharge_minutes)

    power = _find_power_alarms(alarm_df, bdt.site_code)
    if power.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail=f"No Power alarms found for site {bdt.site_code}",
        )

    # Check if any Power alarm occurred on the test date
    power_dates = power["occurred_on"].dt.normalize()
    same_date = power[power_dates == test_date]
    if same_date.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail=(f"No Power alarm on {test_date.date()} for site "
                    f"{bdt.site_code}. Power was never cut from the grid."),
        )

    same_date = same_date.copy()
    same_date["start_diff_min"] = (
        (same_date["occurred_on"] - start_ts).abs() / pd.Timedelta(minutes=1)
    )
    start_candidates = same_date[same_date["start_diff_min"] <= tol_min]
    if start_candidates.empty:
        min_start = same_date["start_diff_min"].min()
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail=(f"No Power alarm start match within ±{tol_min:.0f} min "
                    f"(closest start Δ={min_start:.1f} min)"),
        )

    down = _find_down_alarms(alarm_df, bdt.site_code)
    if not down.empty:
        down = down.copy()
        down = down[down["occurred_on"].notna()]
        down = down[(down["occurred_on"] >= (start_ts - tol)) &
                    (down["occurred_on"] <= (expected_end_ts + tol))]

    attempts = []
    for _, power_row in start_candidates.iterrows():
        power_start = power_row["occurred_on"]
        start_diff_min = float(power_row["start_diff_min"])

        power_clear = power_row.get("cleared_on", pd.NaT)
        if pd.notna(power_clear) and power_clear >= power_start:
            alarm_duration_min = float(
                (power_clear - power_start) / pd.Timedelta(minutes=1)
            )
            end_diff_min = float(
                abs(power_clear - expected_end_ts) / pd.Timedelta(minutes=1)
            )
            duration_diff_min = abs(alarm_duration_min - discharge_minutes)
            attempts.append({
                "path": "Power→Cleared",
                "start_diff_min": start_diff_min,
                "end_diff_min": end_diff_min,
                "duration_min": alarm_duration_min,
                "duration_diff_min": duration_diff_min,
            })

        if not down.empty:
            down_after = down[down["occurred_on"] >= power_start]
            for down_ts in down_after["occurred_on"]:
                alarm_duration_min = float(
                    (down_ts - power_start) / pd.Timedelta(minutes=1)
                )
                end_diff_min = float(
                    abs(down_ts - expected_end_ts) / pd.Timedelta(minutes=1)
                )
                duration_diff_min = abs(alarm_duration_min - discharge_minutes)
                attempts.append({
                    "path": "Power→Down",
                    "start_diff_min": start_diff_min,
                    "end_diff_min": end_diff_min,
                    "duration_min": alarm_duration_min,
                    "duration_diff_min": duration_diff_min,
                })

    if not attempts:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=("No usable end event found for matched Power start "
                    "(need Power clear or Down alarm)"),
        )

    for a in attempts:
        a["passed"] = (
            a["start_diff_min"] <= tol_min
            and a["end_diff_min"] <= tol_min
            and a["duration_diff_min"] <= tol_min
        )

    passed_attempts = [a for a in attempts if a["passed"]]
    if passed_attempts:
        best = min(
            passed_attempts,
            key=lambda a: (a["duration_diff_min"], a["end_diff_min"], a["start_diff_min"]),
        )
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=True, verdict="Accepted",
            detail=(f"{best['path']} matched test window: "
                    f"start Δ={best['start_diff_min']:.1f} min, "
                    f"end Δ={best['end_diff_min']:.1f} min, "
                    f"alarm duration={best['duration_min']:.1f} min vs "
                    f"discharge-table max {discharge_minutes:.1f} min "
                    f"(duration Δ={best['duration_diff_min']:.1f} min, "
                    f"tolerance ±{tol_min:.0f} min)"),
        )

    best = min(
        attempts,
        key=lambda a: (a["duration_diff_min"], a["end_diff_min"], a["start_diff_min"]),
    )
    return RuleResult(
        rule_id="R2", rule_name="Power Alarm + Duration",
        passed=False, verdict="Rejected",
        detail=(f"No Power timing/duration match within ±{tol_min:.0f} min. "
                f"Closest path {best['path']}: "
                f"start Δ={best['start_diff_min']:.1f} min, "
                f"end Δ={best['end_diff_min']:.1f} min, "
                f"duration Δ={best['duration_diff_min']:.1f} min "
                f"(alarm {best['duration_min']:.1f} min vs discharge-table max "
                f"{discharge_minutes:.1f} min)"),
    )



def _rule_5_start_ampere(bdt: BDTData) -> RuleResult:
    """R5: Starting I-Battery ampere should be approximately 0A."""
    if bdt.ibat_before_test is None:
        return RuleResult(
            rule_id="R5", rule_name="Starting I-Battery ampere",
            passed=None, verdict="N/A",
            detail="Starting I-Battery ampere not found in file",
        )

    passed = abs(bdt.ibat_before_test) < 0.5
    return RuleResult(
        rule_id="R5", rule_name="Starting I-Battery ampere",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Starting I-Battery ampere: {bdt.ibat_before_test} A "
                f"(approximate 0A threshold: |I| < 0.5A)"),
    )


def _rule_6_end_voltage(bdt: BDTData, health_pct: float) -> RuleResult:
    """R6: Completion OR rule — discharge >=180 min OR end voltage 45–47 V."""
    if bdt.end_voltage is None:
        return RuleResult(
            rule_id="R6", rule_name="End Voltage Range",
            passed=None, verdict="N/A",
            detail="End voltage not found in file",
        )

    reported = bdt.discharge_minutes
    in_voltage_range = 45.0 <= bdt.end_voltage <= 47.0
    passed = reported >= 180 or in_voltage_range
    return RuleResult(
        rule_id="R6", rule_name="End Voltage Range",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Discharge: {reported:.0f} min (target >=180) OR "
                f"end voltage: {bdt.end_voltage}V (range: 45.0-47.0V)"),
    )


def _rule_7_inverse_relationship(bdt: BDTData) -> RuleResult:
    """R7: Voltage and ampere have inverse relationship throughout test."""
    # Only use readings where both V and A are present to keep alignment
    pairs = [(v, a) for _, v, a in bdt.discharge_readings
             if v is not None and a is not None]

    if len(pairs) < 3:
        return RuleResult(
            rule_id="R7", rule_name="V/A Inverse",
            passed=None, verdict="N/A",
            detail=f"Not enough paired readings ({len(pairs)}, need 3+)",
        )

    v_arr = np.array([v for v, _ in pairs])
    a_arr = np.array([a for _, a in pairs])

    # Avoid NumPy runtime warnings from corrcoef when one series is constant.
    if np.std(v_arr) == 0 or np.std(a_arr) == 0:
        return RuleResult(
            rule_id="R7", rule_name="V/A Inverse",
            passed=None, verdict="N/A",
            detail="Cannot compute correlation (constant values?)",
        )

    # Check correlation — should be negative (inverse)
    corr = np.corrcoef(v_arr, a_arr)[0, 1]

    if np.isnan(corr):
        return RuleResult(
            rule_id="R7", rule_name="V/A Inverse",
            passed=None, verdict="N/A",
            detail="Cannot compute correlation (constant values?)",
        )

    # Negative correlation = inverse relationship = good
    passed = corr < 0
    return RuleResult(
        rule_id="R7", rule_name="V/A Inverse",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Voltage-current correlation: {corr:.3f} "
                f"({'expected inverse trend' if corr < 0 else 'unexpected direct trend'})"),
    )


def _is_lithium(brand: str) -> bool:
    """Check if battery brand indicates lithium chemistry."""
    return "lith" in str(brand or "").lower()


def _theoretical_backup_minutes(bdt: BDTData, health_pct: float) -> float | None:
    """Calculate theoretical backup time in minutes from battery specs.

    Formula: BT(hrs) = (Battery_AH × Battery_V × Num_Strings × Efficiency) / Load_W
    Where Load_W = Bus_Bar_V × Bus_Bar_A from "Before disconnecting Rectifier".
    Returns minutes (×60).
    """
    if (bdt.battery_ah is None or bdt.battery_voltage is None
            or bdt.num_strings is None):
        return None

    # Load = bus bar readings at "Before disconnecting Rectifier"
    load_v = bdt.start_voltage
    load_a = bdt.start_ampere
    if load_v is None or load_a is None or load_v <= 0 or load_a <= 0:
        return None
    load_w = load_v * load_a

    efficiency = 1.0 if _is_lithium(bdt.battery_brand) else health_pct
    capacity_wh = bdt.battery_ah * bdt.battery_voltage * bdt.num_strings * efficiency
    return (capacity_wh / load_w) * 60  # convert hours to minutes


def _rule_8_backup_time(bdt: BDTData, health_pct: float,
                        tolerance: float = BDT_DEFAULT_TOLERANCE) -> RuleResult:
    """R8: Sizing-vs-actual discharge time consistency check (never N/A).

    Business rules:
    - The test target is capped at 180 minutes.
    - If theoretical duration is >180, accept only when actual discharge >=180.
    - Otherwise (theoretical <=180), compare actual vs theoretical with a
      fractional tolerance window (``theoretical_mins * tolerance``), floored at
      ``BDT_SIZING_TOLERANCE_MINUTES`` so very short tests never get tighter
      than the historical default.
    """
    reported = float(bdt.discharge_minutes or 0.0)
    theoretical_mins = _theoretical_backup_minutes(bdt, health_pct)

    if theoretical_mins is None:
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=False, verdict="Rejected",
            detail=("Cannot compute theoretical duration (missing/invalid AH, voltage, "
                    "strings, or starting load readings)"),
        )

    # Cap-driven branch: batteries theoretically needing >180 min are expected to
    # hit/exceed the 180-min test cap.
    if theoretical_mins > 180.0:
        short_by = max(0.0, 180.0 - reported)
        passed = reported >= 180.0
        if passed:
            detail = (f"Theoretical: {theoretical_mins:.0f} min (>180 cap), "
                      f"actual: {reported:.0f} min (reached cap)")
        else:
            detail = (f"Theoretical: {theoretical_mins:.0f} min (>180 cap), "
                      f"actual: {reported:.0f} min, short by {short_by:.1f} min to 180")
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=passed,
            verdict="Accepted" if passed else "Rejected",
            detail=detail,
        )

    # Normal branch: compare against theoretical target with a configurable
    # fractional tolerance, floored at the historical 15-min default so very
    # short theoretical windows still get a reasonable allowance.
    tol_min = max(theoretical_mins * tolerance, float(BDT_SIZING_TOLERANCE_MINUTES))
    delta = abs(theoretical_mins - reported)
    passed = delta <= tol_min
    return RuleResult(
        rule_id="R8", rule_name="Sizing vs Actual",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Theoretical: {theoretical_mins:.0f} min, actual: {reported:.0f} min, "
                f"difference: {delta:.1f} min (limit: {tol_min:.1f} min, "
                f"{tolerance * 100:.0f}% of theoretical)"),
    )


def _rule_9_discharge_current_tolerance(bdt: BDTData) -> RuleResult:
    """R9: Discharge current should stay within ±1A from baseline."""
    readings = [(label, a) for label, _, a in bdt.discharge_readings if a is not None]
    if len(readings) < 2:
        return RuleResult(
            rule_id="R9", rule_name="Discharge Current Tolerance",
            passed=None, verdict="N/A",
            detail=f"Insufficient discharge current readings ({len(readings)}, need 2+)",
        )

    baseline_label, baseline = readings[0]
    for label, current in readings[1:]:
        diff = abs(current - baseline)
        if diff > 1.0:
            return RuleResult(
                rule_id="R9", rule_name="Discharge Current Tolerance",
                passed=False, verdict="Rejected",
                detail=(f"Baseline at {baseline_label}: {baseline:.2f}A; "
                        f"{label}: {current:.2f}A (|Δ|={diff:.2f}A > 1.0A)"),
            )

    return RuleResult(
        rule_id="R9", rule_name="Discharge Current Tolerance",
        passed=True, verdict="Accepted",
        detail=f"All discharge currents stayed within ±1.0A from baseline ({baseline:.2f}A)",
    )


def _find_door_alarms(
    alarm_df: pd.DataFrame,
    site_code: str,
    test_date: pd.Timestamp,
    window_start: pd.Timestamp | None = None,
    window_end: pd.Timestamp | None = None,
    strict_window: bool = False,
) -> pd.DataFrame:
    """Find same-site door alarms, preferring those inside the BDT test window."""
    required_cols = {"site_id", "occurred_on"}
    if not required_cols.issubset(alarm_df.columns):
        return alarm_df.iloc[0:0]

    alarm_df = _normalize_alarm_datetimes(alarm_df)
    site_mask = (
        alarm_df["site_id"].astype(str).str.strip().str.upper()
        == site_code.strip().upper()
    )
    date_mask = alarm_df["occurred_on"].dt.normalize() == test_date

    category_mask = pd.Series(False, index=alarm_df.index)
    if "alarm_category" in alarm_df.columns:
        category_mask = (
            alarm_df["alarm_category"].astype(str).str.strip().str.lower() == "door"
        )

    name_mask = pd.Series(False, index=alarm_df.index)
    if "alarm_name" in alarm_df.columns:
        name_mask = alarm_df["alarm_name"].astype(str).str.contains("door", case=False, na=False)

    source_mask = pd.Series(False, index=alarm_df.index)
    if "file_source" in alarm_df.columns:
        source_mask = alarm_df["file_source"].astype(str).str.contains("door", case=False, na=False)

    door_mask = category_mask | name_mask | source_mask
    matches = alarm_df[site_mask & date_mask & door_mask]
    if matches.empty or window_start is None:
        return matches

    window_matches = matches[matches["occurred_on"] >= window_start]
    if window_end is not None:
        window_matches = window_matches[window_matches["occurred_on"] <= window_end]
    if not window_matches.empty:
        return window_matches
    return matches.iloc[0:0] if strict_window else matches


def _rule_10_door_alarm_match(bdt: BDTData,
                              alarm_df: pd.DataFrame | None) -> RuleResult:
    """R10: Same-site/date Door alarm must exist."""
    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R10", rule_name="Door Alarm Condition",
            passed=None, verdict="N/A",
            detail="No alarm data loaded",
        )

    if bdt.test_date is None:
        return RuleResult(
            rule_id="R10", rule_name="Door Alarm Condition",
            passed=False, verdict="Revise",
            detail="Cannot validate door alarm condition: missing test date",
        )

    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return RuleResult(
            rule_id="R10", rule_name="Door Alarm Condition",
            passed=False, verdict="Revise",
            detail=f"Cannot validate door alarm condition: invalid test date {bdt.test_date!r}",
        )

    window_start, window_end = _build_test_window(bdt)
    doors = _find_door_alarms(
        alarm_df,
        bdt.site_code,
        test_date,
        window_start,
        window_end,
        strict_window=window_start is not None,
    )
    if doors.empty:
        return RuleResult(
            rule_id="R10", rule_name="Door Alarm Condition",
            passed=False, verdict="Rejected",
            detail=(f"No Door alarm found for site {bdt.site_code} during "
                    f"the test window on {test_date.date()}"),
        )

    return RuleResult(
        rule_id="R10", rule_name="Door Alarm Condition",
        passed=True, verdict="Accepted",
        detail=(f"Door alarm found for site {bdt.site_code} on {test_date.date()} "
                f"({len(doors)} match(es){' within test window' if window_start is not None else ''})"),
    )


def _rule_3_string_vs_busbar(bdt: BDTData) -> RuleResult:
    """R3: Rectifier amp minus summed string amps must stay between -3A and 0A."""
    if not bdt.string_discharge_readings or not bdt.discharge_readings:
        return RuleResult(
            rule_id="R3", rule_name="String vs Bus Bar Ampere",
            passed=None, verdict="N/A",
            detail="No per-string discharge data available",
        )

    tolerance = BDT_STRING_AMPERE_TOLERANCE_A
    checked = 0

    # string_discharge_readings[0] is the "Before disconnecting" row,
    # while discharge_readings starts at the first timed row (10 min, etc.).
    # Slice off index 0 to align the two lists.
    string_readings = bdt.string_discharge_readings[1:]

    for dr, sr in zip(bdt.discharge_readings, string_readings):
        bus_a = dr[2]  # bus bar ampere
        string_pairs = sr
        string_amps = [a for _, a in string_pairs if a is not None]

        if bus_a is None or not string_amps:
            continue

        string_sum = sum(string_amps)
        diff = bus_a - string_sum
        checked += 1

        if diff > 0 or diff < -tolerance:
            return RuleResult(
                rule_id="R3", rule_name="String vs Bus Bar Ampere",
                passed=False, verdict="Rejected",
                detail=(f"Batteries Amp not matched with the rectifier summation Amp "
                        f"at {dr[0]}: rectifier={bus_a:.2f}A, "
                        f"strings_sum={string_sum:.2f}A "
                        f"(E-(G+I)={diff:.2f}A, required -{tolerance:.1f}A to 0.0A)"),
            )

    if checked == 0:
        return RuleResult(
            rule_id="R3", rule_name="String vs Bus Bar Ampere",
            passed=None, verdict="N/A",
            detail="No valid paired readings found",
        )

    return RuleResult(
        rule_id="R3", rule_name="String vs Bus Bar Ampere",
        passed=True, verdict="Accepted",
        detail=(f"All {checked} time points within tolerance "
                f"(E-(G+I) between -{tolerance:.1f}A and 0.0A)"),
    )


def _normalize_for_comparison(val: str) -> str:
    """Strip units, whitespace, and normalize for comparison."""
    if val is None:
        return ""
    s = str(val).strip().lower()
    # Remove "none" / "na" / "n/a"
    if s in ("none", "na", "n/a", "nan", "--", "-", ""):
        return ""
    # Strip common units only for numeric-like strings.
    match = re.match(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(?:ah|vdc|mins?|min|v|a)?\s*$", s)
    if match:
        return match.group(1)
    s = " ".join(s.split())
    return s


def _values_match(bdt_val: str, summary_val: str, field_name: str) -> bool:
    """Compare a BDT sheet value against a Summary sheet value with tolerance."""
    a = _normalize_for_comparison(bdt_val)
    b = _normalize_for_comparison(summary_val)
    if not a and not b:
        return True  # both empty = match
    if not a or not b:
        return False  # one empty, one not = mismatch
    if field_name.strip().lower() == "test date":
        try:
            def _parse_date(text: str):
                ts = pd.to_datetime(text, errors="coerce", format="%Y-%m-%d")
                if pd.isna(ts):
                    ts = pd.to_datetime(text, errors="coerce", dayfirst=True)
                if pd.isna(ts):
                    ts = pd.to_datetime(text, errors="coerce")
                return ts

            da = _parse_date(a)
            db = _parse_date(b)
            if not pd.isna(da) and not pd.isna(db):
                return pd.Timestamp(da).normalize() == pd.Timestamp(db).normalize()
        except Exception:
            pass
    # Try numeric comparison with epsilon
    try:
        fa, fb = float(a), float(b)
        return abs(fa - fb) < 0.5
    except (ValueError, TypeError):
        pass
    # String: case-insensitive containment (Summary may abbreviate or expand)
    return a in b or b in a


_SUMMARY_KEY_ALIASES = {
    "Short Code": ("Short Code", "Site Code"),
    "PLVD Value": ("PLVD Value", "PLD Value"),
    "Rectifier Brand": ("Rectifier Brand",),
    "# of Modules": ("# of Modules", "Number of Modules", "No of Modules"),
    "Battery Brand": ("Battery Brand",),
    "Battery Volt": ("Battery Volt", "Battery Voltage"),
    "No of String": ("No of String", "No of Strings", "Number of Strings"),
    "No of Batteries": ("No of Batteries", "No of Batteries ", "Number of Batteries"),
    "Start Volt": ("Start Volt", "Start Voltage"),
    "Start Amp": ("Start Amp",),
    "End Volt": ("End Volt", "End Voltage"),
    "End Amp": ("End Amp",),
    "Discharge time( Mins)": ("Discharge time( Mins)", "Discharge Time (mins)", "Discharge Time (min)"),
    "Test Date": ("Test Date",),
}


def _normalize_summary_key(key) -> str:
    return "".join(ch for ch in str(key or "").strip().lower() if ch.isalnum())


def _summary_lookup_value(summary_data: dict[str, str], canonical_key: str) -> str:
    normalized = {}
    for key, value in summary_data.items():
        nk = _normalize_summary_key(key)
        if nk and nk not in normalized:
            normalized[nk] = value
    for alias in _SUMMARY_KEY_ALIASES.get(canonical_key, (canonical_key,)):
        val = normalized.get(_normalize_summary_key(alias))
        if val is not None:
            return str(val)
    return ""


def _rule_11_summary_checklist(bdt: BDTData) -> RuleResult:
    """R11: Cross-check key fields between BDT sheet and Summary sheet."""
    if not bdt.summary_data:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=None, verdict="N/A",
            detail="No Summary sheet data available",
        )

    checks = [
        ("Short Code",      str(bdt.site_code or ""),           "Short Code"),
        ("PLD Value",       str(bdt.pld_value or ""),           "PLVD Value"),
        ("Rectifier Brand", str(bdt.rectifier_brand or ""),     "Rectifier Brand"),
        ("Number of Modules", str(bdt.num_modules or ""),       "# of Modules"),
        ("Battery Brand",   str(bdt.battery_brand or ""),       "Battery Brand"),
        ("Battery Voltage", str(bdt.battery_voltage or ""),     "Battery Volt"),
        ("Number of Strings", str(bdt.num_strings or ""),       "No of String"),
        ("Number of Batteries", str(bdt.num_batteries or ""),   "No of Batteries"),
        ("Start Voltage",   str(bdt.start_voltage or ""),       "Start Volt"),
        ("Start Amp",       str(bdt.start_ampere or ""),        "Start Amp"),
        ("End Voltage",     str(bdt.end_voltage or ""),         "End Volt"),
        ("End Amp",         str(bdt.end_ampere or ""),          "End Amp"),
        ("Discharge Time (mins)", str(bdt.discharge_minutes or ""), "Discharge time( Mins)"),
        ("Test Date",       (bdt.test_date.strftime("%Y-%m-%d") if bdt.test_date else ""), "Test Date"),
    ]

    mismatches = []
    checked = 0
    for display_name, bdt_val, summary_key in checks:
        summary_val = _summary_lookup_value(bdt.summary_data, summary_key)
        if not bdt_val and not summary_val:
            continue  # skip fields missing from both
        checked += 1
        if not _values_match(bdt_val, summary_val, display_name):
            mismatches.append(f"{display_name}: BDT='{bdt_val}' vs Summary='{summary_val}'")

    if checked == 0:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=None, verdict="N/A",
            detail="No comparable fields found between BDT and Summary sheets",
        )

    if not mismatches:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=True, verdict="Accepted",
            detail=f"All {checked} checklist fields match between BDT and Summary sheets",
        )

    n = len(mismatches)
    detail = f"{n} mismatch(es): " + "; ".join(mismatches[:5])
    if n > 5:
        detail += f" (and {n - 5} more)"

    if n >= 4:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=False, verdict="Rejected",
            detail=detail,
        )
    return RuleResult(
        rule_id="R11", rule_name="Summary Checklist",
        passed=False, verdict="Revise",
        detail=detail,
    )
