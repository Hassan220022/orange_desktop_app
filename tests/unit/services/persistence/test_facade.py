"""Tests for the Persistence facade and its sub-facades."""

from services.persistence.facade import Persistence


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
