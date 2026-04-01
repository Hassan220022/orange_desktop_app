"""
BDT Validator — run validation rules against parsed BDT data.

Cross-references BDT (Battery Discharge Test) reports against loaded alarm
data to detect fraudulent or incorrect test submissions.
"""

from dataclasses import dataclass, field
from datetime import datetime, time

import pandas as pd
import numpy as np

try:
    from .bdt_parser import BDTData
    from .constants import (
        BDT_DEFAULT_TOLERANCE,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_REQUIRED_PHOTO_COUNT,
    )
except ImportError:
    from bdt_parser import BDTData
    from constants import (
        BDT_DEFAULT_TOLERANCE,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_REQUIRED_PHOTO_COUNT,
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
                 health_pct: float = BDT_DEFAULT_HEALTH_PCT) -> ValidationResult:
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

    result.rules.append(_rule_1_photos(bdt))
    result.rules.append(_rule_2_power_alarm_match(bdt, alarm_df))
    result.rules.append(_rule_3_duration_match(bdt, alarm_df, tolerance))
    result.rules.append(_rule_4_discharge_table(bdt, tolerance))
    result.rules.append(_rule_5_start_ampere(bdt))
    result.rules.append(_rule_6_end_voltage(bdt, health_pct))
    result.rules.append(_rule_7_inverse_relationship(bdt))
    result.rules.append(_rule_8_backup_time(bdt, health_pct))
    result.rules.append(_rule_9_discharge_current_tolerance(bdt))
    result.rules.append(_rule_10_door_alarm_match(bdt, alarm_df))

    # Overall verdict
    failed = [r for r in result.rules if r.verdict == "Rejected"]
    revise = [r for r in result.rules if r.verdict == "Revise"]

    if failed:
        result.overall = "Rejected"
    elif revise:
        result.overall = "Revise"
    else:
        result.overall = "Accepted"

    return result


# ── Rule implementations ──────────────────────────────────

_REQUIRED_PHOTO_CATEGORIES = ("rectifier", "batteries")


def _slot_category(slot) -> str:
    """Return normalized slot category from parser metadata."""
    category = getattr(slot, "category", "")
    if category:
        return str(category).strip().lower()

    # Compatibility fallback for older parsed objects without slot.category
    label = str(getattr(slot, "label", "")).strip().lower()
    if "rectifier" in label:
        return "rectifier"
    if "batter" in label:
        return "batteries"
    return ""


def _rule_1_photos(bdt: BDTData) -> RuleResult:
    """R1: Photo completeness policy (16=Accepted, 0=Rejected, partial=Revise)."""
    if bdt.photos_deferred:
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=None, verdict="N/A",
            detail="Photo validation deferred; photos not loaded yet",
        )

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
        if filled_slots >= BDT_REQUIRED_PHOTO_COUNT:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=True, verdict="Accepted",
                detail=(f"All required photos are available "
                        f"({filled_slots}/{BDT_REQUIRED_PHOTO_COUNT})"),
            )
        missing_count = max(BDT_REQUIRED_PHOTO_COUNT - filled_slots, 0)
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Revise",
            detail=(f"Photo set incomplete: {filled_slots}/{BDT_REQUIRED_PHOTO_COUNT} "
                    f"(missing {missing_count})"),
        )

    # Fallback when per-slot metadata is unavailable.
    count = int(bdt.photo_count or 0)
    if count == 0:
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Rejected",
            detail="No photos embedded in file",
        )
    if count >= BDT_REQUIRED_PHOTO_COUNT:
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=True, verdict="Accepted",
            detail=f"All required photos are available ({count}/{BDT_REQUIRED_PHOTO_COUNT})",
        )
    missing_count = BDT_REQUIRED_PHOTO_COUNT - count
    return RuleResult(
        rule_id="R1", rule_name="Photos",
        passed=False,
        verdict="Revise",
        detail=(f"Photo set incomplete: {count}/{BDT_REQUIRED_PHOTO_COUNT} "
                f"(missing {missing_count})"),
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
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _rule_2_power_alarm_match(bdt: BDTData,
                               alarm_df: pd.DataFrame | None) -> RuleResult:
    """R2: Same-site/date Power alarm matches test start/end times ±5 min."""
    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=None, verdict="N/A",
            detail="No alarm data loaded",
        )
    if bdt.test_date is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail="No test date found in BDT file",
        )

    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=f"Invalid test date: {bdt.test_date!r}",
        )

    start_time = _parse_test_time(bdt.time_in)
    end_time = _parse_test_time(bdt.time_out)
    if start_time is None or end_time is None:
        missing_parts = []
        if start_time is None:
            missing_parts.append("time_in")
        if end_time is None:
            missing_parts.append("time_out")
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Revise",
            detail=(f"Cannot validate alarm timing: invalid {', '.join(missing_parts)} "
                    f"(expected HH:MM or HH:MM:SS)"),
        )

    start_ts = test_date + pd.Timedelta(
        hours=start_time.hour, minutes=start_time.minute, seconds=start_time.second
    )
    end_ts = test_date + pd.Timedelta(
        hours=end_time.hour, minutes=end_time.minute, seconds=end_time.second
    )
    if end_ts < start_ts:
        end_ts += pd.Timedelta(days=1)

    power = _find_power_alarms(alarm_df, bdt.site_code)
    if power.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=f"No Power alarms found for site {bdt.site_code}",
        )

    # Check if any Power alarm occurred on the test date
    power_dates = power["occurred_on"].dt.normalize()
    same_date = power[power_dates == test_date]
    if same_date.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=(f"No Power alarm on {test_date.date()} for site "
                    f"{bdt.site_code}. Power was never cut from the grid."),
        )

    if "cleared_on" not in same_date.columns:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Revise",
            detail="Cannot validate alarm timing: cleared_on column missing",
        )
    same_date = same_date[same_date["cleared_on"].notna()]
    if same_date.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Revise",
            detail="Cannot validate alarm timing: matching Power alarms have no cleared_on time",
        )

    tol = pd.Timedelta(minutes=5)
    start_diff = (same_date["occurred_on"] - start_ts).abs()
    end_diff = (same_date["cleared_on"] - end_ts).abs()
    match = same_date[(start_diff <= tol) & (end_diff <= tol)]

    if match.empty:
        min_start = (start_diff.min() / pd.Timedelta(minutes=1))
        min_end = (end_diff.min() / pd.Timedelta(minutes=1))
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=(f"No Power alarm time match within ±5 min "
                    f"(closest diffs: start {min_start:.1f} min, end {min_end:.1f} min)"),
        )

    return RuleResult(
        rule_id="R2", rule_name="Power Alarm Match",
        passed=True, verdict="Accepted",
        detail=(f"Power alarm matched test window ({len(match)} match(es), "
                f"tolerance ±5 min)"),
    )


def _rule_3_duration_match(bdt: BDTData, alarm_df: pd.DataFrame | None,
                            tolerance: float) -> RuleResult:
    """R3: Test duration matches Power alarm duration."""
    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=None, verdict="N/A",
            detail="No alarm data loaded",
        )
    if bdt.test_date is None:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=False, verdict="Rejected",
            detail="No test date in BDT file",
        )

    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=False, verdict="Rejected",
            detail=f"Invalid test date: {bdt.test_date!r}",
        )
    all_power = _find_power_alarms(alarm_df, bdt.site_code)
    power = all_power[all_power["occurred_on"].dt.normalize() == test_date]

    if power.empty:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=False, verdict="Rejected",
            detail="No matching Power alarm to compare duration",
        )

    # Get alarm duration in minutes
    alarm_dur_mins = None
    if "_duration_secs" in power.columns:
        alarm_dur_mins = power["_duration_secs"].max() / 60.0
    elif "duration" in power.columns:
        # Parse HH:MM:SS
        dur_str = power["duration"].iloc[0]
        try:
            parts = str(dur_str).split(":")
            alarm_dur_mins = (int(parts[0]) * 60 + int(parts[1])
                              + int(parts[2]) / 60.0)
        except (ValueError, IndexError):
            pass

    if alarm_dur_mins is None or alarm_dur_mins == 0:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=None, verdict="N/A",
            detail="Cannot determine alarm duration",
        )

    bdt_mins = bdt.discharge_minutes
    diff_ratio = abs(bdt_mins - alarm_dur_mins) / alarm_dur_mins if alarm_dur_mins > 0 else 1.0

    passed = diff_ratio <= tolerance
    return RuleResult(
        rule_id="R3", rule_name="Duration Match",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"BDT: {bdt_mins:.0f} min, Alarm: {alarm_dur_mins:.0f} min "
                f"(diff: {diff_ratio*100:.0f}%, tolerance: {tolerance*100:.0f}%)"),
    )


def _rule_4_discharge_table(bdt: BDTData,
                             tolerance: float) -> RuleResult:
    """R4: Backup time matches discharge table calculation."""
    if not bdt.discharge_readings:
        return RuleResult(
            rule_id="R4", rule_name="Discharge Table Match",
            passed=None, verdict="N/A",
            detail="No discharge readings found",
        )

    # Find last reading with data
    last_mins = 0.0
    for label, v, a in bdt.discharge_readings:
        if v is not None or a is not None:
            try:
                last_mins = float(label.split()[0])
            except ValueError:
                pass

    if last_mins == 0:
        return RuleResult(
            rule_id="R4", rule_name="Discharge Table Match",
            passed=False, verdict="Revise",
            detail="Discharge table is empty — no readings recorded",
        )

    reported = bdt.discharge_minutes
    diff_ratio = (abs(reported - last_mins) / last_mins
                  if last_mins > 0 else 1.0)
    passed = diff_ratio <= tolerance

    return RuleResult(
        rule_id="R4", rule_name="Discharge Table Match",
        passed=passed,
        verdict="Accepted" if passed else "Revise",
        detail=(f"Table shows {last_mins:.0f} min of readings, "
                f"reported: {reported:.0f} min"),
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


def _rule_8_backup_time(bdt: BDTData, health_pct: float) -> RuleResult:
    """R8: Lithium sizing-vs-actual discharge time consistency check."""
    reported = bdt.discharge_minutes
    if not _is_lithium(bdt.battery_brand):
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=None, verdict="N/A",
            detail="Not applicable: battery type is not lithium",
        )

    if not 0.95 <= health_pct <= 1.00:
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=None, verdict="N/A",
            detail=(f"Not applicable: health_pct {health_pct:.2f} "
                    f"outside required range [0.95, 1.00]"),
        )

    if reported >= 180:
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=None, verdict="N/A",
            detail=f"Not applicable: actual discharge is {reported:.0f} min (requires <180 min)",
        )

    missing = []
    if bdt.battery_ah is None:
        missing.append("AH")
    if bdt.battery_voltage is None:
        missing.append("voltage")
    if bdt.num_strings is None:
        missing.append("strings")
    if missing:
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=None, verdict="N/A",
            detail=f"Not applicable: battery {', '.join(missing)} not found in file",
        )

    theoretical_mins = _theoretical_backup_minutes(bdt, health_pct)
    if theoretical_mins is None:
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=None, verdict="N/A",
            detail="Not applicable: cannot compute theoretical duration from available load data",
        )

    delta = abs(theoretical_mins - reported)
    passed = delta <= 15.0
    return RuleResult(
        rule_id="R8", rule_name="Sizing vs Actual",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Theoretical: {theoretical_mins:.0f} min, actual: {reported:.0f} min, "
                f"absolute difference: {delta:.1f} min (limit: 15 min)"),
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


def _find_door_alarms(alarm_df: pd.DataFrame, site_code: str,
                      test_date: pd.Timestamp) -> pd.DataFrame:
    """Find same-site same-date alarms that indicate door condition."""
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
    return alarm_df[site_mask & date_mask & door_mask]


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

    doors = _find_door_alarms(alarm_df, bdt.site_code, test_date)
    if doors.empty:
        return RuleResult(
            rule_id="R10", rule_name="Door Alarm Condition",
            passed=False, verdict="Revise",
            detail=(f"No Door alarm found for site {bdt.site_code} on "
                    f"{test_date.date()}"),
        )

    return RuleResult(
        rule_id="R10", rule_name="Door Alarm Condition",
        passed=True, verdict="Accepted",
        detail=f"Door alarm found for site {bdt.site_code} on {test_date.date()} ({len(doors)} match(es))",
    )
