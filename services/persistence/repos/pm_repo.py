"""PM validation run and rule result repository."""

import json
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)
try:
    from alarm_app.constants import BDT_RULE_NAME_BY_CODE
    from ..hashing import compute_canonical_json_sha256
    from ..models import (
        PMParameterSet,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
    )
    from ..retry import safe_flush
except ImportError:
    from constants import BDT_RULE_NAME_BY_CODE
    from ..hashing import compute_canonical_json_sha256
    from ..models import (
        PMParameterSet,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
    )
    from ..retry import safe_flush


def get_or_create_rule_catalog(session: Session) -> dict[str, int]:
    """Ensure R1-R11 exist in pm_rule_catalog. Return {rule_code: id} map."""
    result = {}
    seeded = 0
    for code, name in BDT_RULE_NAME_BY_CODE.items():
        existing = session.query(PMRuleCatalog).filter_by(rule_code=code).first()
        if existing:
            if existing.name != name:
                existing.name = name
            result[code] = existing.id
        else:
            r = PMRuleCatalog(rule_code=code, name=name)
            session.add(r)
            safe_flush(session)
            result[code] = r.id
            seeded += 1
    if seeded:
        _log.info("Rule catalog seeded: %d new rules added", seeded)
    return result


def seed_rule_versions(session: Session, code_ref: str = "alarm_app.bdt.validator") -> None:
    """Seed initial rule versions for R1-R11. Idempotent."""
    from datetime import datetime

    try:
        from ..models import PMRuleVersion
    except ImportError:
        from ..models import PMRuleVersion

    catalog = get_or_create_rule_catalog(session)

    for rule_code, rule_id in catalog.items():
        existing = session.query(PMRuleVersion).filter_by(
            rule_id=rule_id, version="1.0"
        ).first()
        if not existing:
            session.add(PMRuleVersion(
                rule_id=rule_id,
                version="1.0",
                valid_from=datetime(2026, 1, 1),
                code_ref=f"{code_ref}.{rule_code.lower()}",
            ))
    session.commit()


def get_or_create_parameter_set(session: Session, params: dict) -> int:
    """Get or create a parameter set. Returns the parameter_set_id."""
    params_sha = compute_canonical_json_sha256(params)
    existing = session.query(PMParameterSet).filter_by(params_sha256=params_sha).first()
    if existing:
        return existing.id

    ps = PMParameterSet(
        params_sha256=params_sha,
        params_json=json.dumps(params, sort_keys=True, default=str),
    )
    session.add(ps)
    safe_flush(session)
    return ps.id


def save_validation_run(session: Session, *, bdt_test_id: int,
                        alarm_input_sha256: str,
                        validator_code_ref: str | None,
                        overall_verdict: str,
                        rule_results: list[dict],
                        params: dict | None = None,
                        autocommit: bool = True,
                        catalog_map: dict[str, int] | None = None,
                        parameter_set_id: int | None = None) -> PMValidationRun | None:
    """Save a PM validation run with all rule results.

    Returns None if an identical run already exists (idempotent).
    rule_results: list of {"rule_code": "R1", "verdict": "Accepted", "detail": "..."}
    """
    param_set_id = parameter_set_id
    if param_set_id is None and params:
        params_sha = compute_canonical_json_sha256(params)
        ps = session.query(PMParameterSet).filter_by(params_sha256=params_sha).first()
        if not ps:
            ps = PMParameterSet(params_sha256=params_sha,
                                params_json=json.dumps(params, default=str))
            session.add(ps)
            safe_flush(session)
        param_set_id = ps.id

    # SQLite treats NULLs as distinct in unique constraints, so check manually
    existing = session.query(PMValidationRun).filter_by(
        bdt_test_id=bdt_test_id,
        parameter_set_id=param_set_id,
        alarm_input_sha256=alarm_input_sha256,
        validator_code_ref=validator_code_ref,
    ).first()
    if existing:
        _log.warning("Duplicate validation run skipped: bdt_test_id=%d, verdict=%s", bdt_test_id, overall_verdict)
        return None

    run = PMValidationRun(
        bdt_test_id=bdt_test_id,
        parameter_set_id=param_set_id,
        alarm_input_sha256=alarm_input_sha256,
        validator_code_ref=validator_code_ref,
        overall_verdict=overall_verdict,
    )
    session.add(run)
    try:
        safe_flush(session)
    except IntegrityError:
        if autocommit:
            session.rollback()
            _log.warning("Duplicate validation run skipped (IntegrityError): bdt_test_id=%d", bdt_test_id)
            return None
        raise

    catalog = catalog_map or get_or_create_rule_catalog(session)

    for rr in rule_results:
        rule_code = rr["rule_code"]
        rule_id = catalog.get(rule_code)
        if rule_id is None:
            continue
        session.add(PMRuleResult(
            validation_run_id=run.id,
            rule_id=rule_id,
            verdict=rr.get("verdict", "N/A"),
            evidence_json=json.dumps(rr.get("detail", ""), default=str),
        ))

    if autocommit:
        session.commit()
    else:
        safe_flush(session)
    _log.info("Validation run saved: bdt_test_id=%d, verdict=%s", bdt_test_id, overall_verdict)
    return run


def load_all_validation_results(session: Session) -> list:
    """Load all validation runs from DB as ValidationResult dataclass objects.

    Reconstructs the same objects the BDTValidationThread produces,
    so the UI can display them without re-running validation.

    Uses eager loading (joinedload/selectinload) to avoid N+1 queries:
    - BDTTest joined at query time (no session.get per run)
    - photos + blob_asset selectinloaded (no lazy load per test)
    - rule_results selectinloaded (no lazy load per run)
    - UploadedFile batch-loaded (no session.get per run)
    """
    try:
        from alarm_app.bdt.parser import BDTData
    except ImportError:
        from bdt.parser import BDTData
    try:
        from alarm_app.bdt.validator import RuleResult, ValidationResult
    except ImportError:
        from bdt.validator import RuleResult, ValidationResult
    try:
        from ..models import BDTPhoto, BDTTest, UploadedFile
    except ImportError:
        from ..models import BDTPhoto, BDTTest, UploadedFile

    from sqlalchemy.orm import selectinload

    # Build rule_id -> rule_code map
    catalog_rows = session.query(PMRuleCatalog).all()
    id_to_catalog = {r.id: (r.rule_code, r.name) for r in catalog_rows}

    # Eager-load BDTTest, rule_results, photos, and photo blobs in 4 queries total
    runs = (
        session.query(PMValidationRun)
        .options(
            selectinload(PMValidationRun.bdt_test)
            .selectinload(BDTTest.photos)
            .selectinload(BDTPhoto.blob_asset),
            selectinload(PMValidationRun.rule_results),
        )
        .order_by(PMValidationRun.run_at.desc())
        .all()
    )

    # Batch-preload UploadedFile rows referenced by these BDT tests
    file_ids = {
        run.bdt_test.file_id
        for run in runs
        if run.bdt_test and run.bdt_test.file_id
    }
    uploaded_map = {}
    if file_ids:
        uploaded_map = {
            uf.id: uf
            for uf in session.query(UploadedFile)
            .filter(UploadedFile.id.in_(file_ids))
            .all()
        }

    results = []
    for run in runs:
        bdt_db = run.bdt_test
        if not bdt_db:
            continue
        uploaded_file = uploaded_map.get(bdt_db.file_id)

        # Reconstruct BDTData with fields from DB
        from pathlib import Path

        try:
            from alarm_app.bdt.parser import PhotoSlot
        except ImportError:
            from bdt.parser import PhotoSlot

        # Rebuild photo_slots from DB photos + blob storage
        photo_slots = []
        for photo in sorted(bdt_db.photos, key=lambda p: p.slot_index or 0):
            image_path = ""
            image_ext = "jpeg"
            if photo.blob_asset and photo.blob_asset.local_path:
                blob_path = Path(photo.blob_asset.local_path)
                if blob_path.exists():
                    image_path = str(blob_path)
                    mime = photo.blob_asset.mime_type or ""
                    if "png" in mime:
                        image_ext = "png"
            photo_slots.append(PhotoSlot(
                label=photo.slot_category or "other",
                image_data=None,
                image_path=image_path,
                image_ext=image_ext,
                category=photo.slot_category or "other",
            ))

        # Reconstruct discharge readings from JSON
        discharge_readings = []
        if bdt_db.discharge_readings_json:
            try:
                raw = json.loads(bdt_db.discharge_readings_json)
                discharge_readings = [
                    (str(r[0]) if r[0] else "", r[1], r[2] if len(r) > 2 else None)
                    for r in raw
                ]
            except (json.JSONDecodeError, TypeError):
                pass

        string_discharge_readings = []
        if bdt_db.string_discharge_readings_json:
            try:
                string_discharge_readings = json.loads(bdt_db.string_discharge_readings_json)
            except (json.JSONDecodeError, TypeError):
                pass

        bdt_data = BDTData(
            file_path=str(uploaded_file.original_path or "") if uploaded_file else "",
            filename=str(uploaded_file.original_name or "") if uploaded_file else "",
            site_code=bdt_db.site_code or "",
            site_name=bdt_db.site_name or "",
            test_date=bdt_db.test_date,
            time_in=bdt_db.time_in or "",
            time_out=bdt_db.time_out or "",
            battery_brand=bdt_db.battery_brand or "",
            battery_ah=bdt_db.battery_ah,
            battery_voltage=bdt_db.battery_voltage,
            num_strings=bdt_db.num_strings,
            num_batteries=bdt_db.num_batteries,
            num_modules=bdt_db.num_modules,
            rectifier_brand=bdt_db.rectifier_brand or "",
            start_voltage=bdt_db.start_voltage,
            end_voltage=bdt_db.end_voltage,
            start_ampere=bdt_db.start_ampere,
            end_ampere=bdt_db.end_ampere,
            discharge_minutes=bdt_db.discharge_minutes or 0.0,
            pld_value=bdt_db.pld_value or "",
            ibat_before_test=bdt_db.ibat_before_test,
            starting_ibattery_ampere=bdt_db.starting_ibattery_ampere,
            after_reconnect_voltage=bdt_db.after_reconnect_voltage,
            after_reconnect_ampere=bdt_db.after_reconnect_ampere,
            discharge_readings=discharge_readings,
            string_discharge_readings=string_discharge_readings,
            photo_slots=photo_slots,
            photo_count=len([s for s in photo_slots if s.image_data or getattr(s, "image_path", "")]),
        )

        # Reconstruct rule results (already eager-loaded)
        rule_results = []
        for rr in sorted(run.rule_results, key=lambda r: r.rule_id):
            code, catalog_name = id_to_catalog.get(rr.rule_id, (f"R{rr.rule_id}", ""))
            detail = ""
            if rr.evidence_json:
                try:
                    detail = json.loads(rr.evidence_json)
                except (json.JSONDecodeError, TypeError):
                    detail = rr.evidence_json
            rule_results.append(RuleResult(
                rule_id=code,
                rule_name=catalog_name or BDT_RULE_NAME_BY_CODE.get(code, code),
                passed=rr.verdict == "Accepted" if rr.verdict else None,
                verdict=rr.verdict or "N/A",
                detail=str(detail),
            ))

        vr = ValidationResult(
            filename=(
                str(uploaded_file.original_name or "")
                if uploaded_file else (bdt_db.site_code or "")
            ),
            site_code=bdt_db.site_code or "",
            test_date=str(bdt_db.test_date) if bdt_db.test_date else "",
            overall=run.overall_verdict or "",
            rules=rule_results,
            bdt_data=bdt_data,
        )
        results.append(vr)

    _log.info("Loaded %d validation results from DB", len(results))
    return results


def load_validation_history(session: Session, site_code: str,
                            limit: int = 50) -> list[dict]:
    """Load recent validation runs for a site."""
    try:
        from ..models import BDTTest
    except ImportError:
        from ..models import BDTTest

    from sqlalchemy.orm import selectinload

    runs = (
        session.query(PMValidationRun)
        .options(selectinload(PMValidationRun.rule_results))
        .join(BDTTest)
        .filter(BDTTest.site_code == site_code.strip().upper())
        .order_by(PMValidationRun.run_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "run_id": r.id,
            "bdt_test_id": r.bdt_test_id,
            "overall_verdict": r.overall_verdict,
            "alarm_input_sha256": r.alarm_input_sha256,
            "run_at": r.run_at.isoformat() if r.run_at else None,
            "rule_count": len(r.rule_results),
        }
        for r in runs
    ]
