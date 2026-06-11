"""Standalone dialog windows."""

import os
import secrets
import webbrowser
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

MAX_ANALYSIS_TABLE_ROWS = 5000

try:
    from alarm_app.bdt.rule_docs import full_rules_html, iter_rule_docs
    from alarm_app.constants import APP_NAME, APP_VERSION, BT_HEADERS, BT_WIDTHS, HT_MEET_HEADERS, HT_MEET_WIDTHS
    from alarm_app.core.backup_time import fmt_td as _fmt_td
    from alarm_app.core.temp_alarm import (
        compute_ht_meet_rows,
        enrich_source_with_site_metadata,
        export_temp_alarm_workbook,
        ht_export_filename,
        ht_export_week_from_date,
        ht_export_week_range,
    )
    from alarm_app.data import state
    from alarm_app.runtime.chatgpt_connector import ChatGPTConnectorManager
    from alarm_app.runtime.tunnels import TunnelStartError
except ImportError:
    from bdt.rule_docs import full_rules_html, iter_rule_docs
    from constants import APP_NAME, APP_VERSION, BT_HEADERS, BT_WIDTHS, HT_MEET_HEADERS, HT_MEET_WIDTHS
    from core.backup_time import fmt_td as _fmt_td
    from core.temp_alarm import (
        compute_ht_meet_rows,
        enrich_source_with_site_metadata,
        export_temp_alarm_workbook,
        ht_export_filename,
        ht_export_week_from_date,
        ht_export_week_range,
    )
    from data import state
    from runtime.chatgpt_connector import ChatGPTConnectorManager
    from runtime.tunnels import TunnelStartError


def _resolved_parent_theme_mode(parent) -> str:
    current = parent
    while current is not None:
        mode = getattr(current, "_theme_mode", None)
        if mode:
            if mode == "auto" and hasattr(current, "_detect_os_theme"):
                try:
                    return str(current._detect_os_theme() or "dark")
                except Exception:
                    return "dark"
            return str(mode)
        current = current.parent() if hasattr(current, "parent") else None
    return "dark"


def _local_mcp_base_url() -> str:
    host = os.environ.get("ALARM_BACKEND_HOST", "127.0.0.1")
    port = os.environ.get("ALARM_BACKEND_PORT", "8787")
    return f"http://{host}:{port}"


class ColumnFilterPopup(QDialog):
    """Google-Sheets-style column filter popup with sort + value checkboxes."""

    applied = pyqtSignal(str, object)  # (column_name, selected_values_set_or_None)

    _STYLE_DARK = """
    QDialog { background:#1a1a2a; border:1px solid #2a2a3e; border-radius:8px; }
    QLabel, QWidget#filter_list_inner, QScrollArea, QScrollArea > QWidget > QWidget {
        color:#cdd6f4; background:#1a1a2a;
    }
    QLabel#lbl_hdr { color:#6c7086; font-size:11px; font-weight:700;
                     letter-spacing:0.5px; text-transform:uppercase; }
    QPushButton { background:#2a2a3e; color:#cdd6f4; border:1px solid #3a3a52;
                  border-radius:5px; padding:6px 14px; font-size:12px;
                  font-weight:600; min-width:60px; }
    QPushButton:hover { background:#313150; border-color:#89b4fa; color:#89b4fa; }
    QPushButton#btn_sort_asc { background:#1a2744; color:#89b4fa; border-color:#2a4070; }
    QPushButton#btn_sort_desc { background:#1a2744; color:#89b4fa; border-color:#2a4070; }
    QPushButton#btn_apply { background:#1a2e22; color:#a6e3a1; border-color:#244030; }
    QPushButton#btn_apply:hover { background:#1e3828; border-color:#a6e3a1; }
    QPushButton#btn_clear { background:#2e1a22; color:#f38ba8; border-color:#5a2030; }
    QPushButton#btn_clear:hover { background:#3d1e2c; border-color:#f38ba8; }
    QLineEdit { background:#13131f; color:#cdd6f4; border:1px solid #2a2a3e;
                border-radius:5px; padding:5px 8px; font-size:12px; }
    QLineEdit:focus { border-color:#454560; }
    QCheckBox { color:#cdd6f4; font-size:12px; spacing:6px;
                background:transparent; padding:3px 0; }
    QCheckBox::indicator { width:16px; height:16px; border-radius:4px;
                           border:1px solid #3a3a52; background:#13131f; }
    QCheckBox::indicator:checked { background:#1a2744; border-color:#89b4fa; }
    QScrollArea { border:none; background:#1a1a2a; }
    QScrollArea QWidget#filter_list_inner { background:#1a1a2a; }
    """

    _STYLE_LIGHT = """
    QDialog { background:#eff1f5; border:1px solid #bcc0cc; border-radius:8px; }
    QLabel, QWidget#filter_list_inner, QScrollArea, QScrollArea > QWidget > QWidget {
        color:#4c4f69; background:#eff1f5;
    }
    QLabel#lbl_hdr { color:#7c7f93; font-size:11px; font-weight:700;
                     letter-spacing:0.5px; text-transform:uppercase; }
    QPushButton { background:#ccd0da; color:#4c4f69; border:1px solid #bcc0cc;
                  border-radius:5px; padding:6px 14px; font-size:12px;
                  font-weight:600; min-width:60px; }
    QPushButton:hover { background:#dce0e8; border-color:#1e66f5; color:#1e66f5; }
    QPushButton#btn_sort_asc, QPushButton#btn_sort_desc {
        background:#dce8ff; color:#1e66f5; border-color:#8caaee;
    }
    QPushButton#btn_apply { background:#d8f1dd; color:#2f7d32; border-color:#81c995; }
    QPushButton#btn_apply:hover { background:#c7ebcf; border-color:#2f7d32; }
    QPushButton#btn_clear { background:#f8d7df; color:#c2415d; border-color:#e78284; }
    QPushButton#btn_clear:hover { background:#f5c3cf; border-color:#c2415d; }
    QLineEdit { background:#ffffff; color:#4c4f69; border:1px solid #bcc0cc;
                border-radius:5px; padding:5px 8px; font-size:12px; }
    QLineEdit:focus { border-color:#7287fd; }
    QCheckBox { color:#4c4f69; font-size:12px; spacing:6px;
                background:transparent; padding:3px 0; }
    QCheckBox::indicator { width:16px; height:16px; border-radius:4px;
                           border:1px solid #8c8fa1; background:#ffffff; }
    QCheckBox::indicator:checked { background:#dce8ff; border-color:#1e66f5; }
    QScrollArea { border:none; background:#eff1f5; }
    QScrollArea QWidget#filter_list_inner { background:#eff1f5; }
    """

    def __init__(self, col_name: str, display_name: str,
                 unique_values: list[str],
                 selected: set | None,
                 sort_callback, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setStyleSheet(self._style_for_mode(self._resolved_theme_mode(parent)))
        self._col = col_name
        self._sort_cb = sort_callback
        self._checks: list[tuple[QCheckBox, str]] = []
        self.setFixedWidth(280)
        self.setMaximumHeight(440)
        self._build(display_name, unique_values, selected)

    @classmethod
    def _style_for_mode(cls, mode: str) -> str:
        return cls._STYLE_LIGHT if mode == "light" else cls._STYLE_DARK

    @staticmethod
    def _resolved_theme_mode(parent) -> str:
        return _resolved_parent_theme_mode(parent)

    def _build(self, display_name, values, selected):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # ── Sort buttons ──
        sort_row = QHBoxLayout(); sort_row.setSpacing(6)
        btn_asc = QPushButton("\u2191 Ascending")
        btn_asc.setObjectName("btn_sort_asc")
        btn_asc.setProperty("compact", True)
        btn_asc.clicked.connect(lambda: (self._sort_cb(self._col, Qt.AscendingOrder), self.close()))
        btn_desc = QPushButton("\u2193 Descending")
        btn_desc.setObjectName("btn_sort_desc")
        btn_desc.setProperty("compact", True)
        btn_desc.clicked.connect(lambda: (self._sort_cb(self._col, Qt.DescendingOrder), self.close()))
        sort_row.addWidget(btn_asc)
        sort_row.addWidget(btn_desc)
        lay.addLayout(sort_row)

        # ── Separator ──
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#2a2a3e;")
        lay.addWidget(sep)

        # ── Header ──
        lbl = QLabel(f"Filter: {display_name}")
        lbl.setObjectName("lbl_hdr")
        lay.addWidget(lbl)

        # ── Search box ──
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search values …")
        self._search.textChanged.connect(self._filter_list)
        lay.addWidget(self._search)

        # ── Select All ──
        self._chk_all = QCheckBox("Select All")
        self._chk_all.setChecked(selected is None)
        self._chk_all.stateChanged.connect(self._toggle_all)
        lay.addWidget(self._chk_all)

        # ── Scrollable value list ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("filter_list_inner")
        self._list_lay = QVBoxLayout(inner)
        self._list_lay.setContentsMargins(4, 0, 4, 0)
        self._list_lay.setSpacing(1)

        for v in sorted(values, key=lambda x: x.lower() if x else ""):
            cb = QCheckBox(v if v else "(empty)")
            cb.setChecked(selected is None or v in selected)
            cb.stateChanged.connect(self._on_item_toggled)
            self._list_lay.addWidget(cb)
            self._checks.append((cb, v))

        self._list_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        # ── Buttons ──
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        btn_apply = QPushButton("Apply")
        btn_apply.setObjectName("btn_apply")
        btn_apply.setProperty("compact", True)
        btn_apply.clicked.connect(self._apply)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("compact", True)
        btn_cancel.clicked.connect(self.close)
        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("btn_clear")
        btn_clear.setProperty("compact", True)
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_clear)
        lay.addLayout(btn_row)

    def _toggle_all(self, state):
        checked = state == Qt.Checked
        for cb, _ in self._checks:
            if cb.isVisible():
                cb.setChecked(checked)

    def _on_item_toggled(self):
        all_checked = all(cb.isChecked() for cb, _ in self._checks if cb.isVisible())
        self._chk_all.blockSignals(True)
        self._chk_all.setChecked(all_checked)
        self._chk_all.blockSignals(False)

    def _filter_list(self, text):
        t = text.strip().lower()
        for cb, val in self._checks:
            cb.setVisible(not t or t in val.lower())

    def _apply(self):
        checked = {v for cb, v in self._checks if cb.isChecked()}
        all_vals = {v for _, v in self._checks}
        if checked == all_vals:
            self.applied.emit(self._col, None)  # None = no filter
        else:
            self.applied.emit(self._col, checked)
        self.close()

    def _clear(self):
        self.applied.emit(self._col, None)
        self.close()


class DailyReviewReportDialog(QDialog):
    """Aggregate the number of reviewed BDT files by day."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daily Review Report")
        self.setMinimumSize(720, 420)
        self.setModal(True)
        self._build()
        self._refresh()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color:#6c7086; font-size:11px;")
        lay.addWidget(self._summary)

        self._tbl = QTableWidget(0, 7)
        self._tbl.setHorizontalHeaderLabels(
            ["Date", "Tests Reviewed", "Accepted", "Rejected", "Revise", "N/A", "Users"])
        self._tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._tbl, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("btn_dir")
        btn_refresh.clicked.connect(self._refresh)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

    def _refresh(self):
        rows = state.summarize_review_events_by_day()
        self._tbl.setRowCount(len(rows))
        total = 0
        for r, row in enumerate(rows):
            total += int(row.get("tests_reviewed", 0) or 0)
            values = [
                row.get("date", ""),
                row.get("tests_reviewed", 0),
                row.get("Accepted", 0),
                row.get("Rejected", 0),
                row.get("Revise", 0),
                row.get("N/A", 0),
                row.get("users", ""),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                self._tbl.setItem(r, c, item)
        self._summary.setText(
            f"{total} tests reviewed across {len(rows)} day(s).")


class AlarmIdConfigDialog(QDialog):
    """Dialog to configure Power/Down/Door alarm ID lists."""

    saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Alarm IDs")
        self.setFixedSize(460, 500)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        note = QLabel(
            "Enter alarm IDs (comma-separated) to classify alarms.\n"
            "IDs not in any list keep their filename-based category.")
        note.setStyleSheet("color:#6c7086; font-size:11px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        # Power IDs
        lbl_p = QLabel("Power Alarm IDs")
        lbl_p.setStyleSheet(
            "color:#f38ba8; font-size:12px; font-weight:600;")
        lay.addWidget(lbl_p)
        self._txt_power = QLineEdit()
        self._txt_power.setPlaceholderText("e.g. 22001, 22002, 22003")
        self._txt_power.setMinimumHeight(32)
        lay.addWidget(self._txt_power)

        # Down IDs
        lbl_d = QLabel("Down Alarm IDs")
        lbl_d.setStyleSheet(
            "color:#fab387; font-size:12px; font-weight:600;")
        lay.addWidget(lbl_d)
        self._txt_down = QLineEdit()
        self._txt_down.setPlaceholderText("e.g. 35001, 35002, 35003")
        self._txt_down.setMinimumHeight(32)
        lay.addWidget(self._txt_down)

        # Door IDs
        lbl_dr = QLabel("Door Alarm IDs")
        lbl_dr.setStyleSheet(
            "color:#89dceb; font-size:12px; font-weight:600;")
        lay.addWidget(lbl_dr)
        self._txt_door = QLineEdit()
        self._txt_door.setPlaceholderText("e.g. 91001, 91002, 91003")
        self._txt_door.setMinimumHeight(32)
        lay.addWidget(self._txt_door)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_save = QPushButton("Save")
        btn_save.setObjectName("btn_search")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        lay.addLayout(btn_row)

        # Load current config
        ids = state.load_alarm_ids()
        self._txt_power.setText(", ".join(ids.get("power", [])))
        self._txt_down.setText(", ".join(ids.get("down", [])))
        self._txt_door.setText(", ".join(ids.get("door", [])))

    def _save(self):
        power = [x.strip() for x in self._txt_power.text().split(",")
                 if x.strip()]
        down  = [x.strip() for x in self._txt_down.text().split(",")
                 if x.strip()]
        door  = [x.strip() for x in self._txt_door.text().split(",")
                 if x.strip()]
        state.save_alarm_ids({"power": power, "down": down, "door": door})
        self.saved.emit()
        self.accept()


class FeatureFlagDialog(QDialog):
    """Toggle feature flags: sync_on, cloud_read_on, bootstrap_on."""

    _STYLE = """
    QCheckBox {
        color:#cdd6f4;
        font-size:13px;
        spacing:8px;
        background:transparent;
        padding:4px 0;
    }
    QCheckBox::indicator {
        width:16px;
        height:16px;
        border-radius:4px;
        border:1px solid #3a3a52;
        background:#13131f;
    }
    QCheckBox::indicator:checked {
        background:#1a2744;
        border-color:#89b4fa;
    }
    """

    def __init__(self, flags: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feature Flags")
        self.setFixedWidth(300)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self.setStyleSheet(self.styleSheet() + self._STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        self._checks: dict[str, QCheckBox] = {}

        for key, label in [
            ("sync_on", "Enable sync to server"),
            ("cloud_read_on", "Read from cloud API"),
            ("bootstrap_on", "Bootstrap backfill"),
        ]:
            cb = QCheckBox(label)
            cb.setObjectName("feature_flag_toggle")
            cb.setChecked(bool(flags.get(key, False)))
            self._checks[key] = cb
            layout.addWidget(cb)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Save")
        btn_ok.setObjectName("btn_search")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def get_flags(self) -> dict:
        return {k: cb.isChecked() for k, cb in self._checks.items()}


class _UpdateCheckWorker(QThread):
    finished = pyqtSignal(object)

    def run(self):
        try:
            from alarm_app.updater import fetch_latest_release
        except ImportError:
            from updater import fetch_latest_release
        release = fetch_latest_release()
        self.finished.emit(release)


class _DownloadWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            import os
            import platform
            import tempfile
            import urllib.request

            ext = ".dmg" if platform.system() == "Darwin" else ".exe"
            asset_name = self._url.rsplit("/", 1)[-1] if "/" in self._url else f"AlarmViewer_Update{ext}"
            dest = os.path.join(tempfile.gettempdir(), asset_name)

            req = urllib.request.Request(self._url)
            req.add_header("Accept", "application/octet-stream")
            req.add_header("User-Agent", "AlarmViewer-UpdateCheck")

            with urllib.request.urlopen(req, timeout=600) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))

            self.finished.emit(dest)
        except Exception as exc:
            self.error.emit(str(exc))


class AppSettingsDialog(QDialog):
    """Central app settings dialog."""

    def __init__(self, settings: dict, parent=None, *, connector_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._settings = dict(settings or {})
        self._connector_manager = connector_manager or ChatGPTConnectorManager(local_base_url=_local_mcp_base_url())
        self._chatgpt_enabled = bool(self._settings.get("chatgpt_mcp_enabled", False))
        env_token = os.environ.get("ALARM_MCP_TOKEN", "").strip()
        self._chatgpt_token_from_env = bool(env_token)
        self._chatgpt_token = env_token or str(self._settings.get("chatgpt_mcp_token") or "") or secrets.token_urlsafe(32)
        self._latest_release = None
        self._update_check_worker = None
        self._download_thread = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        title = QLabel("Application Settings")
        title.setObjectName("assistant_title")
        lay.addWidget(title)

        self.cmb_theme = QComboBox()
        self.cmb_theme.setObjectName("filter_combo")
        for value, label in (("auto", "Auto"), ("dark", "Dark"), ("light", "Light")):
            self.cmb_theme.addItem(label, value)
        theme_index = self.cmb_theme.findData(str(self._settings.get("theme_mode") or "auto"))
        self.cmb_theme.setCurrentIndex(max(theme_index, 0))
        self._add_labeled_row(lay, "Theme", self.cmb_theme)

        self.chk_assistant = QCheckBox("Show assistant panel")
        self.chk_assistant.setChecked(bool(self._settings.get("assistant_open", True)))
        lay.addWidget(self.chk_assistant)

        self.chk_skip_photos = QCheckBox("Skip BDT photos during validation")
        self.chk_skip_photos.setChecked(bool(self._settings.get("skip_photos", False)))
        lay.addWidget(self.chk_skip_photos)

        api_title = QLabel("OpenRouter")
        api_title.setObjectName("workspace_card_title")
        lay.addWidget(api_title)

        self.edit_api_key = QLineEdit()
        self.edit_api_key.setObjectName("filter_input")
        self.edit_api_key.setEchoMode(QLineEdit.Password)
        self.edit_api_key.setPlaceholderText("sk-or-...")
        self.edit_api_key.setText(str(self._settings.get("openrouter_api_key") or ""))
        self._add_labeled_row(lay, "API Key", self.edit_api_key)

        flags_title = QLabel("Feature Flags")
        flags_title.setObjectName("workspace_card_title")
        lay.addWidget(flags_title)

        self.chk_sync = QCheckBox("Enable sync to server")
        self.chk_sync.setChecked(bool(self._settings.get("sync_on", False)))
        lay.addWidget(self.chk_sync)
        self.chk_cloud = QCheckBox("Read from cloud API")
        self.chk_cloud.setChecked(bool(self._settings.get("cloud_read_on", False)))
        lay.addWidget(self.chk_cloud)
        self.chk_bootstrap = QCheckBox("Bootstrap backfill")
        self.chk_bootstrap.setChecked(bool(self._settings.get("bootstrap_on", False)))
        lay.addWidget(self.chk_bootstrap)

        # ── Updates section ──
        updates_title = QLabel("Updates")
        updates_title.setObjectName("workspace_card_title")
        lay.addWidget(updates_title)

        self._lbl_version = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self._lbl_version.setStyleSheet("color:#89b4fa; font-size:12px; font-weight:600;")
        lay.addWidget(self._lbl_version)

        check_row = QHBoxLayout()
        check_row.setSpacing(8)
        self._btn_check = QPushButton("Check for Updates")
        self._btn_check.setObjectName("btn_search")
        self._btn_check.clicked.connect(self._on_check_updates)
        check_row.addWidget(self._btn_check)
        check_row.addStretch()
        lay.addLayout(check_row)

        self._lbl_update_status = QLabel("")
        self._lbl_update_status.setWordWrap(True)
        self._lbl_update_status.setStyleSheet("color:#a6e3a1; font-size:11px;")
        self._lbl_update_status.hide()
        lay.addWidget(self._lbl_update_status)

        self._btn_update = QPushButton("Update")
        self._btn_update.setObjectName("btn_search")
        self._btn_update.clicked.connect(self._on_update)
        self._btn_update.hide()
        lay.addWidget(self._btn_update)

        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setFormat("Downloading %p%")
        self._progress.hide()
        lay.addWidget(self._progress)

        chatgpt_title = QLabel("ChatGPT Connector")
        chatgpt_title.setObjectName("workspace_card_title")
        lay.addWidget(chatgpt_title)

        self.chk_chatgpt_mcp_enabled = QCheckBox("Enable ChatGPT MCP via Cloudflare Quick Tunnel")
        self.chk_chatgpt_mcp_enabled.setChecked(self._chatgpt_enabled)
        self.chk_chatgpt_mcp_enabled.stateChanged.connect(self._on_chatgpt_enabled_changed)
        lay.addWidget(self.chk_chatgpt_mcp_enabled)

        self.edit_chatgpt_url = QLineEdit()
        self.edit_chatgpt_url.setObjectName("filter_input")
        self.edit_chatgpt_url.setReadOnly(True)
        self.edit_chatgpt_url.setPlaceholderText("Generated after Cloudflare Quick Tunnel starts")
        self.edit_chatgpt_url.setText(str(self._settings.get("chatgpt_mcp_public_url") or ""))
        self._add_labeled_row(lay, "Cloudflare URL", self.edit_chatgpt_url)

        self._lbl_chatgpt_status = QLabel(
            "Turn this on to start a Cloudflare Quick Tunnel. Alarm Viewer generates the ChatGPT connector URL for you."
        )
        self._lbl_chatgpt_status.setWordWrap(True)
        self._lbl_chatgpt_status.setStyleSheet("color:#6c7086; font-size:11px;")
        lay.addWidget(self._lbl_chatgpt_status)

        chatgpt_row = QHBoxLayout()
        chatgpt_row.setSpacing(8)
        self._btn_chatgpt_setup = QPushButton("Copy URL and Open ChatGPT")
        self._btn_chatgpt_setup.setObjectName("btn_search")
        self._btn_chatgpt_setup.setEnabled(self._chatgpt_enabled and bool(self.edit_chatgpt_url.text().strip()))
        self._btn_chatgpt_setup.clicked.connect(self._copy_public_url_and_open_chatgpt)
        chatgpt_row.addWidget(self._btn_chatgpt_setup)
        lay.addLayout(chatgpt_row)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setObjectName("btn_search")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

    def _on_check_updates(self):
        self._btn_check.setEnabled(False)
        self._btn_check.setText("Checking...")
        self._lbl_update_status.hide()
        self._btn_update.hide()
        self._progress.hide()

        self._update_check_worker = _UpdateCheckWorker(self)
        self._update_check_worker.finished.connect(self._on_check_finished)
        self._update_check_worker.start()

    def _on_check_finished(self, release):
        self._btn_check.setEnabled(True)
        self._btn_check.setText("Check for Updates")
        self._latest_release = release

        if release is None:
            self._lbl_update_status.setStyleSheet("color:#f38ba8; font-size:11px;")
            self._lbl_update_status.setText("Could not reach GitHub. Check your internet connection.")
            self._lbl_update_status.show()
            return

        try:
            from alarm_app.updater import is_update_available
        except ImportError:
            from updater import is_update_available

        if is_update_available(release):
            self._lbl_update_status.setStyleSheet("color:#a6e3a1; font-size:11px;")
            self._lbl_update_status.setText(
                f"New version available: {release.display_version}  "
                f"(you have v{APP_VERSION})"
            )
            self._lbl_update_status.show()
            self._btn_update.show()
        else:
            self._lbl_update_status.setStyleSheet("color:#6c7086; font-size:11px;")
            self._lbl_update_status.setText(
                f"You are up to date (v{APP_VERSION}).  "
                f"Latest release: {release.display_version}"
            )
            self._lbl_update_status.show()

    def _on_update(self):
        if self._latest_release is None:
            return

        try:
            from alarm_app.updater import get_platform_asset
        except ImportError:
            from updater import get_platform_asset

        asset = get_platform_asset(self._latest_release)
        if asset is None:
            self._lbl_update_status.setStyleSheet("color:#f38ba8; font-size:11px;")
            self._lbl_update_status.setText("No downloadable package found for your platform.")
            self._lbl_update_status.show()
            return

        download_url = asset.get("browser_download_url", "")
        if not download_url:
            self._lbl_update_status.setStyleSheet("color:#f38ba8; font-size:11px;")
            self._lbl_update_status.setText("Download URL not found in release assets.")
            self._lbl_update_status.show()
            return

        self._btn_check.setEnabled(False)
        self._btn_update.setEnabled(False)
        self._btn_update.setText("Downloading...")
        self._progress.setValue(0)
        self._progress.show()

        self._download_thread = _DownloadWorker(download_url, self)
        self._download_thread.progress.connect(self._progress.setValue)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.error.connect(self._on_download_error)
        self._download_thread.start()

    def _on_download_finished(self, filepath):
        self._progress.hide()
        self._btn_check.setEnabled(True)
        self._btn_update.setEnabled(True)
        self._btn_update.setText("Update")
        self._lbl_update_status.setStyleSheet("color:#a6e3a1; font-size:11px;")
        self._lbl_update_status.setText(
            "Downloaded. Opening installer... Close this app before installing."
        )
        self._lbl_update_status.show()

        try:
            from alarm_app.updater import open_downloaded_file
        except ImportError:
            from updater import open_downloaded_file

        open_downloaded_file(filepath)

    def _on_download_error(self, error_msg):
        self._progress.hide()
        self._btn_check.setEnabled(True)
        self._btn_update.setEnabled(True)
        self._btn_update.setText("Update")
        self._lbl_update_status.setStyleSheet("color:#f38ba8; font-size:11px;")
        self._lbl_update_status.setText(f"Download failed: {error_msg}")
        self._lbl_update_status.show()

    def _add_labeled_row(self, parent_layout: QVBoxLayout, label: str, widget):
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setObjectName("filter_inline")
        row.addWidget(lbl)
        row.addWidget(widget, 1)
        parent_layout.addLayout(row)

    def _on_chatgpt_enabled_changed(self, state_value):
        enabled = state_value == Qt.Checked
        if enabled:
            try:
                status = self._connector_manager.enable()
            except TunnelStartError as exc:
                self.chk_chatgpt_mcp_enabled.blockSignals(True)
                self.chk_chatgpt_mcp_enabled.setChecked(False)
                self.chk_chatgpt_mcp_enabled.blockSignals(False)
                self._chatgpt_enabled = False
                self._btn_chatgpt_setup.setEnabled(False)
                self._lbl_chatgpt_status.setStyleSheet("color:#f38ba8; font-size:11px;")
                self._lbl_chatgpt_status.setText(str(exc))
                return
            self._chatgpt_enabled = True
            self.edit_chatgpt_url.setText(status.public_url)
            self._btn_chatgpt_setup.setEnabled(True)
            if not status.token_from_env:
                saved = state.load_state() or {}
                self._chatgpt_token = str(saved.get("chatgpt_mcp_token") or self._chatgpt_token)
            self._sync_chatgpt_parent(status.public_url)
            self._lbl_chatgpt_status.setStyleSheet("color:#a6e3a1; font-size:11px;")
            self._lbl_chatgpt_status.setText("Cloudflare Quick Tunnel is active. Copy the URL to finish setup in ChatGPT.")
            return

        status = self._connector_manager.disable()
        self._chatgpt_enabled = False
        self.edit_chatgpt_url.setText(status.public_url)
        self._btn_chatgpt_setup.setEnabled(False)
        if not self._chatgpt_token_from_env:
            self._chatgpt_token = ""
        self._sync_chatgpt_parent(status.public_url)
        self._lbl_chatgpt_status.setStyleSheet("color:#6c7086; font-size:11px;")
        self._lbl_chatgpt_status.setText("Cloudflare Quick Tunnel is disabled.")

    def _sync_chatgpt_parent(self, public_url: str):
        parent = self.parent()
        if parent is not None:
            parent._chatgpt_mcp_enabled = self._chatgpt_enabled
            parent._chatgpt_mcp_public_url = public_url
            parent._chatgpt_mcp_token = "" if self._chatgpt_token_from_env else self._chatgpt_token

    def _persist_chatgpt_connector(self, public_url: str):
        saved = state.load_state() or {}
        saved["chatgpt_mcp_enabled"] = self.chk_chatgpt_mcp_enabled.isChecked()
        saved["chatgpt_mcp_public_url"] = public_url
        if self._chatgpt_token_from_env:
            saved.pop("chatgpt_mcp_token", None)
        else:
            saved["chatgpt_mcp_token"] = self._chatgpt_token
        state.save_state(saved)
        parent = self.parent()
        if parent is not None:
            parent._chatgpt_mcp_enabled = self.chk_chatgpt_mcp_enabled.isChecked()
            parent._chatgpt_mcp_public_url = public_url
            parent._chatgpt_mcp_token = "" if self._chatgpt_token_from_env else self._chatgpt_token

    def _copy_public_url_and_open_chatgpt(self):
        url = self.edit_chatgpt_url.text().strip()
        parsed = urlparse(url)
        if not self.chk_chatgpt_mcp_enabled.isChecked() or parsed.scheme != "https" or not parsed.path.endswith("/mcp"):
            self._lbl_chatgpt_status.setStyleSheet("color:#f38ba8; font-size:11px;")
            self._lbl_chatgpt_status.setText("Enable the Cloudflare Quick Tunnel before opening ChatGPT setup.")
            return
        query_items = [(key, value) for key, value in parse_qsl(parsed.query) if key != "token"]
        safe_public_url = urlunparse(parsed._replace(query=urlencode(query_items)))
        query_items.append(("token", self._chatgpt_token))
        connector_url = urlunparse(parsed._replace(query=urlencode(query_items)))
        self._persist_chatgpt_connector(safe_public_url)
        QApplication.clipboard().setText(connector_url)
        webbrowser.open("https://chatgpt.com/#settings/Connectors", new=2)
        self._lbl_chatgpt_status.setStyleSheet("color:#a6e3a1; font-size:11px;")
        self._lbl_chatgpt_status.setText("Connector URL copied. In ChatGPT, create a connector and paste it as the Connector URL.")

    def get_settings(self) -> dict:
        return {
            "theme_mode": str(self.cmb_theme.currentData() or "auto"),
            "assistant_open": self.chk_assistant.isChecked(),
            "skip_photos": self.chk_skip_photos.isChecked(),
            "openrouter_api_key": self.edit_api_key.text().strip(),
            "chatgpt_mcp_enabled": self.chk_chatgpt_mcp_enabled.isChecked(),
            "chatgpt_mcp_public_url": self.edit_chatgpt_url.text().strip(),
            "chatgpt_mcp_token": "" if self._chatgpt_token_from_env else self._chatgpt_token,
            "sync_on": self.chk_sync.isChecked(),
            "cloud_read_on": self.chk_cloud.isChecked(),
            "bootstrap_on": self.chk_bootstrap.isChecked(),
        }


_TOLERANCE_FIELD_DEFS: tuple[dict, ...] = (
    {
        "key": "sizing_fractional_tolerance",
        "label": "R8 sizing tolerance (% of theoretical)",
        "suffix": " %",
        "decimals": 1,
        "step": 0.5,
        "minimum": 0.0,
        "maximum": 100.0,
        "scale": 100.0,
        "help_template": "Rule R8 checks if the battery lasted as long as expected. "
                         "It currently allows the actual test time to be {value}% shorter or longer "
                         "than expected before R8 fails.",
    },
    {
        "key": "sizing_minutes_floor",
        "label": "R8 sizing minutes floor",
        "suffix": " min",
        "decimals": 1,
        "step": 1.0,
        "minimum": 0.0,
        "maximum": 600.0,
        "help_template": "Smallest difference in minutes that Rule R8 will allow. "
                         "Currently {value} min — stops small batteries from being judged "
                         "too strictly when the expected time is short.",
    },
    {
        "key": "completion_minutes",
        "label": "R6 / R8 completion target",
        "suffix": " min",
        "decimals": 0,
        "step": 5.0,
        "minimum": 30.0,
        "maximum": 600.0,
        "help_template": "How many minutes a battery must run to count as a complete test. "
                         "Currently {value} min. Rules R6 and R8 both use this number.",
    },
    {
        "key": "power_timing_min",
        "label": "R2 power-alarm timing/duration tolerance",
        "suffix": " min",
        "decimals": 0,
        "step": 1.0,
        "minimum": 0.0,
        "maximum": 240.0,
        "help_template": "How many minutes the power-cut alarm start time, end time, and discharge "
                         "duration can be off and still match. Currently {value} min — bigger values "
                         "forgive clock differences between the site and the alarm system.",
    },
    {
        "key": "min_backup_minutes_for_battery_rules",
        "label": "Minimum Network Summary backup minutes required before battery-dependent BDT rules apply",
        "suffix": " min",
        "decimals": 1,
        "step": 1.0,
        "minimum": 0.0,
        "maximum": 240.0,
        "help_template": "When Network Summary says backup is below {value} min, the validator treats the file "
                         "as a component check and skips battery-dependent rules.",
    },
    {
        "key": "string_ampere_a",
        "label": "R3 rectifier-vs-string reject band",
        "suffix": " A",
        "decimals": 2,
        "step": 0.1,
        "minimum": 0.0,
        "maximum": 100.0,
        "help_template": "Reject when summed string current exceeds bus current by more than "
                         "{value} A on any timed row.",
    },
    {
        "key": "string_ampere_pos_accept_a",
        "label": "R3 positive-gap accept band",
        "suffix": " A",
        "decimals": 2,
        "step": 0.1,
        "minimum": 0.0,
        "maximum": 100.0,
        "help_template": "Accepted when bus-above-strings gap stays within {value} A.",
    },
    {
        "key": "string_ampere_pos_revise_a",
        "label": "R3 positive-gap revise ceiling",
        "suffix": " A",
        "decimals": 2,
        "step": 0.1,
        "minimum": 0.0,
        "maximum": 100.0,
        "help_template": "Revise between the accept band and {value} A; reject above this unless severe.",
    },
    {
        "key": "string_imbalance_reject_ratio",
        "label": "R3 string-imbalance reject share",
        "suffix": " %",
        "decimals": 0,
        "step": 1.0,
        "minimum": 50.0,
        "maximum": 100.0,
        "scale": 100.0,
        "help_template": "Reject when one active string carries at least {value}% of string current.",
    },
    {
        "key": "string_imbalance_revise_ratio",
        "label": "R3 string-imbalance revise share",
        "suffix": " %",
        "decimals": 0,
        "step": 1.0,
        "minimum": 50.0,
        "maximum": 100.0,
        "scale": 100.0,
        "help_template": "Revise when one active string carries at least {value}% of string current.",
    },
    {
        "key": "discharge_current_a",
        "label": "R9 legacy discharge-current floor",
        "suffix": " A",
        "decimals": 2,
        "step": 0.1,
        "minimum": 0.0,
        "maximum": 50.0,
        "help_template": "Legacy absolute floor still used with the percentage band when both "
                         "delta and slope look severe. Currently {value} A.",
    },
    {
        "key": "discharge_current_accept_a",
        "label": "R9 max delta accept band",
        "suffix": " A",
        "decimals": 1,
        "step": 0.5,
        "minimum": 0.0,
        "maximum": 100.0,
        "help_template": "Accepted when max |ΔI| from baseline stays within {value} A and slope is calm.",
    },
    {
        "key": "discharge_slope_accept_a_per_min",
        "label": "R9 bus-current slope accept band",
        "suffix": " A/min",
        "decimals": 2,
        "step": 0.05,
        "minimum": 0.0,
        "maximum": 5.0,
        "help_template": "Accepted when bus-current slope stays within {value} A/min.",
    },
    {
        "key": "discharge_slope_reject_a_per_min",
        "label": "R9 bus-current slope reject band",
        "suffix": " A/min",
        "decimals": 2,
        "step": 0.05,
        "minimum": 0.0,
        "maximum": 5.0,
        "help_template": "Reject when bus-current slope reaches {value} A/min or higher.",
    },
    {
        "key": "incomplete_reject_minutes",
        "label": "R2/R6 incomplete reject floor",
        "suffix": " min",
        "decimals": 0,
        "step": 5.0,
        "minimum": 0.0,
        "maximum": 180.0,
        "help_template": "Reject severe incomplete tests when discharge evidence stops before {value} min.",
    },
    {
        "key": "incomplete_revise_minutes",
        "label": "R2/R6 short-discharge revise band",
        "suffix": " min",
        "decimals": 0,
        "step": 5.0,
        "minimum": 0.0,
        "maximum": 240.0,
        "help_template": "Revise on weak/short backup evidence when discharge stops before {value} min.",
    },
    {
        "key": "start_ampere_a",
        "label": "R5 starting current threshold",
        "suffix": " A",
        "decimals": 2,
        "step": 0.05,
        "minimum": 0.0,
        "maximum": 10.0,
        "help_template": "Largest starting battery current that is still acceptable. "
                         "Currently {value} A — if the battery is already drawing or pushing more current "
                         "than this before the rectifier is unplugged, Rule R5 fails.",
    },
    {
        "key": "end_voltage_min",
        "label": "R6 end-voltage minimum",
        "suffix": " V",
        "decimals": 2,
        "step": 0.5,
        "minimum": 30.0,
        "maximum": 70.0,
        "help_template": "Lowest voltage that Rule R6 accepts at the end of the test. "
                         "Currently {value} V.",
    },
    {
        "key": "end_voltage_max",
        "label": "R6 end-voltage maximum",
        "suffix": " V",
        "decimals": 2,
        "step": 0.5,
        "minimum": 30.0,
        "maximum": 70.0,
        "help_template": "Highest voltage that Rule R6 accepts at the end of the test. "
                         "Currently {value} V.",
    },
)


def _format_spinbox_value(value: float, decimals: int) -> str:
    """Format ``value`` with the same precision the spinbox displays.

    Trailing zeros after the decimal point are trimmed so the help text
    reads naturally (``15`` instead of ``15.0``) while still honouring
    the field's configured decimals when the value isn't a round number.
    """
    if decimals <= 0:
        return f"{value:.0f}"
    formatted = f"{value:.{decimals}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def _render_tolerance_help(spec: dict, value: float) -> str:
    """Build the live tooltip text for a tolerance spinbox."""
    template = spec.get("help_template") or spec.get("help") or ""
    if "{value}" not in template:
        return template
    decimals = int(spec.get("decimals", 2))
    return template.format(value=_format_spinbox_value(float(value), decimals))


class BdtParametersDialog(QDialog):
    """Edit active BDT validation parameters and tolerances."""

    def __init__(self, *, health_pct: int,
                 tolerances: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BDT Validation Parameters")
        self.setMinimumSize(520, 720)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._tol_spinboxes: dict[str, tuple[QDoubleSpinBox, float]] = {}
        self._block_checkboxes: dict[str, QCheckBox] = {}
        self._build(health_pct, tolerances or {})

    def _build(self, health_pct: int, tolerances: dict):
        try:
            from alarm_app.bdt.validator import BDTTolerances
            from alarm_app.constants import BDT_RULES, format_bdt_rule_label
        except ImportError:
            from bdt.validator import BDTTolerances
            from constants import BDT_RULES, format_bdt_rule_label
        parsed_tolerances = BDTTolerances.from_dict(tolerances)
        verdict_policy = parsed_tolerances.verdict_policy
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        intro = QLabel(
            "These settings control how strict each BDT validation rule is. "
            "Hover any field to see what it does."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#6c7086; font-size:12px; background:transparent;")
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setObjectName("filter_list")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)

        container = QWidget()
        container.setObjectName("filter_list_inner")
        scroll.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # --- Health card ----------------------------------------------------
        health_card = QFrame()
        health_card.setObjectName("workspace_card")
        health_lay = QVBoxLayout(health_card)
        health_lay.setContentsMargins(12, 12, 12, 12)
        health_lay.setSpacing(8)
        health_title = QLabel("Battery Health")
        health_title.setObjectName("workspace_card_title")
        health_lay.addWidget(health_title)
        self._spn_health = QSpinBox()
        self._spn_health.setRange(50, 100)
        self._spn_health.setValue(int(health_pct))
        self._spn_health.setSuffix(" %")
        self._spn_health.setObjectName("filter_spin")
        health_lay.addWidget(self._spn_health)
        self._lbl_health_help = QLabel()
        self._lbl_health_help.setWordWrap(True)
        self._lbl_health_help.setStyleSheet("color:#6c7086; font-size:11px; background:transparent;")
        health_lay.addWidget(self._lbl_health_help)
        self._refresh_health_help(self._spn_health.value())
        self._spn_health.valueChanged.connect(self._refresh_health_help)
        lay.addWidget(health_card)

        # --- Tolerances card -----------------------------------------------
        tol_card = QFrame()
        tol_card.setObjectName("workspace_card")
        tol_lay = QVBoxLayout(tol_card)
        tol_lay.setContentsMargins(12, 12, 12, 12)
        tol_lay.setSpacing(8)
        tol_title = QLabel("Validation Tolerances")
        tol_title.setObjectName("workspace_card_title")
        tol_lay.addWidget(tol_title)
        tol_help = QLabel(
            "Each rule uses one of these limits to accept, reject, or flag a test for review. "
            "The defaults match the values built into the app."
        )
        tol_help.setWordWrap(True)
        tol_help.setStyleSheet("color:#6c7086; font-size:11px; background:transparent;")
        tol_lay.addWidget(tol_help)
        for spec in _TOLERANCE_FIELD_DEFS:
            row = self._build_tolerance_row(spec, tolerances)
            tol_lay.addLayout(row)
        lay.addWidget(tol_card)

        block_card = QFrame()
        block_card.setObjectName("workspace_card")
        block_lay = QVBoxLayout(block_card)
        block_lay.setContentsMargins(12, 12, 12, 12)
        block_lay.setSpacing(8)
        block_title = QLabel("Overall Verdict Blocking")
        block_title.setObjectName("workspace_card_title")
        block_lay.addWidget(block_title)
        block_help = QLabel(
            "Checked rules can change the overall Verdict when they are Rejected or Revise. "
            "Unchecked rules still run and appear in the table, but they do not block acceptance."
        )
        block_help.setWordWrap(True)
        block_help.setStyleSheet("color:#6c7086; font-size:11px; background:transparent;")
        block_lay.addWidget(block_help)
        for rule_id, rule_name in BDT_RULES:
            checkbox = QCheckBox(format_bdt_rule_label(rule_id, rule_name))
            checkbox.setObjectName("filter_inline")
            checkbox.setChecked(verdict_policy.block_overall.get(rule_id, True))
            checkbox.setToolTip(
                "When unchecked, this rule still runs but does not change the overall Verdict."
            )
            block_lay.addWidget(checkbox)
            self._block_checkboxes[rule_id] = checkbox
        lay.addWidget(block_card)
        lay.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_reset = QPushButton("Reset to defaults")
        btn_reset.setObjectName("btn_clear")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setObjectName("btn_search")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_reset)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)

    def _build_tolerance_row(self, spec: dict, tolerances: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(spec["label"])
        label.setObjectName("filter_inline")
        label.setWordWrap(True)
        label.setMinimumWidth(220)
        row.addWidget(label, 2)

        spin = QDoubleSpinBox()
        spin.setObjectName("filter_spin")
        spin.setDecimals(int(spec.get("decimals", 2)))
        spin.setSingleStep(float(spec.get("step", 0.1)))
        spin.setMinimum(float(spec.get("minimum", 0.0)))
        spin.setMaximum(float(spec.get("maximum", 1000.0)))
        spin.setSuffix(spec.get("suffix", ""))
        scale = float(spec.get("scale", 1.0))
        raw_value = tolerances.get(spec["key"])
        from_defaults = _BDTTolerances_default_value(spec["key"])
        value = raw_value if raw_value is not None else from_defaults
        try:
            spin.setValue(float(value) * scale)
        except (TypeError, ValueError):
            spin.setValue(from_defaults * scale)

        def _refresh_tooltip(v: float, target=spin, field=spec) -> None:
            target.setToolTip(_render_tolerance_help(field, v))

        _refresh_tooltip(spin.value())
        spin.valueChanged.connect(_refresh_tooltip)
        row.addWidget(spin, 1)
        self._tol_spinboxes[spec["key"]] = (spin, scale)
        return row

    def _reset_defaults(self) -> None:
        try:
            from alarm_app.bdt.validator import BDTVerdictPolicy
        except ImportError:
            from bdt.validator import BDTVerdictPolicy
        for spec in _TOLERANCE_FIELD_DEFS:
            spin, scale = self._tol_spinboxes[spec["key"]]
            spin.setValue(_BDTTolerances_default_value(spec["key"]) * scale)
        defaults = BDTVerdictPolicy.defaults()
        for rule_id, checkbox in self._block_checkboxes.items():
            checkbox.setChecked(defaults.block_overall.get(rule_id, True))

    def _refresh_health_help(self, value: int) -> None:
        self._lbl_health_help.setText(
            f"Used in Rule R8 to estimate how long a lead-acid battery should last. "
            f"Currently {int(value)}% means the app treats the battery as delivering "
            f"{int(value)} percent of its rated capacity. "
            f"Lithium batteries are checked a different way and ignore this number."
        )

    def get_values(self) -> int:
        return self._spn_health.value()

    def get_tolerances(self) -> dict[str, float]:
        try:
            from alarm_app.bdt.validator import BDTVerdictPolicy, _verdict_policy_key
        except ImportError:
            from bdt.validator import BDTVerdictPolicy, _verdict_policy_key
        out: dict[str, float] = {}
        for key, (spin, scale) in self._tol_spinboxes.items():
            scale = scale if scale else 1.0
            out[key] = float(spin.value()) / scale
        for rule_id, checkbox in self._block_checkboxes.items():
            out[_verdict_policy_key(rule_id)] = 1.0 if checkbox.isChecked() else 0.0
        return out


def _BDTTolerances_default_value(key: str) -> float:
    """Return the default value of a single field on ``BDTTolerances``."""
    try:
        from alarm_app.bdt.validator import BDTTolerances
    except ImportError:
        from bdt.validator import BDTTolerances
    return float(getattr(BDTTolerances.defaults(), key))


class AcceptedPmReportDialog(QDialog):
    """Explain the Accepted PM report workflow before the user selects a sheet."""

    def __init__(self, *, health_pct: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Accepted PM Report")
        self.setMinimumWidth(680)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build(health_pct)

    def _build(self, health_pct: int):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        intro = QLabel(
            "This workflow cross-checks an accepted PM list against the current BDT validation "
            "results and the local alarm store, then exports a correlation workbook for review."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#cdd6f4; font-size:13px; background:transparent;")
        lay.addWidget(intro)

        summary = QLabel(
            "Use this when you need to confirm whether accepted PM activity lines up with the "
            "best matching BDT test and the related Power/Down alarm timeline."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color:#6c7086; font-size:12px; background:transparent;")
        lay.addWidget(summary)

        steps_card = QFrame()
        steps_card.setObjectName("workspace_card")
        steps_lay = QVBoxLayout(steps_card)
        steps_lay.setContentsMargins(12, 12, 12, 12)
        steps_lay.setSpacing(8)
        steps_title = QLabel("What This Action Does")
        steps_title.setObjectName("workspace_card_title")
        steps_lay.addWidget(steps_title)
        for text in [
            "1. Reads the uploaded Accepted PM workbook or CSV and tries to identify the site, date, and optional acceptance-status columns automatically.",
            "2. Keeps only accepted rows when the sheet contains a status column with values such as Accepted or Accept.",
            "3. Pulls the matching alarm subset from the local DuckDB alarm store using the sheet site IDs and date window.",
            "4. Matches each accepted PM row to the closest BDT validation result by site and test date.",
            "5. Exports one report showing the PM row, matched BDT verdict, theoretical backup estimate, measured test duration, and correlated alarm times.",
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            steps_lay.addWidget(lbl)
        lay.addWidget(steps_card)

        fields_card = QFrame()
        fields_card.setObjectName("workspace_card")
        fields_lay = QVBoxLayout(fields_card)
        fields_lay.setContentsMargins(12, 12, 12, 12)
        fields_lay.setSpacing(8)
        fields_title = QLabel("What You Need Before Running It")
        fields_title.setObjectName("workspace_card_title")
        fields_lay.addWidget(fields_title)
        for text in [
            "Validated BDT results must already be loaded in this workspace.",
            "The local alarm store must contain matching alarm history for the same sites and dates.",
            "The input sheet should contain a site identifier column and a test/date column. A status column is optional.",
            f"The current BDT health parameter ({int(health_pct)}%) is used when calculating theoretical backup time from BDT inputs.",
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            fields_lay.addWidget(lbl)
        lay.addWidget(fields_card)

        output_card = QFrame()
        output_card.setObjectName("workspace_card")
        output_lay = QVBoxLayout(output_card)
        output_lay.setContentsMargins(12, 12, 12, 12)
        output_lay.setSpacing(8)
        output_title = QLabel("Main Output Columns")
        output_title.setObjectName("workspace_card_title")
        output_lay.addWidget(output_title)
        for text in [
            "Matched BDT file name, test date, and validation verdict",
            "Theoretical backup time from BDT inputs",
            "Measured backup time from the BDT discharge duration",
            "Power alarm start, down alarm start, and power clear timestamps",
            "Backup time calculated from the matched alarm pair and the final alarm-correlation status",
        ]:
            lbl = QLabel(f"\u2022 {text}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            output_lay.addWidget(lbl)
        lay.addWidget(output_card)

        note = QLabel(
            "If no matching alarm rows are found for the uploaded sites and dates, the report will stop before export."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#fab387; font-size:11px; background:transparent;")
        lay.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_continue = QPushButton("Choose Accepted PM Sheet")
        btn_continue.setObjectName("btn_search")
        btn_continue.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_continue)
        lay.addLayout(btn_row)


class BdtValidationIntroDialog(QDialog):
    """Explain the BDT validation workflow before the run starts."""

    def __init__(
        self,
        *,
        source_label: str,
        health_pct: int,
        skip_photos: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Validate BDT Files")
        self.setMinimumWidth(700)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build(
            source_label=source_label,
            health_pct=health_pct,
            skip_photos=skip_photos,
        )

    def _build(
        self,
        *,
        source_label: str,
        health_pct: int,
        skip_photos: bool,
    ):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        intro = QLabel(
            "This workflow parses the selected BDT files, applies the full validation rule set, "
            "and produces one validation result per file with rule-by-rule verdicts."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#cdd6f4; font-size:13px; background:transparent;")
        lay.addWidget(intro)

        summary = QLabel(
            "Use this before review or export when you want the app to inspect the BDT workbook "
            "structure, compare it against alarm history, and calculate the final acceptance verdict."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color:#6c7086; font-size:12px; background:transparent;")
        lay.addWidget(summary)

        settings_card = QFrame()
        settings_card.setObjectName("workspace_card")
        settings_lay = QVBoxLayout(settings_card)
        settings_lay.setContentsMargins(12, 12, 12, 12)
        settings_lay.setSpacing(8)
        settings_title = QLabel("Run Settings")
        settings_title.setObjectName("workspace_card_title")
        settings_lay.addWidget(settings_title)
        for text in [
            f"Source: {source_label}",
            f"Health: {int(health_pct)}%",
            f"Skip Photos: {'Enabled' if skip_photos else 'Disabled'}",
        ]:
            lbl = QLabel(f"\u2022 {text}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            settings_lay.addWidget(lbl)
        lay.addWidget(settings_card)

        steps_card = QFrame()
        steps_card.setObjectName("workspace_card")
        steps_lay = QVBoxLayout(steps_card)
        steps_lay.setContentsMargins(12, 12, 12, 12)
        steps_lay.setSpacing(8)
        steps_title = QLabel("What Validation Does")
        steps_title.setObjectName("workspace_card_title")
        steps_lay.addWidget(steps_title)
        for text in [
            "1. Reads the selected BDT workbooks from the chosen source mode.",
            "2. Parses the BDT sheets into structured battery, discharge-table, and summary data.",
            "3. Loads the relevant alarm slice for each site/date when alarm-backed rules need correlation.",
            "4. Runs the BDT validation rules and records Accepted, Rejected, Revise, or N/A for each rule.",
            "5. Saves the validation results so they can be reviewed, exported, and reopened later from DB.",
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            steps_lay.addWidget(lbl)
        lay.addWidget(steps_card)

        rules_card = QFrame()
        rules_card.setObjectName("workspace_card")
        rules_lay = QVBoxLayout(rules_card)
        rules_lay.setContentsMargins(12, 12, 12, 12)
        rules_lay.setSpacing(8)
        rules_title = QLabel("What The Main Parameters Affect")
        rules_title.setObjectName("workspace_card_title")
        rules_lay.addWidget(rules_title)
        for text in [
            "Health controls the usable-capacity assumption for theoretical backup-time calculations on lead-acid batteries.",
            "Skip Photos ignores the photo-check rule during parsing when image content is not required for this run.",
        ]:
            lbl = QLabel(f"\u2022 {text}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            rules_lay.addWidget(lbl)
        lay.addWidget(rules_card)

        note = QLabel(
            "If no BDT files are selected or discovered for the chosen source, the run will stop before validation starts."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#fab387; font-size:11px; background:transparent;")
        lay.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_continue = QPushButton("Start Validation")
        btn_continue.setObjectName("btn_search")
        btn_continue.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_continue)
        lay.addLayout(btn_row)


class BdtRulesReferenceDialog(QDialog):
    """Plain-language reference for every BDT validation rule and insight.

    Layout: rule list on the left, scrollable HTML body on the right.
    Use Ctrl+F inside the body to search the full reference. All numeric
    thresholds shown in the body come from the user's saved
    :class:`BDTTolerances` bundle and the live battery-health setting,
    so the dialog always matches the current configuration.
    """

    def __init__(self, *, tolerances, health_pct: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BDT Rules & Insights")
        self.setMinimumWidth(880)
        self.setMinimumHeight(680)
        self._theme_mode = _resolved_parent_theme_mode(parent)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build(tolerances=tolerances, health_pct=health_pct)

    def _label_style(self, role: str) -> str:
        if self._theme_mode == "light":
            palette = {
                "intro": "color:#4c4f69; font-size:13px; font-weight:600; background:transparent;",
                "summary": "color:#7c7f93; font-size:12px; background:transparent;",
            }
        else:
            palette = {
                "intro": "color:#cdd6f4; font-size:13px; font-weight:600; background:transparent;",
                "summary": "color:#6c7086; font-size:12px; background:transparent;",
            }
        return palette[role]

    def _build(self, *, tolerances, health_pct: int):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        intro = QLabel(
            "Each BDT file goes through validation checks and battery backup "
            "insights. Use the list on the left to jump to a section, or "
            "press Ctrl+F inside the panel on the right to search the full "
            "reference."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(self._label_style("intro"))
        lay.addWidget(intro)

        summary = QLabel(
            "All numbers below come from your current settings. To change them, "
            "close this window and click Open Parameters."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet(self._label_style("summary"))
        lay.addWidget(summary)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        nav = QListWidget()
        nav.setObjectName("rules_reference_nav")
        nav.setUniformItemSizes(True)
        nav.setMinimumWidth(200)
        nav.setMaximumWidth(240)

        nav_keys: list[str] = []
        for key, title, _html in iter_rule_docs(tolerances=tolerances,
                                                health_pct=health_pct):
            QListWidgetItem(title, nav)
            nav_keys.append(key)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setOpenLinks(False)
        browser.setHtml(full_rules_html(tolerances=tolerances,
                                        health_pct=health_pct))
        if self._theme_mode == "light":
            browser.setStyleSheet(
                "QTextBrowser { background:#ffffff; color:#4c4f69; "
                "border:1px solid #ccd0da; border-radius:6px; "
                "padding:8px; font-size:12px; }"
            )
        else:
            browser.setStyleSheet(
                "QTextBrowser { background:#1a1a2a; color:#cdd6f4; "
                "border:1px solid #2a2a3e; border-radius:6px; "
                "padding:8px; font-size:12px; }"
            )

        def _on_nav(row: int) -> None:
            if 0 <= row < len(nav_keys):
                browser.scrollToAnchor(nav_keys[row])

        nav.currentRowChanged.connect(_on_nav)
        nav.setCurrentRow(0)

        splitter.addWidget(nav)
        splitter.addWidget(browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 600])
        lay.addWidget(splitter, 1)

        self._nav = nav
        self._browser = browser
        self._nav_keys = nav_keys

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_search")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)


class BackupTimeDialog(QDialog):
    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏱  Backup Time Analysis")
        self.resize(1050, 680)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._df = df
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 10, 12, 10)

        # ── summary strip ───────────────���────────────────────────
        strip = QFrame()
        strip.setStyleSheet(
            "background:#313244; border-radius:6px; padding:6px;")
        sl = QHBoxLayout(strip)
        sl.setSpacing(30)

        df = self._df
        n  = len(df)

        if n and "backup_td" not in df.columns:
            def _parse_bt(s):
                try:
                    h, m, sec = map(int, s.split(":"))
                    return pd.Timedelta(hours=h, minutes=m, seconds=sec)
                except Exception:
                    return pd.NaT
            secs = df["backup_time"].apply(_parse_bt)
        else:
            secs = df.get("backup_td",
                          pd.Series(dtype="timedelta64[ns]"))

        for label, val, color in [
            ("Matched pairs",
             str(n), "#89b4fa"),
            ("Unique sites",
             str(df["site_id"].nunique()) if n else "0", "#a6e3a1"),
            ("Avg backup time",
             _fmt_td(secs.mean()) if not secs.empty else "—", "#fab387"),
            ("Longest backup",
             _fmt_td(secs.max()) if not secs.empty else "—", "#f38ba8"),
            ("Shortest backup",
             _fmt_td(secs.min()) if not secs.empty else "—", "#94e2d5"),
        ]:
            vb = QVBoxLayout()
            lv = QLabel(val)
            lv.setAlignment(Qt.AlignCenter)
            lv.setFont(QFont("Segoe UI", 14, QFont.Bold))
            lv.setStyleSheet(f"color:{color};")
            lt = QLabel(label)
            lt.setAlignment(Qt.AlignCenter)
            lt.setStyleSheet("color:#6c7086; font-size:11px;")
            vb.addWidget(lv)
            vb.addWidget(lt)
            sl.addLayout(vb)

        sl.addStretch()

        btn_exp = QPushButton("💾  Export CSV")
        btn_exp.setObjectName("btn_export")
        btn_exp.clicked.connect(self._export)
        sl.addWidget(btn_exp)

        lay.addWidget(strip)

        # ── note ─────��───────────────────────────────────────────
        note = QLabel(
            "Backup Time = time between the Power alarm (mains failure) "
            "and the matched end event for the same site/date. The end event "
            "is the latest Down alarm inside the power window, or Power Cleared "
            "if no Down alarm matches. Only pairs within a 72-hour window are shown.")
        note.setStyleSheet("color:#6c7086; font-size:11px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        table_df = df.head(MAX_ANALYSIS_TABLE_ROWS)
        if len(df) > len(table_df):
            preview = QLabel(
                f"Showing first {len(table_df):,} of {len(df):,} rows. Export includes all rows.")
            preview.setStyleSheet("color:#fab387; font-size:11px;")
            lay.addWidget(preview)

        # ── table ─────��──────────────────────────────────────────
        cols = [c for c in BT_HEADERS if c in table_df.columns]
        self._tbl = QTableWidget(len(table_df), len(cols))
        self._tbl.setHorizontalHeaderLabels([BT_HEADERS[c] for c in cols])
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSortingEnabled(False)  # must be OFF during population
        self._tbl.verticalHeader().setDefaultSectionSize(24)
        self._tbl.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        hdr = self._tbl.horizontalHeader()
        for i, c in enumerate(cols):
            hdr.resizeSection(i, BT_WIDTHS.get(c, 120))
        hdr.setStretchLastSection(True)

        for r, row in table_df.iterrows():
            for ci, c in enumerate(cols):
                val = row.get(c, "")
                item = QTableWidgetItem(
                    "" if pd.isna(val) else str(val))
                item.setTextAlignment(
                    Qt.AlignCenter if c in (
                        "backup_time", "network_type", "vendor")
                    else Qt.AlignLeft | Qt.AlignVCenter)
                if c == "backup_time":
                    item.setForeground(QColor("#fab387"))
                elif c == "site_id":
                    item.setForeground(QColor("#cba6f7"))
                self._tbl.setItem(r, ci, item)

        self._tbl.setSortingEnabled(True)  # enable AFTER all items are set
        lay.addWidget(self._tbl)

    # ── export ────────��────────────────────────────────────��─────
    def _export(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Backup Times",
            f"backup_times_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            "Excel Files (*.xlsx)")
        if not fp:
            return
        try:
            self._df.drop(columns=["backup_td"], errors="ignore").to_excel(
                fp, index=False, engine="openpyxl")
            QMessageBox.information(self, "Export OK", f"Saved to:\n{fp}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))


class _TempAlarmExportThread(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        matches: pd.DataFrame,
        path: str,
        source_df: pd.DataFrame,
        week_label: str | None,
        site_metadata_df: pd.DataFrame | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._matches = matches
        self._path = path
        self._source_df = source_df
        self._week_label = week_label
        self._site_metadata_df = site_metadata_df
        self.warning_result: dict[str, object] = {}

    def run(self):
        try:
            self.warning_result = export_temp_alarm_workbook(
                self._matches,
                self._path,
                week_label=self._week_label,
                source_df=self._source_df,
                site_metadata_df=self._site_metadata_df,
                return_warnings=True,
            ) or {}
            self.succeeded.emit(self._path)
        except Exception as exc:
            self.failed.emit(str(exc))


class _TempAlarmPreviewThread(QThread):
    succeeded = pyqtSignal(object, object, object, str, str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        source_df: pd.DataFrame,
        site_metadata_df: pd.DataFrame | None,
        filter_text: str,
        week_label: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self._source_df = source_df
        self._site_metadata_df = site_metadata_df
        self._filter_text = filter_text
        self._week_label = week_label

    def run(self):
        try:
            preview_source, meet, missing_ids = _build_temp_alarm_preview(
                self._source_df,
                self._site_metadata_df,
                self._filter_text,
                self._week_label,
            )
            self.succeeded.emit(preview_source, meet, missing_ids, self._week_label or "", self._filter_text)
        except Exception as exc:
            self.failed.emit(str(exc))


class TempAlarmDialog(QDialog):
    """HT Alarm Workbook Meet preview dialog."""

    def __init__(self, df: pd.DataFrame, source_df: pd.DataFrame, margin_minutes: int = 60, result_filter_query=None, selected_temp_df: pd.DataFrame | None = None, week_label: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HT Alarm Workbook — Meet Preview")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        max_width = available.width() - 80 if available else 1280
        target_width = max(1180, min(1280, max_width))
        self.setMinimumSize(min(target_width, 1240), 720)
        self.resize(target_width, 760)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._source_df = source_df
        self._result_filter_query = result_filter_query
        self._selected_temp_df = selected_temp_df
        self._df = df
        self._margin_minutes = max(0, int(margin_minutes or 0))
        self._week_label = week_label or self._infer_default_week_label()
        self._site_metadata_df = _load_site_metadata_catalog()
        self._preview_source_df = pd.DataFrame()
        self._preview_missing_metadata_ids: list[str] = []
        self._preview_week_label = None
        self._preview_filter_text = ""
        self._tbl = None
        self._summary_strip = None
        self._table_host = None
        self._btn_export = None
        self._btn_apply_week = None
        self._week_input = None
        self._metadata_filter_input = None
        self._export_status = None
        self._export_progress = None
        self._export_thread = None
        self._preview_thread = None
        self._export_after_preview_refresh = False
        self._metadata_warning = None
        self._build()
        self._start_preview_recompute()

    def _infer_default_week_label(self) -> str:
        """Try to infer the default HT export week label from the meet data or source."""
        df = self._df
        if not df.empty:
            if "Last Occurred On" in df.columns:
                times = pd.to_datetime(df["Last Occurred On"], errors="coerce").dropna()
            elif "temp_time" in df.columns:
                times = pd.to_datetime(df["temp_time"], errors="coerce").dropna()
            else:
                times = pd.Series(dtype="datetime64[ns]")
            if not times.empty:
                try:
                    return ht_export_week_from_date(times.max())["week_label"]
                except Exception:
                    pass
        # Fall back to source_df
        src = self._source_df
        if src is not None and not src.empty and "occurred_on" in src.columns:
            times = pd.to_datetime(src["occurred_on"], errors="coerce").dropna()
            if not times.empty:
                try:
                    return ht_export_week_from_date(times.max())["week_label"]
                except Exception:
                    pass
        return ""

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 14, 16, 14)

        # ── Top header strip ────────────────────────────────────
        top = QFrame()
        top.setObjectName("tempDashboardHeader")
        top.setStyleSheet("QFrame#tempDashboardHeader { background:#313244; border-radius:8px; }")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(12, 10, 12, 10)
        tl.setSpacing(10)
        tl.setAlignment(Qt.AlignVCenter)

        # Week label control
        week_label_lbl = QLabel("Export Week")
        week_label_lbl.setStyleSheet("color:#a6adc8; font-size:11px; font-weight:700;")
        tl.addWidget(week_label_lbl)

        self._week_input = QLineEdit()
        self._week_input.setPlaceholderText("e.g. W27-24")
        self._week_input.setText(self._week_label or "")
        self._week_input.setFixedSize(112, 36)
        self._week_input.setAlignment(Qt.AlignCenter)
        self._week_input.setStyleSheet(
            """
            QLineEdit {
                background:#11111b;
                border:1px solid #89b4fa;
                border-radius:6px;
                color:#cdd6f4;
                font-size:13px;
                font-weight:700;
                padding:0 8px;
            }
            QLineEdit:focus { border-color:#b4befe; }
            QLineEdit:disabled {
                background:#313244;
                border-color:#45475a;
                color:#6c7086;
            }
            """
        )
        tl.addWidget(self._week_input)

        self._btn_apply_week = QPushButton("Apply")
        self._btn_apply_week.setFixedSize(100, 36)
        self._btn_apply_week.setStyleSheet(
            """
            QPushButton {
                background:#1e1e2e;
                border:1px solid #45475a;
                border-radius:6px;
                color:#cdd6f4;
                font-size:11px;
                font-weight:700;
                min-width:78px;
                max-width:78px;
                padding:0 10px;
            }
            QPushButton:hover { border-color:#89b4fa; }
            QPushButton:disabled {
                color:#6c7086;
                border-color:#313244;
            }
            """
        )
        self._btn_apply_week.setFixedSize(100, 36)
        self._btn_apply_week.clicked.connect(self._apply_week_now)
        tl.addWidget(self._btn_apply_week)

        self._metadata_filter_input = QLineEdit()
        self._metadata_filter_input.setPlaceholderText("Filter site / area / subcontractor")
        self._metadata_filter_input.setFixedSize(220, 36)
        self._metadata_filter_input.setStyleSheet(
            """
            QLineEdit {
                background:#11111b;
                border:1px solid #45475a;
                border-radius:6px;
                color:#cdd6f4;
                font-size:13px;
                padding:0 10px;
            }
            QLineEdit:focus { border-color:#89b4fa; }
            QLineEdit:disabled {
                background:#313244;
                border-color:#45475a;
                color:#6c7086;
            }
            """
        )
        self._metadata_filter_input.setFixedSize(220, 36)
        self._metadata_filter_input.returnPressed.connect(self._apply_metadata_filter_now)
        self._metadata_filter_input.editingFinished.connect(self._apply_metadata_filter_now)
        tl.addWidget(self._metadata_filter_input)

        # Summary metric cards
        self._summary_strip = QHBoxLayout()
        self._summary_strip.setSpacing(10)
        tl.addLayout(self._summary_strip, 0)
        tl.addStretch(1)

        # Export button card
        export_card = QFrame()
        export_card.setObjectName("tempExportCard")
        export_card.setFixedWidth(120)
        export_card.setStyleSheet("QFrame#tempExportCard { background:transparent; }")
        el = QVBoxLayout(export_card)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(6)
        el.setAlignment(Qt.AlignCenter)

        self._export_status = QLabel("")
        self._export_status.setAlignment(Qt.AlignCenter)
        self._export_status.setWordWrap(True)
        self._export_status.setStyleSheet("color:#94e2d5; font-size:10px;")
        self._export_status.hide()
        el.addWidget(self._export_status)

        self._export_progress = QProgressBar()
        self._export_progress.setRange(0, 0)
        self._export_progress.setFixedWidth(100)
        self._export_progress.hide()
        el.addWidget(self._export_progress, 0, Qt.AlignCenter)

        self._btn_export = QPushButton("Export XLSX")
        self._btn_export.setObjectName("btn_export")
        self._btn_export.setMinimumSize(112, 40)
        self._btn_export.clicked.connect(self._export)
        el.addWidget(self._btn_export)
        tl.addWidget(export_card)
        lay.addWidget(top)

        note = QLabel(
            "HT alarms that meet the daily threshold (>7 hours HT minus Power). "
            "Set the week label above to scope the workbook export."
        )
        note.setStyleSheet("color:#6c7086; font-size:11px; padding:6px 0;")
        note.setWordWrap(True)
        lay.addWidget(note)
        self._metadata_warning = QLabel(self._metadata_warning_text())
        self._metadata_warning.setStyleSheet("color:#fab387; font-size:11px; padding:6px 0;")
        self._metadata_warning.setWordWrap(True)
        self._metadata_warning.setVisible(bool(self._metadata_warning.text()))
        lay.addWidget(self._metadata_warning)

        self._table_host = QVBoxLayout()
        self._table_host.setSpacing(8)
        lay.addLayout(self._table_host, 1)
        self._render_summary()
        self._render_table()

    def _apply_week_now(self, force: bool = False):
        new_label = self._week_input.text().strip()
        if not force and new_label == self._week_label and not self._preview_is_stale(new_label):
            return
        self._week_label = new_label
        self._start_preview_recompute()

    def _apply_metadata_filter_now(self):
        self._apply_week_now()

    def _current_filter_text(self) -> str:
        return self._metadata_filter_input.text().strip() if self._metadata_filter_input else ""

    def _preview_is_stale(self, week_label: str | None = None) -> bool:
        current_week = week_label if week_label is not None else self._week_label
        return current_week != self._preview_week_label or self._current_filter_text() != self._preview_filter_text

    def _clear_results_for_week_apply(self):
        self._df = pd.DataFrame(columns=list(HT_MEET_HEADERS))
        self._render_summary()
        self._render_table()
        QApplication.processEvents()

    def _start_preview_recompute(self):
        if self._preview_thread and self._preview_thread.isRunning():
            return
        self._clear_results_for_week_apply()
        self._set_previewing(True)
        self._preview_thread = _TempAlarmPreviewThread(
            self._source_df,
            self._site_metadata_df,
            self._current_filter_text(),
            self._week_label or None,
            self,
        )
        self._preview_thread.succeeded.connect(self._on_preview_ready)
        self._preview_thread.failed.connect(self._on_preview_failed)
        self._preview_thread.finished.connect(self._on_preview_finished)
        self._preview_thread.finished.connect(self._preview_thread.deleteLater)
        self._preview_thread.start()

    def _on_preview_ready(self, preview_source, meet, missing_ids, week_label: str, filter_text: str):
        self._preview_source_df = preview_source
        self._df = meet
        self._preview_missing_metadata_ids = list(missing_ids or [])
        self._preview_week_label = week_label
        self._preview_filter_text = filter_text
        if self._metadata_warning:
            self._metadata_warning.setText(self._metadata_warning_text())
            self._metadata_warning.setVisible(bool(self._metadata_warning.text()))
        self._render_summary()
        self._render_table()
    def _on_preview_failed(self, msg: str):
        self._export_after_preview_refresh = False
        QMessageBox.critical(self, "HT Meet Preview Failed", msg)

    def _on_preview_finished(self):
        self._set_previewing(False)
        self._preview_thread = None
        if self._export_after_preview_refresh:
            self._export_after_preview_refresh = False
            self._export()

    def _set_previewing(self, previewing: bool):
        if self._btn_apply_week:
            self._btn_apply_week.setEnabled(not previewing)
            self._btn_apply_week.setText("Applying..." if previewing else "Apply")
        if self._btn_export:
            self._btn_export.setEnabled(not previewing)
        if self._week_input:
            self._week_input.setEnabled(not previewing)
        if self._metadata_filter_input:
            self._metadata_filter_input.setEnabled(not previewing)
        if self._export_status:
            self._export_status.setText("Refreshing preview...")
            self._export_status.setVisible(previewing)
        if self._export_progress:
            self._export_progress.setVisible(previewing)
        if previewing:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _render_summary(self):
        while self._summary_strip.count():
            item = self._summary_strip.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        df = self._df
        n = len(df)
        site_count = df["Site Name"].nunique() if n and "Site Name" in df.columns else 0
        week_label_str = self._week_label or _infer_label_from_source(self._source_df)
        date_range_str = ""
        if week_label_str:
            try:
                s, e = _week_range_for_label(week_label_str)
                if s and e:
                    date_range_str = f"{_fmt_date_short(s)} – {_fmt_date_short(e)}"
            except Exception:
                date_range_str = ""
        for label, val, color in [
            ("Meet Rows", f"{n:,}", "#f38ba8"),
            ("Sites", f"{site_count:,}", "#a6e3a1"),
            ("Export Week", week_label_str or _not_available_str(), "#fab387"),
            ("Date Range", date_range_str or _not_available_str(), "#94e2d5"),
        ]:
            box = QFrame()
            box.setObjectName("tempMetricCard")
            box.setMinimumWidth(100)
            box.setMaximumWidth(146)
            box.setStyleSheet("QFrame#tempMetricCard { background:#181825; border-radius:8px; }")
            vb = QVBoxLayout(box)
            vb.setContentsMargins(10, 8, 10, 8)
            vb.setSpacing(4)
            lv = QLabel(val)
            lv.setAlignment(Qt.AlignCenter)
            lv.setWordWrap(True)
            lv.setFont(QFont("Segoe UI", 13, QFont.Bold))
            lv.setStyleSheet(f"color:{color};")
            lt = QLabel(label)
            lt.setAlignment(Qt.AlignCenter)
            lt.setWordWrap(True)
            lt.setStyleSheet("color:#a6adc8; font-size:10px;")
            vb.addWidget(lv)
            vb.addWidget(lt)
            self._summary_strip.addWidget(box)

    def _render_table(self):
        while self._table_host.count():
            item = self._table_host.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        df = self._df
        table_df = df.head(MAX_ANALYSIS_TABLE_ROWS)
        if len(df) > len(table_df):
            note = QLabel(
                f"Showing first {len(table_df):,} of {len(df):,} rows. Export includes all rows.")
            note.setStyleSheet("color:#fab387; font-size:11px;")
            self._table_host.addWidget(note)
        cols = [c for c in HT_MEET_HEADERS if c in table_df.columns]
        self._tbl = QTableWidget(len(table_df), len(cols))
        self._tbl.setUpdatesEnabled(False)
        self._tbl.setHorizontalHeaderLabels([HT_MEET_HEADERS[c] for c in cols])
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSortingEnabled(False)
        self._tbl.setWordWrap(False)
        self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._tbl.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._tbl.verticalHeader().setDefaultSectionSize(24)
        self._tbl.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        hdr = self._tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        for i, c in enumerate(cols):
            hdr.resizeSection(i, HT_MEET_WIDTHS.get(c, 120))
        hdr.setStretchLastSection(False)
        try:
            for r, row in enumerate(table_df.itertuples(index=False, name=None)):
                row_values = dict(zip(table_df.columns, row))
                for ci, c in enumerate(cols):
                    val = row_values.get(c, "")
                    item = QTableWidgetItem("" if pd.isna(val) else str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    if c == "Site Name":
                        item.setForeground(QColor("#cba6f7"))
                    elif c == "Alarm Source":
                        item.setForeground(QColor("#89b4fa"))
                    self._tbl.setItem(r, ci, item)
        finally:
            self._tbl.setSortingEnabled(True)
            self._tbl.setUpdatesEnabled(True)
        self._table_host.addWidget(self._tbl, 1)

    def _export(self):
        if self._export_thread and self._export_thread.isRunning():
            return
        if self._preview_thread and self._preview_thread.isRunning():
            self._export_after_preview_refresh = True
            return
        # Sync week label from input
        entered = self._week_input.text().strip()
        if entered:
            self._week_label = entered
        week_label = self._week_label or _infer_label_from_source(self._source_df)
        if week_label:
            try:
                ht_export_week_range(week_label)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Export Week", str(exc))
                return
        if self._preview_is_stale(self._week_label):
            self._export_after_preview_refresh = True
            self._apply_week_now(force=True)
            return
        default_name = (
            ht_export_filename(week_label)
            if week_label
            else f"ht_alarm_workbook_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        fp, _ = QFileDialog.getSaveFileName(
            self,
            "Export HT Alarm Workbook",
            default_name,
            "Excel Files (*.xlsx)",
        )
        if not fp:
            return
        self._set_exporting(True)
        self._export_thread = _TempAlarmExportThread(
            self._df,
            fp,
            self._preview_source_df,
            week_label if week_label else None,
            self._site_metadata_df,
            self,
        )
        self._export_thread.succeeded.connect(self._on_export_done)
        self._export_thread.failed.connect(self._on_export_failed)
        self._export_thread.finished.connect(self._on_export_thread_finished)
        self._export_thread.finished.connect(self._export_thread.deleteLater)
        self._export_thread.start()

    def _set_exporting(self, exporting: bool):
        if self._btn_export:
            self._btn_export.setEnabled(not exporting)
            self._btn_export.setText("Exporting..." if exporting else "Export XLSX")
        if hasattr(self, "_week_input") and self._week_input:
            self._week_input.setEnabled(not exporting)
        if self._export_status:
            self._export_status.setText("Exporting workbook...")
            self._export_status.setVisible(exporting)
        if self._export_progress:
            self._export_progress.setVisible(exporting)
        if exporting:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _on_export_done(self, fp: str):
        self._set_exporting(False)
        warning = ""
        if self._export_thread and getattr(self._export_thread, "warning_result", None):
            count = int(self._export_thread.warning_result.get("missing_metadata_count") or 0)
            if count:
                ids = self._export_thread.warning_result.get("missing_metadata_site_ids") or []
                suffix = f": {', '.join(ids[:10])}" if ids else ""
                if len(ids) > 10:
                    suffix += ", …"
                warning = f"\n\nWarning: {count} site(s) missing Site Metadata{suffix}. See workbook Missing Metadata sheet."
        QMessageBox.information(self, "Export OK", f"Saved to:\n{fp}{warning}")

    def _metadata_warning_text(self) -> str:
        if self._site_metadata_df is None or self._site_metadata_df.empty:
            return "Site Metadata Catalog not loaded. Export still works; enrichment fields may remain alarm-derived."
        if self._preview_missing_metadata_ids:
            ids = self._preview_missing_metadata_ids[:10]
            suffix = ", …" if len(self._preview_missing_metadata_ids) > 10 else ""
            return f"Missing Site Metadata for: {', '.join(ids)}{suffix}. Export still works and will include a Missing Metadata sheet."
        return ""

    def _on_export_failed(self, msg: str):
        self._set_exporting(False)
        QMessageBox.critical(self, "Export Failed", msg)

    def _on_export_thread_finished(self):
        self._export_thread = None

    def closeEvent(self, event):
        if self._preview_thread and self._preview_thread.isRunning():
            QMessageBox.information(
                self,
                "Preview Refresh in Progress",
                "Wait for the HT Meet preview refresh to finish before closing this window.",
            )
            event.ignore()
            return
        if self._export_thread and self._export_thread.isRunning():
            QMessageBox.information(
                self,
                "Export in Progress",
                "Wait for the HT Alarm Workbook export to finish before closing this window.",
            )
            event.ignore()
            return
        super().closeEvent(event)


def _infer_label_from_source(source_df: pd.DataFrame | None) -> str:
    if source_df is None or source_df.empty or "occurred_on" not in source_df.columns:
        return ""
    times = pd.to_datetime(source_df["occurred_on"], errors="coerce").dropna()
    if times.empty:
        return ""
    try:
        return ht_export_week_from_date(times.max())["week_label"]
    except Exception:
        return ""


def _build_temp_alarm_preview(
    source_df: pd.DataFrame | None,
    site_metadata_df: pd.DataFrame | None,
    filter_text: str,
    week_label: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    source = _filter_temp_alarm_source_for_metadata(source_df, site_metadata_df, filter_text)
    if source is None:
        source = pd.DataFrame()
    missing_ids: list[str] = []
    if site_metadata_df is not None and not site_metadata_df.empty:
        source, missing = enrich_source_with_site_metadata(source, site_metadata_df)
        missing_ids = _missing_site_ids(missing)
    _study, meet = compute_ht_meet_rows(source, week_label=week_label)
    return source, meet, missing_ids


def _filter_temp_alarm_source_for_metadata(
    source_df: pd.DataFrame | None,
    site_metadata_df: pd.DataFrame | None,
    filter_text: str,
) -> pd.DataFrame | None:
    text = str(filter_text or "").strip()
    if not text or source_df is None or source_df.empty:
        return source_df
    source = source_df.copy()
    mask = pd.Series(False, index=source.index)
    for column in ("site_id", "site_name", "site_code", "area", "contractor", "alarm_source"):
        if column in source.columns:
            mask |= source[column].fillna("").astype(str).str.contains(text, case=False, na=False, regex=False)
    if site_metadata_df is not None and not site_metadata_df.empty and "site_id" in source.columns:
        meta_mask = pd.Series(False, index=site_metadata_df.index)
        for column in site_metadata_df.columns:
            meta_mask |= site_metadata_df[column].fillna("").astype(str).str.contains(text, case=False, na=False, regex=False)
        site_ids = {_normalize_site_text(v) for v in site_metadata_df.loc[meta_mask, "site_id"].dropna()} if "site_id" in site_metadata_df.columns else set()
        source_ids = source["site_id"].map(_normalize_site_text)
        mask |= source_ids.isin(site_ids)
    return source[mask].copy().reset_index(drop=True)


def _normalize_site_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return "".join(ch for ch in str(value).strip().upper() if ch.isalnum())


def _missing_site_ids(missing: pd.DataFrame | None) -> list[str]:
    if missing is None or missing.empty or "Site ID" not in missing.columns:
        return []
    values = missing["Site ID"].dropna().astype(str).str.strip()
    return sorted({value for value in values if value})


def _week_range_for_label(week_label: str) -> tuple[str, str] | tuple[None, None]:
    """Return (start, end) date strings for a week label using ht_export_week_range."""
    if not week_label:
        return None, None
    try:
        start, end = ht_export_week_range(week_label)
        return str(start.date()), str(end.date())
    except Exception:
        return None, None


def _load_site_metadata_catalog() -> pd.DataFrame:
    try:
        from alarm_app.data import catalog_store
    except ImportError:
        try:
            from data import catalog_store
        except ImportError:
            return pd.DataFrame()
    try:
        return catalog_store.search_site_metadata(limit=None)
    except Exception:
        return pd.DataFrame()


def _not_available_str() -> str:
    return "—"


def _fmt_date_short(date_str: str) -> str:
    """Convert a YYYY-MM-DD string to MM/DD format."""
    try:
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[1]}/{parts[2]}"
    except Exception:
        pass
    return date_str
