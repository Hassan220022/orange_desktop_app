"""Sync batch endpoint -- receives events from desktop sync worker."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas import SyncBatchRequest, SyncBatchResponse, SyncEventResult

router = APIRouter(prefix="/v1/sync", tags=["sync"])


@router.post("/batches", response_model=SyncBatchResponse)
def receive_batch(req: SyncBatchRequest, db: Session = Depends(get_db)):
    results = []
    for evt in req.events:
        try:
            from alarm_app.db.repos.sync_repo import append_outbox_event

            append_outbox_event(
                db,
                entity_type=evt.entity_type,
                entity_local_id=evt.entity_local_id,
                op=evt.op,
                entity_hash=evt.entity_hash,
                payload=evt.payload,
                origin_device_id=evt.origin_device_id,
                event_id=evt.event_id,
            )
            results.append(SyncEventResult(
                event_id=evt.event_id, status="applied",
            ))
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                results.append(SyncEventResult(
                    event_id=evt.event_id, status="duplicate",
                ))
            else:
                results.append(SyncEventResult(
                    event_id=evt.event_id, status="retryable_failed",
                    message=str(e),
                ))
    return SyncBatchResponse(results=results)


@router.get("/status")
def sync_status(db: Session = Depends(get_db)):
    from alarm_app.data.sync_monitor import outbox_stats

    return outbox_stats(db)
