"""Tests for the Persistence facade and its sub-facades."""

from unittest.mock import MagicMock

import pytest

from services.persistence.facade import Persistence, _alarm_get_by_hash, _state_delete_value


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the Persistence singleton between tests so each one starts clean."""
    Persistence.reset_instance()
    yield
    Persistence.reset_instance()


def test_persistence_is_singleton():
    a = Persistence.instance()
    b = Persistence.instance()
    assert a is b


def test_facade_exposes_sub_facades():
    p = Persistence.instance()
    assert p.alarms is not None
    assert p.bdt is not None
    assert p.blobs is not None
    assert p.files is not None
    assert p.pm is not None
    assert p.catalog is not None
    assert p.state is not None
    assert p.sync is not None


def test_alarms_subfacade_uses_alarm_repo():
    """The alarms sub-facade should expose the alarm_repo functions."""
    p = Persistence.instance()
    assert hasattr(p.alarms, "upsert")
    assert hasattr(p.alarms, "get_by_hash")
    assert hasattr(p.alarms, "load_alarms_as_df")


def test_state_subfacade_exposes_key_value_api():
    """The state sub-facade exposes get/set/delete for UI state."""
    p = Persistence.instance()
    assert hasattr(p.state, "get")
    assert hasattr(p.state, "set")
    assert hasattr(p.state, "delete")
    assert hasattr(p.state, "load_all")


def test_reset_instance_clears_singleton():
    """reset_instance() should produce a fresh instance on the next instance() call."""
    a = Persistence.instance()
    Persistence.reset_instance()
    b = Persistence.instance()
    assert a is not b


def test_alarms_get_by_hash_returns_record():
    """The shim should look up a single alarm by row_hash on the session."""
    from services.persistence.models import AlarmRecord

    session = MagicMock()
    expected = AlarmRecord(row_hash="abc")
    session.query(AlarmRecord).filter_by.return_value.first.return_value = expected

    result = _alarm_get_by_hash(session, "abc")
    assert result is expected
    session.query.return_value.filter_by.assert_called_once_with(row_hash="abc")


def test_state_delete_value_returns_false_when_missing():
    """Deleting a missing key should return False and not call session.delete()."""
    session = MagicMock()
    session.get.return_value = None

    assert _state_delete_value(session, "ghost-key") is False
    session.delete.assert_not_called()


def test_state_delete_value_removes_and_commits_when_present():
    """Deleting an existing key should remove it and commit."""
    row = MagicMock()
    session = MagicMock()
    session.get.return_value = row

    assert _state_delete_value(session, "real-key") is True
    session.delete.assert_called_once_with(row)
    session.commit.assert_called_once()


def test_state_facade_get_set_delete_load_all_delegate(tmp_path, monkeypatch):
    """_StateFacade.get/set/delete/load_all should all hit the session."""
    from services.persistence import facade

    p = Persistence.instance()
    session = MagicMock()

    # get
    facade.state_repo.get_value = MagicMock(return_value={"k": "v"})
    assert p.state.get(session, "k") == {"k": "v"}
    facade.state_repo.get_value.assert_called_once_with(session, "k", default=None)

    # set
    facade.state_repo.set_value = MagicMock()
    p.state.set(session, "k", {"k": "v"})
    facade.state_repo.set_value.assert_called_once_with(session, "k", {"k": "v"})

    # delete
    p.state.delete(session, "k")  # delegates to _state_delete_value; mock the session
    # load_all
    facade.state_repo.load_state = MagicMock(return_value={"a": 1})
    assert p.state.load_all(session) == {"a": 1}
    facade.state_repo.load_state.assert_called_once_with(session)
