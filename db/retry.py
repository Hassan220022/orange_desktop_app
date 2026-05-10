"""
Retry helpers for SQLite write contention.

SQLite in WAL mode allows only one writer at a time. When multiple
threads write to the same database, the second writer blocks for
busy_timeout milliseconds (currently 30 s).  If the first writer
takes longer, the second gets ``OperationalError: database is locked``.

:func:`safe_flush` retries ``session.flush()`` with exponential backoff
so transient lock contention is transparent to calling code.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable

from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)


def _is_lock_error(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


def safe_flush(
    session: Session,
    *,
    max_attempts: int = 3,
    base_delay: float = 0.1,
) -> None:
    """Flush the session, retrying on SQLite lock errors.

    Delays use exponential backoff: *base_delay* × 2^attempt.
    """
    from sqlalchemy.exc import OperationalError

    for attempt in range(max_attempts):
        try:
            session.flush()
            return
        except OperationalError as exc:
            if not _is_lock_error(exc) or attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            _log.warning(
                "SQLite lock contention on flush (attempt %d/%d); retrying in %.2fs",
                attempt + 1, max_attempts, delay,
            )
            time.sleep(delay)


def retry_on_lock(
    max_attempts: int = 3,
    base_delay: float = 0.1,
    *,
    return_on_lock=None,
):
    """Decorator that retries the wrapped function on SQLite lock errors.

    If *return_on_lock* is not None and all attempts fail with a lock
    error, the given value is returned instead of re-raising.
    """
    from sqlalchemy.exc import OperationalError

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except OperationalError as exc:
                    if not _is_lock_error(exc):
                        raise
                    if attempt == max_attempts - 1:
                        if return_on_lock is not None:
                            _log.warning(
                                "%s failed after %d lock-retry attempts; returning sentinel",
                                func.__name__, max_attempts,
                            )
                            return return_on_lock
                        raise
                    delay = base_delay * (2 ** attempt)
                    _log.warning(
                        "%s lock contention (attempt %d/%d); retrying in %.2fs",
                        func.__name__, attempt + 1, max_attempts, delay,
                    )
                    time.sleep(delay)
            return None  # unreachable

        return wrapper

    return decorator
