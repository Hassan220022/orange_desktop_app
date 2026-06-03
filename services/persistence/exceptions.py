"""Typed exceptions raised by the persistence layer."""


class PersistenceError(Exception):
    """Base class for all persistence-layer errors."""


class AlarmLoadError(PersistenceError):
    """Raised when an alarm record cannot be loaded from storage."""


class AlarmCacheError(PersistenceError):
    """Raised when the DuckDB-backed alarm cache cannot be read or written."""


class StateError(PersistenceError):
    """Raised when a state key-value operation fails."""


class SyncError(PersistenceError):
    """Raised when a sync outbox or checkpoint operation fails."""


class HashingError(PersistenceError):
    """Raised when content hashing fails."""


class CatalogError(PersistenceError):
    """Raised when reference-data catalog operations fail."""


class EngineCreationError(PersistenceError):
    """Raised when the SQLAlchemy engine cannot be created or configured."""
