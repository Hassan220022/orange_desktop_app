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
        BDT_POWER_TIMING_TOLERANCE_MIN,
        BDT_COMPLETION_MINUTES,
        BDT_STRING_AMPERE_TOLERANCE_A,
    )
except ImportError:
    from bdt_parser import BDTData
    from constants import (
        BDT_DEFAULT_TOLERANCE,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_REQUIRED_PHOTO_COUNT,
        BDT_POWER_TIMING_TOLERANCE_MIN,
        BDT_COMPLETION_MINUTES,
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

    result.rules.append(_rule_1_photos(bdt))
    result.rules.append(_rule_2_power_alarm_match(bdt, alarm_df, tol_override=power_timing_tol))
    result.rules.append(_rule_3_string_vs_busbar(bdt))
    result.rules.append(_rule_4_discharge_table(bdt, tolerance))
    result.rules.append(_rule_5_start_ampere(bdt))
    result.rules.append(_rule_6_end_voltage(bdt, health_pct))
    result.rules.append(_rule_7_inverse_relationship(bdt))
    result.rules.append(_rule_8_backup_time(bdt, health_pct))
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
    """R1: Photo completeness — count + required categories (rectifier & batteries)."""
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

        # Check required categories: must have at least one rectifier AND one batteries photo
        filled_categories = set()
        for slot in bdt.photo_slots:
            if bool(getattr(slot, "image_data", None)):
                cat = _slot_category(slot)
                if cat:
                    filled_categories.add(cat)

        missing_cats = [
            c for c in _REQUIRED_PHOTO_CATEGORIES if c not in filled_categories
        ]

        if filled_slots >= BDT_REQUIRED_PHOTO_COUNT and not missing_cats:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=True, verdict="Accepted",
                detail=(f"All required photos available "
                        f"({filled_slots}/{BDT_REQUIRED_PHOTO_COUNT}), "
                        f"categories: {', '.join(sorted(filled_categories))}"),
            )

        # Build detail about what's incomplete
        parts = []
        if filled_slots < BDT_REQUIRED_PHOTO_COUNT:
            missing_n = BDT_REQUIRED_PHOTO_COUNT - filled_slots
            parts.append(f"{filled_slots}/{BDT_REQUIRED_PHOTO_COUNT} (missing {missing_n})")
        if missing_cats:
            parts.append(f"missing category: {', '.join(missing_cats)}")

        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Revise",
            detail=f"Photo set incomplete: {'; '.join(parts)}",
        )

    # Fallback when per-slot metadata is unavailable (no category check possible).
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
    for fmt in (
        "%H:%M:%S", "%H:%M",
        "%I:%M:%S%p", "%I:%M:%S %p",   # 12-hour with AM/PM (e.g. "12:31:10PM")
        "%I:%M%p", "%I:%M %p",          # 12-hour without seconds
    ):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _max_reached_discharge_minutes(bdt: BDTData) -> float | None:
    """Return max discharge-minute label that has at least one real reading."""
    max_mins = 0.0
    for label, v, a in bdt.discharge_readings:
        if v is None and a is None:
            continue
        try:
            mins = float(str(label).split()[0])
        except (ValueError, TypeError, IndexError):
            continue
        if mins > max_mins:
            max_mins = mins
    return max_mins if max_mins > 0 else None


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
    if discharge_minutes > BDT_COMPLETION_MINUTES:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail=(f"Invalid discharge duration ({discharge_minutes:.1f} min): "
                    f"must not exceed {BDT_COMPLETION_MINUTES} min"),
        )

    start_time = _parse_test_time(bdt.time_in)
    if start_time is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail="Cannot validate alarm timing: invalid time_in (expected HH:MM or HH:MM:SS)",
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
        a["within_limit"] = a["duration_min"] <= BDT_COMPLETION_MINUTES
        a["passed"] = (
            a["within_limit"]
            and a["start_diff_min"] <= tol_min
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
                    f"tolerance ±{tol_min:.0f} min, max {BDT_COMPLETION_MINUTES} min)"),
        )

    best = min(
        attempts,
        key=lambda a: (a["duration_diff_min"], a["end_diff_min"], a["start_diff_min"]),
    )
    limit_note = ""
    if not best["within_limit"]:
        limit_note = f"; exceeds max {BDT_COMPLETION_MINUTES} min"
    return RuleResult(
        rule_id="R2", rule_name="Power Alarm + Duration",
        passed=False, verdict="Rejected",
        detail=(f"No Power timing/duration match within ±{tol_min:.0f} min. "
                f"Closest path {best['path']}: "
                f"start Δ={best['start_diff_min']:.1f} min, "
                f"end Δ={best['end_diff_min']:.1f} min, "
                f"duration Δ={best['duration_diff_min']:.1f} min "
                f"(alarm {best['duration_min']:.1f} min vs discharge-table max "
                f"{discharge_minutes:.1f} min)"
                f"{limit_note}"),
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

    last_mins = _max_reached_discharge_minutes(bdt)
    if last_mins is None:
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
    """R8: Sizing-vs-actual discharge time consistency check (never N/A).

    Business rules:
    - The test target is capped at 180 minutes.
    - If theoretical duration is >180, accept only when actual discharge >=180.
    - Otherwise (theoretical <=180), compare actual vs theoretical with ±15 min tolerance.
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

    # Normal branch: compare against theoretical target with fixed tolerance.
    delta = abs(theoretical_mins - reported)
    passed = delta <= 15.0
    return RuleResult(
        rule_id="R8", rule_name="Sizing vs Actual",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Theoretical: {theoretical_mins:.0f} min, actual: {reported:.0f} min, "
                f"difference: {delta:.1f} min (limit: 15 min)"),
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
            passed=False, verdict="Rejected",
            detail=(f"No Door alarm found for site {bdt.site_code} on "
                    f"{test_date.date()}"),
        )

    return RuleResult(
        rule_id="R10", rule_name="Door Alarm Condition",
        passed=True, verdict="Accepted",
        detail=f"Door alarm found for site {bdt.site_code} on {test_date.date()} ({len(doors)} match(es))",
    )


def _rule_3_string_vs_busbar(bdt: BDTData) -> RuleResult:
    """R3: Sum of per-string amperes must not be more than 3A below bus bar ampere."""
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
        diff = string_sum - bus_a
        checked += 1

        if diff < -tolerance:
            return RuleResult(
                rule_id="R3", rule_name="String vs Bus Bar Ampere",
                passed=False, verdict="Rejected",
                detail=(f"At {dr[0]}: string sum {string_sum:.2f}A vs "
                        f"bus bar {bus_a:.2f}A (diff={diff:.2f}A, "
                        f"limit >=-{tolerance:.1f}A)"),
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
                f"(string sum - bus bar >= -{tolerance:.1f}A)"),
    )


def _normalize_for_comparison(val: str) -> str:
    """Strip units, whitespace, and normalize for comparison."""
    if val is None:
        return ""
    s = str(val).strip().lower()
    # Remove common unit suffixes
    for suffix in ("ah", "vdc", "min", "mins", "v", "a", " min"):
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    # Remove "none" / "na" / "n/a"
    if s in ("none", "na", "n/a", "nan", "--", "-", ""):
        return ""
    return s


def _values_match(bdt_val: str, summary_val: str, field_name: str) -> bool:
    """Compare a BDT sheet value against a Summary sheet value with tolerance."""
    a = _normalize_for_comparison(bdt_val)
    b = _normalize_for_comparison(summary_val)
    if not a and not b:
        return True  # both empty = match
    if not a or not b:
        return False  # one empty, one not = mismatch
    # Try numeric comparison with epsilon
    try:
        fa, fb = float(a), float(b)
        return abs(fa - fb) < 0.5
    except (ValueError, TypeError):
        pass
    # String: case-insensitive containment (Summary may abbreviate or expand)
    return a in b or b in a


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
        ("PLVD Value",      str(bdt.pld_value or ""),           "PLVD Value"),
        ("Rectifier Brand", str(bdt.rectifier_brand or ""),     "Rectifier Brand"),
        ("# of Modules",    str(bdt.num_modules or ""),         "# of Modules"),
        ("Battery Brand",   str(bdt.battery_brand or ""),       "Battery Brand"),
        ("Battery Voltage",  str(bdt.battery_voltage or ""),    "Battery Volt"),
        ("# of Strings",    str(bdt.num_strings or ""),         "No of String"),
        ("# of Batteries",  str(bdt.num_batteries or ""),       "No of Batteries"),
        ("Start Voltage",   str(bdt.start_voltage or ""),       "Start Volt"),
        ("Start Amp",       str(bdt.start_ampere or ""),        "Start Amp"),
        ("End Voltage",     str(bdt.end_voltage or ""),         "End Volt"),
        ("End Amp",         str(bdt.end_ampere or ""),          "End Amp"),
        ("Discharge Time",  str(bdt.discharge_minutes or ""),   "Discharge time( Mins)"),
        ("Test Date",       (bdt.test_date.strftime("%Y-%m-%d") if bdt.test_date else ""), "Test Date"),
    ]

    mismatches = []
    checked = 0
    for display_name, bdt_val, summary_key in checks:
        summary_val = bdt.summary_data.get(summary_key, "")
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
