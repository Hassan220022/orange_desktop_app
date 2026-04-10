"""
BDT History -- store and compare battery discharge test records across time.

Persists BDT validation results per site to detect equipment changes
between consecutive PM visits (battery type, count, rectifier, modules).
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

import pandas as pd

try:
    from ..constants import APP_VERSION
except ImportError:
    from alarm_app.constants import APP_VERSION


HISTORY_DIR = Path.home() / ".alarm_viewer" / "bdt_history"
PM_RUNS_DIR = HISTORY_DIR / "_pm_runs"
PM_RULE_RESULTS_DIR = HISTORY_DIR / "_pm_rule_results"


@dataclass
class BDTTestRecord:
    """Stored snapshot of a BDT test for future comparison."""
    site_code: str
    test_date: str            # ISO format YYYY-MM-DD
    file_path: str
    battery_brand: str
    battery_ah: float | None
    battery_voltage: float | None
    num_strings: int | None
    num_batteries: int | None
    num_modules: int | None
    rectifier_brand: str
    overall_verdict: str
    saved_at: str             # ISO datetime when saved


@dataclass
class BDTComparison:
    """Result of comparing current vs previous BDT test."""
    previous: BDTTestRecord
    current_date: str
    differences: list[str]      # Human-readable change descriptions
    has_critical_change: bool   # True if battery type/count/rectifier changed


def _iso_date_str(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value or "")


def _normalize_site_code(value) -> str:
    return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())


def _canonical_json_sha256(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _alarm_subset_for_hash(alarm_df, site_code: str, test_date: str) -> list[dict]:
    if alarm_df is None:
        return []
    if not isinstance(alarm_df, pd.DataFrame) or alarm_df.empty:
        return []

    subset = alarm_df.copy()

    if "site_id" in subset.columns:
        keys = subset["site_id"].fillna("").map(_normalize_site_code)
        subset = subset[keys == _normalize_site_code(site_code)]

    if "occurred_on" in subset.columns and test_date:
        occurred = pd.to_datetime(subset["occurred_on"], errors="coerce", format="mixed")
        subset = subset[occurred.dt.strftime("%Y-%m-%d") == test_date]

    if subset.empty:
        return []

    candidate_cols = [
        "site_id",
        "alarm_name",
        "alarm_id",
        "network_type",
        "vendor",
        "occurred_on",
        "cleared_on",
        "duration",
        "clearance_status",
        "alarm_source",
        "alarm_category",
        "site_down_flag",
        "file_source",
    ]
    cols = [c for c in candidate_cols if c in subset.columns]
    if not cols:
        return []
    subset = subset[cols].copy()

    for col in subset.columns:
        if col in ("occurred_on", "cleared_on"):
            ts = pd.to_datetime(subset[col], errors="coerce", format="mixed")
            subset[col] = ts.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
        else:
            subset[col] = subset[col].fillna("").astype(str).str.strip()

    subset = subset.sort_values(cols).reset_index(drop=True)
    return subset.to_dict(orient="records")


def compute_alarm_input_sha256(alarm_df, site_code: str, test_date: str) -> str:
    """Return deterministic alarm-input hash for PM replayability."""
    rows = _alarm_subset_for_hash(alarm_df, site_code, test_date)
    payload = {
        "site_code": _normalize_site_code(site_code),
        "test_date": test_date,
        "rows": rows,
    }
    return _canonical_json_sha256(payload)


def save_test_record(bdt, verdict: str) -> None:
    """Persist a BDT test result for future comparison.

    Args:
        bdt: BDTData instance (from bdt_parser)
        verdict: Overall validation verdict string
    """
    if not bdt.site_code or not bdt.test_date:
        return

    site_dir = HISTORY_DIR / bdt.site_code.strip().upper()
    site_dir.mkdir(parents=True, exist_ok=True)

    test_date_str = (bdt.test_date.strftime("%Y-%m-%d")
                     if isinstance(bdt.test_date, (date, datetime))
                     else str(bdt.test_date))

    record = BDTTestRecord(
        site_code=bdt.site_code,
        test_date=test_date_str,
        file_path=str(bdt.file_path or ""),
        battery_brand=str(bdt.battery_brand or ""),
        battery_ah=bdt.battery_ah,
        battery_voltage=bdt.battery_voltage,
        num_strings=bdt.num_strings,
        num_batteries=getattr(bdt, "num_batteries", None),
        num_modules=getattr(bdt, "num_modules", None),
        rectifier_brand=str(getattr(bdt, "rectifier_brand", "") or ""),
        overall_verdict=verdict,
        saved_at=datetime.now().isoformat(),
    )

    filename = f"{test_date_str}.json"
    path = site_dir / filename
    path.write_text(json.dumps(asdict(record), indent=2, default=str))


def load_previous_test(site_code: str, before_date: date) -> BDTTestRecord | None:
    """Find the most recent test record for a site before the given date.

    Args:
        site_code: Site identifier (e.g., "0167DE")
        before_date: Find tests BEFORE this date

    Returns:
        BDTTestRecord or None if no history found
    """
    site_dir = HISTORY_DIR / site_code.strip().upper()
    if not site_dir.exists():
        return None

    best_record = None
    best_date = None

    for json_file in site_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
            record_date = date.fromisoformat(data["test_date"])
            if record_date < before_date:
                if best_date is None or record_date > best_date:
                    best_date = record_date
                    best_record = BDTTestRecord(**{
                        k: data.get(k) for k in BDTTestRecord.__dataclass_fields__
                    })
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    return best_record


def compare_tests(current_bdt, previous: BDTTestRecord) -> BDTComparison:
    """Compare current BDT data against a previous test record.

    Args:
        current_bdt: BDTData instance (current test)
        previous: BDTTestRecord (historical test)

    Returns:
        BDTComparison with list of differences and critical change flag
    """
    differences = []
    critical = False

    current_date = (current_bdt.test_date.strftime("%Y-%m-%d")
                    if isinstance(current_bdt.test_date, (date, datetime))
                    else str(current_bdt.test_date or ""))

    # Critical fields: changes here indicate equipment swap
    _crit = [
        ("Battery Brand",
         str(current_bdt.battery_brand or "").strip().lower(),
         str(previous.battery_brand or "").strip().lower()),
        ("Number of Batteries",
         str(getattr(current_bdt, "num_batteries", None) or ""),
         str(previous.num_batteries or "")),
        ("Number of Modules",
         str(getattr(current_bdt, "num_modules", None) or ""),
         str(previous.num_modules or "")),
        ("Rectifier Brand",
         str(getattr(current_bdt, "rectifier_brand", "") or "").strip().lower(),
         str(previous.rectifier_brand or "").strip().lower()),
    ]

    for label, curr, prev in _crit:
        if curr and prev and curr != prev:
            differences.append(f"{label}: '{prev}' -> '{curr}'")
            critical = True

    # Non-critical fields: spec changes
    _spec = [
        ("Battery AH", current_bdt.battery_ah, previous.battery_ah),
        ("Battery Voltage", current_bdt.battery_voltage, previous.battery_voltage),
        ("Number of Strings", current_bdt.num_strings, previous.num_strings),
    ]

    for label, curr, prev in _spec:
        if curr is not None and prev is not None and curr != prev:
            differences.append(f"{label}: {prev} -> {curr}")

    return BDTComparison(
        previous=previous,
        current_date=current_date,
        differences=differences,
        has_critical_change=critical,
    )


def save_validation_run(
    *,
    bdt_data,
    validation_result,
    alarm_df,
    params: dict,
    validator_code_ref: str | None = None,
) -> dict | None:
    """Persist PM run metadata and one rule row per evaluated rule."""
    site_code = str(getattr(bdt_data, "site_code", "") or "").strip().upper()
    if not site_code:
        return None

    test_date = _iso_date_str(getattr(bdt_data, "test_date", ""))
    if not test_date:
        return None

    rules = list(getattr(validation_result, "rules", []) or [])
    if not rules:
        return None

    validator_ref = validator_code_ref or f"alarm_app.bdt_validator.validate_bdt@{APP_VERSION}"
    params_sha256 = _canonical_json_sha256(params or {})
    alarm_input_sha256 = compute_alarm_input_sha256(alarm_df, site_code, test_date)
    idempotency_material = {
        "site_code": site_code,
        "test_date": test_date,
        "params_sha256": params_sha256,
        "alarm_input_sha256": alarm_input_sha256,
        "validator_code_ref": validator_ref,
    }
    idempotency_key = _canonical_json_sha256(idempotency_material)
    run_uuid = str(uuid5(NAMESPACE_URL, idempotency_key))

    PM_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    PM_RULE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    run_path = PM_RUNS_DIR / f"{idempotency_key}.json"
    rules_path = PM_RULE_RESULTS_DIR / f"{run_uuid}.jsonl"

    run_payload = {
        "run_id": run_uuid,
        "idempotency_key": idempotency_key,
        "site_code": site_code,
        "test_date": test_date,
        "file_path": str(getattr(bdt_data, "file_path", "") or ""),
        "overall_verdict": str(getattr(validation_result, "overall", "") or ""),
        "validator_code_ref": validator_ref,
        "params": params or {},
        "params_sha256": params_sha256,
        "alarm_input_sha256": alarm_input_sha256,
        "rule_count": len(rules),
        "is_complete_rule_set": len(rules) == 11,
        "created_at": datetime.now().isoformat(),
    }

    if not run_path.exists():
        run_path.write_text(
            json.dumps(run_payload, indent=2, default=str),
            encoding="utf-8",
        )

    if not rules_path.exists():
        seen_rule_ids: set[str] = set()
        with rules_path.open("w", encoding="utf-8") as fh:
            for idx, rule in enumerate(rules, start=1):
                rule_id = str(getattr(rule, "rule_id", "") or "")
                if not rule_id or rule_id in seen_rule_ids:
                    continue
                seen_rule_ids.add(rule_id)

                row = {
                    "run_id": run_uuid,
                    "rule_order": idx,
                    "rule_id": rule_id,
                    "rule_name": str(getattr(rule, "rule_name", "") or ""),
                    "verdict": str(getattr(rule, "verdict", "") or ""),
                    "detail": str(getattr(rule, "detail", "") or ""),
                    "passed": getattr(rule, "passed", None),
                    "rule_version": validator_ref,
                    "evidence": {
                        "detail": str(getattr(rule, "detail", "") or ""),
                        "passed": getattr(rule, "passed", None),
                    },
                    "created_at": datetime.now().isoformat(),
                }
                fh.write(json.dumps(row, default=str) + "\n")

    return run_payload
