"""Alarm upsert endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import pandas as pd

from ..deps import get_db
from ..schemas import AlarmBatchRequest, AlarmBatchResponse

router = APIRouter(prefix="/v1/alarms", tags=["alarms"])


@router.post("/upsert", response_model=AlarmBatchResponse)
def upsert_alarms(req: AlarmBatchRequest, db: Session = Depends(get_db)):
    from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms

    records = [a.model_dump() for a in req.alarms]
    df = pd.DataFrame(records)
    for col in ("occurred_on", "cleared_on"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    inserted, skipped = bulk_upsert_alarms(db, df)
    return AlarmBatchResponse(inserted=inserted, skipped=skipped)
