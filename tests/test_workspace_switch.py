"""Tests for fast Alarms ↔ BDT workspace switching."""

from types import SimpleNamespace

from alarm_app.data import state
from alarm_app.ui.state_manager import StateManager


def test_set_workspace_view_persists_only_workspace_key(monkeypatch):
    saved_payloads = []

    def _save_state(payload):
        saved_payloads.append(dict(payload))

    monkeypatch.setattr(state, "save_state", _save_state)

    apply_calls = {"count": 0}

    def _apply_workspace_state(index):
        apply_calls["count"] += 1
        apply_calls["last"] = index

    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, index):
            for callback in self._callbacks:
                callback(index)

    class _Tabs:
        def __init__(self):
            self._index = 0
            self.currentChanged = _Signal()

        def currentIndex(self):
            return self._index

        def setCurrentIndex(self, index):
            if self._index != index:
                self._index = index
                self.currentChanged.emit(index)

    tabs = _Tabs()
    tabs.currentChanged.connect(_apply_workspace_state)

    viewer = SimpleNamespace(
        _workspace_defs=({"label": "Alarms"}, {"label": "BDT"}),
        _tabs=tabs,
        setUpdatesEnabled=lambda _enabled: None,
        _apply_workspace_state=_apply_workspace_state,
        _save_workspace_view=lambda: StateManager.persist_partial(
            {"workspace_view": viewer._tabs.currentIndex()}
        ),
    )

    from alarm_app.ui.viewer import AlarmViewer

    AlarmViewer._set_workspace_view(viewer, 1)

    assert viewer._tabs.currentIndex() == 1
    assert apply_calls["count"] == 1
    assert apply_calls["last"] == 1
    assert len(saved_payloads) == 1
    assert saved_payloads[0] == {"workspace_view": 1}
