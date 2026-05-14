"""PyQt5 GUI E2E tests for the main AlarmViewer window."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"


import pandas as pd
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from alarm_app.ui.dialogs import AppSettingsDialog
from alarm_app.ui.state_manager import StateManager
from alarm_app.runtime.chatgpt_connector import ChatGPTConnectorStatus

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

    # Mock OpenRouter fetch to prevent real HTTP calls during GUI tests
    monkeypatch.setattr(
        "alarm_app.llm_tools.openrouter_models.fetch_free_tool_models",
        lambda *a, **kw: [],
    )
    monkeypatch.setattr(
        "llm_tools.openrouter_models.fetch_free_tool_models",
        lambda *a, **kw: [],
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

    def test_settings_dialog_changes_theme(self, gui_app, monkeypatch):
        assert gui_app._theme_mode == "auto"

        def _set_theme_and_accept(dialog_self):
            if hasattr(dialog_self, "cmb_theme"):
                idx = dialog_self.cmb_theme.findData("dark")
                if idx >= 0:
                    dialog_self.cmb_theme.setCurrentIndex(idx)
            dialog_self.accept()
            return QDialog.Accepted

        monkeypatch.setattr(QDialog, "exec_", _set_theme_and_accept)
        gui_app._show_settings()
        assert gui_app._theme_mode == "dark"

    def test_settings_dialog_uses_cloudflare_only_connector_controls(self, gui_app):
        dialog = AppSettingsDialog({}, gui_app)

        assert dialog.edit_chatgpt_url.isReadOnly()
        assert dialog.edit_chatgpt_url.placeholderText() == "Generated after Cloudflare Quick Tunnel starts"
        assert dialog._btn_chatgpt_setup.text() == "Copy URL and Open ChatGPT"
        assert not hasattr(dialog, "_btn_copy_local_mcp")
        assert "Local MCP endpoint" not in dialog._lbl_chatgpt_status.text()

    def test_chatgpt_setup_requires_enabled_quick_tunnel(self, gui_app, monkeypatch):
        opened = []
        monkeypatch.setattr("alarm_app.ui.dialogs.webbrowser.open", lambda *args, **kwargs: opened.append(args))
        dialog = AppSettingsDialog({}, gui_app)

        dialog._copy_public_url_and_open_chatgpt()

        assert opened == []
        assert "Enable the Cloudflare Quick Tunnel" in dialog._lbl_chatgpt_status.text()

    def test_chatgpt_setup_copies_tokenized_url_and_persists_token(self, gui_app, monkeypatch):
        saved_states = []
        monkeypatch.setattr("alarm_app.ui.dialogs.webbrowser.open", lambda *args, **kwargs: True)
        monkeypatch.setattr("alarm_app.ui.dialogs.state.load_state", lambda: {"theme_mode": "auto"})
        monkeypatch.setattr("alarm_app.ui.dialogs.state.save_state", lambda data: saved_states.append(dict(data)))
        dialog = AppSettingsDialog(
            {
                "chatgpt_mcp_enabled": True,
                "chatgpt_mcp_public_url": "https://alarm.example/mcp",
            },
            gui_app,
        )

        dialog._copy_public_url_and_open_chatgpt()

        copied = QApplication.clipboard().text()
        assert copied.startswith("https://alarm.example/mcp?token=")
        assert saved_states[-1]["chatgpt_mcp_public_url"] == "https://alarm.example/mcp"
        assert saved_states[-1]["chatgpt_mcp_token"]

    def test_chatgpt_setup_uses_env_token_when_configured(self, gui_app, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "env-token")
        saved_states = []
        monkeypatch.setattr("alarm_app.ui.dialogs.webbrowser.open", lambda *args, **kwargs: True)
        monkeypatch.setattr("alarm_app.ui.dialogs.state.load_state", lambda: {})
        monkeypatch.setattr("alarm_app.ui.dialogs.state.save_state", lambda data: saved_states.append(dict(data)))
        dialog = AppSettingsDialog(
            {
                "chatgpt_mcp_enabled": True,
                "chatgpt_mcp_public_url": "https://alarm.example/mcp",
            },
            gui_app,
        )

        dialog._copy_public_url_and_open_chatgpt()

        assert QApplication.clipboard().text() == "https://alarm.example/mcp?token=env-token"
        assert "chatgpt_mcp_token" not in saved_states[-1]

    def test_chatgpt_setup_persists_public_url_without_stale_token(self, gui_app, monkeypatch):
        saved_states = []
        monkeypatch.setattr("alarm_app.ui.dialogs.webbrowser.open", lambda *args, **kwargs: True)
        monkeypatch.setattr("alarm_app.ui.dialogs.state.load_state", lambda: {})
        monkeypatch.setattr("alarm_app.ui.dialogs.state.save_state", lambda data: saved_states.append(dict(data)))
        dialog = AppSettingsDialog(
            {
                "chatgpt_mcp_enabled": True,
                "chatgpt_mcp_public_url": "https://alarm.example/mcp?foo=1&token=old",
            },
            gui_app,
        )

        dialog._copy_public_url_and_open_chatgpt()

        assert saved_states[-1]["chatgpt_mcp_public_url"] == "https://alarm.example/mcp?foo=1"
        assert "token=old" not in QApplication.clipboard().text()

    def test_chatgpt_enable_toggle_starts_manager_and_shows_public_url(self, gui_app, monkeypatch):
        saved_state = {"chatgpt_mcp_token": "generated-token"}
        monkeypatch.setattr("alarm_app.ui.dialogs.state.load_state", lambda: dict(saved_state))

        class _Manager:
            def __init__(self):
                self.enable_calls = 0

            def enable(self):
                self.enable_calls += 1
                return ChatGPTConnectorStatus(
                    enabled=True,
                    public_url="https://alarm-test.trycloudflare.com/mcp",
                    connector_url="https://alarm-test.trycloudflare.com/mcp?token=generated-token",
                    token_from_env=False,
                )

            def disable(self):
                raise AssertionError("disable should not be called")

        manager = _Manager()
        dialog = AppSettingsDialog({}, gui_app, connector_manager=manager)

        dialog.chk_chatgpt_mcp_enabled.setChecked(True)

        assert manager.enable_calls == 1
        assert dialog.edit_chatgpt_url.text() == "https://alarm-test.trycloudflare.com/mcp"
        assert dialog.get_settings()["chatgpt_mcp_enabled"] is True

    def test_chatgpt_disable_toggle_stops_manager_and_clears_public_url(self, gui_app):
        class _Manager:
            def __init__(self):
                self.disable_calls = 0

            def enable(self):
                raise AssertionError("enable should not be called")

            def disable(self):
                self.disable_calls += 1
                return ChatGPTConnectorStatus(
                    enabled=False,
                    public_url="",
                    connector_url="",
                    token_from_env=False,
                )

        manager = _Manager()
        dialog = AppSettingsDialog(
            {
                "chatgpt_mcp_enabled": True,
                "chatgpt_mcp_public_url": "https://alarm-test.trycloudflare.com/mcp",
                "chatgpt_mcp_token": "saved-token",
            },
            gui_app,
            connector_manager=manager,
        )

        dialog.chk_chatgpt_mcp_enabled.setChecked(False)

        assert manager.disable_calls == 1
        assert dialog.edit_chatgpt_url.text() == ""
        assert dialog.get_settings()["chatgpt_mcp_enabled"] is False

    def test_state_manager_collects_chatgpt_connector_url(self, gui_app):
        gui_app._chatgpt_mcp_public_url = "https://alarm.example/mcp"
        gui_app._chatgpt_mcp_token = "secret-token"
        gui_app._chatgpt_mcp_enabled = True

        state = StateManager.collect(gui_app)

        assert state["chatgpt_mcp_public_url"] == "https://alarm.example/mcp"
        assert state["chatgpt_mcp_token"] == "secret-token"
        assert state["chatgpt_mcp_enabled"] is True

    def test_state_manager_does_not_persist_env_chatgpt_token(self, gui_app, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "env-token")
        gui_app._chatgpt_mcp_public_url = "https://alarm.example/mcp"
        gui_app._chatgpt_mcp_token = "env-token"

        state = StateManager.collect(gui_app)

        assert state["chatgpt_mcp_token"] == ""

    def test_state_manager_does_not_restore_stale_quick_tunnel_enabled(self, gui_app):
        StateManager.apply(gui_app, {
            "chatgpt_mcp_enabled": True,
            "chatgpt_mcp_public_url": "https://old.trycloudflare.com/mcp",
            "chatgpt_mcp_token": "saved-token",
        })

        assert gui_app._chatgpt_mcp_enabled is False

    def test_close_event_stops_active_chatgpt_connector(self, gui_app):
        class _Manager:
            def __init__(self):
                self.disable_calls = 0

            def disable(self):
                self.disable_calls += 1
                return ChatGPTConnectorStatus(False, "", "", False)

        class _Event:
            def __init__(self):
                self.accepted = False
                self.ignored = False

            def accept(self):
                self.accepted = True

            def ignore(self):
                self.ignored = True

        manager = _Manager()
        gui_app._chatgpt_connector_manager = manager
        gui_app._chatgpt_mcp_enabled = True
        event = _Event()

        gui_app.closeEvent(event)

        assert manager.disable_calls == 1
        assert gui_app._chatgpt_mcp_enabled is False
        assert event.accepted is True

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

    def test_search_filters_actually_filter_rows(self, gui_app):
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
        assert gui_app._model.rowCount() == 2

        gui_app._ui.edit_site.setText("SITE01")
        gui_app._search()
        assert gui_app._model.rowCount() == 1
        model_df = gui_app._model._df
        assert "Power" in model_df["alarm_name"].iloc[0], (
            f"Filtered row should have 'Power' in alarm_name, "
            f"got {model_df['alarm_name'].to_dict()}"
        )

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
