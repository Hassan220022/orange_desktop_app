"""
BDT Validator — run validation rules against parsed BDT data.

Cross-references BDT (Battery Discharge Test) reports against loaded alarm
data to detect fraudulent or incorrect test submissions.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import cast

import numpy as np
import pandas as pd

try:
    from alarm_app.bdt.parser import BDTData
    from alarm_app.bdt.evidence_metrics import (
        discharge_trend_metrics,
        has_discharge_evidence,
        max_reached_discharge_minutes,
        worst_r3_evidence,
    )
    from alarm_app.constants import (
        BDT_COMPLETION_MINUTES,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_DEFAULT_TOLERANCE,
        BDT_DISCHARGE_CURRENT_ACCEPT_A,
        BDT_DISCHARGE_CURRENT_PCT,
        BDT_DISCHARGE_CURRENT_TOLERANCE_A,
        BDT_DISCHARGE_SLOPE_ACCEPT_A_PER_MIN,
        BDT_DISCHARGE_SLOPE_REJECT_A_PER_MIN,
        BDT_DISCHARGE_SPIKE_REJECT_A,
        BDT_END_VOLTAGE_MAX,
        BDT_END_VOLTAGE_MIN,
        BDT_INCOMPLETE_REJECT_MINUTES,
        BDT_INCOMPLETE_REVISE_MINUTES,
        BDT_OVERALL_IGNORE_NA_RULES,
        BDT_POWER_TIMING_TOLERANCE_MIN,
        BDT_REQUIRED_PHOTO_COUNT,
        BDT_SIZING_TOLERANCE_MINUTES,
        BDT_START_AMPERE_THRESHOLD_A,
        BDT_STRING_AMPERE_POS_ACCEPT_A,
        BDT_STRING_AMPERE_POS_REVISE_A,
        BDT_STRING_AMPERE_POS_TOLERANCE_A,
        BDT_STRING_AMPERE_TOLERANCE_A,
        BDT_STRING_IMBALANCE_REJECT_RATIO,
        BDT_STRING_IMBALANCE_REVISE_RATIO,
    )
    from alarm_app.core.battery_topology import battery_topology_from_bdt
except ImportError:
    from bdt.parser import BDTData
    from bdt.evidence_metrics import (
        discharge_trend_metrics,
        has_discharge_evidence,
        max_reached_discharge_minutes,
        worst_r3_evidence,
    )
    from constants import (
        BDT_COMPLETION_MINUTES,
        BDT_DEFAULT_HEALTH_PCT,
        BDT_DEFAULT_TOLERANCE,
        BDT_DISCHARGE_CURRENT_ACCEPT_A,
        BDT_DISCHARGE_CURRENT_PCT,
        BDT_DISCHARGE_CURRENT_TOLERANCE_A,
        BDT_DISCHARGE_SLOPE_ACCEPT_A_PER_MIN,
        BDT_DISCHARGE_SLOPE_REJECT_A_PER_MIN,
        BDT_DISCHARGE_SPIKE_REJECT_A,
        BDT_END_VOLTAGE_MAX,
        BDT_END_VOLTAGE_MIN,
        BDT_INCOMPLETE_REJECT_MINUTES,
        BDT_INCOMPLETE_REVISE_MINUTES,
        BDT_OVERALL_IGNORE_NA_RULES,
        BDT_POWER_TIMING_TOLERANCE_MIN,
        BDT_REQUIRED_PHOTO_COUNT,
        BDT_SIZING_TOLERANCE_MINUTES,
        BDT_START_AMPERE_THRESHOLD_A,
        BDT_STRING_AMPERE_POS_ACCEPT_A,
        BDT_STRING_AMPERE_POS_REVISE_A,
        BDT_STRING_AMPERE_POS_TOLERANCE_A,
        BDT_STRING_AMPERE_TOLERANCE_A,
        BDT_STRING_IMBALANCE_REJECT_RATIO,
        BDT_STRING_IMBALANCE_REVISE_RATIO,
    )
    from core.battery_topology import battery_topology_from_bdt


BDT_TOLERANCE_PROFILE_VERSION = 4
BDT_TOLERANCE_PROFILE_VERSION_KEY = "_profile_version"
_LEGACY_START_AMPERE_DEFAULT_A = 0.5
_LEGACY_FLOAT_EPSILON = 1e-6

BDT_VERDICT_RULE_IDS: tuple[str, ...] = (
    "R1", "R2", "R3", "R5", "R6", "R7", "R8", "R9", "R10", "R11",
)


@dataclass(frozen=True)
class BDTVerdictPolicy:
    """Per-rule switches for whether a rule can block the overall verdict."""

    block_overall: dict[str, bool]

    @classmethod
    def defaults(cls) -> "BDTVerdictPolicy":
        return cls(block_overall={
            rule_id: rule_id not in {"R1", "R10"}
            for rule_id in BDT_VERDICT_RULE_IDS
        })

    @classmethod
    def from_dict(cls, data: dict | None) -> "BDTVerdictPolicy":
        defaults = cls.defaults()
        block_overall = dict(defaults.block_overall)
        if not data:
            return defaults
        for rule_id in BDT_VERDICT_RULE_IDS:
            key = _verdict_policy_key(rule_id)
            if key not in data or data[key] is None:
                continue
            try:
                block_overall[rule_id] = bool(float(data[key]))
            except (TypeError, ValueError):
                pass
        return cls(block_overall=block_overall)

    def to_dict(self) -> dict[str, float]:
        return {
            _verdict_policy_key(rule_id): 1.0 if self.block_overall.get(rule_id, True) else 0.0
            for rule_id in BDT_VERDICT_RULE_IDS
        }


def _verdict_policy_key(rule_id: str) -> str:
    return f"block_overall_{str(rule_id).strip().lower()}"


def rule_blocks_overall_verdict(policy: BDTVerdictPolicy, rule_id: str) -> bool:
    return policy.block_overall.get(str(rule_id).strip().upper(), True)


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
    battery_backup_insight: dict = field(default_factory=dict)
    validation_context: dict = field(default_factory=dict)


def rule_blocks_overall_verdict_for_result(
    rule: RuleResult,
    policy: BDTVerdictPolicy,
    *,
    ignore_na_rules: frozenset[str] | set[str] | None = None,
) -> bool:
    """Return True when this rule outcome should affect overall Accepted/Revise/Rejected."""
    if rule.verdict == "Skipped":
        return False
    if not rule_blocks_overall_verdict(policy, rule.rule_id):
        return False
    if rule.verdict == "N/A":
        ignored = ignore_na_rules if ignore_na_rules is not None else frozenset(BDT_OVERALL_IGNORE_NA_RULES)
        if rule.rule_id in ignored:
            return False
        if rule.rule_id == "R2" and "no alarm data" in str(rule.detail).lower():
            return True
        return False
    return rule.verdict in {"Rejected", "Revise"}


@dataclass
class BDTTolerances:
    """User-configurable tolerance thresholds applied by the BDT validator.

    Every numeric threshold a non-developer might want to relax or tighten
    lives here so the UI can edit them and the validator can stay pure.
    Fractional fields are dimensionless ratios; ``*_a`` are amps,
    ``*_v`` are volts, and ``*_minutes``/``*_min`` are minutes.
    """
    sizing_fractional_tolerance: float = BDT_DEFAULT_TOLERANCE
    sizing_minutes_floor: float = float(BDT_SIZING_TOLERANCE_MINUTES)
    power_timing_min: float = float(BDT_POWER_TIMING_TOLERANCE_MIN)
    string_ampere_a: float = float(BDT_STRING_AMPERE_TOLERANCE_A)
    string_ampere_pos_a: float = float(BDT_STRING_AMPERE_POS_TOLERANCE_A)
    string_ampere_pos_accept_a: float = float(BDT_STRING_AMPERE_POS_ACCEPT_A)
    string_ampere_pos_revise_a: float = float(BDT_STRING_AMPERE_POS_REVISE_A)
    string_imbalance_reject_ratio: float = float(BDT_STRING_IMBALANCE_REJECT_RATIO)
    string_imbalance_revise_ratio: float = float(BDT_STRING_IMBALANCE_REVISE_RATIO)
    discharge_current_a: float = float(BDT_DISCHARGE_CURRENT_TOLERANCE_A)
    discharge_current_pct: float = float(BDT_DISCHARGE_CURRENT_PCT)
    discharge_current_accept_a: float = float(BDT_DISCHARGE_CURRENT_ACCEPT_A)
    discharge_slope_accept_a_per_min: float = float(
        BDT_DISCHARGE_SLOPE_ACCEPT_A_PER_MIN)
    discharge_slope_reject_a_per_min: float = float(
        BDT_DISCHARGE_SLOPE_REJECT_A_PER_MIN)
    discharge_spike_reject_a: float = float(BDT_DISCHARGE_SPIKE_REJECT_A)
    incomplete_reject_minutes: float = float(BDT_INCOMPLETE_REJECT_MINUTES)
    incomplete_revise_minutes: float = float(BDT_INCOMPLETE_REVISE_MINUTES)
    start_ampere_a: float = float(BDT_START_AMPERE_THRESHOLD_A)
    end_voltage_min: float = float(BDT_END_VOLTAGE_MIN)
    end_voltage_max: float = float(BDT_END_VOLTAGE_MAX)
    completion_minutes: float = float(BDT_COMPLETION_MINUTES)
    min_backup_minutes_for_battery_rules: float = 10.0
    verdict_policy: BDTVerdictPolicy = field(default_factory=BDTVerdictPolicy.defaults)

    @classmethod
    def defaults(cls) -> "BDTTolerances":
        return cls()

    @classmethod
    def from_dict(cls, data: dict | None) -> "BDTTolerances":
        """Build from a persisted settings dict, ignoring unknown keys and
        falling back to defaults for missing/invalid entries."""
        defaults = cls()
        if not data:
            return defaults
        has_profile_version = BDT_TOLERANCE_PROFILE_VERSION_KEY in data
        kwargs: dict[str, float] = {}
        for fld in defaults.__dataclass_fields__:
            if fld == "verdict_policy":
                continue
            if fld in data and data[fld] is not None:
                try:
                    kwargs[fld] = float(data[fld])
                except (TypeError, ValueError):
                    pass
        if (
            not has_profile_version
            and "start_ampere_a" in kwargs
            and abs(kwargs["start_ampere_a"] - _LEGACY_START_AMPERE_DEFAULT_A) <= _LEGACY_FLOAT_EPSILON
        ):
            kwargs.pop("start_ampere_a")
        default_values = {
            fld: getattr(defaults, fld)
            for fld in defaults.__dataclass_fields__
            if fld != "verdict_policy"
        }
        verdict_policy = BDTVerdictPolicy.from_dict(data)
        return cls(
            **{**default_values, **kwargs},
            verdict_policy=verdict_policy,
        )

    def to_dict(self) -> dict[str, float]:
        values = {
            fld: getattr(self, fld)
            for fld in self.__dataclass_fields__
            if fld != "verdict_policy"
        }
        values.update(self.verdict_policy.to_dict())
        values[BDT_TOLERANCE_PROFILE_VERSION_KEY] = float(BDT_TOLERANCE_PROFILE_VERSION)
        return values


def validate_bdt(bdt: BDTData, alarm_df: pd.DataFrame | None,
                 tolerance: float | None = None,
                 health_pct: float = BDT_DEFAULT_HEALTH_PCT,
                 power_timing_tol: float | None = None,
                 tolerances: BDTTolerances | None = None,
                 network_no_usable_backup: bool = False,
                 network_backup_minutes: float | None = None,
                 network_backup_reasons: list[str] | None = None) -> ValidationResult:
    """Validate a parsed BDT file against alarm data.

    Args:
        bdt: Parsed BDT data from bdt_parser.
        alarm_df: Loaded alarm DataFrame (may be None if no alarms loaded).
        tolerance: Legacy fractional tolerance for sizing-vs-actual (R8).
            When ``tolerances`` is provided this argument is ignored.
        health_pct: Battery health percentage applied to lead-acid sizing.
        power_timing_tol: Legacy override for the R2 power-alarm timing
            window (minutes). When ``tolerances`` is provided this argument
            is ignored.
        tolerances: Full bundle of user-configurable tolerance thresholds.
            When omitted, defaults from ``BDTTolerances`` are used and
            mixed with any legacy ``tolerance``/``power_timing_tol``
            overrides for backwards compatibility.

    Returns:
        ValidationResult with per-rule verdicts and overall verdict.
    """
    if tolerances is None:
        tolerances = BDTTolerances.defaults()
        if tolerance is not None:
            tolerances.sizing_fractional_tolerance = float(tolerance)
        if power_timing_tol is not None:
            tolerances.power_timing_min = float(power_timing_tol)

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
    network_skip_reasons = list(network_backup_reasons or [])
    component_check = bool(network_no_usable_backup) and not battery_skip_reason
    active_r11_groups = {"A", "B1", "B2"}
    if component_check:
        active_r11_groups = {"A"}
        result.validation_context.update({
            "validation_mode": "component_check_no_backup_battery",
            "network_no_usable_backup": True,
            "network_backup_minutes": network_backup_minutes,
            "network_backup_reasons": network_skip_reasons,
        })
    elif network_no_usable_backup and battery_skip_reason:
        result.validation_context.update({
            "network_no_usable_backup_also": True,
            "network_backup_minutes": network_backup_minutes,
            "network_backup_reasons": network_skip_reasons,
        })
    elif battery_skip_reason.startswith("Faulty battery"):
        active_r11_groups = {"A", "B1"}
    elif battery_skip_reason:
        active_r11_groups = {"A"}

    result.rules.append(_rule_1_photos(bdt))
    if battery_skip_reason:
        result.rules.extend(_skipped_battery_rules(battery_skip_reason))
    elif component_check:
        skip_reason = (
            "Network Summary declares no usable backup battery; component check only"
        )
        result.rules.extend(
            _skipped_battery_rules(
                skip_reason,
                only=("R2", "R5", "R6", "R7", "R8"),
            )
        )
        if has_discharge_evidence(bdt):
            result.rules.append(_rule_3_string_vs_busbar(bdt, tolerances=tolerances))
            result.rules.append(
                _rule_9_discharge_current_tolerance(bdt, tolerances=tolerances))
        else:
            result.rules.extend(
                _skipped_battery_rules(skip_reason, only=("R3", "R9")))
    else:
        result.rules.append(
            _rule_2_power_alarm_match(
                bdt, alarm_df,
                tol_override=tolerances.power_timing_min,
                tolerances=tolerances,
            ))
        result.rules.append(_rule_3_string_vs_busbar(bdt, tolerances=tolerances))
        result.rules.append(_rule_5_start_ampere(bdt, tolerances=tolerances))
        result.rules.append(
            _rule_6_end_voltage(bdt, health_pct, tolerances=tolerances))
        result.rules.append(_rule_7_inverse_relationship(bdt))
        result.rules.append(
            _rule_8_backup_time(bdt, health_pct, tolerances=tolerances))
        result.rules.append(
            _rule_9_discharge_current_tolerance(bdt, tolerances=tolerances))
    result.rules.append(_rule_10_door_alarm_match(bdt, alarm_df))
    result.rules.append(_rule_11_summary_checklist(bdt, active_groups=active_r11_groups))

    # Overall verdict — per-rule blocking policy from tolerances.verdict_policy.
    verdict_policy = tolerances.verdict_policy
    blocking_failed = [
        r for r in result.rules
        if r.verdict == "Rejected"
        and rule_blocks_overall_verdict_for_result(r, verdict_policy)
    ]
    blocking_revise = [
        r for r in result.rules
        if r.verdict == "Revise"
        and rule_blocks_overall_verdict_for_result(r, verdict_policy)
    ]
    no_alarm_data_na = any(
        r.verdict == "N/A"
        and r.rule_id == "R2"
        and rule_blocks_overall_verdict(verdict_policy, "R2")
        and "no alarm data" in str(r.detail).lower()
        for r in result.rules
    )

    if blocking_failed:
        result.overall = "Rejected"
    elif battery_skip_reason:
        result.overall = "Rejected"
    elif blocking_revise:
        result.overall = "Revise"
    elif no_alarm_data_na:
        result.overall = "Revise"
    else:
        result.overall = "Accepted"

    if component_check and result.overall == "Accepted":
        result.validation_context["display_overall"] = "Accepted (component check - no backup battery)"

    result.validation_context["verdict_policy"] = tolerances.verdict_policy.to_dict()

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


def _skipped_battery_rules(
        reason: str,
        *,
        only: tuple[str, ...] | None = None) -> list[RuleResult]:
    rules = (
        ("R2", "Power Alarm + Duration"),
        ("R3", "String vs Bus Bar Ampere"),
        ("R5", "Starting I-Battery ampere"),
        ("R6", "End Voltage Range"),
        ("R7", "V/A Inverse"),
        ("R8", "Sizing vs Actual"),
        ("R9", "Discharge Current Tolerance"),
    )
    selected = [
        (rule_id, rule_name)
        for rule_id, rule_name in rules
        if only is None or rule_id in only
    ]
    return [
        RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            passed=None,
            verdict="Skipped",
            detail=f"{reason}; battery-dependent rule not considered",
        )
        for rule_id, rule_name in selected
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


@dataclass(frozen=True)
class DoorEvidenceRow:
    """Per-candidate door alarm scoring against the BDT onsite window."""
    row_index: int
    site_id: str
    alarm_name: str
    occurred_on: pd.Timestamp
    cleared_on: pd.Timestamp | None
    overlap_min: float
    entry_delta_min: float | None
    exit_delta_min: float | None
    contained: bool
    overlaps: bool
    status_label: str


@dataclass(frozen=True)
class DoorEvidence:
    """Shared door-presence evaluation for R10 and the detail panel."""
    window_start: pd.Timestamp | None
    window_end: pd.Timestamp | None
    candidates: pd.DataFrame
    rows: list[DoorEvidenceRow]
    best: DoorEvidenceRow | None
    verdict: str
    detail: str


def _door_candidates_strict(
    alarm_df: pd.DataFrame,
    site_code: str,
    test_date: pd.Timestamp,
) -> pd.DataFrame:
    """Same site, same date, alarm_category == Door only."""
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

    return alarm_df[site_mask & date_mask & category_mask].copy()


def _valid_door_cleared(
    occurred_on: pd.Timestamp,
    cleared_on: object,
) -> pd.Timestamp | None:
    if cleared_on is None or (isinstance(cleared_on, float) and np.isnan(cleared_on)):
        return None
    try:
        cleared_ts = pd.Timestamp(cleared_on)
    except Exception:
        return None
    if pd.isna(cleared_ts) or cleared_ts < occurred_on:
        return None
    return cleared_ts


def _door_overlap_minutes(
    door_start: pd.Timestamp,
    door_end: pd.Timestamp,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> float:
    if door_end <= window_start or door_start >= window_end:
        return 0.0
    overlap_start = max(door_start, window_start)
    overlap_end = min(door_end, window_end)
    return float((overlap_end - overlap_start) / pd.Timedelta(minutes=1))


def _score_door_candidate(
    row_index: int,
    row: pd.Series,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> DoorEvidenceRow:
    occurred_on = pd.Timestamp(row["occurred_on"])
    cleared_ts = _valid_door_cleared(occurred_on, row.get("cleared_on"))
    door_end_for_overlap = cleared_ts if cleared_ts is not None else window_end
    overlap_min = _door_overlap_minutes(
        occurred_on, door_end_for_overlap, window_start, window_end
    )
    overlaps = overlap_min > 0.0
    contained = (
        cleared_ts is not None
        and occurred_on >= window_start
        and cleared_ts <= window_end
    )
    entry_delta_min = float(
        (occurred_on - window_start) / pd.Timedelta(minutes=1)
    )
    exit_delta_min = (
        float((cleared_ts - window_end) / pd.Timedelta(minutes=1))
        if cleared_ts is not None
        else None
    )
    if not overlaps:
        status_label = "No overlap"
    elif contained:
        status_label = "Accepted"
    else:
        status_label = "Revise"

    return DoorEvidenceRow(
        row_index=row_index,
        site_id=str(row.get("site_id", "")),
        alarm_name=str(row.get("alarm_name", "")),
        occurred_on=occurred_on,
        cleared_on=cleared_ts,
        overlap_min=overlap_min,
        entry_delta_min=entry_delta_min,
        exit_delta_min=exit_delta_min,
        contained=contained,
        overlaps=overlaps,
        status_label=status_label,
    )


def _format_door_ts(ts: pd.Timestamp | None) -> str:
    if ts is None or pd.isna(ts):
        return "?"
    return ts.strftime("%H:%M")


def _format_door_window(
    window_start: pd.Timestamp | None,
    window_end: pd.Timestamp | None,
) -> str:
    if window_start is None or window_end is None:
        return "unknown"
    return f"{_format_door_ts(window_start)}→{_format_door_ts(window_end)}"


def _door_evidence_detail(
    best: DoorEvidenceRow,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    verdict: str,
) -> str:
    occ = _format_door_ts(best.occurred_on)
    clr = _format_door_ts(best.cleared_on)
    window_text = _format_door_window(window_start, window_end)
    entry = best.entry_delta_min
    exit_delta = best.exit_delta_min
    entry_text = f"{entry:+.0f}m" if entry is not None else "n/a"
    exit_text = f"{exit_delta:+.0f}m" if exit_delta is not None else "n/a"

    if verdict == "Accepted":
        return (
            f"Door alarm {occ}→{clr} inside onsite window ({window_text}); "
            f"overlap {best.overlap_min:.0f}m; "
            f"entry Δ={entry_text}, exit Δ={exit_text}"
        )
    if verdict == "Revise":
        if best.cleared_on is None:
            return (
                f"Door alarm {occ}→{clr} overlaps onsite window ({window_text}) "
                f"by {best.overlap_min:.0f}m but cleared_on is missing — reviewer decision"
            )
        return (
            f"Door alarm {occ}→{clr} overlaps onsite window ({window_text}) "
            f"by {best.overlap_min:.0f}m but extends outside recorded time_in/time_out; "
            f"entry Δ={entry_text}, exit Δ={exit_text} — reviewer decision"
        )
    return ""


def _evaluate_door_evidence(bdt: BDTData, alarm_df: pd.DataFrame) -> DoorEvidence:
    window_start, window_end = _build_test_window(bdt)

    if bdt.test_date is None:
        return DoorEvidence(
            window_start=window_start,
            window_end=window_end,
            candidates=alarm_df.iloc[0:0],
            rows=[],
            best=None,
            verdict="Rejected",
            detail="Door alarm evidence is required, but the BDT test date is missing",
        )

    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return DoorEvidence(
            window_start=window_start,
            window_end=window_end,
            candidates=alarm_df.iloc[0:0],
            rows=[],
            best=None,
            verdict="Rejected",
            detail=(
                f"Door alarm evidence is required, but the BDT test date "
                f"is invalid: {bdt.test_date!r}"
            ),
        )

    if window_start is None or window_end is None:
        return DoorEvidence(
            window_start=window_start,
            window_end=window_end,
            candidates=alarm_df.iloc[0:0],
            rows=[],
            best=None,
            verdict="Revise",
            detail=(
                "Cannot evaluate door alarm evidence: invalid or missing time_in "
                "(expected HH:MM, HH:MM:SS, or AM/PM format)"
            ),
        )

    candidates = _door_candidates_strict(alarm_df, bdt.site_code, test_date)
    if candidates.empty:
        return DoorEvidence(
            window_start=window_start,
            window_end=window_end,
            candidates=candidates,
            rows=[],
            best=None,
            verdict="Rejected",
            detail=(
                f"No Door alarm found for site {bdt.site_code} on {test_date.date()}"
            ),
        )

    rows = [
        _score_door_candidate(int(idx), row, window_start, window_end)
        for idx, row in candidates.iterrows()
    ]
    overlapping = [row for row in rows if row.overlaps]
    if not overlapping:
        return DoorEvidence(
            window_start=window_start,
            window_end=window_end,
            candidates=candidates,
            rows=rows,
            best=None,
            verdict="Rejected",
            detail=(
                f"Door alarm(s) found on {test_date.date()} but none overlap onsite "
                f"window ({_format_door_window(window_start, window_end)})"
            ),
        )

    best = max(
        overlapping,
        key=lambda row: (
            row.overlap_min,
            -(
                abs(row.entry_delta_min or 0.0)
                + abs(row.exit_delta_min or 0.0)
            ),
        ),
    )
    verdict = "Accepted" if best.contained else "Revise"
    detail = _door_evidence_detail(best, window_start, window_end, verdict)
    return DoorEvidence(
        window_start=window_start,
        window_end=window_end,
        candidates=candidates,
        rows=rows,
        best=best,
        verdict=verdict,
        detail=detail,
    )


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


def _rule_2_power_alarm_match(
        bdt: BDTData,
        alarm_df: pd.DataFrame | None,
        tol_override: float | None = None,
        tolerances: "BDTTolerances | None" = None) -> RuleResult:
    """R2: Unified Power timing + duration check (Power→Cleared or Power→Down)."""
    tol_bundle = tolerances or BDTTolerances.defaults()
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
            passed=False, verdict="Revise",
            detail="Cannot check Power alarm evidence: no test date found in BDT file",
        )

    try:
        test_date = pd.Timestamp(bdt.test_date).normalize()
    except Exception:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=f"Cannot check Power alarm evidence: invalid test date {bdt.test_date!r}",
        )

    discharge_minutes = _max_reached_discharge_minutes(bdt)
    if discharge_minutes is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=("Cannot validate timing: no reached minute found in discharge table "
                    "(need at least one row with V or A reading)"),
        )

    reject_min = float(tol_bundle.incomplete_reject_minutes)
    revise_min = float(tol_bundle.incomplete_revise_minutes)
    if discharge_minutes < reject_min:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Rejected",
            detail=(f"Incomplete test: discharge table reached only "
                    f"{discharge_minutes:.0f} min (< {reject_min:.0f} min reject floor)"),
        )
    if discharge_minutes < revise_min:
        short_detail = (
            f"Short discharge evidence: reached {discharge_minutes:.0f} min "
            f"(< {revise_min:.0f} min revise band)"
        )
    else:
        short_detail = ""

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
            passed=False, verdict="Revise",
            detail=f"No matching Power alarm evidence found for site {bdt.site_code}",
        )

    power = power.copy()
    power = power[power["occurred_on"].notna()]
    if "cleared_on" not in power.columns:
        power["cleared_on"] = pd.NaT
    power = _normalize_alarm_datetimes(power)

    power_dates = power["occurred_on"].dt.normalize()
    same_date = power[power_dates == test_date].copy()
    if same_date.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=(f"No matching Power alarm evidence found on {test_date.date()} "
                    f"for site {bdt.site_code}"),
        )

    same_date["start_diff_min"] = (
        (same_date["occurred_on"] - start_ts).abs() / pd.Timedelta(minutes=1)
    )
    start_candidates = same_date[same_date["start_diff_min"] <= tol_min].copy()
    if start_candidates.empty:
        min_start = same_date["start_diff_min"].min()
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm + Duration",
            passed=False, verdict="Revise",
            detail=(f"No matching Power alarm start evidence within ±{tol_min:.0f} min "
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
        power_clear_upper = power_start + pd.Timedelta(minutes=discharge_minutes + tol_min)
        clear_usable_for_down = (
            pd.notna(power_clear)
            and power_clear >= power_start
            and power_clear <= power_clear_upper
        )
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

        if not down.empty and clear_usable_for_down:
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
            cast(float, a["start_diff_min"]) <= tol_min
            and cast(float, a["end_diff_min"]) <= tol_min
            and cast(float, a["duration_diff_min"]) <= tol_min
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
        passed=False, verdict="Revise",
        detail=(f"No matching Power timing/duration evidence within ±{tol_min:.0f} min. "
                f"Closest path {best['path']}: "
                f"start Δ={best['start_diff_min']:.1f} min, "
                f"end Δ={best['end_diff_min']:.1f} min, "
                f"duration Δ={best['duration_diff_min']:.1f} min "
                f"(alarm {best['duration_min']:.1f} min vs discharge-table max "
                f"{discharge_minutes:.1f} min)"),
    )



def _rule_5_start_ampere(bdt: BDTData,
                         tolerances: "BDTTolerances | None" = None) -> RuleResult:
    """R5: Starting I-Battery ampere should be near idle before discharge."""
    if bdt.ibat_before_test is None:
        return RuleResult(
            rule_id="R5", rule_name="Starting I-Battery ampere",
            passed=None, verdict="N/A",
            detail="Starting I-Battery ampere not found in file",
        )

    tol = tolerances or BDTTolerances.defaults()
    threshold_a = float(tol.start_ampere_a)
    passed = abs(bdt.ibat_before_test) <= threshold_a
    return RuleResult(
        rule_id="R5", rule_name="Starting I-Battery ampere",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"Starting I-Battery ampere: {bdt.ibat_before_test} A "
                f"(idle-current tolerance: |I| <= {threshold_a:.2f}A)"),
    )


def _rule_6_end_voltage(bdt: BDTData, health_pct: float,
                        tolerances: "BDTTolerances | None" = None) -> RuleResult:
    """R6: accept completed tests, in-range stops, or depleted low-voltage stops.

    Low end voltage below the normal stop band is weak/depleted battery evidence,
    not fake spreadsheet evidence. Short tests with high end voltage still fail
    because they appear to have stopped before depletion or completion.
    """
    if bdt.end_voltage is None:
        return RuleResult(
            rule_id="R6", rule_name="End Voltage Range",
            passed=None, verdict="N/A",
            detail="End voltage not found in file",
        )

    tol = tolerances or BDTTolerances.defaults()
    completion_min = float(tol.completion_minutes)
    reject_min = float(tol.incomplete_reject_minutes)
    revise_min = float(tol.incomplete_revise_minutes)
    v_min = float(tol.end_voltage_min)
    v_max = float(tol.end_voltage_max)

    reported = float(bdt.discharge_minutes or 0.0)
    reached = max_reached_discharge_minutes(bdt)
    effective_minutes = reported
    if reached is not None:
        effective_minutes = max(effective_minutes, reached)
    end_voltage = float(bdt.end_voltage)
    reached_completion = effective_minutes >= completion_min
    in_voltage_range = v_min <= end_voltage <= v_max
    depleted_low_voltage = end_voltage < v_min
    passed = reached_completion or in_voltage_range or depleted_low_voltage

    if effective_minutes < reject_min:
        return RuleResult(
            rule_id="R6", rule_name="End Voltage Range",
            passed=False, verdict="Rejected",
            detail=(f"Incomplete test: discharge reached only {effective_minutes:.0f} min "
                    f"(< {reject_min:.0f} min reject floor); "
                    f"end voltage: {end_voltage:.1f}V"),
        )

    if reached_completion:
        reason = "reached completion target"
    elif in_voltage_range:
        reason = "end voltage inside normal stop range"
    elif depleted_low_voltage:
        reason = "low end voltage indicates depleted/weak battery stop"
    else:
        reason = "short duration with high end voltage suggests early stop"

    if passed:
        verdict = "Accepted"
    elif effective_minutes < revise_min:
        verdict = "Revise"
        reason = (
            f"short discharge ({effective_minutes:.0f} min < {revise_min:.0f} min revise band); "
            f"{reason}"
        )
    else:
        verdict = "Rejected"

    return RuleResult(
        rule_id="R6", rule_name="End Voltage Range",
        passed=passed if verdict == "Accepted" else False,
        verdict=verdict,
        detail=(f"Discharge: {effective_minutes:.0f} min (target >= {completion_min:.0f}); "
                f"end voltage: {end_voltage:.1f}V (normal range: {v_min:.1f}-{v_max:.1f}V); "
                f"{reason}"),
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

    topology = battery_topology_from_bdt(bdt)
    sizing_voltage = topology.string_voltage or bdt.battery_voltage
    if sizing_voltage is None:
        return None

    efficiency = 1.0 if topology.chemistry == "lithium" else health_pct
    capacity_wh = bdt.battery_ah * sizing_voltage * bdt.num_strings * efficiency
    return (capacity_wh / load_w) * 60  # convert hours to minutes


def _rule_8_backup_time(bdt: BDTData, health_pct: float,
                        tolerance: float | None = None,
                        tolerances: "BDTTolerances | None" = None) -> RuleResult:
    """R8: Sizing-vs-actual discharge time plausibility check (never N/A).

    Business rules:
    - Missing/invalid battery specs remain Rejected because the theoretical
      backup time cannot be checked.
    - Actual backup shorter than theoretical is valid weak/short backup evidence.
    - When theoretical exceeds the completion cap, an actual below the cap is
      still Accepted as weak backup evidence and reports how short it was.
    - Actual backup materially above theoretical is suspicious over-performance
      and is Rejected when it exceeds the configured tolerance window.
    """
    tol = tolerances or BDTTolerances.defaults()
    fractional = (
        float(tolerance) if tolerance is not None else float(tol.sizing_fractional_tolerance)
    )
    minutes_floor = float(tol.sizing_minutes_floor)
    completion_min = float(tol.completion_minutes)

    reported = float(bdt.discharge_minutes or 0.0)
    theoretical_mins = _theoretical_backup_minutes(bdt, health_pct)

    if theoretical_mins is None:
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=False, verdict="Rejected",
            detail=("Cannot compute theoretical duration (missing/invalid AH, voltage, "
                    "strings, or starting load readings)"),
        )

    fractional_window = theoretical_mins * fractional
    tol_min = max(fractional_window, minutes_floor)
    floor_won = minutes_floor > fractional_window
    if floor_won:
        explanation = f"{minutes_floor:.0f} min floor"
    else:
        explanation = f"{fractional * 100:.0f}% of theoretical"

    if theoretical_mins > completion_min:
        short_by = max(0.0, completion_min - reported)
        if reported < completion_min:
            detail = (f"Theoretical: {theoretical_mins:.0f} min (>{completion_min:.0f} cap), "
                      f"actual: {reported:.0f} min; weak/short backup evidence, "
                      f"short by {short_by:.1f} min to cap")
        else:
            detail = (f"Theoretical: {theoretical_mins:.0f} min (>{completion_min:.0f} cap), "
                      f"actual: {reported:.0f} min (reached cap)")
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=True, verdict="Accepted", detail=detail,
        )

    upper_limit = theoretical_mins + tol_min
    if reported <= upper_limit:
        if reported < theoretical_mins:
            short_by = theoretical_mins - reported
            status = f"weak/short backup evidence, short by {short_by:.1f} min"
        else:
            over_by = reported - theoretical_mins
            status = f"within expected upper window, over by {over_by:.1f} min"
        return RuleResult(
            rule_id="R8", rule_name="Sizing vs Actual",
            passed=True, verdict="Accepted",
            detail=(f"Theoretical: {theoretical_mins:.0f} min, actual: {reported:.0f} min; "
                    f"{status} (upper limit: {upper_limit:.1f} min, {explanation})"),
        )

    over_by = reported - theoretical_mins
    return RuleResult(
        rule_id="R8", rule_name="Sizing vs Actual",
        passed=False, verdict="Rejected",
        detail=(f"Theoretical: {theoretical_mins:.0f} min, actual: {reported:.0f} min; "
                f"over-performance beyond expected sizing by {over_by:.1f} min "
                f"(upper limit: {upper_limit:.1f} min, {explanation})"),
    )


def _rule_9_discharge_current_tolerance(
        bdt: BDTData,
        tolerances: "BDTTolerances | None" = None) -> RuleResult:
    """R9: Discharge current stability using max delta, slope, and late spikes."""
    metrics = discharge_trend_metrics(bdt)
    if metrics is None:
        count = sum(1 for _, _, a in bdt.discharge_readings if a is not None)
        return RuleResult(
            rule_id="R9", rule_name="Discharge Current Tolerance",
            passed=None, verdict="N/A",
            detail=f"Insufficient discharge current readings ({count}, need 2+)",
        )

    tol = tolerances or BDTTolerances.defaults()
    accept_delta = float(tol.discharge_current_accept_a)
    accept_slope = float(tol.discharge_slope_accept_a_per_min)
    reject_slope = float(tol.discharge_slope_reject_a_per_min)
    reject_spike = float(tol.discharge_spike_reject_a)
    abs_floor = float(tol.discharge_current_a)
    pct = float(tol.discharge_current_pct)
    legacy_band = max(abs(metrics.baseline_amp) * pct, abs_floor)

    verdict = "Accepted"
    reasons: list[str] = []

    if metrics.bus_amp_slope >= reject_slope:
        verdict = "Rejected"
        reasons.append(
            f"bus current trend {metrics.bus_amp_slope:.2f} A/min "
            f"(>= {reject_slope:.2f} reject slope)")
    if metrics.late_delta >= reject_spike:
        verdict = "Rejected"
        reasons.append(
            f"late-interval spike |Δ|={metrics.late_delta:.2f}A "
            f"(>= {reject_spike:.1f}A)")
    if metrics.max_delta > legacy_band and verdict != "Rejected":
        if (
            metrics.max_delta > accept_delta
            and metrics.bus_amp_slope > accept_slope
        ):
            verdict = "Rejected"
            reasons.append(
                f"max |Δ|={metrics.max_delta:.2f}A with slope "
                f"{metrics.bus_amp_slope:.2f} A/min beyond accept bands")
        elif metrics.max_delta > accept_delta or metrics.bus_amp_slope > accept_slope:
            if verdict != "Rejected":
                verdict = "Revise"
            reasons.append(
                f"max |Δ|={metrics.max_delta:.2f}A (accept <= {accept_delta:.1f}A) "
                f"or slope {metrics.bus_amp_slope:.2f} A/min (accept <= {accept_slope:.2f})")

    if verdict == "Accepted":
        detail = (
            f"Bus current stable: max |Δ|={metrics.max_delta:.2f}A, "
            f"slope={metrics.bus_amp_slope:.2f} A/min "
            f"(accept bands: {accept_delta:.1f}A / {accept_slope:.2f} A/min)"
        )
    else:
        detail = "; ".join(reasons)

    return RuleResult(
        rule_id="R9", rule_name="Discharge Current Tolerance",
        passed=verdict == "Accepted",
        verdict=verdict,
        detail=detail,
    )


def _find_door_alarms(
    alarm_df: pd.DataFrame,
    site_code: str,
    test_date: pd.Timestamp,
    window_start: pd.Timestamp | None = None,
    window_end: pd.Timestamp | None = None,
    strict_window: bool = False,
) -> pd.DataFrame:
    """List same-site Door-category alarms on the test date.

    ``window_start``, ``window_end``, and ``strict_window`` are accepted for
    backward compatibility but no longer filter candidates. Use
    :func:`_evaluate_door_evidence` for onsite-window verdict logic.
    """
    _ = (window_start, window_end, strict_window)
    return _door_candidates_strict(alarm_df, site_code, test_date)


def _rule_10_door_alarm_match(bdt: BDTData,
                              alarm_df: pd.DataFrame | None) -> RuleResult:
    """R10: Door alarm evidence aligned with human reviewer judgment."""
    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R10", rule_name="Door Alarm Condition",
            passed=False, verdict="Revise",
            detail="Door alarm evidence is required, but no alarm data loaded",
        )

    evidence = _evaluate_door_evidence(bdt, alarm_df)
    passed: bool | None = evidence.verdict == "Accepted"
    if evidence.verdict == "N/A":
        passed = None
    return RuleResult(
        rule_id="R10", rule_name="Door Alarm Condition",
        passed=passed,
        verdict=evidence.verdict,
        detail=evidence.detail,
    )


def _rule_3_string_vs_busbar(bdt: BDTData,
                             tolerances: "BDTTolerances | None" = None) -> RuleResult:
    """R3: Rectifier vs string amps with E−Σ bands and string-imbalance checks."""
    evidence = worst_r3_evidence(bdt)
    if evidence is None:
        if not bdt.string_discharge_readings or not bdt.discharge_readings:
            detail = "No per-string discharge data available"
        else:
            detail = "No valid paired readings found"
        return RuleResult(
            rule_id="R3", rule_name="String vs Bus Bar Ampere",
            passed=None, verdict="N/A",
            detail=detail,
        )

    tol = tolerances or BDTTolerances.defaults()
    neg_reject = float(tol.string_ampere_a)
    pos_accept = float(tol.string_ampere_pos_accept_a)
    pos_revise = float(tol.string_ampere_pos_revise_a)
    imb_reject = float(tol.string_imbalance_reject_ratio)
    imb_revise = float(tol.string_imbalance_revise_ratio)

    verdict = "Accepted"
    reasons: list[str] = []

    if evidence.worst_imbalance_ratio >= imb_reject:
        verdict = "Rejected"
        reasons.append(
            f"string imbalance {evidence.worst_imbalance_ratio:.0%} at "
            f"{evidence.worst_imbalance_label} (>= {imb_reject:.0%})")
    elif evidence.worst_imbalance_ratio >= imb_revise:
        verdict = "Revise"
        reasons.append(
            f"string imbalance {evidence.worst_imbalance_ratio:.0%} at "
            f"{evidence.worst_imbalance_label} (revise band >= {imb_revise:.0%})")

    if evidence.max_neg_delta > neg_reject:
        verdict = "Rejected"
        reasons.append(
            f"strings exceed bus by {evidence.max_neg_delta:.2f}A "
            f"(> {neg_reject:.1f}A reject bound)")
    elif evidence.max_pos_delta > 10.0:
        verdict = "Rejected"
        reasons.append(
            f"severe bus-above-strings gap {evidence.max_pos_delta:.2f}A (> 10A)")
    elif evidence.max_pos_delta > pos_revise:
        verdict = "Rejected"
        reasons.append(
            f"max positive E-(G+I)={evidence.max_pos_delta:.2f}A "
            f"(> {pos_revise:.1f}A reject bound)")
    elif evidence.max_pos_delta > pos_accept:
        if verdict != "Rejected":
            verdict = "Revise"
        reasons.append(
            f"max positive E-(G+I)={evidence.max_pos_delta:.2f}A "
            f"(revise band > {pos_accept:.1f}A)")

    if verdict == "Accepted":
        detail = (
            f"All {evidence.checked_points} time points within accept bands "
            f"(E-(G+I) +<={pos_accept:.1f}A / -<={neg_reject:.1f}A; "
            f"imbalance < {imb_revise:.0%})"
        )
    else:
        detail = "Batteries Amp not matched with the rectifier summation Amp; " + "; ".join(
            reasons)

    return RuleResult(
        rule_id="R3", rule_name="String vs Bus Bar Ampere",
        passed=verdict == "Accepted",
        verdict=verdict,
        detail=detail,
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


def _has_numeric_comparison_value(value: str) -> bool:
    normalized = _normalize_for_comparison(value)
    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", normalized))


_SUMMARY_KEY_ALIASES = {
    "Short Code": ("Short Code", "Site Code", "Site ID"),
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
    raw_entries = []
    for key, value in summary_data.items():
        raw_key = str(key or "").strip()
        nk = _normalize_summary_key(key)
        raw_entries.append((raw_key, value))
        if nk and nk not in normalized:
            normalized[nk] = value
    aliases = list(_SUMMARY_KEY_ALIASES.get(canonical_key, (canonical_key,)))
    normalized_aliases = [_normalize_summary_key(alias) for alias in aliases]
    for alias in normalized_aliases:
        val = normalized.get(alias)
        if val is not None:
            return str(val)
    for alias in aliases:
        alias_text = " ".join(str(alias or "").strip().casefold().split())
        if not alias_text:
            continue
        for raw_key, value in raw_entries:
            key_text = " ".join(raw_key.casefold().split())
            if not key_text.startswith(alias_text):
                continue
            suffix = key_text[len(alias_text):]
            if not suffix or not suffix[0].isalnum():
                return str(value)
    return ""


def _rule_11_summary_checklist(bdt: BDTData, active_groups: set[str] | None = None) -> RuleResult:
    """R11: Cross-check key fields between BDT sheet and Summary sheet."""
    if not bdt.summary_data:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=None, verdict="N/A",
            detail="No Summary sheet data available",
        )

    active = set(active_groups or {"A", "B1", "B2"})
    checks = [
        ("A", "Short Code",      str(bdt.site_code or ""),           "Short Code"),
        ("A", "PLD Value",       str(bdt.pld_value or ""),           "PLVD Value"),
        ("A", "Rectifier Brand", str(bdt.rectifier_brand or ""),     "Rectifier Brand"),
        ("A", "Number of Modules", str(bdt.num_modules or ""),       "# of Modules"),
        ("B1", "Battery Brand",   str(bdt.battery_brand or ""),       "Battery Brand"),
        ("B1", "Battery Voltage", str(bdt.battery_voltage or ""),     "Battery Volt"),
        ("B1", "Number of Strings", str(bdt.num_strings or ""),       "No of String"),
        ("B1", "Number of Batteries", str(bdt.num_batteries or ""),   "No of Batteries"),
        ("B2", "Start Voltage",   str(bdt.start_voltage or ""),       "Start Volt"),
        ("B2", "Start Amp",       str(bdt.start_ampere or ""),        "Start Amp"),
        ("B2", "End Voltage",     str(bdt.end_voltage or ""),         "End Volt"),
        ("B2", "End Amp",         str(bdt.end_ampere or ""),          "End Amp"),
        ("B2", "Discharge Time (mins)", str(bdt.discharge_minutes or ""), "Discharge time( Mins)"),
        ("A", "Test Date",       (bdt.test_date.strftime("%Y-%m-%d") if bdt.test_date else ""), "Test Date"),
    ]

    mismatches = []
    group_checked = {"A": 0, "B1": 0, "B2": 0}
    group_mismatches = {"A": 0, "B1": 0, "B2": 0}
    checked = 0
    for group, display_name, bdt_val, summary_key in checks:
        if group not in active:
            continue
        summary_val = _summary_lookup_value(bdt.summary_data, summary_key)
        if display_name == "PLD Value" and not _has_numeric_comparison_value(bdt_val):
            continue
        if not bdt_val and not summary_val:
            continue  # skip fields missing from both
        checked += 1
        group_checked[group] += 1
        if not _values_match(bdt_val, summary_val, display_name):
            group_mismatches[group] += 1
            mismatches.append(f"{display_name}: BDT='{bdt_val}' vs Summary='{summary_val}'")

    group_detail = _r11_group_detail(group_checked, group_mismatches, active)
    if checked == 0:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=None, verdict="N/A",
            detail=f"No comparable fields found between BDT and Summary sheets; {group_detail}",
        )

    if not mismatches:
        return RuleResult(
            rule_id="R11", rule_name="Summary Checklist",
            passed=True, verdict="Accepted",
            detail=f"All {checked} active checklist fields match between BDT and Summary sheets; {group_detail}",
        )

    n = len(mismatches)
    detail = f"{n} mismatch(es): " + "; ".join(mismatches[:5])
    if n > 5:
        detail += f" (and {n - 5} more)"
    detail += f"; {group_detail}"

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


def _r11_group_detail(group_checked: dict[str, int], group_mismatches: dict[str, int], active: set[str]) -> str:
    labels = {"A": "Group A", "B1": "Group B1", "B2": "Group B2"}
    parts = []
    for group in ("A", "B1", "B2"):
        label = labels[group]
        if group in active:
            matched = group_checked[group] - group_mismatches[group]
            parts.append(
                f"{label}: checked {group_checked[group]}, matched {matched}, "
                f"mismatches {group_mismatches[group]}"
            )
        else:
            parts.append(f"skipped {label} (inactive for this battery context)")
    return "; ".join(parts)
