"""
BDT History -- store and compare battery discharge test records across time.

Persists BDT validation results per site to detect equipment changes
between consecutive PM visits (battery type, count, rectifier, modules).
"""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

try:
    from alarm_app.constants import APP_VERSION, BDT_RULES
    from alarm_app.core.battery_topology import (
        battery_topology_from_bdt,
        build_battery_topology,
        format_voltage,
        is_lead_acid_to_lithium_upgrade,
    )
except ImportError:
    from constants import APP_VERSION, BDT_RULES
    from core.battery_topology import (
        battery_topology_from_bdt,
        build_battery_topology,
        format_voltage,
        is_lead_acid_to_lithium_upgrade,
    )

HISTORY_DIR = Path.home() / ".alarm_viewer" / "bdt_history"
PM_RUNS_DIR = HISTORY_DIR / "_pm_runs"
PM_RULE_RESULTS_DIR = HISTORY_DIR / "_pm_rule_results"
_log = logging.getLogger(__name__)


def _get_session():
    try:
        from alarm_app.db.engine import get_shared_session, init_app_db
    except ImportError:
        from db.engine import get_shared_session, init_app_db

    # Ensure tables exist (idempotent, cheap after first call)
    try:
        init_app_db()
    except Exception:
        pass

    return get_shared_session()


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
    upgrade_detected: bool = False
    change_status: str = "No Critical Changes"


def _iso_date_str(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value or "")


def _normalize_site_code(value) -> str:
    return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())


def _canonical_json_sha256(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_sqlite_lock_error(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


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


def _bdt_test_to_record(db_row) -> BDTTestRecord:
    """Convert a BDTTest ORM row to a BDTTestRecord dataclass."""
    test_date = db_row.test_date
    if hasattr(test_date, "strftime"):
        test_date_str = test_date.strftime("%Y-%m-%d")
    else:
        test_date_str = str(test_date or "")

    created_at = db_row.created_at
    if hasattr(created_at, "isoformat"):
        saved_at = created_at.isoformat()
    else:
        saved_at = str(created_at or "")

    return BDTTestRecord(
        site_code=str(db_row.site_code or ""),
        test_date=test_date_str,
        file_path="",
        battery_brand=str(db_row.battery_brand or ""),
        battery_ah=db_row.battery_ah,
        battery_voltage=db_row.battery_voltage,
        num_strings=db_row.num_strings,
        num_batteries=db_row.num_batteries,
        num_modules=db_row.num_modules,
        rectifier_brand=str(db_row.rectifier_brand or ""),
        overall_verdict="",
        saved_at=saved_at,
    )


def _to_test_date_obj(raw_value) -> date | None:
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        _log.debug("Invalid date format for _to_test_date_obj: %s", raw_value)
        return None


def _build_bdt_dict(bdt_data, verdict: str | None = None) -> dict:
    test_date_obj = _to_test_date_obj(getattr(bdt_data, "test_date", ""))
    payload = {
        "site_code": str(getattr(bdt_data, "site_code", "") or ""),
        "test_date": test_date_obj,
        "file_path": str(getattr(bdt_data, "file_path", "") or ""),
        "battery_brand": str(getattr(bdt_data, "battery_brand", "") or ""),
        "battery_ah": getattr(bdt_data, "battery_ah", None),
        "battery_voltage": getattr(bdt_data, "battery_voltage", None),
        "num_strings": getattr(bdt_data, "num_strings", None),
        "num_batteries": getattr(bdt_data, "num_batteries", None),
        "num_modules": getattr(bdt_data, "num_modules", None),
        "rectifier_brand": str(getattr(bdt_data, "rectifier_brand", "") or ""),
        "start_voltage": getattr(bdt_data, "start_voltage", None),
        "end_voltage": getattr(bdt_data, "end_voltage", None),
        "start_ampere": getattr(bdt_data, "start_ampere", None),
        "end_ampere": getattr(bdt_data, "end_ampere", None),
        "discharge_minutes": getattr(bdt_data, "discharge_minutes", None),
        "pld_value": getattr(bdt_data, "pld_value", None),
        "site_name": getattr(bdt_data, "site_name", ""),
        "time_in": getattr(bdt_data, "time_in", ""),
        "time_out": getattr(bdt_data, "time_out", ""),
        "ibat_before_test": getattr(bdt_data, "ibat_before_test", None),
        "starting_ibattery_ampere": getattr(bdt_data, "starting_ibattery_ampere", None),
        "after_reconnect_voltage": getattr(bdt_data, "after_reconnect_voltage", None),
        "after_reconnect_ampere": getattr(bdt_data, "after_reconnect_ampere", None),
        "discharge_readings": getattr(bdt_data, "discharge_readings", []),
        "string_discharge_readings": getattr(bdt_data, "string_discharge_readings", []),
        "summary_data": getattr(bdt_data, "summary_data", {}),
        # Layout metadata for multi-layout support
        "core_layout": getattr(bdt_data, "core_layout", ""),
        "photo_layout_id": getattr(bdt_data, "photo_layout_id", ""),
        "required_photo_count": getattr(bdt_data, "required_photo_count", 16),
    }
    if verdict is not None:
        payload["overall_verdict"] = verdict
    return payload


def _register_bdt_uploaded_file(session, bdt_data) -> int | None:
    file_path = str(getattr(bdt_data, "file_path", "") or "").strip()
    if not file_path:
        return None
    path_obj = Path(file_path)
    if not path_obj.is_file():
        return None

    try:
        from alarm_app.db.hashing import compute_file_sha256
    except ImportError:
        from db.hashing import compute_file_sha256
    try:
        from alarm_app.db.repos.file_repo import register_file as _register_file
    except ImportError:
        from db.repos.file_repo import register_file as _register_file

    file_sha256 = compute_file_sha256(path_obj)
    record = _register_file(
        session,
        file_sha256=file_sha256,
        original_path=str(path_obj),
        original_name=path_obj.name,
        file_size=path_obj.stat().st_size,
        source_kind="bdt_xlsx",
    )
    return int(record.id) if record and getattr(record, "id", None) else None


def _build_rule_results(validation_result) -> list[dict]:
    rules = list(getattr(validation_result, "rules", []) or [])
    seen_rule_ids: set[str] = set()
    output = []
    for rule in rules:
        rule_id = str(getattr(rule, "rule_id", "") or "")
        if not rule_id or rule_id in seen_rule_ids:
            continue
        seen_rule_ids.add(rule_id)
        output.append({
            "rule_code": rule_id,
            "verdict": str(getattr(rule, "verdict", "") or ""),
            "detail": str(getattr(rule, "detail", "") or ""),
        })
    return output


def _build_run_payload(
    *,
    bdt_data,
    validation_result,
    params: dict,
    validator_ref: str,
    params_sha256: str,
    alarm_input_sha256: str,
    idempotency_key: str,
    run_uuid: str,
    rule_count: int,
) -> dict:
    test_date = _iso_date_str(getattr(bdt_data, "test_date", ""))
    overall_verdict = str(getattr(validation_result, "overall", "") or "")
    return {
        "run_id": run_uuid,
        "idempotency_key": idempotency_key,
        "site_code": str(getattr(bdt_data, "site_code", "") or "").strip().upper(),
        "test_date": test_date,
        "file_path": str(getattr(bdt_data, "file_path", "") or ""),
        "overall_verdict": overall_verdict,
        "validator_code_ref": validator_ref,
        "params": params or {},
        "params_sha256": params_sha256,
        "alarm_input_sha256": alarm_input_sha256,
        "rule_count": rule_count,
        "is_complete_rule_set": rule_count == len(BDT_RULES),
        "created_at": datetime.now().isoformat(),
    }


def save_test_record(bdt, verdict: str) -> None:
    """Persist a BDT test result for future comparison.

    Args:
        bdt: BDTData instance (from bdt_parser)
        verdict: Overall validation verdict string
    """
    if not bdt.site_code or not bdt.test_date:
        return

    bdt_dict = _build_bdt_dict(bdt, verdict=verdict)

    try:
        from alarm_app.db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    except ImportError:
        from db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    session = _get_session()
    try:
        file_id = _register_bdt_uploaded_file(session, bdt)
        bdt_record = _save_bdt_test(session, bdt_dict, file_id=file_id)
        session.commit()

        # Persist photos to blob storage
        photo_slots = getattr(bdt, "photo_slots", [])
        if photo_slots and bdt_record:
            try:
                try:
                    from alarm_app.db.repos.photo_service import persist_bdt_photos
                except ImportError:
                    from db.repos.photo_service import persist_bdt_photos
                persist_bdt_photos(session, bdt_record.id, photo_slots)
            except Exception:
                pass  # photo persistence is best-effort
    finally:
        session.close()


def load_previous_test(site_code: str, before_date: date) -> BDTTestRecord | None:
    """Find the most recent test record for a site before the given date.

    Args:
        site_code: Site identifier (e.g., "0167DE")
        before_date: Find tests BEFORE this date

    Returns:
        BDTTestRecord or None if no history found
    """
    try:
        from alarm_app.db.repos.bdt_repo import load_previous_test as _load_previous_test
    except ImportError:
        from db.repos.bdt_repo import load_previous_test as _load_previous_test
    session = _get_session()
    try:
        db_row = _load_previous_test(session, site_code, before_date)
        if db_row is None:
            return None
        return _bdt_test_to_record(db_row)
    finally:
        session.close()


def load_second_most_recent_test(site_code: str) -> BDTTestRecord | None:
    """Return the second most recent test for a site.

    Useful when test_date is None or load_previous_test found nothing:
    we grab the two newest rows and return the older one.

    Args:
        site_code: Site identifier (e.g., "0167DE")

    Returns:
        BDTTestRecord or None if fewer than two tests exist
    """
    if not site_code or not str(site_code).strip():
        return None
    try:
        from alarm_app.db.repos.bdt_repo import load_second_most_recent as _load
    except ImportError:
        from db.repos.bdt_repo import load_second_most_recent as _load
    session = _get_session()
    try:
        db_row = _load(session, site_code)
        if db_row is None:
            return None
        return _bdt_test_to_record(db_row)
    finally:
        session.close()


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

    current_topology = battery_topology_from_bdt(current_bdt)
    previous_topology = build_battery_topology(
        brand=previous.battery_brand,
        battery_ah=previous.battery_ah,
        battery_voltage=previous.battery_voltage,
        num_strings=previous.num_strings,
        num_batteries=previous.num_batteries,
    )
    upgrade_detected = is_lead_acid_to_lithium_upgrade(previous_topology, current_topology)

    if upgrade_detected:
        critical = True
        differences.append(
            "Lead-acid to lithium upgrade: "
            f"{previous.battery_brand or 'previous battery'} -> "
            f"{getattr(current_bdt, 'battery_brand', '') or 'current battery'} "
            f"(previous string voltage {format_voltage(previous_topology.string_voltage)}V, "
            f"current string voltage {format_voltage(current_topology.string_voltage)}V)"
        )

    # Critical fields: changes here indicate equipment swap. Battery topology
    # fields are summarized once for lead-acid-to-lithium upgrades instead of
    # producing noisy raw 12V/48V, 16/3, 4/3 mismatches.
    _crit = []
    if not upgrade_detected:
        _crit.extend([
            ("Battery Brand",
             str(current_bdt.battery_brand or "").strip().lower(),
             str(previous.battery_brand or "").strip().lower()),
            ("Number of Batteries",
             str(getattr(current_bdt, "num_batteries", None) or ""),
             str(previous.num_batteries or "")),
        ])
    _crit.extend([
        ("Number of Modules",
         str(getattr(current_bdt, "num_modules", None) or ""),
         str(previous.num_modules or "")),
        ("Rectifier Brand",
         str(getattr(current_bdt, "rectifier_brand", "") or "").strip().lower(),
         str(previous.rectifier_brand or "").strip().lower()),
    ])

    for label, curr, prev in _crit:
        if curr and prev and curr != prev:
            differences.append(f"{label}: '{prev}' -> '{curr}'")
            critical = True

    # Non-critical fields: spec changes
    _spec = [] if upgrade_detected else [
        ("Battery AH", current_bdt.battery_ah, previous.battery_ah),
        ("Battery Voltage", current_bdt.battery_voltage, previous.battery_voltage),
        ("Number of Strings", current_bdt.num_strings, previous.num_strings),
    ]

    for s_label, s_curr, s_prev in _spec:
        if s_curr is not None and s_prev is not None and s_curr != s_prev:
            differences.append(f"{s_label}: {s_prev} -> {s_curr}")

    return BDTComparison(
        previous=previous,
        current_date=current_date,
        differences=differences,
        has_critical_change=critical,
        upgrade_detected=upgrade_detected,
        change_status=(
            "Battery Technology Upgrade Detected"
            if upgrade_detected
            else ("Equipment Change Detected" if critical else "No Critical Changes")
        ),
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

    rule_results = _build_rule_results(validation_result)
    if not rule_results:
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

    overall_verdict = str(getattr(validation_result, "overall", "") or "")
    insight = getattr(validation_result, "battery_backup_insight", {}) or {}
    if not isinstance(insight, dict):
        insight = {}
    bdt_dict = _build_bdt_dict(bdt_data)

    try:
        from alarm_app.db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    except ImportError:
        from db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    try:
        from alarm_app.db.repos.pm_repo import save_validation_run as _save_pm_run
    except ImportError:
        from db.repos.pm_repo import save_validation_run as _save_pm_run

    session = _get_session()
    try:
        file_id = _register_bdt_uploaded_file(session, bdt_data)
        bdt_db = _save_bdt_test(session, bdt_dict, file_id=file_id)
        session.flush()

        _save_pm_run(
            session,
            bdt_test_id=bdt_db.id,
            alarm_input_sha256=alarm_input_sha256,
            validator_code_ref=validator_ref,
            overall_verdict=overall_verdict,
            rule_results=rule_results,
            params=params or {},
            insight=insight,
        )
    finally:
        session.close()

    return _build_run_payload(
        bdt_data=bdt_data,
        validation_result=validation_result,
        params=params or {},
        validator_ref=validator_ref,
        params_sha256=params_sha256,
        alarm_input_sha256=alarm_input_sha256,
        idempotency_key=idempotency_key,
        run_uuid=run_uuid,
        rule_count=len(rule_results),
    )


def save_validation_batch(
    *,
    items: list[dict],
    alarm_df,
    params: dict,
    validator_code_ref: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Persist BDT tests + PM validation runs in one DB session/commit.

    Returns (run_payloads, photo_jobs, failed_items).
    failed_items: list of dicts with keys: site_code, test_date, error_type, error_message.
    """
    if not items:
        return [], [], []

    try:
        from alarm_app.db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    except ImportError:
        from db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    try:
        from alarm_app.db.repos.pm_repo import (
            get_or_create_parameter_set as _get_or_create_parameter_set,
        )
    except ImportError:
        from db.repos.pm_repo import (
            get_or_create_parameter_set as _get_or_create_parameter_set,
        )
    try:
        from alarm_app.db.repos.pm_repo import (
            get_or_create_rule_catalog as _get_or_create_rule_catalog,
        )
    except ImportError:
        from db.repos.pm_repo import (
            get_or_create_rule_catalog as _get_or_create_rule_catalog,
        )
    try:
        from alarm_app.db.repos.pm_repo import (
            save_validation_run as _save_pm_run,
        )
    except ImportError:
        from db.repos.pm_repo import (
            save_validation_run as _save_pm_run,
        )

    params = params or {}
    validator_ref = validator_code_ref or f"alarm_app.bdt_validator.validate_bdt@{APP_VERSION}"
    params_sha256 = _canonical_json_sha256(params)
    run_payloads: list[dict] = []
    photo_jobs: list[dict] = []
    failed_items: list[dict] = []
    from sqlalchemy.exc import IntegrityError as _IntegrityError
    from sqlalchemy.exc import OperationalError as _OperationalError

    session = _get_session()
    try:
        parameter_set_id = _get_or_create_parameter_set(session, params) if params else None
        catalog_map = _get_or_create_rule_catalog(session)

        for item in items:
            bdt_data = item.get("bdt_data")
            validation_result = item.get("validation_result")
            if not bdt_data or not validation_result:
                continue

            site_code = str(getattr(bdt_data, "site_code", "") or "").strip().upper()
            if not site_code:
                continue
            test_date = _iso_date_str(getattr(bdt_data, "test_date", ""))
            if not test_date:
                continue

            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                try:
                    with session.begin_nested():
                        bdt_dict = _build_bdt_dict(bdt_data)
                        file_id = _register_bdt_uploaded_file(session, bdt_data)
                        bdt_db = _save_bdt_test(session, bdt_dict, file_id=file_id)
                        if bdt_db is None:
                            break

                        rule_results = _build_rule_results(validation_result)
                        if not rule_results:
                            break

                        alarm_input_sha256 = compute_alarm_input_sha256(alarm_df, site_code, test_date)

                        # Build idempotency key for PM run
                        idempotency_material = {
                            "site_code": site_code,
                            "test_date": test_date,
                            "params_sha256": params_sha256,
                            "alarm_input_sha256": alarm_input_sha256,
                            "validator_code_ref": validator_ref,
                        }
                        idempotency_key = _canonical_json_sha256(idempotency_material)
                        run_uuid = str(uuid5(NAMESPACE_URL, idempotency_key))
                        overall_verdict = str(getattr(validation_result, "overall", "") or "")
                        insight = getattr(validation_result, "battery_backup_insight", {}) or {}
                        if not isinstance(insight, dict):
                            insight = {}
                        validation_context = getattr(validation_result, "validation_context", {}) or {}
                        if isinstance(validation_context, dict) and validation_context:
                            insight = dict(insight)
                            insight["validation_context"] = validation_context

                        pm_run = _save_pm_run(
                            session,
                            bdt_test_id=bdt_db.id,
                            alarm_input_sha256=alarm_input_sha256,
                            validator_code_ref=validator_ref,
                            overall_verdict=overall_verdict,
                            rule_results=rule_results,
                            params=params,
                            insight=insight,
                            autocommit=False,
                            catalog_map=catalog_map,
                            parameter_set_id=parameter_set_id,
                        )

                        if pm_run is not None:
                            run_payloads.append(_build_run_payload(
                                bdt_data=bdt_data,
                                validation_result=validation_result,
                                params=params,
                                validator_ref=validator_ref,
                                params_sha256=params_sha256,
                                alarm_input_sha256=alarm_input_sha256,
                                idempotency_key=idempotency_key,
                                run_uuid=run_uuid,
                                rule_count=len(rule_results),
                            ))

                            # Queue photo jobs only after PM run is successfully persisted
                            photo_slots = list(getattr(bdt_data, "photo_slots", []) or [])
                            if photo_slots:
                                photo_jobs.append({
                                    "bdt_test_id": int(bdt_db.id),
                                    "photo_slots": photo_slots,
                                })
                    break
                except _IntegrityError:
                    # Duplicate: rollback savepoint only, continue with remaining items.
                    # FR-005: duplicate PM run must not roll back whole batch.
                    _log.debug("Duplicate BDT/PM run skipped for site=%s date=%s", site_code, test_date)
                    failed_items.append({
                        "site_code": site_code,
                        "test_date": test_date,
                        "error_type": "duplicate",
                        "error_message": "Duplicate PM run skipped (idempotent)",
                    })
                    break
                except _OperationalError as e:
                    attempts += 1
                    if _is_sqlite_lock_error(e) and attempts < max_attempts:
                        _log.warning(
                            "SQLite lock while persisting BDT site=%s date=%s attempt=%d/%d; retrying",
                            site_code, test_date, attempts, max_attempts,
                        )
                        time.sleep(0.2 * attempts)
                        continue
                    _log.error("Failed to persist item site=%s date=%s: %s", site_code, test_date, str(e), exc_info=True)
                    failed_items.append({
                        "site_code": site_code,
                        "test_date": test_date,
                        "error_type": "db_error",
                        "error_message": str(e),
                    })
                    break
                except Exception as e:
                    # Non-duplicate error: rollback savepoint only, log and continue.
                    # FR-005: item-scoped failure must not roll back whole batch.
                    _log.error("Failed to persist item site=%s date=%s: %s", site_code, test_date, str(e), exc_info=True)
                    failed_items.append({
                        "site_code": site_code,
                        "test_date": test_date,
                        "error_type": "db_error",
                        "error_message": str(e),
                    })
                    break

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return run_payloads, photo_jobs, failed_items


def persist_photo_jobs(photo_jobs: list[dict]) -> int:
    """Persist queued BDT photo jobs with per-job isolation.

    Each job runs in its own thread with its own session so that
    concurrent photo writes saturate the disk I/O without contending
    for a single session object.

    Returns count of successfully persisted photos. Individual job
    failures are logged but do not roll back other jobs in the batch.
    """
    if not photo_jobs:
        return 0

    try:
        from alarm_app.db.repos.photo_service import persist_bdt_photos
    except ImportError:
        from db.repos.photo_service import persist_bdt_photos

    def _persist_one_job(job: dict) -> int:
        bdt_test_id = int(job.get("bdt_test_id") or 0)
        photo_slots = list(job.get("photo_slots") or [])
        if not bdt_test_id or not photo_slots:
            return 0

        session = _get_session()
        try:
            job_count = persist_bdt_photos(
                session,
                bdt_test_id,
                photo_slots,
                autocommit=True,
            )
            return job_count or 0
        except Exception:
            _log.error(
                "Failed to persist photos for bdt_test_id=%d",
                bdt_test_id, exc_info=True,
            )
            try:
                session.rollback()
            except Exception:
                pass
            return 0
        finally:
            session.close()

    total = 0
    max_workers = min(len(photo_jobs), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_persist_one_job, job): job for job in photo_jobs}
        for future in as_completed(futures):
            try:
                total += future.result()
            except Exception:
                job = futures[future]
                _log.error(
                    "Photo job failed for bdt_test_id=%d",
                    int(job.get("bdt_test_id") or 0), exc_info=True,
                )

    _log.info("Photo persistence batch complete: %d photos stored", total)
    return total
