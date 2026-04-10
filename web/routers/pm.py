"""PM validation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas import PMRunResponse

router = APIRouter(prefix="/v1/pm", tags=["pm"])


@router.get("/runs/{run_id}", response_model=PMRunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    from alarm_app.db.models import PMValidationRun

    run = db.get(PMValidationRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return PMRunResponse(
        run_id=run.id,
        bdt_test_id=run.bdt_test_id,
        overall_verdict=run.overall_verdict or "",
        alarm_input_sha256=run.alarm_input_sha256,
        run_at=run.run_at.isoformat() if run.run_at else None,
        rules=[
            {"rule_id": rr.rule_id, "verdict": rr.verdict,
             "evidence": rr.evidence_json}
            for rr in run.rule_results
        ],
    )
