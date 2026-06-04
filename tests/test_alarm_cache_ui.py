import sys
from types import SimpleNamespace

import pandas as pd
from PyQt5.QtCore import Qt

from alarm_app.data import alarm_store
from alarm_app.ui.model import AlarmTableModel
from alarm_app.ui.viewer import AlarmViewer


class _Label:
    def __init__(self):
        self.text = ""
        self.style = ""

    def setText(self, text):
        self.text = text

    def setStyleSheet(self, style):
        self.style = style


class _StatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, timeout=0):
        self.messages.append((message, timeout))


class _Header:
    def __init__(self, section=0, order=Qt.AscendingOrder):
        self._section = section
        self._order = order
        self.calls = []

    def sortIndicatorSection(self):
        return self._section

    def sortIndicatorOrder(self):
        return self._order

    def setSortIndicator(self, section, order):
        self.calls.append((section, order))
        self._section = section
        self._order = order


class _Table:
    def __init__(self, header):
        self._header = header

    def horizontalHeader(self):
        return self._header


class _LineEdit:
    def __init__(self, value=""):
        self._value = value

    def text(self):
        return self._value

    def clear(self):
        self._value = ""


class _Combo:
    def __init__(self, text="All"):
        self._text = text
        self.items = []
        self.blocked = []

    def currentText(self):
        return self._text

    def clear(self):
        self.items = []

    def addItem(self, text):
        self.items.append(text)

    def findText(self, text):
        try:
            return self.items.index(text)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        if 0 <= index < len(self.items):
            self._text = self.items[index]

    def blockSignals(self, blocked):
        self.blocked.append(blocked)


class _Check:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked


class _Spin:
    def __init__(self, value=0):
        self._value = value

    def value(self):
        return self._value


class _DateValue:
    def __init__(self, value):
        self._value = value

    def toPyDate(self):
        return self._value


class _DateEdit:
    def __init__(self, value):
        self._value = _DateValue(value)

    def date(self):
        return self._value


class _Button:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = enabled

    def setText(self, text):
        self.text = text


class _Progress:
    def __init__(self):
        self.visible = False
        self.value = 0

    def setVisible(self, visible):
        self.visible = visible

    def setValue(self, value):
        self.value = value


class _ListWidget:
    def count(self):
        return 0

    def item(self, _index):
        raise IndexError("no items")


class _StatsLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _ModelStub:
    def __init__(self, row_count=0):
        self.loaded = None
        self._row_count = row_count
        self.cleared = False

    def clear(self):
        self.cleared = True
        self.loaded = None
        self._row_count = 0

    def load_page(self, df, total_rows, offset):
        self.loaded = (df.copy(), total_rows, offset)
        self._row_count = len(df)

    def rowCount(self):
        return self._row_count

    def columns(self):
        if self.loaded is None:
            return []
        return list(self.loaded[0].columns)


def _build_query_viewer():
    header = _Header(section=2, order=Qt.DescendingOrder)
    stats = {key: _StatsLabel() for key in ("total", "power", "down", "door", "sites", "avg_dur")}
    ui = SimpleNamespace(
        edit_site=_LineEdit("A001, B002"),
        cb_cat=_Combo("Power"),
        cb_net=_Combo("4G"),
        cb_vnd=_Combo("Huawei"),
        chk_mindur=_Check(True),
        spn_mindur=_Spin(15),
        chk_date=_Check(True),
        chk_date_range=_Check(True),
        chk_date_days=_Check(True),
        d_from=_DateEdit(pd.Timestamp("2026-04-01").date()),
        d_to=_DateEdit(pd.Timestamp("2026-04-05").date()),
        edit_days=_LineEdit("2026-04-02,2026-04-04"),
    )
    viewer = SimpleNamespace(
        _ui=ui,
        _both_pd_active=True,
        _uploaded_site_keys={"A001"},
        _col_filters={"vendor": {"Huawei"}, "alarm_category": {"Power"}},
        _table=_Table(header),
        _alarm_table_columns=["site_id", "alarm_name", "vendor"],
        _sbar=_StatusBar(),
    )
    viewer._current_alarm_columns = lambda: list(viewer._alarm_table_columns)
    viewer._build_alarm_query = lambda **kwargs: AlarmViewer._build_alarm_query(viewer, **kwargs)
    viewer._stats = stats
    return viewer


def test_alarm_table_model_load_page_tracks_total_rows_and_offset():
    df = pd.DataFrame({"site_id": ["A001", "B002"]})
    model = AlarmTableModel()

    model.load_page(df, total_rows=25, offset=10)

    assert model.rowCount() == 2
    assert model.total_rows() == 25
    assert model.page_offset() == 10
    assert model.get_df()["site_id"].tolist() == ["A001", "B002"]


def test_build_alarm_query_maps_ui_state():
    viewer = _build_query_viewer()

    query = AlarmViewer._build_alarm_query(viewer, limit=50, offset=100)

    assert query.site_text == "A001, B002"
    assert query.category == "Power"
    assert query.vendor == "Huawei"
    assert query.network_type == "4G"
    assert query.min_duration_secs == 900
    assert {pd.Timestamp(day).date() for day in query.manual_days} == {
        pd.Timestamp("2026-04-02").date(),
        pd.Timestamp("2026-04-04").date(),
    }
    assert query.date_from == pd.Timestamp("2026-04-01").date()
    assert query.date_to == pd.Timestamp("2026-04-05").date()
    assert query.both_pd is True
    assert query.site_scope_keys == {"A001"}
    assert query.col_filters == {"vendor": {"Huawei"}, "alarm_category": {"Power"}}
    assert query.sort_by == "vendor"
    assert query.sort_desc is True
    assert query.limit == 50
    assert query.offset == 100


def test_db_load_uses_query_page_path_without_materializing_full_df(monkeypatch):
    viewer = SimpleNamespace(
        _ui=SimpleNamespace(lbl_loaded=_Label()),
        _get_alarm_load_mode=lambda: "db",
        _load_alarm_page=lambda **kwargs: True,
        _current_alarm_total=lambda: 42,
        _pending_alarm_load_mode=None,
        _full_df=pd.DataFrame(),
    )
    viewer._load_alarm_dataframe_from_db = lambda: (_ for _ in ()).throw(AssertionError("full DataFrame load should not run"))

    AlarmViewer._load(viewer)

    assert viewer._pending_alarm_load_mode == "db"
    assert viewer._ui.lbl_loaded.text == "✓  42 cached records"
    assert viewer._full_df.empty


def test_db_load_falls_back_to_state_dataframe_before_cache_miss_dialog(monkeypatch):
    recovered_df = pd.DataFrame({"site_id": ["A001"], "alarm_name": ["Power"]})
    applied = []
    dialog_calls = []
    viewer = SimpleNamespace(
        _ui=SimpleNamespace(
            lbl_loaded=_Label(),
            btn_load=_Button(),
            file_list=_ListWidget(),
        ),
        _get_alarm_load_mode=lambda: "db",
        _load_alarm_page=lambda **kwargs: True,
        _current_alarm_total=lambda: 0,
        _load_alarm_dataframe_from_db=lambda: recovered_df,
        _apply_loaded_alarm_dataframe=lambda df, msg: applied.append((df.copy(), msg)),
        _file_infos=[],
        _sbar=_StatusBar(),
        _prog=_Progress(),
        _pending_alarm_load_mode=None,
        _full_df=pd.DataFrame(),
    )

    monkeypatch.setattr(
        "alarm_app.ui.viewer.QMessageBox.information",
        lambda *args, **kwargs: dialog_calls.append((args, kwargs)),
    )

    AlarmViewer._load(viewer)

    assert len(applied) == 1
    recovered, message = applied[0]
    assert recovered.equals(recovered_df)
    assert message == "Recovered 1 alarm records from local DB fallback"
    assert dialog_calls == []
    assert viewer._pending_alarm_load_mode == "db"


def test_apply_loaded_alarm_dataframe_keeps_in_memory_results_when_db_render_unavailable(monkeypatch):
    input_df = pd.DataFrame({"site_id": ["A001"], "alarm_name": ["Power"]})
    populated = []
    refreshed = []
    viewer = SimpleNamespace(
        _ui=SimpleNamespace(btn_load=_Button(), lbl_loaded=_Label()),
        _prog=_Progress(),
        _sbar=_StatusBar(),
        _lbl_count=_Label(),
        _page_offset=99,
        _full_df=pd.DataFrame(),
        _has_query_backed_alarm_data=lambda: True,
        _load_alarm_page=lambda **kwargs: True,
        _current_alarm_total=lambda: 0,
        _apply_filters=lambda df: df,
        _populate=lambda df: populated.append(df.copy()),
        _refresh_stats=lambda df: refreshed.append(df.copy()),
        _reset_date_range=lambda df: None,
    )

    monkeypatch.setattr("alarm_app.ui.viewer.state.load_alarm_ids", lambda: {})
    monkeypatch.setattr("alarm_app.ui.viewer.classify_by_alarm_id", lambda df, alarm_ids: df.copy())
    monkeypatch.setattr("alarm_app.ui.viewer.compute_site_down_flag", lambda df: df.copy())

    AlarmViewer._apply_loaded_alarm_dataframe(viewer, input_df, "Loaded parsed alarms")

    assert viewer._page_offset == 0
    assert viewer._full_df.equals(input_df.reset_index(drop=True))
    assert len(populated) == 1
    assert populated[0].equals(input_df)
    assert len(refreshed) == 1
    assert refreshed[0].equals(input_df)
    assert viewer._lbl_count.text == "Showing  1  of  1 records"
    assert viewer._sbar.messages[-1][0] == "Loaded parsed alarms; displaying in-memory results"


def test_load_alarm_page_fetches_count_page_stats_and_facets(monkeypatch):
    header = _Header(section=1, order=Qt.AscendingOrder)
    model = _ModelStub()
    stats = {key: _StatsLabel() for key in ("total", "power", "down", "door", "sites", "avg_dur")}
    viewer = SimpleNamespace(
        _ui=SimpleNamespace(
            cb_cat=_Combo("All"),
            cb_net=_Combo("All"),
            cb_vnd=_Combo("All"),
        ),
        _page_size=2,
        _page_offset=0,
        _page_total_rows=0,
        _alarm_query_active=False,
        _alarm_table_columns=[],
        _model=model,
        _btn_prev_page=_Button(),
        _btn_next_page=_Button(),
        _lbl_count=_Label(),
        _lbl_page=_Label(),
        _lbl_page_range=_Label(),
        _table=_Table(header),
        _sbar=_StatusBar(),
        _stats=stats,
    )
    viewer._has_query_backed_alarm_data = lambda: True
    viewer._current_alarm_columns = lambda: ["site_id", "alarm_name"]
    viewer._build_alarm_query = lambda **kwargs: alarm_store.AlarmQuery(limit=kwargs["limit"], offset=kwargs["offset"])
    viewer._apply_col_widths = lambda cols: setattr(viewer, "_width_cols", cols)
    viewer._update_pagination_controls = lambda: AlarmViewer._update_pagination_controls(viewer)
    viewer._refresh_alarm_stats = lambda query=None: AlarmViewer._refresh_alarm_stats(viewer, query)
    viewer._refresh_alarm_facets = lambda: AlarmViewer._refresh_alarm_facets(viewer)
    viewer._set_combo_values = lambda combo, values, current: AlarmViewer._set_combo_values(
        viewer, combo, values, current
    )

    monkeypatch.setattr("alarm_app.ui.viewer.alarm_store.count_alarms", lambda query: 5)
    monkeypatch.setattr(
        "alarm_app.ui.viewer.alarm_store.query_alarms",
        lambda query: pd.DataFrame(
            {
                "site_id": ["A001", "A002"],
                "alarm_name": ["Power", "Down"],
                "vendor": ["Huawei", "Nokia"],
                "network_type": ["4G", "5G"],
                "alarm_category": ["Power", "Down"],
            }
        ),
    )
    monkeypatch.setattr(
        "alarm_app.ui.viewer.alarm_store.stats",
        lambda query: {
            "total": 5,
            "power": 2,
            "down": 2,
            "door": 1,
            "sites": 4,
            "avg_duration_secs": 3661,
        },
    )
    monkeypatch.setattr(
        "alarm_app.ui.viewer.alarm_store.distinct_values",
        lambda column, query=None: {
            "alarm_category": ["Down", "Power"],
            "network_type": ["4G", "5G"],
            "vendor": ["Huawei", "Nokia"],
        }[column],
    )

    loaded = AlarmViewer._load_alarm_page(viewer, offset=2, status_message="Loaded page")

    assert loaded is True
    assert viewer._page_total_rows == 5
    assert viewer._page_offset == 2
    assert viewer._alarm_query_active is True
    assert model.loaded is not None
    page_df, total_rows, offset = model.loaded
    assert total_rows == 5
    assert offset == 2
    assert page_df["site_id"].tolist() == ["A001", "A002"]
    assert viewer._lbl_count.text == "Showing  3-4  of  5 records"
    assert viewer._lbl_page.text == "Page 2/3"
    assert viewer._lbl_page_range.text == "Rows 3-4 of 5"
    assert stats["avg_dur"].text == "01:01:01"
    assert viewer._ui.cb_vnd.items == ["All", "Huawei", "Nokia"]
    assert viewer._sbar.messages[-1][0] == "Loaded page"


# ── "Clear cached data" feature ──────────────────────────────
# User request: "I need the user to be able to clear the cashed alarms and
# bdt's cause sometime I addes some features and the cashed doesn't get
# updated !! aka don't fully rescan !!"
# Clarification: "do you know that clearing cache mean clean database as
# well !!"


def _make_minimal_viewer(monkeypatch) -> SimpleNamespace:
    """Build a minimal viewer stub for testing _clear_caches() in
    isolation. The stub has the attributes and methods the production
    method touches."""
    model = _ModelStub()
    stats = {key: _StatsLabel() for key in ("total", "power", "down", "door", "sites", "avg_dur")}

    viewer = SimpleNamespace(
        _ui=SimpleNamespace(lbl_loaded=_Label()),
        _sbar=_StatusBar(),
        _lbl_count=_Label(),
        _stats=stats,
        _model=model,
        _page_size=500,
        _page_offset=0,
        _page_total_rows=0,
        _alarm_query_active=False,
        _col_filters={},
        _full_df=pd.DataFrame(),
        _bdt_results=[],
        _bdt_by_site={},
        _reviewed_bdt_keys=set(),
        _bdt_validation_panel=None,
        _bdt_workspace_panel=None,
        _refresh_stats=lambda df: None,
    )
    # Bind the production _clear_caches() so we can call it on the stub.
    # We use AlarmViewer._clear_caches as an unbound function and pass
    # the stub as ``self`` explicitly.
    viewer._clear_caches = lambda: AlarmViewer._clear_caches(viewer)
    return viewer

def test_viewer_has_scoped_clear_cache_methods():
    """Regression: viewer exposes separate scoped cache-clear handlers."""
    assert hasattr(AlarmViewer, "_clear_alarm_caches")
    assert hasattr(AlarmViewer, "_clear_bdt_caches")
    assert hasattr(AlarmViewer, "_clear_caches")


def test_viewer_clear_alarm_caches_resets_only_alarm_state(monkeypatch):
    from unittest.mock import MagicMock
    from PyQt5.QtWidgets import QMessageBox

    viewer = _make_minimal_viewer(monkeypatch)
    bdt_result = MagicMock()
    viewer._full_df = pd.DataFrame({"site_id": ["A", "B"]})
    viewer._page_offset = 100
    viewer._page_total_rows = 250
    viewer._alarm_query_active = True
    viewer._col_filters = {"vendor": {"Huawei"}}
    viewer._bdt_results = [bdt_result]
    viewer._bdt_by_site = {"X": [bdt_result]}
    viewer._reviewed_bdt_keys = {"X"}
    fake_bdt_panel = MagicMock()
    viewer._bdt_validation_panel = fake_bdt_panel

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    _patch_clear_alarm_caches(monkeypatch, lambda: {
        "alarm_duckdb_files": 1,
        "alarm_records": 100,
    })
    _patch_clear_bdt_caches(
        monkeypatch,
        lambda: (_ for _ in ()).throw(AssertionError("BDT clear must not run")),
    )

    AlarmViewer._clear_alarm_caches(viewer)

    assert viewer._full_df.empty
    assert viewer._page_offset == 0
    assert viewer._page_total_rows == 0
    assert viewer._alarm_query_active is False
    assert viewer._col_filters == {}
    assert viewer._model.cleared is True
    assert viewer._bdt_results == [bdt_result]
    assert viewer._bdt_by_site == {"X": [bdt_result]}
    assert viewer._reviewed_bdt_keys == {"X"}
    fake_bdt_panel.set_results.assert_not_called()
    assert any("Cleared alarm cache" in m for m, _ in viewer._sbar.messages)


def test_viewer_clear_bdt_caches_resets_only_bdt_state(monkeypatch):
    from unittest.mock import MagicMock
    from PyQt5.QtWidgets import QMessageBox

    viewer = _make_minimal_viewer(monkeypatch)
    viewer._full_df = pd.DataFrame({"site_id": ["A", "B"]})
    viewer._page_offset = 100
    viewer._page_total_rows = 250
    viewer._alarm_query_active = True
    viewer._col_filters = {"vendor": {"Huawei"}}
    viewer._bdt_results = [MagicMock()]
    viewer._bdt_by_site = {"X": [MagicMock()]}
    viewer._reviewed_bdt_keys = {"X"}
    fake_bdt_panel = MagicMock()
    fake_bdt_workspace = MagicMock()
    viewer._bdt_validation_panel = fake_bdt_panel
    viewer._bdt_workspace_panel = fake_bdt_workspace

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    _patch_clear_alarm_caches(
        monkeypatch,
        lambda: (_ for _ in ()).throw(AssertionError("Alarm clear must not run")),
    )
    _patch_clear_bdt_caches(monkeypatch, lambda: {
        "bdt_history_files": 2,
        "bdt_tests": 10,
        "bdt_photos": 5,
        "blob_assets": 7,
        "pm_validation_runs": 5,
        "pm_rule_results": 50,
        "bdt_summary_catalog": 1,
    })

    AlarmViewer._clear_bdt_caches(viewer)

    assert viewer._full_df["site_id"].tolist() == ["A", "B"]
    assert viewer._page_offset == 100
    assert viewer._page_total_rows == 250
    assert viewer._alarm_query_active is True
    assert viewer._col_filters == {"vendor": {"Huawei"}}
    assert viewer._model.cleared is False
    assert viewer._bdt_results == []
    assert viewer._bdt_by_site == {}
    assert viewer._reviewed_bdt_keys == set()
    fake_bdt_panel.set_results.assert_called_once_with([])
    fake_bdt_workspace.invalidate_caches.assert_called_once_with()
    assert any("Cleared BDT cache" in m for m, _ in viewer._sbar.messages)


def test_clear_alarm_caches_cancels_when_user_says_no(monkeypatch):
    from PyQt5.QtWidgets import QMessageBox

    viewer = _make_minimal_viewer(monkeypatch)
    viewer._full_df = pd.DataFrame({"site_id": ["A"]})
    viewer._page_offset = 50
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    called = []
    _patch_clear_alarm_caches(monkeypatch, lambda: called.append(True) or {})

    AlarmViewer._clear_alarm_caches(viewer)

    assert not viewer._full_df.empty
    assert viewer._page_offset == 50
    assert called == []
    assert any("cancelled" in m for m, _ in viewer._sbar.messages)


def test_clear_bdt_caches_cancels_when_user_says_no(monkeypatch):
    from unittest.mock import MagicMock
    from PyQt5.QtWidgets import QMessageBox

    viewer = _make_minimal_viewer(monkeypatch)
    viewer._bdt_results = [MagicMock()]
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    called = []
    _patch_clear_bdt_caches(monkeypatch, lambda: called.append(True) or {})

    AlarmViewer._clear_bdt_caches(viewer)

    assert viewer._bdt_results
    assert called == []
    assert any("cancelled" in m for m, _ in viewer._sbar.messages)


def test_clear_alarm_caches_refuses_while_background_thread_running(monkeypatch):
    viewer = SimpleNamespace(
        _sbar=_StatusBar(),
        _iter_background_threads=lambda: [_RunningThread()],
    )
    dialogs = []
    monkeypatch.setattr(
        "alarm_app.ui.viewer.QMessageBox.information",
        lambda *args, **kwargs: dialogs.append((args, kwargs)),
    )
    _patch_clear_alarm_caches(
        monkeypatch,
        lambda: (_ for _ in ()).throw(AssertionError("clear_alarm_caches must not run")),
    )

    AlarmViewer._clear_alarm_caches(viewer)

    assert dialogs
    assert viewer._sbar.messages[-1][0] == "Clear alarm cache blocked while background work is running"


def test_clear_bdt_caches_refuses_while_background_thread_running(monkeypatch):
    viewer = SimpleNamespace(
        _sbar=_StatusBar(),
        _iter_background_threads=lambda: [_RunningThread()],
    )
    dialogs = []
    monkeypatch.setattr(
        "alarm_app.ui.viewer.QMessageBox.information",
        lambda *args, **kwargs: dialogs.append((args, kwargs)),
    )
    _patch_clear_bdt_caches(
        monkeypatch,
        lambda: (_ for _ in ()).throw(AssertionError("clear_bdt_caches must not run")),
    )

    AlarmViewer._clear_bdt_caches(viewer)

    assert dialogs
    assert viewer._sbar.messages[-1][0] == "Clear BDT cache blocked while background work is running"


def test_viewer_clear_caches_resets_pagination_and_in_memory_state(monkeypatch):
    """Calling _clear_caches() must reset _full_df, _page_offset,
    _bdt_results, _bdt_by_site, _page_total_rows, and the alarm model."""
    from unittest.mock import MagicMock, patch
    from PyQt5.QtWidgets import QMessageBox

    viewer = _make_minimal_viewer(monkeypatch)
    viewer._full_df = pd.DataFrame({"site_id": ["A", "B"]})
    viewer._page_offset = 100
    viewer._page_total_rows = 250
    viewer._bdt_results = [MagicMock()]
    viewer._bdt_by_site = {"X": [MagicMock()]}
    viewer._reviewed_bdt_keys = {"X"}

    # Stub the QMessageBox.question to auto-accept (Yes)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.Yes),
    )
    # Stub the success QMessageBox.information
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: QMessageBox.Ok),
    )
    # Stub the clear_all_caches call. The function was imported via
    # `from services.persistence.alarm_cache import clear_all_caches`
    # at the top of viewer.py, so we patch it in the SAME module
    # instance the function object lives in.
    _patch_clear_all_caches(monkeypatch, lambda: {
        "alarm_duckdb_files": 1,
        "bdt_history_files": 3,
        "alarm_records": 100,
        "bdt_tests": 10,
        "bdt_photos": 5,
        "blob_assets": 200,
        "pm_validation_runs": 5,
        "pm_rule_results": 50,
        "bdt_summary_catalog": 1,
    })

    # The BDT validation panel exists on AlarmViewer, so the clear must
    # also tell it to reset. Stub the BDT panel here.
    fake_bdt_panel = MagicMock()
    viewer._bdt_validation_panel = fake_bdt_panel
    viewer._bdt_workspace_panel = None  # not present in this stub

    viewer._clear_caches()

    # In-memory state reset
    assert viewer._full_df.empty
    assert viewer._page_offset == 0
    assert viewer._page_total_rows == 0
    assert viewer._bdt_results == []
    assert viewer._bdt_by_site == {}
    assert viewer._reviewed_bdt_keys == set()

    # BDT panel reset
    fake_bdt_panel.set_results.assert_called_once_with([])

    # Status message contains the cleared count
    assert any("Cleared cached data" in m for m, _ in viewer._sbar.messages)


def test_viewer_clear_caches_cancels_when_user_says_no(monkeypatch):
    """If the user clicks 'No' in the confirm dialog, _clear_caches()
    must NOT touch any persistent state and must NOT call
    clear_all_caches()."""
    from unittest.mock import MagicMock, patch
    from PyQt5.QtWidgets import QMessageBox

    viewer = _make_minimal_viewer(monkeypatch)
    viewer._full_df = pd.DataFrame({"site_id": ["A"]})
    viewer._page_offset = 50

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.No),
    )

    called = []
    _patch_clear_all_caches(monkeypatch, lambda: called.append(True) or {})

    fake_bdt_panel = MagicMock()
    viewer._bdt_validation_panel = fake_bdt_panel

    viewer._clear_caches()

    # Nothing was changed
    assert not viewer._full_df.empty
    assert viewer._page_offset == 50
    # clear_all_caches was NOT called
    assert called == []
    # BDT panel was NOT touched
    fake_bdt_panel.set_results.assert_not_called()
    # Status bar shows cancellation
    assert any("cancelled" in m for m, _ in viewer._sbar.messages)


def _patch_viewer_clear_function(monkeypatch, name, replacement):
    """Patch a cache-clear function on the viewer module instance in use."""
    import importlib
    for mod_name in ("alarm_app.ui.viewer", "ui.viewer"):
        mod = importlib.import_module(mod_name)
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, replacement)
            return mod
    raise RuntimeError(f"Could not find a viewer module with `{name}` bound")


def _patch_clear_all_caches(monkeypatch, replacement):
    return _patch_viewer_clear_function(monkeypatch, "clear_all_caches", replacement)


def _patch_clear_alarm_caches(monkeypatch, replacement):
    return _patch_viewer_clear_function(monkeypatch, "clear_alarm_caches", replacement)


def _patch_clear_bdt_caches(monkeypatch, replacement):
    return _patch_viewer_clear_function(monkeypatch, "clear_bdt_caches", replacement)


class _RunningThread:
    def isRunning(self):
        return True


def test_clear_caches_refuses_while_background_thread_running(monkeypatch):
    viewer = SimpleNamespace(
        _sbar=_StatusBar(),
        _iter_background_threads=lambda: [_RunningThread()],
    )
    dialogs = []
    monkeypatch.setattr(
        "alarm_app.ui.viewer.QMessageBox.information",
        lambda *args, **kwargs: dialogs.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "alarm_app.ui.viewer.clear_all_caches",
        lambda: (_ for _ in ()).throw(AssertionError("clear_all_caches must not run")),
    )

    AlarmViewer._clear_caches(viewer)

    assert dialogs
    assert viewer._sbar.messages[-1][0] == "Clear cached data blocked while background work is running"


def test_apply_loaded_alarm_dataframe_skips_duplicate_classification_when_prepared(monkeypatch):
    input_df = pd.DataFrame({
        "site_id": ["A001"],
        "alarm_name": ["Power"],
        "alarm_category": ["Power"],
        "site_down_flag": ["No"],
        "duration": ["00:01:00"],
        "_duration_secs": [60.0],
    })
    viewer = SimpleNamespace(
        _ui=SimpleNamespace(btn_load=_Button(), lbl_loaded=_Label()),
        _prog=_Progress(),
        _sbar=_StatusBar(),
        _lbl_count=_Label(),
        _page_offset=99,
        _full_df=pd.DataFrame(),
        _has_query_backed_alarm_data=lambda: False,
        _apply_filters=lambda df: df,
        _populate=lambda df: None,
        _refresh_stats=lambda df: None,
        _reset_date_range=lambda df: None,
    )
    monkeypatch.setattr(
        "alarm_app.ui.viewer.classify_by_alarm_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("classification should be skipped")),
    )
    monkeypatch.setattr(
        "alarm_app.ui.viewer.compute_site_down_flag",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("site down should be skipped")),
    )

    AlarmViewer._apply_loaded_alarm_dataframe(viewer, input_df, "Loaded parsed alarms")

    assert viewer._full_df.equals(input_df.reset_index(drop=True))


def test_iter_background_threads_includes_bdt_photo_thread():
    photo_thread = object()
    bdt_thread = SimpleNamespace(_photo_thread=photo_thread)
    viewer = SimpleNamespace(
        _loader=None,
        _restore_thread=None,
        _bt_thread=None,
        _bdt_validation_panel=SimpleNamespace(_bdt_thread=bdt_thread),
    )

    threads = list(AlarmViewer._iter_background_threads(viewer))

    assert bdt_thread in threads
    assert photo_thread in threads


def test_alarm_source_mode_help_explains_read_and_save_behavior():
    from alarm_app.ui.panels.left_panel import ALARM_SOURCE_TOOLTIPS

    assert set(ALARM_SOURCE_TOOLTIPS) == {"directory", "db", "both"}
    assert "reads selected CSV/XLSX alarm files" in ALARM_SOURCE_TOOLTIPS["directory"]
    assert "saves/replaces the alarm DuckDB cache" in ALARM_SOURCE_TOOLTIPS["directory"]
    assert "reads only the saved DuckDB alarm cache" in ALARM_SOURCE_TOOLTIPS["db"]
    assert "does not write" in ALARM_SOURCE_TOOLTIPS["db"]
    assert "reads saved DuckDB first" in ALARM_SOURCE_TOOLTIPS["both"]
    assert "saves the merged/re-derived alarm cache" in ALARM_SOURCE_TOOLTIPS["both"]



_qt_app = None


def _ensure_qapp():
    from PyQt5.QtWidgets import QApplication

    global _qt_app
    _qt_app = QApplication.instance() or QApplication([])
    return _qt_app


class _SignalStub:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)


class _ComboStub:
    def __init__(self):
        self.currentIndexChanged = _SignalStub()
        self._index = 0

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, index):
        self._index = index


class _BdtValidationPanelStub:
    def __init__(self):
        self.cmb_bdt_source = _ComboStub()
        self._run_validation = lambda: None
        self._generate_pm_accept_report = lambda: None
        self._show_daily_review_report = lambda: None
        self._export_bdt_results = lambda: None


def test_left_panel_exposes_alarm_only_clear_button(monkeypatch):
    _ensure_qapp()
    from alarm_app.ui.panels.left_panel import LeftPanel

    called = []
    viewer = SimpleNamespace(
        _browse=lambda: None,
        _scan=lambda: None,
        _load=lambda: None,
        _cancel_alarm_load=lambda: None,
        _on_alarm_source_changed=lambda *_: None,
        _clear_alarm_caches=lambda: called.append("alarm"),
    )

    panel = LeftPanel(viewer)

    assert panel.btn_clear_alarm_caches.text() == "Clear alarm cache"
    assert "BDT validation results" in panel.btn_clear_alarm_caches.toolTip()
    assert not hasattr(panel, "btn_clear_caches")


def test_bdt_workspace_exposes_bdt_only_clear_button(monkeypatch):
    _ensure_qapp()
    from alarm_app.ui.panels.bdt_workspace_panel import BdtWorkspacePanel

    viewer = SimpleNamespace(
        _bdt_validation_panel=_BdtValidationPanelStub(),
        _browse_bdt=lambda: None,
        _scan_bdt=lambda: None,
        _import_bdt_summary_catalog=lambda: None,
        _clear_bdt_caches=lambda: None,
        _skip_photos=False,
        _toggle_skip_photos=lambda checked: None,
    )

    panel = BdtWorkspacePanel(viewer)

    assert panel.btn_clear_bdt_caches.text() == "Clear BDT cache"
    assert "Alarm cache" in panel.btn_clear_bdt_caches.toolTip()
    assert panel.btn_clear_bdt_caches in panel._adaptive_primary_buttons
    assert panel.btn_clear_bdt_caches in panel._workflow_buttons
