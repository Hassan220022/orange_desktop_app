"""
BDT Validator — run validation rules against parsed BDT data.

Cross-references BDT (Battery Discharge Test) reports against loaded alarm
data to detect fraudulent or incorrect test submissions.
"""

from dataclasses import dataclass, field

import pandas as pd
import numpy as np

try:
    from .bdt_parser import BDTData
    from .constants import BDT_DEFAULT_TOLERANCE, BDT_DEFAULT_HEALTH_PCT
except ImportError:
    from bdt_parser import BDTData
    from constants import BDT_DEFAULT_TOLERANCE, BDT_DEFAULT_HEALTH_PCT


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

def _rule_1_photos(bdt: BDTData) -> RuleResult:
    """R1: Photos exist in placeholders (per-slot reporting)."""
    if bdt.photos_deferred:
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=None, verdict="N/A",
            detail="Photo validation deferred; photos not loaded yet",
        )

    # Use per-slot data when available
    if bdt.photo_slots:
        filled = [s for s in bdt.photo_slots if s.image_data]
        missing = [s for s in bdt.photo_slots if not s.image_data]
        total = len(bdt.photo_slots)
        n_filled = len(filled)

        if n_filled == total:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=True, verdict="Accepted",
                detail=f"All {total} photo slots filled",
            )
        if n_filled == 0:
            return RuleResult(
                rule_id="R1", rule_name="Photos",
                passed=False, verdict="Rejected",
                detail="No photos embedded in file",
            )
        missing_names = ", ".join(s.label for s in missing)
        return RuleResult(
            rule_id="R1", rule_name="Photos",
            passed=False, verdict="Revise",
            detail=(f"{n_filled}/{total} slots filled. "
                    f"Missing: {missing_names}"),
        )

    # Fallback to simple media count
    has = bdt.photo_count > 0
    return RuleResult(
        rule_id="R1", rule_name="Photos",
        passed=has,
        verdict="Accepted" if has else "Rejected",
        detail=(f"{bdt.photo_count} photo(s) found"
                if has else "No photos embedded in file"),
    )


def _find_power_alarms(alarm_df: pd.DataFrame, site_code: str) -> pd.DataFrame:
    """Find Power alarms for a site, with file_source fallback if unconfigured."""
    # Ensure occurred_on is datetime
    if not pd.api.types.is_datetime64_any_dtype(alarm_df["occurred_on"]):
        alarm_df = alarm_df.copy()
        alarm_df["occurred_on"] = pd.to_datetime(
            alarm_df["occurred_on"], errors="coerce", format="mixed")

    site_mask = (
        alarm_df["site_id"].astype(str).str.strip().str.upper()
        == site_code.strip().upper()
    ) & (alarm_df["occurred_on"].notna())

    # Try alarm_category first
    cat_mask = site_mask & (alarm_df["alarm_category"] == "Power")
    power = alarm_df[cat_mask]
    if not power.empty:
        return power

    # Fallback: if no alarms classified as Power, use file_source keyword
    if "file_source" in alarm_df.columns:
        src_mask = site_mask & (
            alarm_df["file_source"].astype(str).str.contains(
                "power", case=False, na=False))
        return alarm_df[src_mask]

    return power  # empty


def _rule_2_power_alarm_match(bdt: BDTData,
                               alarm_df: pd.DataFrame | None) -> RuleResult:
    """R2: Power alarm exists on test date for the same site."""
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
    power = _find_power_alarms(alarm_df, bdt.site_code)

    if power.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=f"No Power alarms found for site {bdt.site_code}",
        )

    # Check if any Power alarm occurred on the test date
    power_dates = power["occurred_on"].dt.normalize()
    match = power[power_dates == test_date]

    if match.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=(f"No Power alarm on {test_date.date()} for site "
                    f"{bdt.site_code}. Power was never cut from the grid."),
        )

    return RuleResult(
        rule_id="R2", rule_name="Power Alarm Match",
        passed=True, verdict="Accepted",
        detail=f"Power alarm found on {test_date.date()} ({len(match)} match(es))",
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
    """R5: I Battery — battery current before test in 0.0–0.4 A range (rounds to 0)."""
    if bdt.ibat_before_test is None:
        return RuleResult(
            rule_id="R5", rule_name="I Battery",
            passed=None, verdict="N/A",
            detail="Ibat before test not found in file",
        )

    passed = abs(bdt.ibat_before_test) < 0.5
    return RuleResult(
        rule_id="R5", rule_name="I Battery",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=f"Ibat before test: {bdt.ibat_before_test} A (range: 0.0–0.4)",
    )


def _rule_6_end_voltage(bdt: BDTData, health_pct: float) -> RuleResult:
    """R6: End voltage — auto-accept if test cutoff at ≥180 min with
    remaining capacity, otherwise require 45–47 V range."""
    if bdt.end_voltage is None:
        return RuleResult(
            rule_id="R6", rule_name="End Voltage Range",
            passed=None, verdict="N/A",
            detail="End voltage not found in file",
        )

    # Auto-accept when test was cut off early (≥180 min) and battery
    # still had theoretical capacity remaining.
    reported = bdt.discharge_minutes
    if reported >= 180:
        theoretical = _theoretical_backup_minutes(bdt, health_pct)
        if theoretical is not None and theoretical > reported:
            return RuleResult(
                rule_id="R6", rule_name="End Voltage Range",
                passed=True, verdict="Accepted",
                detail=(f"End voltage: {bdt.end_voltage}V — test cutoff at "
                        f"{reported:.0f} min (theoretical: {theoretical:.0f} min); "
                        f"battery had remaining capacity"),
            )

    passed = 45.0 <= bdt.end_voltage <= 47.0
    return RuleResult(
        rule_id="R6", rule_name="End Voltage Range",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=f"End voltage: {bdt.end_voltage}V (range: 45.0-47.0V)",
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
        detail=(f"V/A correlation: {corr:.3f} "
                f"({'inverse' if corr < 0 else 'direct'} relationship)"),
    )


def _is_lithium(brand: str) -> bool:
    """Check if battery brand indicates lithium chemistry."""
    return "lith" in brand.lower()


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
    """R8: Reported discharge time vs theoretical backup time from battery specs."""
    missing = []
    if bdt.battery_ah is None:
        missing.append("AH")
    if bdt.battery_voltage is None:
        missing.append("voltage")
    if bdt.num_strings is None:
        missing.append("strings")
    if missing:
        return RuleResult(
            rule_id="R8", rule_name="Theoretical BT",
            passed=None, verdict="N/A",
            detail=f"Battery {', '.join(missing)} not found in file",
        )

    theoretical_mins = _theoretical_backup_minutes(bdt, health_pct)
    if theoretical_mins is None:
        return RuleResult(
            rule_id="R8", rule_name="Theoretical BT",
            passed=None, verdict="N/A",
            detail="Cannot compute theoretical BT (no load data before disconnect)",
        )

    reported = bdt.discharge_minutes

    # 3-hour cutoff detection: theoretical > 180 min but reported ~180 min
    if theoretical_mins > 180 and abs(reported - 180) <= 5.0:
        return RuleResult(
            rule_id="R8", rule_name="Theoretical BT",
            passed=False, verdict="Rejected",
            detail=(f"Suspected 3hr cutoff — theoretical: {theoretical_mins:.0f} min, "
                    f"reported: {reported:.0f} min"),
        )

    # Check if reported exceeds theoretical by more than 15%
    if reported > theoretical_mins * 1.15:
        return RuleResult(
            rule_id="R8", rule_name="Theoretical BT",
            passed=False, verdict="Rejected",
            detail=(f"Reported ({reported:.0f} min) exceeds theoretical "
                    f"({theoretical_mins:.0f} min) by "
                    f">{((reported / theoretical_mins) - 1) * 100:.0f}%"),
        )

    return RuleResult(
        rule_id="R8", rule_name="Theoretical BT",
        passed=True, verdict="Accepted",
        detail=(f"Theoretical: {theoretical_mins:.0f} min, "
                f"reported: {reported:.0f} min"),
    )
