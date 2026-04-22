import pandas as pd

from alarm_app.ui.viewer import AlarmViewer


class _StatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, timeout=0):
        self.messages.append((message, timeout))


class _Label:
    def __init__(self):
        self.text = ""
        self.style = ""

    def setText(self, text):
        self.text = text

    def setStyleSheet(self, style):
        self.style = style


class _LineEdit:
    def text(self):
        return ""


class _Progress:
    def __init__(self):
        self.visible = None
        self.value = None

    def setVisible(self, value):
        self.visible = value

    def setValue(self, value):
        self.value = value


class _Button:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, value):
        self.enabled = value


class _ListItem:
    def __init__(self, payload, selected=True):
        self._payload = payload
        self._selected = selected

    def isSelected(self):
        return self._selected

    def data(self, _role):
        return self._payload


class _ListWidget:
    def __init__(self, items):
        self._items = items

    def count(self):
        return len(self._items)

    def item(self, idx):
        return self._items[idx]


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)


class _DummyLoaderThread:
    calls = []

    def __init__(self, selected):
        self.selected = selected
        self.progress = _Signal()
        self.finished = _Signal()
        self.error = _Signal()

    def start(self):
        _DummyLoaderThread.calls.append(self.selected)


class _DummyViewer:
    def __init__(self):
        self._sbar = _StatusBar()
        self._lbl_loaded = _Label()
        self._lbl_count = _Label()
        self._restored_file_paths = ["/tmp/alarm_a.csv", "/tmp/alarm_b.xlsx"]
        self._pending_sort_col = None
        self._full_df = pd.DataFrame()
        self._file_infos = []
        self._edit_dir = _LineEdit()
        self._bdt_restored = False

    def _apply_filters(self, df):
        return df

    def _populate(self, _df):
        return None

    def _refresh_stats(self, _df):
        return None

    def _restore_bdt_results(self):
        self._bdt_restored = True


def test_alarm_db_load_uses_local_cache_only(monkeypatch):
    expected = pd.DataFrame({"site_id": ["A001"], "alarm_name": ["Power"]})
    monkeypatch.setattr(
        "alarm_app.ui.viewer.state.load_dataframe",
        lambda: expected,
    )

    loaded = AlarmViewer._load_alarm_dataframe_from_db(object())

    assert loaded is expected


def test_empty_cache_restore_does_not_clear_local_cache(monkeypatch):
    cleared = {"called": False}

    def _clear():
        cleared["called"] = True

    monkeypatch.setattr("alarm_app.ui.viewer.state.clear_cache", _clear)
    viewer = _DummyViewer()

    AlarmViewer._on_cache_restored(viewer, None)

    assert cleared["called"] is False
    assert viewer._sbar.messages[-1][0] == "No cached alarm data found"


def test_successful_cache_restore_rebuilds_file_infos(monkeypatch):
    monkeypatch.setattr("alarm_app.ui.viewer.state.load_alarm_ids", lambda: {})
    monkeypatch.setattr("alarm_app.ui.viewer.classify_by_alarm_id", lambda df, _ids: df)
    monkeypatch.setattr("alarm_app.ui.viewer.compute_site_down_flag", lambda df: df)

    viewer = _DummyViewer()
    restored_df = pd.DataFrame({"site_id": ["A001"], "alarm_name": ["Power"]})

    AlarmViewer._on_cache_restored(viewer, restored_df)

    assert viewer._file_infos == [
        {"path": "/tmp/alarm_a.csv", "filename": "alarm_a.csv"},
        {"path": "/tmp/alarm_b.xlsx", "filename": "alarm_b.xlsx"},
    ]
    assert "records (restored)" in viewer._lbl_loaded.text
    assert "Session restored" in viewer._sbar.messages[-1][0]
    assert viewer._bdt_restored is True


def test_db_load_falls_back_to_directory_when_cache_missing(monkeypatch):
    info_payload = {"path": "/tmp/alarm_a.csv", "filename": "alarm_a.csv"}
    viewer = _DummyViewer()
    viewer._full_df = pd.DataFrame()
    viewer._file_list = _ListWidget([_ListItem(info_payload, selected=True)])
    viewer._btn_load = _Button()
    viewer._prog = _Progress()
    viewer._loader = None

    viewer._get_alarm_load_mode = lambda: "db"
    viewer._load_alarm_dataframe_from_db = lambda: None
    viewer._on_loaded = lambda *_args, **_kwargs: None
    viewer._on_error = lambda *_args, **_kwargs: None

    shown = {"called": False}

    def _info(*_args, **_kwargs):
        shown["called"] = True

    monkeypatch.setattr("alarm_app.ui.viewer.LoaderThread", _DummyLoaderThread)
    monkeypatch.setattr("alarm_app.ui.viewer.QMessageBox.information", _info)

    AlarmViewer._load(viewer)

    assert shown["called"] is False
    assert viewer._pending_alarm_load_mode == "directory"
    assert viewer._loader is not None
    assert _DummyLoaderThread.calls[-1] == [info_payload]
    assert any(
        "loading selected files from directory" in msg.lower()
        for msg, _timeout in viewer._sbar.messages
    )


def test_db_load_falls_back_to_all_files_when_none_selected(monkeypatch):
    payload_a = {"path": "/tmp/alarm_a.csv", "filename": "alarm_a.csv"}
    payload_b = {"path": "/tmp/alarm_b.xlsx", "filename": "alarm_b.xlsx"}
    viewer = _DummyViewer()
    viewer._full_df = pd.DataFrame()
    viewer._file_infos = [payload_a, payload_b]
    viewer._file_list = _ListWidget([_ListItem(payload_a, selected=False), _ListItem(payload_b, selected=False)])
    viewer._btn_load = _Button()
    viewer._prog = _Progress()
    viewer._loader = None

    viewer._get_alarm_load_mode = lambda: "db"
    viewer._load_alarm_dataframe_from_db = lambda: None
    viewer._on_loaded = lambda *_args, **_kwargs: None
    viewer._on_error = lambda *_args, **_kwargs: None

    shown = {"called": False}
    warned = {"called": False}

    monkeypatch.setattr("alarm_app.ui.viewer.LoaderThread", _DummyLoaderThread)
    monkeypatch.setattr(
        "alarm_app.ui.viewer.QMessageBox.information",
        lambda *_args, **_kwargs: shown.update(called=True),
    )
    monkeypatch.setattr(
        "alarm_app.ui.viewer.QMessageBox.warning",
        lambda *_args, **_kwargs: warned.update(called=True),
    )

    AlarmViewer._load(viewer)

    assert shown["called"] is False
    assert warned["called"] is False
    assert viewer._loader is not None
    assert _DummyLoaderThread.calls[-1] == [payload_a, payload_b]
    assert any(
        "loading all discovered files" in msg.lower()
        for msg, _timeout in viewer._sbar.messages
    )
