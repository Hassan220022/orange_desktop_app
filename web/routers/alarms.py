"""Alarm upsert endpoint."""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import pandas as pd

_log = logging.getLogger(__name__)

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
    _log.info("Alarm upsert: inserted=%d, skipped=%d", inserted, skipped)
    return AlarmBatchResponse(inserted=inserted, skipped=skipped)


@router.get("/query")
def query_alarms(db: Session = Depends(get_db),
                 site_id: str | None = None,
                 limit: int = 10000):
    from alarm_app.db.repos.alarm_repo import load_alarms_as_df

    df = load_alarms_as_df(db)
    if df.empty:
        _log.info("Alarm query: result_count=0")
        return {"alarms": []}
    if site_id:
        df = df[df["site_id"] == site_id]
    df = df.head(limit)
    # Convert timestamps to strings for JSON serialization
    for col in df.select_dtypes(include=["datetime64"]).columns:
        df[col] = df[col].astype(str)
    _log.info("Alarm query: result_count=%d", len(df))
    return {"alarms": df.to_dict(orient="records")}
