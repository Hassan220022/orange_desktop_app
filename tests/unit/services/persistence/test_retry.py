"""Tests for the persistence-layer retry helpers."""

import pytest

from services.persistence import retry
from services.persistence.exceptions import PersistenceError


def test_safe_flush_succeeds_on_first_attempt():
    """safe_flush calls session.flush() and returns."""
    class FakeSession:
        def __init__(self):
            self.calls = 0

        def flush(self):
            self.calls += 1

    s = FakeSession()
    retry.safe_flush(s, max_attempts=3, base_delay=0.0)
    assert s.calls == 1


def test_safe_flush_retries_on_lock_then_succeeds():
    """safe_flush retries on 'database is locked' OperationalError."""
    from sqlalchemy.exc import OperationalError

    class FlakySession:
        def __init__(self):
            self.calls = 0

        def flush(self):
            self.calls += 1
            if self.calls < 3:
                raise OperationalError("stmt", {}, Exception("database is locked"))

    s = FlakySession()
    retry.safe_flush(s, max_attempts=5, base_delay=0.0)
    assert s.calls == 3


def test_safe_flush_raises_on_non_lock_error():
    from sqlalchemy.exc import OperationalError

    class FailSession:
        def flush(self):
            raise OperationalError("stmt", {}, Exception("some other error"))

    with pytest.raises(OperationalError):
        retry.safe_flush(FailSession(), max_attempts=3, base_delay=0.0)


def test_with_retry_succeeds_on_first_attempt():
    calls = []

    @retry.with_retry(max_attempts=3, backoff=0.0)
    def succeed():
        calls.append(1)
        return "ok"

    assert succeed() == "ok"
    assert len(calls) == 1


def test_with_retry_eventually_succeeds():
    calls = []

    @retry.with_retry(max_attempts=3, backoff=0.0)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise OSError("transient")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3


def test_with_retry_raises_persistence_error_after_exhaustion():
    @retry.with_retry(max_attempts=2, backoff=0.0, retryable_exceptions=(OSError,))
    def always_fail():
        raise OSError("boom")

    with pytest.raises(PersistenceError):
        always_fail()


def test_with_retry_does_not_catch_non_retryable():
    @retry.with_retry(max_attempts=3, backoff=0.0, retryable_exceptions=(OSError,))
    def bad():
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        bad()
