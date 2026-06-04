"""Retry helpers for SQLite write contention and generic transient failures.

Port of v1 db/retry.py. The v1 functions (``safe_flush``, ``retry_on_lock``)
are preserved as-is because they encode SQLite-specific knowledge (lock
error string match, exponential backoff). The v2 plan also adds a generic
``with_retry`` decorator that wraps any function with a parameterized
retry policy.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from .exceptions import PersistenceError

_log = logging.getLogger(__name__)

T = TypeVar("T")


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


def with_retry(
    max_attempts: int = 3,
    backoff: float = 0.0,
    *,
    retryable_exceptions: tuple[type[BaseException], ...] = (OSError, IOError),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Generic retry decorator.

    Retries the wrapped function up to *max_attempts* times, sleeping
    *backoff* seconds between attempts, when the function raises one of
    *retryable_exceptions*. Non-retryable exceptions propagate immediately.
    After exhausting attempts, raises PersistenceError from the last
    underlying exception.

    SQLite-lock-specific use cases should keep using ``safe_flush`` or
    ``retry_on_lock`` — this decorator is for everything else.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break
                    if backoff > 0:
                        time.sleep(backoff)
            assert last_exc is not None
            raise PersistenceError(
                f"{func.__name__} failed after {max_attempts} attempts"
            ) from last_exc
        return wrapper
    return decorator
