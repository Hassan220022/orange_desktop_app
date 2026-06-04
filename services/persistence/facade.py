"""Single entry point for all persistence operations.

Usage:

    p = Persistence.instance()
    p.alarms.upsert(session, df)
    p.state.set(session, "key", "value")
    p.cache.save_dataframe(df)

This facade is the only thing the rest of the codebase should import for
persistence. The SQLAlchemy engine, ORM models, and repositories remain
private to this package.
"""

from __future__ import annotations

import logging

from . import alarm_cache
from .repos import (
    alarm_repo,
    bdt_repo,
    blob_repo,
    catalog_repo,
    file_repo,
    pm_repo,
    state_repo,
    sync_repo,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shim helpers — small wrappers the repos don't expose directly.
# ---------------------------------------------------------------------------


def _alarm_get_by_hash(session, row_hash: str):
    """Return a single alarm record by its row_hash (or None)."""
    from .models import AlarmRecord

    return session.query(AlarmRecord).filter_by(row_hash=row_hash).first()


def _state_delete_value(session, key: str) -> bool:
    """Delete a single key from the ui_state table. Returns True if removed."""
    from .models import UIState

    row = session.get(UIState, key)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Sub-facades
# ---------------------------------------------------------------------------


class _AlarmsFacade:
    upsert = staticmethod(alarm_repo.bulk_upsert_alarms)
    get_by_hash = staticmethod(_alarm_get_by_hash)
    load_alarms_as_df = staticmethod(alarm_repo.load_alarms_as_df)
    count = staticmethod(alarm_repo.count_alarms)


class _BDTFacade:
    upsert = staticmethod(bdt_repo.save_bdt_test)
    get_by_id = staticmethod(bdt_repo.load_previous_test)
    list_recent = staticmethod(bdt_repo.load_second_most_recent)
    list_photos = staticmethod(bdt_repo.save_bdt_photo)


class _BlobsFacade:
    upsert = staticmethod(blob_repo.store_blob)
    get_by_hash = staticmethod(blob_repo.get_blob_by_sha256)
    exists = staticmethod(blob_repo.blob_exists)


class _FilesFacade:
    upsert = staticmethod(file_repo.register_file)
    get_by_hash = staticmethod(file_repo.get_file_by_hash)
    exists = staticmethod(file_repo.file_exists)


class _PMFacade:
    create_run = staticmethod(pm_repo.save_validation_run)
    add_rule_result = staticmethod(pm_repo.save_validation_run)
    get_run = staticmethod(pm_repo.load_all_validation_results)
    seed_catalog = staticmethod(pm_repo.get_or_create_rule_catalog)


class _CatalogFacade:
    list_sites = staticmethod(catalog_repo.query_site_metadata)
    upsert_site = staticmethod(catalog_repo.merge_site_metadata)


class _StateFacade:
    def get(self, session, key: str, default=None):
        return state_repo.get_value(session, key, default=default)

    def set(self, session, key: str, value) -> None:
        return state_repo.set_value(session, key, value)

    def delete(self, session, key: str) -> bool:
        return _state_delete_value(session, key)

    def load_all(self, session):
        return state_repo.load_state(session)


class _SyncFacade:
    append_outbox = staticmethod(sync_repo.append_outbox_event)
    load_pending = staticmethod(sync_repo.load_pending_outbox)
    mark_synced = staticmethod(sync_repo.mark_outbox_synced)
    save_checkpoint = staticmethod(sync_repo.save_sync_checkpoint)
    load_checkpoint = staticmethod(sync_repo.load_sync_checkpoint)


class _CacheFacade:
    save_dataframe = staticmethod(alarm_cache.save_dataframe)
    load_dataframe = staticmethod(alarm_cache.load_dataframe)
    has_dataframe = staticmethod(alarm_cache.has_alarm_cache)
    clear = staticmethod(alarm_cache.clear_cache)
    clear_all = staticmethod(alarm_cache.clear_all_caches)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class Persistence:
    """Singleton facade for all persistence operations."""

    _instance: Persistence | None = None

    def __init__(self):
        self.alarms = _AlarmsFacade()
        self.bdt = _BDTFacade()
        self.blobs = _BlobsFacade()
        self.files = _FilesFacade()
        self.pm = _PMFacade()
        self.catalog = _CatalogFacade()
        self.state = _StateFacade()
        self.sync = _SyncFacade()
        self.cache = _CacheFacade()

    @classmethod
    def instance(cls) -> Persistence:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for tests only)."""
        cls._instance = None
