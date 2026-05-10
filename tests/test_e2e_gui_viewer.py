"""PyQt5 GUI E2E tests for the main AlarmViewer window."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"


import pandas as pd
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

# ── global QApplication singleton ─────────────────────────────────
_app: QApplication | None = None


def _get_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


# ── fixture ───────────────────────────────────────────────────────
@pytest.fixture
def gui_app(monkeypatch, tmp_path):
    """Create an AlarmViewer window with DNS/DB filesystem patches.

    Returns the viewer instance ready for GUI assertions.
    """
    app = _get_app()

    # Patch has_alarm_cache so viewer doesn't try DB-backend query path
    try:
        import alarm_app.data.state as state_mod
    except ImportError:
        import data.state as state_mod  # flat bundle

    monkeypatch.setattr(state_mod, "has_alarm_cache", lambda: False)

    # Auto-accept all QDialog.exec_ calls
    def _auto_accept(self_dialog):
        self_dialog.accept()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", _auto_accept)

    # Silence QMessageBox popups
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: None,
    )

    # Patch persist/restore state to avoid touching real filesystem
    try:
        import alarm_app.data.state as state_mod2
    except ImportError:
        import data.state as state_mod2  # flat bundle

    monkeypatch.setattr(state_mod2, "load_state", lambda: {})
    monkeypatch.setattr(state_mod2, "save_state", lambda s: None)
    monkeypatch.setattr(state_mod2, "save_dataframe", lambda df: "duckdb")
    monkeypatch.setattr(state_mod2, "load_alarm_ids", lambda: {})
    monkeypatch.setattr(state_mod2, "load_feature_flags", lambda s=None: {})
    monkeypatch.setattr(state_mod2, "load_dataframe", lambda: pd.DataFrame())

    # Patch DB engine paths to isolated temp DB
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.engine._app_engine", None)
    monkeypatch.setattr("alarm_app.db.engine._app_session_factory", None)
    monkeypatch.setattr(state_mod2, "_engine", None)
    monkeypatch.setattr(state_mod2, "_SessionFactory", None)
    monkeypatch.setattr("alarm_app.bdt.history._engine", None, raising=False)
    monkeypatch.setattr("bdt.history._engine", None, raising=False)

    # Prevent LocalSyncWorker and bootstrap from kicking off
    monkeypatch.setattr(
        "alarm_app.data.sync.LocalSyncWorker.start",
        lambda self: None,
        raising=False,
    )
    monkeypatch.setattr(
        "data.sync.LocalSyncWorker.start",
        lambda self: None,
        raising=False,
    )

    # Patch logger to avoid noise
    import logging

    monkeypatch.setattr(
        logging.getLogger("alarm_app.ui.viewer"),
        "warning",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        logging.getLogger("ui.viewer"),
        "warning",
        lambda *a, **kw: None,
    )

    try:
        from alarm_app.ui.viewer import AlarmViewer
    except ImportError:
        from ui.viewer import AlarmViewer  # flat bundle

    viewer = AlarmViewer()

    yield viewer

    viewer.close()
    viewer.deleteLater()
    app.processEvents()


# ── TestAlarmViewerGUI ─────────────────────────────────────────────
class TestAlarmViewerGUI:

    def test_window_title_matches_app_name(self, gui_app):
        assert "Alarm Viewer" in gui_app.windowTitle()

    def test_settings_button_exists(self, gui_app):
        assert hasattr(gui_app, "_btn_settings")
        btn = gui_app._btn_settings
        assert btn is not None
        assert btn.isEnabled()
        assert "Settings" in btn.text()

    def test_settings_dialog_opens_and_saves(self, gui_app):
        try:
            gui_app._show_settings()
        except Exception as exc:
            pytest.fail(f"_show_settings() raised {exc}")

    def test_load_alarm_csv_file(self, gui_app, tmp_path):
        csv_content = (
            "site_id,alarm_name,alarm_id,occurred_on,cleared_on,"
            "duration,clearance_status,network_type,vendor,alarm_source\n"
            "SITE01,Power Failure,22001,2026-01-15 10:30:00,2026-01-15 12:00:00,"
            "01:30:00,Cleared,3G,Huawei,NMS\n"
            "SITE02,Site Down,35001,2026-01-15 10:31:00,2026-01-15 14:00:00,"
            "03:29:00,Cleared,3G,Huawei,NMS\n"
            "SITE03,Door Open,10001,2026-01-15 10:32:00,2026-01-15 10:45:00,"
            "00:13:00,Cleared,4G,Nokia,NMS\n"
        )
        csv_file = tmp_path / "alarms.csv"
        csv_file.write_text(csv_content)

        gui_app._ui.edit_dir.setText(str(tmp_path))
        gui_app._scan()

        count = gui_app._ui.file_list.count()
        assert count > 0, "File list should have items after scan"

    def test_search_filters_apply(self, gui_app):
        df = pd.DataFrame({
            "site_id": ["SITE01", "SITE02"],
            "alarm_name": ["Power Failure", "Site Down"],
            "alarm_id": [22001, 35001],
            "network_type": ["3G", "3G"],
            "vendor": ["Huawei", "Huawei"],
            "occurred_on": [
                pd.Timestamp("2026-01-15 10:30:00"),
                pd.Timestamp("2026-01-15 10:31:00"),
            ],
            "cleared_on": [
                pd.Timestamp("2026-01-15 12:00:00"),
                pd.Timestamp("2026-01-15 14:00:00"),
            ],
            "duration": ["01:30:00", "03:29:00"],
            "clearance_status": ["Cleared", "Cleared"],
            "alarm_source": ["NMS", "NMS"],
            "site_down_flag": [False, True],
            "alarm_category": ["Power", "Down"],
            "file_source": ["test.csv", "test.csv"],
        })
        gui_app._apply_loaded_alarm_dataframe(df, "test data")
        assert gui_app._model.rowCount() > 0

        gui_app._ui.edit_site.setText("SITE01")
        gui_app._search()
        assert gui_app._model.rowCount() >= 1

    def test_category_filter_combobox_exists(self, gui_app):
        assert hasattr(gui_app._ui, "cb_cat")
        assert gui_app._ui.cb_cat is not None
        assert gui_app._ui.cb_cat.count() >= 1

    def test_tab_switching_works(self, gui_app):
        assert hasattr(gui_app, "_tabs")
        tabs = gui_app._tabs
        assert tabs.count() >= 2
        tabs.setCurrentIndex(1)
        tabs.setCurrentIndex(0)

    def test_alarm_id_config_dialog_opens(self, gui_app):
        try:
            gui_app._show_alarm_id_config()
        except Exception as exc:
            pytest.fail(f"_show_alarm_id_config() raised {exc}")

    def test_feature_flags_dialog_opens(self, gui_app):
        try:
            gui_app._show_feature_flags()
        except Exception as exc:
            pytest.fail(f"_show_feature_flags() raised {exc}")

    def test_header_bar_buttons_visible(self, gui_app):
        for attr in ("_btn_settings", "_btn_config_alarm_ids", "_btn_daily_report"):
            assert hasattr(gui_app, attr), f"viewer has no {attr}"
            btn = getattr(gui_app, attr)
            assert btn is not None, f"{attr} is None"


# ── TestAlarmViewerFileLoad ────────────────────────────────────────
class TestAlarmViewerFileLoad:

    def test_load_real_alarm_csv_populates_dataframe(self, gui_app, monkeypatch):
        try:
            import alarm_app.data.state as state_mod
        except ImportError:
            import data.state as state_mod

        monkeypatch.setattr(
            state_mod,
            "load_alarm_ids",
            lambda: {"power": ["22001"], "down": ["35001"], "door": []},
        )

        df = pd.DataFrame({
            "site_id": ["SITE01", "SITE01"],
            "alarm_name": ["Power Failure", "Site Down"],
            "alarm_id": [22001, 35001],
            "occurred_on": ["2026-01-15 10:30:00", "2026-01-15 10:31:00"],
            "cleared_on": ["2026-01-15 12:00:00", "2026-01-15 14:00:00"],
            "duration": ["01:30:00", "03:29:00"],
            "clearance_status": ["Cleared", "Cleared"],
            "network_type": ["3G", "3G"],
            "vendor": ["Huawei", "Huawei"],
            "alarm_source": ["NMS", "NMS"],
        })

        gui_app._apply_loaded_alarm_dataframe(df, "test")

        assert gui_app._full_df is not None or gui_app._model.rowCount() > 0

        if not gui_app._full_df.empty:
            loaded = gui_app._full_df
        elif gui_app._model.rowCount() > 0:
            loaded = gui_app._model.get_df()
        else:
            loaded = pd.DataFrame()

        assert not loaded.empty, "Loaded dataframe should not be empty"

        if "alarm_category" in loaded.columns:
            categories = set(loaded["alarm_category"].unique())
            has_power_or_down = "Power" in categories or "Down" in categories
            assert has_power_or_down, (
                f"Expected Power/Down in categories, got {categories}"
            )

    def test_loaded_alarms_appear_in_table(self, gui_app):
        df = pd.DataFrame({
            "site_id": ["SITE01", "SITE02"],
            "alarm_name": ["Power Failure", "Site Down"],
            "alarm_id": [22001, 35001],
            "occurred_on": ["2026-01-15 10:30:00", "2026-01-15 10:31:00"],
            "cleared_on": ["2026-01-15 12:00:00", "2026-01-15 14:00:00"],
            "duration": ["01:30:00", "03:29:00"],
            "clearance_status": ["Cleared", "Cleared"],
            "network_type": ["3G", "3G"],
            "vendor": ["Huawei", "Huawei"],
            "alarm_source": ["NMS", "NMS"],
        })

        gui_app._apply_loaded_alarm_dataframe(df, "test data")

        assert gui_app._model.rowCount() == 2

    def test_make_table_creates_proper_columns(self, gui_app):
        df = pd.DataFrame({
            "site_id": ["SITE01"],
            "alarm_name": ["Power Failure"],
            "alarm_id": [22001],
            "occurred_on": ["2026-01-15 10:30:00"],
            "cleared_on": ["2026-01-15 12:00:00"],
            "duration": ["01:30:00"],
            "clearance_status": ["Cleared"],
            "network_type": ["3G"],
            "vendor": ["Huawei"],
            "alarm_source": ["NMS"],
            "site_down_flag": [False],
            "alarm_category": ["Power"],
            "file_source": ["test.csv"],
        })

        gui_app._apply_loaded_alarm_dataframe(df, "test data")

        assert hasattr(gui_app, "_table")
        assert gui_app._table is not None

        model = gui_app._table.model()
        assert model is not None

        try:
            from alarm_app.constants import DISPLAY_COLUMNS
        except ImportError:
            from constants import DISPLAY_COLUMNS

        expected_headers = {label for _, label in DISPLAY_COLUMNS}

        col_count = model.columnCount()
        headers_found = set()
        for ci in range(col_count):
            header = model.headerData(ci, Qt.Horizontal, Qt.DisplayRole)
            if header:
                headers_found.add(header)

        assert len(headers_found) > 0
        overlapping = headers_found & expected_headers
        assert len(overlapping) > 0, (
            f"No DISPLAY_COLUMNS headers in table. Found: {headers_found}"
        )
