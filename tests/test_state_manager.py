"""Tests for UI state collection and lightweight persistence."""

from types import SimpleNamespace

from alarm_app.data import state
from alarm_app.ui.state_manager import StateManager


def test_file_hashes_for_viewer_reuses_cache_when_paths_match(monkeypatch):
    calls = {"count": 0}

    def _compute(file_paths):
        calls["count"] += 1
        return {path: f"hash-{path}" for path in file_paths}

    monkeypatch.setattr(state, "compute_file_hashes", _compute)

    viewer = SimpleNamespace(
        _file_infos=[{"path": "/tmp/a.csv"}, {"path": "/tmp/b.csv"}],
        _file_path_hashes={},
    )

    hashes_first = StateManager.file_hashes_for_viewer(viewer)
    assert hashes_first == {"/tmp/a.csv": "hash-/tmp/a.csv", "/tmp/b.csv": "hash-/tmp/b.csv"}
    assert calls["count"] == 1

    hashes_second = StateManager.file_hashes_for_viewer(viewer)
    assert hashes_second == hashes_first
    assert calls["count"] == 1


def test_file_hashes_for_viewer_recomputes_when_file_list_changes(monkeypatch):
    calls = {"count": 0}

    def _compute(file_paths):
        calls["count"] += 1
        return {path: f"hash-{path}" for path in file_paths}

    monkeypatch.setattr(state, "compute_file_hashes", _compute)

    viewer = SimpleNamespace(
        _file_infos=[{"path": "/tmp/a.csv"}, {"path": "/tmp/b.csv"}],
        _file_path_hashes={"/tmp/a.csv": "stale"},
    )

    hashes = StateManager.file_hashes_for_viewer(viewer)
    assert hashes == {
        "/tmp/a.csv": "hash-/tmp/a.csv",
        "/tmp/b.csv": "hash-/tmp/b.csv",
    }
    assert calls["count"] == 1


def test_persist_partial_writes_only_requested_keys(monkeypatch):
    saved = []

    def _save_state(payload):
        saved.append(dict(payload))

    monkeypatch.setattr(state, "save_state", _save_state)

    StateManager.persist_partial({"workspace_view": 1})

    assert len(saved) == 1
    assert saved[0] == {"workspace_view": 1}


def test_collect_uses_cached_file_hashes_without_recomputing(monkeypatch):
    compute_calls = {"count": 0}

    def _compute(file_paths):
        compute_calls["count"] += 1
        return dict.fromkeys(file_paths, "computed")

    monkeypatch.setattr(state, "compute_file_hashes", _compute)

    viewer = SimpleNamespace(
        _file_infos=[{"path": "/tmp/a.csv"}],
        _file_path_hashes={"/tmp/a.csv": "cached"},
        _ui=SimpleNamespace(
            edit_dir=SimpleNamespace(text=lambda: ""),
            edit_bdt_dir=SimpleNamespace(text=lambda: ""),
            edit_site=SimpleNamespace(text=lambda: ""),
            chk_date=SimpleNamespace(isChecked=lambda: False),
            chk_date_range=SimpleNamespace(isChecked=lambda: False),
            chk_date_days=SimpleNamespace(isChecked=lambda: False),
            d_from=SimpleNamespace(date=lambda: __import__("PyQt5.QtCore", fromlist=["QDate"]).QDate.currentDate()),
            d_to=SimpleNamespace(date=lambda: __import__("PyQt5.QtCore", fromlist=["QDate"]).QDate.currentDate()),
            d_day=SimpleNamespace(date=lambda: __import__("PyQt5.QtCore", fromlist=["QDate"]).QDate.currentDate()),
            edit_days=SimpleNamespace(text=lambda: ""),
            cb_cat=SimpleNamespace(currentIndex=lambda: 0),
            cb_net=SimpleNamespace(currentIndex=lambda: 0),
            cb_vnd=SimpleNamespace(currentIndex=lambda: 0),
            chk_mindur=SimpleNamespace(isChecked=lambda: False),
            spn_mindur=SimpleNamespace(value=lambda: 0),
        ),
        _table=SimpleNamespace(
            horizontalHeader=lambda: SimpleNamespace(
                sortIndicatorSection=lambda: -1,
                sortIndicatorOrder=lambda: 0,
            )
        ),
        _col_filters={},
        _uploaded_folder_path="",
        _get_alarm_load_mode=lambda: "directory",
        _bdt_validation_panel=SimpleNamespace(
            cmb_bdt_source=SimpleNamespace(currentData=lambda: "directory"),
        ),
        _tabs=SimpleNamespace(currentIndex=lambda: 0),
        _sync_flags={},
        _both_pd_active=False,
        _page_offset=0,
        _page_size=500,
        _app_zoom_pct=100,
        _theme_mode="dark",
        _skip_photos=False,
        _chatgpt_mcp_enabled=False,
        _chatgpt_mcp_public_url="",
        _chatgpt_mcp_token="",
        _chat_panel=SimpleNamespace(model=lambda: "", chat_state=lambda: {}),
        _assistant_open=True,
        _assistant_width=320,
        geometry=lambda: __import__("PyQt5.QtCore", fromlist=["QRect"]).QRect(0, 0, 800, 600),
    )

    collected = StateManager.collect(viewer)
    assert collected["file_hashes"] == {"/tmp/a.csv": "cached"}
    assert compute_calls["count"] == 0
