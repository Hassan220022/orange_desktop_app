"""
BDT History -- store and compare battery discharge test records across time.

Persists BDT validation results per site to detect equipment changes
between consecutive PM visits (battery type, count, rectifier, modules).
"""

import json
import hashlib
import logging
from dataclasses import dataclass
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
_log = logging.getLogger(__name__)


_engine = None
_SessionFactory = None


def _get_session():
    global _engine, _SessionFactory
    if _engine is None:
        from alarm_app.db.engine import (
            create_engine as _create_engine,
            init_db as _init_db,
            get_session_factory as _get_session_factory,
        )
        _engine = _create_engine()
        _init_db(_engine)
        _SessionFactory = _get_session_factory(_engine)
    return _SessionFactory()


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
        from alarm_app.db.repos.file_repo import register_file as _register_file
    except ImportError:
        from db.hashing import compute_file_sha256
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
        "is_complete_rule_set": rule_count == 11,
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

    from alarm_app.db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    session = _get_session()
    try:
        file_id = _register_bdt_uploaded_file(session, bdt)
        bdt_record = _save_bdt_test(session, bdt_dict, file_id=file_id)
        session.commit()

        # Persist photos to blob storage
        photo_slots = getattr(bdt, "photo_slots", [])
        if photo_slots and bdt_record:
            try:
                from alarm_app.db.repos.photo_service import persist_bdt_photos
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
    from alarm_app.db.repos.bdt_repo import load_previous_test as _load_previous_test
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
    from alarm_app.db.repos.bdt_repo import load_second_most_recent as _load
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
    bdt_dict = _build_bdt_dict(bdt_data)

    from alarm_app.db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    from alarm_app.db.repos.pm_repo import save_validation_run as _save_pm_run

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

    from alarm_app.db.repos.bdt_repo import save_bdt_test as _save_bdt_test
    from alarm_app.db.repos.pm_repo import (
        save_validation_run as _save_pm_run,
        get_or_create_parameter_set as _get_or_create_parameter_set,
        get_or_create_rule_catalog as _get_or_create_rule_catalog,
    )

    params = params or {}
    validator_ref = validator_code_ref or f"alarm_app.bdt_validator.validate_bdt@{APP_VERSION}"
    params_sha256 = _canonical_json_sha256(params)
    run_payloads: list[dict] = []
    photo_jobs: list[dict] = []
    failed_items: list[dict] = []

    session = _get_session()
    try:
        parameter_set_id = _get_or_create_parameter_set(session, params) if params else None
        catalog_map = _get_or_create_rule_catalog(session)

        from sqlalchemy.exc import IntegrityError as _IntegrityError

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

            # Use savepoint-per-item isolation (FR-005)
            try:
                with session.begin_nested():
                    bdt_dict = _build_bdt_dict(bdt_data)
                    file_id = _register_bdt_uploaded_file(session, bdt_data)
                    bdt_db = _save_bdt_test(session, bdt_dict, file_id=file_id)
                    if bdt_db is None:
                        continue

                    rule_results = _build_rule_results(validation_result)
                    if not rule_results:
                        continue

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

                    pm_run = _save_pm_run(
                        session,
                        bdt_test_id=bdt_db.id,
                        alarm_input_sha256=alarm_input_sha256,
                        validator_code_ref=validator_ref,
                        overall_verdict=overall_verdict,
                        rule_results=rule_results,
                        params=params,
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

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return run_payloads, photo_jobs, failed_items


def persist_photo_jobs(photo_jobs: list[dict]) -> int:
    """Persist queued BDT photo jobs with savepoint-per-job isolation.

    Returns count of successfully persisted photos. Individual job failures
    are logged but do not roll back other jobs in the batch.
    """
    if not photo_jobs:
        return 0

    from alarm_app.db.repos.photo_service import persist_bdt_photos

    session = _get_session()
    total = 0
    try:
        for job in photo_jobs:
            bdt_test_id = int(job.get("bdt_test_id") or 0)
            photo_slots = list(job.get("photo_slots") or [])
            if not bdt_test_id or not photo_slots:
                continue

            try:
                with session.begin_nested():
                    job_count = persist_bdt_photos(
                        session,
                        bdt_test_id,
                        photo_slots,
                        autocommit=False,  # Don't commit inside savepoint
                    )
                    total += job_count
            except Exception:
                _log.error("Failed to persist photos for bdt_test_id=%d", bdt_test_id, exc_info=True)
                # Savepoint rolls back this job only; continue with remaining jobs

        session.commit()
    except Exception:
        session.rollback()
        _log.error("Deferred BDT photo persistence batch failed", exc_info=True)
        raise
    finally:
        session.close()
    return total
