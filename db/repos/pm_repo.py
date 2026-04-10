"""PM validation run and rule result repository."""

import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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
    for code, name in rules.items():
        existing = session.query(PMRuleCatalog).filter_by(rule_code=code).first()
        if existing:
            result[code] = existing.id
        else:
            r = PMRuleCatalog(rule_code=code, name=name)
            session.add(r)
            session.flush()
            result[code] = r.id
    return result


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
    return run
