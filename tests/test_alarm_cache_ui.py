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
    viewer = SimpleNamespace(
        _edit_site=_LineEdit("A001, B002"),
        _cb_cat=_Combo("Power"),
        _cb_net=_Combo("4G"),
        _cb_vnd=_Combo("Huawei"),
        _chk_mindur=_Check(True),
        _spn_mindur=_Spin(15),
        _chk_date=_Check(True),
        _chk_date_range=_Check(True),
        _chk_date_days=_Check(True),
        _d_from=_DateEdit(pd.Timestamp("2026-04-01").date()),
        _d_to=_DateEdit(pd.Timestamp("2026-04-05").date()),
        _edit_days=_LineEdit("2026-04-02,2026-04-04"),
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
    assert set(pd.Timestamp(day).date() for day in query.manual_days) == {
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
        _get_alarm_load_mode=lambda: "db",
        _load_alarm_page=lambda **kwargs: True,
        _current_alarm_total=lambda: 42,
        _lbl_loaded=_Label(),
        _pending_alarm_load_mode=None,
        _full_df=pd.DataFrame(),
    )
    viewer._load_alarm_dataframe_from_db = lambda: (_ for _ in ()).throw(AssertionError("full DataFrame load should not run"))

    AlarmViewer._load(viewer)

    assert viewer._pending_alarm_load_mode == "db"
    assert viewer._lbl_loaded.text == "✓  42 cached records"
    assert viewer._full_df.empty


def test_db_load_falls_back_to_state_dataframe_before_cache_miss_dialog(monkeypatch):
    recovered_df = pd.DataFrame({"site_id": ["A001"], "alarm_name": ["Power"]})
    applied = []
    dialog_calls = []
    viewer = SimpleNamespace(
        _get_alarm_load_mode=lambda: "db",
        _load_alarm_page=lambda **kwargs: True,
        _current_alarm_total=lambda: 0,
        _load_alarm_dataframe_from_db=lambda: recovered_df,
        _apply_loaded_alarm_dataframe=lambda df, msg: applied.append((df.copy(), msg)),
        _file_list=_ListWidget(),
        _file_infos=[],
        _lbl_loaded=_Label(),
        _sbar=_StatusBar(),
        _btn_load=_Button(),
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
        _btn_load=_Button(),
        _prog=_Progress(),
        _sbar=_StatusBar(),
        _lbl_loaded=_Label(),
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
        _page_size=2,
        _page_offset=0,
        _page_total_rows=0,
        _alarm_query_active=False,
        _alarm_table_columns=[],
        _model=model,
        _lbl_count=_Label(),
        _lbl_page=_Label(),
        _lbl_page_range=_Label(),
        _btn_prev_page=_Button(),
        _btn_next_page=_Button(),
        _cb_cat=_Combo("All"),
        _cb_net=_Combo("All"),
        _cb_vnd=_Combo("All"),
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
    assert viewer._cb_vnd.items == ["All", "Huawei", "Nokia"]
    assert viewer._sbar.messages[-1][0] == "Loaded page"
