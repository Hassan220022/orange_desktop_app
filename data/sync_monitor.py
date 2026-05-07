"""Sync outbox monitoring -- lag, queue depth, failure tracking."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

try:
    from alarm_app.db.models import SyncOutboxEvent
except ImportError:
    from db.models import SyncOutboxEvent

_log = logging.getLogger(__name__)


def outbox_stats(session: Session) -> dict:
    """Return sync outbox health metrics."""
    total = session.query(SyncOutboxEvent).count()
    pending = session.query(SyncOutboxEvent).filter_by(status="pending").count()
    synced = session.query(SyncOutboxEvent).filter_by(status="synced").count()

    oldest_pending = (
        session.query(SyncOutboxEvent.created_at)
        .filter_by(status="pending")
        .order_by(SyncOutboxEvent.created_at.asc())
        .first()
    )

    lag_seconds = 0.0
    if oldest_pending and oldest_pending[0]:
        # SQLite func.now() stores UTC; compare with UTC now to avoid
        # timezone-offset skew when computing lag.
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        lag_seconds = (now_utc - oldest_pending[0]).total_seconds()

    stats = {
        "total": total,
        "pending": pending,
        "synced": synced,
        "lag_seconds": round(lag_seconds, 1),
        "health": "healthy" if pending < 100 and lag_seconds < 300 else "degraded",
    }
    _log.debug("Outbox stats: pending=%d, synced=%d, lag_seconds=%.1f, health=%s",
               pending, synced, stats["lag_seconds"], stats["health"])
    return stats
