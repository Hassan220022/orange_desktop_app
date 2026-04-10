"""API request and response schemas."""

from pydantic import BaseModel


class SyncEventIn(BaseModel):
    event_id: str
    origin_device_id: str
    entity_type: str
    entity_local_id: str
    op: str
    entity_hash: str
    payload: dict
    created_at: str | None = None


class SyncBatchRequest(BaseModel):
    idempotency_key: str
    events: list[SyncEventIn]


class SyncEventResult(BaseModel):
    event_id: str
    status: str  # applied, duplicate, rejected, retryable_failed
    canonical_id: int | None = None
    message: str = ""


class SyncBatchResponse(BaseModel):
    results: list[SyncEventResult]


class AlarmUpsertRequest(BaseModel):
    site_id: str
    alarm_name: str
    occurred_on: str
    cleared_on: str | None = None
    duration: str | None = None
    category: str | None = None
    vendor: str | None = None


class AlarmBatchRequest(BaseModel):
    alarms: list[AlarmUpsertRequest]


class AlarmBatchResponse(BaseModel):
    inserted: int
    skipped: int


class PMRunResponse(BaseModel):
    run_id: int
    bdt_test_id: int
    overall_verdict: str
    alarm_input_sha256: str
    run_at: str | None = None
    rules: list[dict] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = ""
