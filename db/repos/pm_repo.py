"""PM validation run and rule result repository."""

import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

_log = logging.getLogger(__name__)
from alarm_app.db.models import (
    PMValidationRun, PMRuleResult, PMRuleCatalog, PMParameterSet,
)
from alarm_app.db.hashing import compute_canonical_json_sha256


def get_or_create_rule_catalog(session: Session) -> dict[str, int]:
    """Ensure R1-R11 exist in pm_rule_catalog. Return {rule_code: id} map."""
    rules = {
        "R1": "Photo completeness",
        "R2": "Power alarm match and duration",
        "R3": "String vs bus bar ampere",
        "R4": "Discharge table consistency",
        "R5": "Starting ampere",
        "R6": "End voltage range",
        "R7": "Voltage/ampere inverse relationship",
        "R8": "Backup time vs sizing",
        "R9": "Discharge current tolerance",
        "R10": "Door alarm match",
        "R11": "Summary checklist",
    }
    result = {}
    seeded = 0
    for code, name in rules.items():
        existing = session.query(PMRuleCatalog).filter_by(rule_code=code).first()
        if existing:
            result[code] = existing.id
        else:
            r = PMRuleCatalog(rule_code=code, name=name)
            session.add(r)
            session.flush()
            result[code] = r.id
            seeded += 1
    if seeded:
        _log.info("Rule catalog seeded: %d new rules added", seeded)
    return result


def seed_rule_versions(session: Session, code_ref: str = "alarm_app.bdt.validator") -> None:
    """Seed initial rule versions for R1-R11. Idempotent."""
    from alarm_app.db.models import PMRuleVersion
    from datetime import datetime

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
    session.flush()
    return ps.id


def save_validation_run(session: Session, *, bdt_test_id: int,
                        alarm_input_sha256: str,
                        validator_code_ref: str | None,
                        overall_verdict: str,
                        rule_results: list[dict],
                        params: dict | None = None) -> PMValidationRun | None:
    """Save a PM validation run with all rule results.

    Returns None if an identical run already exists (idempotent).
    rule_results: list of {"rule_code": "R1", "verdict": "Accepted", "detail": "..."}
    """
    param_set_id = None
    if params:
        params_sha = compute_canonical_json_sha256(params)
        ps = session.query(PMParameterSet).filter_by(params_sha256=params_sha).first()
        if not ps:
            ps = PMParameterSet(params_sha256=params_sha,
                                params_json=json.dumps(params, default=str))
            session.add(ps)
            session.flush()
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
        session.flush()
    except IntegrityError:
        session.rollback()
        _log.warning("Duplicate validation run skipped (IntegrityError): bdt_test_id=%d", bdt_test_id)
        return None

    catalog = get_or_create_rule_catalog(session)

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

    session.commit()
    _log.info("Validation run saved: bdt_test_id=%d, verdict=%s", bdt_test_id, overall_verdict)
    return run


def load_all_validation_results(session: Session) -> list:
    """Load all validation runs from DB as ValidationResult dataclass objects.

    Reconstructs the same objects the BDTValidationThread produces,
    so the UI can display them without re-running validation.
    """
    from alarm_app.db.models import BDTTest
    from alarm_app.bdt.validator import ValidationResult, RuleResult
    from alarm_app.bdt.parser import BDTData

    # Build rule_id -> rule_code map
    catalog_rows = session.query(PMRuleCatalog).all()
    id_to_code = {r.id: r.rule_code for r in catalog_rows}

    runs = (
        session.query(PMValidationRun)
        .join(BDTTest)
        .order_by(PMValidationRun.run_at.desc())
        .all()
    )

    results = []
    for run in runs:
        bdt_db = session.get(BDTTest, run.bdt_test_id)
        if not bdt_db:
            continue

        # Reconstruct BDTData with fields from DB
        from alarm_app.bdt.parser import PhotoSlot
        from pathlib import Path

        # Rebuild photo_slots from DB photos + blob storage
        photo_slots = []
        for photo in sorted(bdt_db.photos, key=lambda p: p.slot_index or 0):
            image_data = None
            image_ext = "jpeg"
            if photo.blob_asset and photo.blob_asset.local_path:
                blob_path = Path(photo.blob_asset.local_path)
                if blob_path.exists():
                    image_data = blob_path.read_bytes()
                    mime = photo.blob_asset.mime_type or ""
                    if "png" in mime:
                        image_ext = "png"
            photo_slots.append(PhotoSlot(
                label=photo.slot_category or "other",
                image_data=image_data,
                image_ext=image_ext,
                category=photo.slot_category or "other",
            ))

        bdt_data = BDTData(
            file_path="",
            filename="",
            site_code=bdt_db.site_code or "",
            test_date=bdt_db.test_date,
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
            photo_slots=photo_slots,
            photo_count=len([s for s in photo_slots if s.image_data]),
        )

        # Reconstruct rule results
        rule_results = []
        for rr in sorted(run.rule_results, key=lambda r: r.rule_id):
            code = id_to_code.get(rr.rule_id, f"R{rr.rule_id}")
            detail = ""
            if rr.evidence_json:
                try:
                    detail = json.loads(rr.evidence_json)
                except (json.JSONDecodeError, TypeError):
                    detail = rr.evidence_json
            rule_results.append(RuleResult(
                rule_id=code,
                rule_name=code,
                passed=rr.verdict == "Accepted" if rr.verdict else None,
                verdict=rr.verdict or "N/A",
                detail=str(detail),
            ))

        vr = ValidationResult(
            filename=bdt_db.site_code or "",
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
    from alarm_app.db.models import BDTTest

    runs = (
        session.query(PMValidationRun)
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
