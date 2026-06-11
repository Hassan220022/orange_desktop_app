"""
AlarmViewer — main window.
All UI construction and slot logic lives here.
"""

import getpass
import logging
import os
import re
import subprocess
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from PyQt5.QtCore import QDate, Qt, QThread
from PyQt5.QtGui import QColor, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from alarm_app.constants import (
        ALL_INTERNAL_COLS,
        APP_NAME,
        APP_VERSION,
        COL_WIDTHS,
        DISPLAY_COLUMNS,
    )
    from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
    from alarm_app.core.filters import compute_date_mask, parse_manual_days
    from alarm_app.core.temp_alarm import ht_export_week_from_date
    from alarm_app.data import alarm_store, state
    from alarm_app.data.catalog_import import import_bdt_summary_workbook, import_network_summary_db_sheet
    from alarm_app.data.loaders import discover_alarm_files
    from alarm_app.data.site_report import (
        build_site_alarm_report,
        collect_site_sheet_keys,
        read_site_sheet,
    )
    from alarm_app.data.sync import LocalSyncWorker
    from alarm_app.runtime.chatgpt_connector import ChatGPTConnectorManager
    from alarm_app.services.persistence.alarm_cache import (
        clear_alarm_caches,
        clear_all_caches,
        clear_bdt_caches,
    )
    from alarm_app.styles import STYLE_DARK, STYLE_LIGHT
    from alarm_app.ui.bridge import UIBridge
    from alarm_app.ui.dialogs import (
        AlarmIdConfigDialog,
        AppSettingsDialog,
        BackupTimeDialog,
        ColumnFilterPopup,
        DailyReviewReportDialog,
        FeatureFlagDialog,
        TempAlarmDialog,
    )
    from alarm_app.ui.filter_state import FilterState
    from alarm_app.ui.model import AlarmTableModel
    from alarm_app.ui.panels.bdt_detail_panel import BdtDetailPanel
    from alarm_app.ui.panels.bdt_validation_panel import BdtValidationPanel
    from alarm_app.ui.panels.bdt_workspace_panel import BdtWorkspacePanel
    from alarm_app.ui.panels.chat_panel import ChatPanel
    from alarm_app.ui.panels.left_panel import LeftPanel
    from alarm_app.ui.panels.search_panel import SearchPanel
    from alarm_app.ui.state_manager import StateManager
    from alarm_app.ui.threads import BackupTimeThread, ExportThread, LoaderThread, TempAlarmThread
except ImportError:
    from constants import (
        ALL_INTERNAL_COLS,
        APP_NAME,
        APP_VERSION,
        COL_WIDTHS,
        DISPLAY_COLUMNS,
    )
    from core.classify import classify_by_alarm_id, compute_site_down_flag
    from core.filters import compute_date_mask, parse_manual_days
    from core.temp_alarm import ht_export_week_from_date
    from data import alarm_store, state
    from data.catalog_import import import_bdt_summary_workbook, import_network_summary_db_sheet
    from data.loaders import discover_alarm_files
    from data.site_report import (
        build_site_alarm_report,
        collect_site_sheet_keys,
        read_site_sheet,
    )
    from data.sync import LocalSyncWorker
    from runtime.chatgpt_connector import ChatGPTConnectorManager
    from services.persistence.alarm_cache import (
        clear_alarm_caches,
        clear_all_caches,
        clear_bdt_caches,
    )
    from styles import STYLE_DARK, STYLE_LIGHT
    from ui.bridge import UIBridge
    from ui.dialogs import (
        AlarmIdConfigDialog,
        AppSettingsDialog,
        BackupTimeDialog,
        ColumnFilterPopup,
        DailyReviewReportDialog,
        FeatureFlagDialog,
        TempAlarmDialog,
    )
    from ui.filter_state import FilterState
    from ui.model import AlarmTableModel
    from ui.panels.bdt_detail_panel import BdtDetailPanel
    from ui.panels.bdt_validation_panel import BdtValidationPanel
    from ui.panels.bdt_workspace_panel import BdtWorkspacePanel
    from ui.panels.chat_panel import ChatPanel
    from ui.panels.left_panel import LeftPanel
    from ui.panels.search_panel import SearchPanel
    from ui.state_manager import StateManager
    from ui.threads import BackupTimeThread, ExportThread, LoaderThread, TempAlarmThread

_log = logging.getLogger(__name__)


def _format_count_label(start: int, end: int, total: int) -> str:
    if total <= 0:
        return ""
    range_text = (
        f"{start:,}" if start == end else f"{start:,}-{end:,}"
    )
    return f"Showing  {range_text}  of  {total:,} records"


def _local_mcp_base_url() -> str:
    host = os.environ.get("ALARM_BACKEND_HOST", "127.0.0.1")
    port = os.environ.get("ALARM_BACKEND_PORT", "8787")
    return f"http://{host}:{port}"


class AlarmViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_user = getpass.getuser() or "desktop"
        self._full_df    = pd.DataFrame()
        self._page_size = 500
        self._page_offset = 0
        self._page_total_rows = 0
        self._alarm_table_columns: list[str] = []
        self._alarm_query_active = False
        self._file_infos: list[dict] = []
        self._loader     = None
        self._col_filters: dict[str, set | None] = {}  # col -> selected values
        self._both_pd_active = False  # "Both P+D" filter flag
        self._uploaded_site_df: pd.DataFrame | None = None
        self._uploaded_site_sheet_name = ""
        self._uploaded_site_id_column = ""
        self._uploaded_site_keys: set[str] = set()
        self._uploaded_site_path = ""
        self._uploaded_folder_path = ""
        self._bdt_uploaded_folder_path = ""
        self._bdt_file_infos: list[dict] = []
        self._bdt_results: list = []
        self._bdt_by_site: dict = {}
        self._last_bdt_health_pct: float | None = None
        self._reviewed_bdt_keys: set = set()
        self._sync_flags = state.load_feature_flags()
        self._sync_worker: LocalSyncWorker | None = None
        app = QApplication.instance()
        self._base_app_font = QFont(app.font()) if app else QFont()
        self._base_app_font_size = self._base_app_font.pointSizeF()
        self._app_zoom_pct = 100
        self._zoom_min_pct = 70
        self._zoom_max_pct = 170
        self._zoom_shortcuts: list[QShortcut] = []
        self._font_size_px_re = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)px", re.IGNORECASE)
        self._theme_mode = "auto"  # will be overridden by state restore
        self._skip_photos = False  # skip photo extraction toggle state
        self._openrouter_api_key = ""
        self._chatgpt_mcp_enabled = False
        self._chatgpt_mcp_public_url = ""
        self._chatgpt_mcp_token = ""
        self._chatgpt_connector_manager = ChatGPTConnectorManager(local_base_url=_local_mcp_base_url())
        self._build_ui()
        self._setup_zoom_shortcuts()
        self.setStyleSheet(self._resolve_theme_style())
        self._restore_ui_state()
        self._restore_bdt_results()  # always try to restore BDT from DB
        self._start_sync_worker_if_enabled()
        self._run_bootstrap_if_enabled()

    # ── UI construction ──────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        screen_w = avail.width() if avail else 1680
        screen_h = avail.height() if avail else 980
        min_w = min(1024, max(860, int(screen_w * 0.68)))
        min_h = min(720, max(620, int(screen_h * 0.68)))
        start_w = min(1680, max(min_w, int(screen_w * 0.96)))
        start_h = min(980, max(min_h, int(screen_h * 0.92)))
        self.setMinimumSize(min_w, min_h)
        self.resize(start_w, start_h)

        root = QWidget(); self.setCentralWidget(root)
        root.setObjectName("root")
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._workspace_defs = (
            {"label": "Alarms", "nav": "Alarms"},
            {"label": "Battery Discharge Tests", "nav": "BDT"},
        )

        self._activity_bar = self._make_activity_bar()
        main.addWidget(self._activity_bar)

        # Horizontal splitter: sidebar | content
        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.setHandleWidth(8)
        self._main_splitter.setStyleSheet(
            "QSplitter::handle { background:#1e1e2e; } "
            "QSplitter::handle:horizontal { width: 8px; }")

        # Left sidebar
        self._left_panel = LeftPanel(self)
        self._sidebar_stack = QStackedWidget()
        self._sidebar_stack.addWidget(self._left_panel)
        self._sidebar = self._sidebar_stack
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setMinimumWidth(50)
        self._sidebar.setMaximumWidth(16777215)
        self._main_splitter.addWidget(self._sidebar)
        self._sidebar_width = 260  # remembered width for toggle

        # Right content area
        right_wrap = QWidget()
        right_wrap.setObjectName("right_wrap")
        right_wrap.setMinimumWidth(0)
        right_wrap.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        rl = QVBoxLayout(right_wrap)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Thin top header strip
        header = self._make_header_strip()
        header.setObjectName("header")
        rl.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setObjectName("main_tabs")
        self._tabs.setMinimumWidth(0)
        self._tabs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._tabs.tabBar().hide()
        self._tabs.currentChanged.connect(self._on_workspace_changed)

        # Tab 1: Alarms (existing content)
        alarms_tab = QWidget()
        al = QVBoxLayout(alarms_tab)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        self._search_panel = SearchPanel(self)
        self._stats = self._left_panel.stats
        splitter.addWidget(self._search_panel)
        splitter.addWidget(self._make_table())
        splitter.setSizes([130, 800])
        al.addWidget(splitter, 1)
        self._tabs.addTab(alarms_tab, "Alarms")

        # Tab 2: Test Validation
        self._bdt_validation_panel = BdtValidationPanel(self)
        # Wire the detail panel into the validation tab splitter
        self._bdt_detail_panel_obj = BdtDetailPanel(self)
        self._bdt_detail_panel = self._bdt_detail_panel_obj
        self._bdt_validation_panel.set_detail_panel(self._bdt_detail_panel)
        self._bdt_validation_panel.row_selected.connect(self._bdt_detail_panel_obj.populate)
        self._tabs.addTab(self._bdt_validation_panel, "Test Validation")
        self._bdt_sidebar = BdtWorkspacePanel(self)
        self._sidebar_stack.addWidget(self._bdt_sidebar)
        self._ui = UIBridge.from_panels(self._left_panel, self._search_panel, self._bdt_sidebar)
        self._toggle_date_filter(self._search_panel.chk_date.isChecked())

        # Embedded assistant panel (Copilot-like, not a separate workspace tab)
        self._chat_panel = ChatPanel(self)
        self._assistant_width = 320
        self._assistant_open = True
        self._content_splitter = QSplitter(Qt.Horizontal)
        self._content_splitter.setHandleWidth(6)
        self._content_splitter.addWidget(self._tabs)
        self._content_splitter.addWidget(self._chat_panel)
        self._content_splitter.setStretchFactor(0, 1)
        self._content_splitter.setStretchFactor(1, 0)
        self._content_splitter.setCollapsible(0, False)
        self._content_splitter.setCollapsible(1, True)
        self._content_splitter.setSizes([1240, self._assistant_width])
        self._content_splitter.splitterMoved.connect(self._on_content_splitter_moved)

        rl.addWidget(self._content_splitter, 1)

        self._main_splitter.addWidget(right_wrap)
        self._main_splitter.setSizes([260, 1420])
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setCollapsible(0, True)
        self._main_splitter.setCollapsible(1, True)
        self._main_splitter.splitterMoved.connect(self._on_main_splitter_moved)
        self._apply_sidebar_constraints()
        self._apply_assistant_constraints()

        main.addWidget(self._main_splitter, 1)
        self._set_workspace_view(0, persist=False)

        # Status bar
        self._sbar = QStatusBar()
        self.setStatusBar(self._sbar)
        self._sbar.showMessage(
            "Browse to a directory, then scan for alarm files.")

        self._prog = QProgressBar()
        self._prog.setRange(0, 100)
        self._prog.setTextVisible(False)
        self._prog.setFixedSize(320, 12)
        self._prog.setVisible(False)
        self._sbar.addPermanentWidget(self._prog)

    # ── top header strip ─────────────────────────────────────────
    @staticmethod
    def _mark_compact_button(button: QPushButton, *, min_h: int = 30):
        button.setProperty("compact", True)
        button.setMinimumWidth(0)
        button.setMinimumHeight(max(min_h, button.fontMetrics().height() + 10))
        button.setMaximumHeight(16777215)
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    def _make_header_strip(self):
        w = QWidget()
        w.setFixedHeight(50)
        l = QHBoxLayout(w)
        l.setContentsMargins(14, 0, 14, 0)
        l.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(
            "color:#89b4fa; font-size:14px; background:transparent;")
        l.addWidget(dot)

        self._lbl_workspace = QLabel(self._workspace_defs[0]["label"])
        self._lbl_workspace.setObjectName("lbl_app_name")
        l.addWidget(self._lbl_workspace)

        self._lbl_count = QLabel("")
        self._lbl_count.setObjectName("lbl_dim")
        l.addWidget(self._lbl_count)

        self._btn_daily_report = QPushButton("Daily Report")
        self._btn_daily_report.setObjectName("btn_dir")
        self._mark_compact_button(self._btn_daily_report)
        self._btn_daily_report.setProperty("full_text", "Daily Report")
        self._btn_daily_report.setProperty("short_text", "Report")
        self._btn_daily_report.clicked.connect(
            lambda: DailyReviewReportDialog(self).exec_())
        l.addWidget(self._btn_daily_report)

        l.addStretch(1)

        btn_config = QPushButton("Configure Alarm IDs")
        btn_config.setObjectName("btn_dir")
        self._mark_compact_button(btn_config)
        btn_config.setProperty("full_text", "Configure Alarm IDs")
        btn_config.setProperty("short_text", "Alarm IDs")
        btn_config.clicked.connect(self._show_alarm_id_config)
        self._btn_config_alarm_ids = btn_config
        l.addWidget(btn_config)

        self._btn_settings = QPushButton("Settings")
        self._btn_settings.setObjectName("btn_dir")
        self._mark_compact_button(self._btn_settings)
        self._btn_settings.setProperty("full_text", "Settings")
        self._btn_settings.setProperty("short_text", "Settings")
        self._btn_settings.clicked.connect(self._show_settings)
        l.addWidget(self._btn_settings)

        self._refresh_header_button_texts()
        return w

    def _make_activity_bar(self):
        w = QWidget()
        w.setObjectName("activity_bar")
        w.setFixedWidth(72)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 12)
        lay.setSpacing(10)

        # brand = QLabel("OR")
        # brand.setObjectName("activity_brand")
        # brand.setAlignment(Qt.AlignCenter)
        # lay.addWidget(brand)

        self._workspace_buttons = []
        for index, workspace in enumerate(self._workspace_defs):
            btn = QPushButton(workspace["nav"])
            btn.setObjectName("activity_btn")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(workspace["label"])
            btn.setFixedHeight(72)
            btn.clicked.connect(lambda _checked=False, idx=index: self._set_workspace_view(idx))
            lay.addWidget(btn)
            self._workspace_buttons.append(btn)

        lay.addStretch()
        return w

    def _set_workspace_view(self, index: int, persist: bool = True):
        target = max(0, min(index, len(self._workspace_defs) - 1))
        if self._tabs.currentIndex() != target:
            self._tabs.setCurrentIndex(target)
        self._apply_workspace_state(target)
        if persist:
            self._save_ui_state()

    def _apply_workspace_state(self, index: int):
        is_bdt = index == 1
        if hasattr(self, "_sidebar_stack"):
            self._sidebar_stack.setCurrentIndex(index)
        if hasattr(self, "_lbl_workspace"):
            self._lbl_workspace.setText(self._workspace_defs[index]["label"])
            self._lbl_workspace.setVisible(True)
        if hasattr(self, "_btn_daily_report"):
            self._btn_daily_report.setVisible(not is_bdt)
        for btn_index, btn in enumerate(getattr(self, "_workspace_buttons", [])):
            btn.setChecked(btn_index == index)
        if is_bdt and hasattr(self, "_bdt_sidebar"):
            self._bdt_sidebar._sync_skip_photos_from_viewer()

    def _on_workspace_changed(self, index: int):
        if 0 <= index < len(self._workspace_defs):
            self._apply_workspace_state(index)

    def _use_short_header_labels(self) -> bool:
        return self.width() < 1760

    def _refresh_header_button_texts(self):
        short = self._use_short_header_labels()
        for attr in ("_btn_daily_report", "_btn_config_alarm_ids", "_btn_settings"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setText(str(btn.property("short_text" if short else "full_text") or btn.text()))

    def _refresh_compact_buttons(self):
        for button in self.findChildren(QPushButton):
            if button.property("compact"):
                button.setMinimumHeight(max(26, button.fontMetrics().height() + 10))
                button.setMaximumHeight(16777215)
                button.setMinimumWidth(0)
                button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    # ── table ────────────────────────────────────────────────────
    def _make_table(self):
        w = QWidget(); vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(6)

        self._model = AlarmTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSortingEnabled(False)  # we handle sorting via popup
        self._table.setWordWrap(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setSectionResizeMode(
            QHeaderView.Fixed)
        hdr = self._table.horizontalHeader()
        hdr.setSortIndicatorShown(True)
        hdr.setHighlightSections(False)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._on_header_clicked)

        # Right-click context menu
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(
            self._table_context_menu)

        # Double-click copies cell value
        self._table.doubleClicked.connect(self._copy_cell)

        vl.addWidget(self._table)

        pager = QWidget()
        pl = QHBoxLayout(pager)
        pl.setContentsMargins(8, 0, 8, 0)
        pl.setSpacing(8)
        self._btn_prev_page = QPushButton("Prev")
        self._mark_compact_button(self._btn_prev_page, min_h=28)
        self._btn_prev_page.clicked.connect(self._load_previous_alarm_page)
        self._btn_next_page = QPushButton("Next")
        self._mark_compact_button(self._btn_next_page, min_h=28)
        self._btn_next_page.clicked.connect(self._load_next_alarm_page)
        self._lbl_page = QLabel("Page 0/0")
        self._lbl_page.setObjectName("lbl_dim")
        self._lbl_page_range = QLabel("Rows 0-0 of 0")
        self._lbl_page_range.setObjectName("lbl_dim")
        pl.addWidget(self._btn_prev_page)
        pl.addWidget(self._btn_next_page)
        pl.addWidget(self._lbl_page)
        pl.addWidget(self._lbl_page_range)
        pl.addStretch()
        vl.addWidget(pager)
        self._update_pagination_controls()
        return w

    # ── table copy support ───────────────────────────────────────
    def _table_context_menu(self, pos):
        """Right-click menu with Copy Cell / Copy Row."""
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self._table)
        act_cell = QAction("Copy Cell", menu)
        act_cell.setShortcut(QKeySequence.Copy)
        act_cell.triggered.connect(
            lambda: self._copy_cell(index))
        menu.addAction(act_cell)

        act_row = QAction("Copy Row", menu)
        act_row.triggered.connect(
            lambda: self._copy_row(index))
        menu.addAction(act_row)

        menu.exec_(self._table.viewport().mapToGlobal(pos))

    def _copy_cell(self, index):
        """Copy the value of the clicked cell to clipboard."""
        if not index.isValid():
            return
        val = self._model.data(index, Qt.DisplayRole)
        if val:
            QApplication.clipboard().setText(str(val))
            self._sbar.showMessage(
                f"Copied: {str(val)[:80]}", 2000)

    def _copy_row(self, index):
        """Copy all cell values of the row as tab-separated text."""
        if not index.isValid():
            return
        row = index.row()
        ncols = self._model.columnCount()
        parts = []
        for c in range(ncols):
            idx = self._model.index(row, c)
            v = self._model.data(idx, Qt.DisplayRole)
            parts.append(str(v) if v else "")
        QApplication.clipboard().setText("\t".join(parts))
        self._sbar.showMessage("Row copied to clipboard", 2000)

    # ── State persistence ────────────────────────────────────────
    def _save_ui_state(self):
        """Collect all widget values and save to state.json."""
        d = StateManager.collect(self)
        state.save_state(d)

    def _restore_ui_state(self):
        """Restore UI settings from state.json and kick off cache load."""
        s = state.load_state()
        if s is None:
            self._sync_flags = state.load_feature_flags({})
            return
        self._sync_flags = state.load_feature_flags(s)
        StateManager.apply(self, s)

        # Stash file_paths for reference
        self._restored_file_paths = s.get("file_paths", [])

        if self._has_query_backed_alarm_data():
            self._sbar.showMessage("Restoring cached alarms...")
            sort_col = getattr(self, "_pending_sort_col", None)
            if sort_col is not None and sort_col >= 0:
                order = (
                    Qt.AscendingOrder
                    if getattr(self, "_pending_sort_order", 0) == 0
                    else Qt.DescendingOrder
                )
                self._table.horizontalHeader().setSortIndicator(sort_col, order)
            if self._load_alarm_page(
                offset=self._page_offset,
                status_message="Session restored from local alarm cache",
            ) and self._current_alarm_total() > 0:
                restored_paths = list(getattr(self, "_restored_file_paths", []) or [])
                self._file_infos = [
                    {"path": p, "filename": os.path.basename(p)}
                    for p in restored_paths
                ]
                total = self._current_alarm_total()
                self._ui.lbl_loaded.setText(f"✓  {total:,} cached records")
                self._ui.lbl_loaded.setStyleSheet("color:#a6e3a1; font-size:11px;")
            else:
                df = self._load_alarm_dataframe_from_db()
                if df is not None and not df.empty:
                    self._apply_loaded_alarm_dataframe(
                        df,
                        f"Recovered {len(df):,} alarm records from local DB fallback",
                    )

    def _on_cache_restored(self, df):
        """Called when background local-cache restore completes."""
        if df is None or df.empty or "site_id" not in df.columns:
            self._sbar.showMessage("No cached alarm data found")
            return

        # Ensure datetime columns are proper dtype
        for col in ("occurred_on", "cleared_on"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")

        # Rebuild file_infos from restored paths so close-save works
        restored_paths = list(getattr(self, "_restored_file_paths", []) or [])
        self._file_infos = [
            {"path": p, "filename": os.path.basename(p)}
            for p in restored_paths
        ]

        self._ui.lbl_loaded.setText(f"✓  {len(df):,} records (restored)")
        self._ui.lbl_loaded.setStyleSheet("color:#a6e3a1; font-size:11px;")
        self._reset_date_range(df)

        # Restore sort indicator
        sort_col = getattr(self, "_pending_sort_col", None)
        if sort_col is not None and sort_col >= 0:
            order = (Qt.AscendingOrder if getattr(self, "_pending_sort_order", 0) == 0
                     else Qt.DescendingOrder)
            self._table.horizontalHeader().setSortIndicator(sort_col, order)

        if self._has_query_backed_alarm_data():
            self._page_offset = 0
            self._load_alarm_page(
                offset=0,
                status_message=f"Session restored — {self._current_alarm_total():,} records",
            )

        # Populate sidebar file list so it's not blank after restore
        directory = self._ui.edit_dir.text().strip()
        if directory and os.path.isdir(directory):
            self._scan()

        # Restore BDT validation results from DB
        self._restore_bdt_results()

    def _restore_bdt_results(self):
        """Load previous BDT validation results from the DB into the UI."""
        try:
            results = self._load_bdt_results_from_db()
            if not results:
                return

            self._apply_bdt_results(
                results,
                status_message=(
                    f"Session restored — {self._current_alarm_total():,} alarms, "
                    f"{len(results)} BDT validations"
                ),
            )
        except Exception:
            _log.warning("BDT restore from DB failed", exc_info=True)

    def _start_sync_worker_if_enabled(self):
        should_run = (
            self._sync_flags.get("sync_on", False)
            or self._sync_flags.get("bootstrap_on", False)
        )
        if not should_run or self._sync_worker is not None:
            return
        try:
            sender = None
            if self._sync_flags.get("sync_on", False):
                try:
                    try:
                        from alarm_app.data.sync_client import http_send_batch
                    except ImportError:
                        from data.sync_client import http_send_batch
                    sender = http_send_batch
                except Exception:
                    _log.warning("HTTP sync client import failed, sync disabled", exc_info=True)
                    pass
            self._sync_worker = LocalSyncWorker(send_batch=sender)
            self._sync_worker.start()
        except Exception:
            _log.warning("Sync worker failed to start", exc_info=True)
            self._sync_worker = None

    def _run_bootstrap_if_enabled(self):
        if not self._sync_flags.get("bootstrap_on"):
            return

        class _BootstrapThread(QThread):
            def run(self_thread):
                try:
                    try:
                        from alarm_app.data.bootstrap import run_bootstrap
                    except ImportError:
                        from data.bootstrap import run_bootstrap
                    try:
                        from alarm_app.db.engine import (
                            create_engine,
                            get_session_factory,
                            init_db,
                        )
                    except ImportError:
                        from db.engine import (
                            create_engine,
                            get_session_factory,
                            init_db,
                        )

                    engine = create_engine()
                    init_db(engine, include_alarm_records=False)
                    SessionCls = get_session_factory(engine)
                    session = SessionCls()
                    try:
                        counts = run_bootstrap(session)
                        total = sum(counts.values())
                        if total > 0:
                            print(
                                f"Bootstrap backfill queued {total} events: {counts}"
                            )
                    finally:
                        session.close()
                except Exception as exc:
                    print(f"Bootstrap error: {exc}")

        self._bootstrap_thread = _BootstrapThread(self)
        self._bootstrap_thread.start()

    def _stop_sync_worker(self):
        worker = self._sync_worker
        self._sync_worker = None
        if worker is None:
            return
        try:
            worker.stop(timeout=2.0)
        except Exception:
            _log.debug("Sync worker stop timed out during toggle", exc_info=True)

    def _toggle_sync(self):
        """Toggle sync_on feature flag and restart or stop the worker."""
        s = state.load_state() or {}
        current = self._sync_flags.get("sync_on", False)
        s["sync_on"] = not current
        state.save_state(s)
        self._sync_flags["sync_on"] = not current

        if not current:
            self._start_sync_worker_if_enabled()
        else:
            self._stop_sync_worker()

    def _close_dialog_colors(self):
        """Return color dict for the close dialog based on current theme."""
        mode = self._theme_mode
        if mode == "auto":
            mode = self._detect_os_theme()
        if mode == "dark":
            return {
                "bg": "#1a1a2a", "border": "#2a2a3e", "text": "#cdd6f4",
                "muted": "#6c7086", "warn": "#fab387", "blue": "#89b4fa",
                "green": "#a6e3a1", "red": "#f38ba8",
                "stay_bg": "#1a2744", "stay_border": "#2a4070", "stay_hover": "#1f3258",
                "exit_bg": "#3d1e2c", "exit_border": "#5a2030", "exit_hover": "#4d2838",
            }
        return {
            "bg": "#e6e9ef", "border": "#ccd0da", "text": "#4c4f69",
            "muted": "#6c6f85", "warn": "#fe640b", "blue": "#1e66f5",
            "green": "#40a02b", "red": "#d20f39",
            "stay_bg": "#d5e0fc", "stay_border": "#a8bff8", "stay_hover": "#c0d0fa",
            "exit_bg": "#f5d5da", "exit_border": "#e8a0b0", "exit_hover": "#f0c0c8",
        }

    def _iter_background_threads(self):
        panel_bdt_thread = getattr(self._bdt_validation_panel, "_bdt_thread", None)
        panel_photo_thread = None
        if panel_bdt_thread is not None:
            panel_photo_thread = getattr(panel_bdt_thread, "_photo_thread", None)
        for thread in (
            getattr(self, "_loader", None),
            getattr(self, "_restore_thread", None),
            getattr(self, "_bt_thread", None),
            panel_bdt_thread,
            panel_photo_thread,
        ):
            if thread is not None:
                yield thread

    def _wait_for_background_threads(self, timeout_ms: int = 30000) -> bool:
        all_finished = True
        for thread in self._iter_background_threads():
            try:
                if thread.isRunning():
                    self._sbar.showMessage("Waiting for background tasks to finish…")
                    if not thread.wait(timeout_ms):
                        all_finished = False
            except Exception:
                pass
        return all_finished

    def closeEvent(self, event):
        """Always warn before closing."""
        c = self._close_dialog_colors()
        dlg = QDialog(self, Qt.FramelessWindowHint)
        dlg.setFixedWidth(380)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {c['bg']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)

        # Icon + title row
        title_row = QHBoxLayout()
        icon = QLabel("\u26a0")
        icon.setStyleSheet(
            f"font-size:28px; background:transparent; color:{c['warn']};")
        title_row.addWidget(icon)
        title_row.addSpacing(8)
        title = QLabel("Close Alarm Viewer?")
        title.setStyleSheet(
            f"color:{c['text']}; font-size:16px; font-weight:700;"
            "background:transparent;")
        title_row.addWidget(title)
        title_row.addStretch()
        lay.addLayout(title_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{c['border']};")
        lay.addWidget(sep)

        total_alarm_rows = self._current_alarm_total()
        summary = alarm_store.stats() if total_alarm_rows > 0 else {}

        # Message adapts to whether data is loaded
        if total_alarm_rows > 0:
            n_rec = total_alarm_rows
            n_sites = int(summary.get("sites", 0) or 0)
            n_files = len(self._file_infos)
            msg = (
                f"<span style='color:{c['muted']};'>"
                f"You currently have locally cached alarm data:</span><br><br>"
                f"<span style='color:{c['blue']};'>{n_rec:,}</span>"
                f"<span style='color:{c['muted']};'> records</span>"
                f"&nbsp;&nbsp;&middot;&nbsp;&nbsp;"
                f"<span style='color:{c['green']};'>{n_sites:,}</span>"
                f"<span style='color:{c['muted']};'> sites</span>"
                f"&nbsp;&nbsp;&middot;&nbsp;&nbsp;"
                f"<span style='color:{c['warn']};'>{n_files}</span>"
                f"<span style='color:{c['muted']};'> files</span><br><br>"
                f"<span style='color:{c['green']};'>"
                f"Your session will be saved and restored next time.</span>")
        else:
            msg = (f"<span style='color:{c['muted']};'>"
                   "Are you sure you want to exit?</span>")

        info = QLabel(msg)
        info.setStyleSheet(
            f"color:{c['text']}; font-size:13px; background:transparent;"
            "line-height:1.5;")
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addSpacing(8)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_cancel = QPushButton("Stay")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {c['stay_bg']}; color: {c['blue']};
                border: 1px solid {c['stay_border']}; border-radius: 6px;
                padding: 8px 24px; font-size: 13px; font-weight: 600;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: {c['stay_hover']}; border-color: {c['blue']};
            }}
        """)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)

        btn_exit = QPushButton("Exit")
        btn_exit.setStyleSheet(f"""
            QPushButton {{
                background: {c['exit_bg']}; color: {c['red']};
                border: 1px solid {c['exit_border']}; border-radius: 6px;
                padding: 8px 24px; font-size: 13px; font-weight: 600;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: {c['exit_hover']}; border-color: {c['red']};
            }}
        """)
        btn_exit.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_exit)

        lay.addLayout(btn_row)

        if dlg.exec_() != QDialog.Accepted:
            event.ignore()
            return

        self._stop_sync_worker()
        self._stop_chatgpt_connector_if_enabled()
        if not self._wait_for_background_threads():
            event.ignore()
            QMessageBox.information(
                self,
                "Background Save In Progress",
                "The app is still saving data to the local DB.\n"
                "Wait a little longer, then close it again.",
            )
            return

        # Save session state before closing
        try:
            self._save_ui_state()
        except Exception as e:
            print(f"[AlarmViewer] save error: {e}")

        event.accept()

    def _stop_chatgpt_connector_if_enabled(self):
        if not getattr(self, "_chatgpt_mcp_enabled", False):
            return
        try:
            status = self._chatgpt_connector_manager.disable()
            self._chatgpt_mcp_enabled = False
            self._chatgpt_mcp_public_url = status.public_url
            self._chatgpt_mcp_token = ""
        except Exception as exc:
            _log.warning("Failed to stop ChatGPT MCP connector: %s", exc)

    def keyPressEvent(self, event):
        """Keyboard shortcuts: sidebar/copy + app zoom."""
        mods = event.modifiers()
        has_primary = bool(mods & (Qt.ControlModifier | Qt.MetaModifier))
        has_alt = bool(mods & Qt.AltModifier)
        txt = event.text() or ""

        if has_primary and not has_alt and (
            event.key() in (Qt.Key_Minus, Qt.Key_Underscore) or txt in ("-", "_", "−")
        ):
            self._zoom_out()
            return
        if has_primary and not has_alt and (
            event.key() in (Qt.Key_Plus, Qt.Key_Equal) or txt in ("+", "=")
        ):
            self._zoom_in()
            return
        if has_primary and not has_alt and event.key() == Qt.Key_0:
            self._zoom_reset()
            return

        if has_primary and not has_alt and event.key() == Qt.Key_B:
            self._toggle_sidebar()
            return
        if has_primary and not has_alt and bool(mods & Qt.ShiftModifier) and event.key() == Qt.Key_L:
            self._toggle_assistant_panel()
            return
        if has_primary and not has_alt and event.key() == Qt.Key_C:
            indexes = self._table.selectionModel().selectedIndexes()
            if indexes:
                # Group by row, join with tab; rows separated by newline
                from collections import defaultdict
                rows_d: dict[int, list] = defaultdict(list)
                for idx in sorted(indexes,
                                  key=lambda i: (i.row(), i.column())):
                    v = self._model.data(idx, Qt.DisplayRole)
                    rows_d[idx.row()].append(str(v) if v else "")
                text = "\n".join(
                    "\t".join(cells) for cells in rows_d.values())
                QApplication.clipboard().setText(text)
                n = len(rows_d)
                self._sbar.showMessage(
                    f"Copied {n} row{'s' if n != 1 else ''}"
                    " to clipboard", 2000)
                return
        super().keyPressEvent(event)

    # ── helpers ──────────────────────────────────────────────────
    @staticmethod
    def _vline():
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setObjectName("vline")
        return f

    def _apply_col_widths(self, cols: list[str]):
        hdr = self._table.horizontalHeader()
        for i, col in enumerate(cols):
            if col in COL_WIDTHS:
                hdr.resizeSection(i, COL_WIDTHS[col])
            else:
                self._table.resizeColumnToContents(i)

    def _current_alarm_total(self) -> int:
        if self._alarm_query_active:
            return self._page_total_rows
        if not self._full_df.empty:
            return len(self._full_df)
        return 0

    def _has_query_backed_alarm_data(self) -> bool:
        return state.has_alarm_cache()

    def _current_alarm_columns(self) -> list[str]:
        cols = []
        if hasattr(self, "_model"):
            cols = self._model.columns()
        if cols:
            return cols
        if self._alarm_table_columns:
            return list(self._alarm_table_columns)
        return list(ALL_INTERNAL_COLS)

    def _update_pagination_controls(self):
        total = max(int(getattr(self, "_page_total_rows", 0) or 0), 0)
        page_size = max(int(getattr(self, "_page_size", 1) or 1), 1)
        offset = max(int(getattr(self, "_page_offset", 0) or 0), 0)
        if total <= 0:
            start = 0
            end = 0
            page_no = 0
            total_pages = 0
        else:
            start = offset + 1
            end = min(offset + self._model.rowCount(), total)
            page_no = (offset // page_size) + 1
            total_pages = ((total - 1) // page_size) + 1
        self._lbl_page.setText(f"Page {page_no}/{total_pages}")
        self._lbl_page_range.setText(f"Rows {start:,}-{end:,} of {total:,}")
        lbl_count = getattr(self, "_lbl_count", None)
        if lbl_count is not None:
            lbl_count.setText(_format_count_label(start, end, total))
        self._btn_prev_page.setEnabled(offset > 0)
        self._btn_next_page.setEnabled(total > 0 and offset + self._model.rowCount() < total)

    def _set_combo_values(self, combo: QComboBox, values: list[str], current_text: str):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All")
        seen = set()
        for value in values:
            text = str(value)
            if text in seen or text == "":
                continue
            combo.addItem(text)
            seen.add(text)
        target = current_text if current_text and current_text != "All" else "All"
        idx = combo.findText(target)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _build_alarm_query(
        self,
        *,
        limit: int | None,
        offset: int,
        exclude_columns: set[str] | None = None,
        ignore_sort: bool = False,
    ) -> alarm_store.AlarmQuery:
        exclude_columns = exclude_columns or set()
        fs = FilterState.from_viewer(self)

        if fs.invalid_manual_days:
            self._sbar.showMessage(
                "Ignored invalid day value(s) in specific days filter",
                2500,
            )

        query = fs.to_alarm_query()

        if "alarm_category" in exclude_columns:
            query = replace(query, category="All")
        if "vendor" in exclude_columns:
            query = replace(query, vendor="All")
        if "network_type" in exclude_columns:
            query = replace(query, network_type="All")

        if exclude_columns:
            query = replace(query, col_filters={
                col: allowed
                for col, allowed in self._col_filters.items()
                if col not in exclude_columns
            })

        if ignore_sort:
            query = replace(query, sort_by=None, sort_desc=False)

        return replace(query, limit=limit, offset=offset)

    @staticmethod
    def _expand_backup_time_query(query: alarm_store.AlarmQuery) -> alarm_store.AlarmQuery:
        """Widen the query window so cross-midnight alarm pairs are not dropped."""
        expanded = replace(query, limit=None, offset=0, sort_by=None, sort_desc=False)

        if expanded.date_from is not None:
            expanded = replace(
                expanded,
                date_from=expanded.date_from - timedelta(days=1),
            )
        if expanded.date_to is not None:
            expanded = replace(
                expanded,
                date_to=expanded.date_to + timedelta(days=1),
            )

        manual_days = list(expanded.manual_days or [])
        if manual_days:
            parsed_days = [pd.Timestamp(day).date() for day in manual_days if not pd.isna(pd.Timestamp(day))]
            if parsed_days:
                start_day = min(parsed_days) - timedelta(days=1)
                end_day = max(parsed_days) + timedelta(days=1)
                expanded = replace(
                    expanded,
                    manual_days=[start_day + timedelta(days=offset) for offset in range((end_day - start_day).days + 1)],
                )
        return expanded

    @staticmethod
    def _expand_temp_alarm_query(query: alarm_store.AlarmQuery) -> alarm_store.AlarmQuery:
        """Widen temp query so Power and Temp correlation can cross filter edges."""
        expanded = AlarmViewer._expand_backup_time_query(query)
        if expanded.date_to is not None:
            expanded = replace(expanded, date_to=expanded.date_to + timedelta(hours=1))
        return expanded

    @staticmethod
    def _build_temp_alarm_source_query(query: alarm_store.AlarmQuery) -> alarm_store.AlarmQuery:
        """Build source rows for HT Meet without dropping user date/duration scope."""
        return replace(query, limit=None, offset=0, sort_by=None, sort_desc=False)

    def _refresh_alarm_stats(self, query: alarm_store.AlarmQuery | None = None):
        summary = alarm_store.stats(query or self._build_alarm_query(limit=None, offset=0, ignore_sort=True))
        self._stats["total"].setText(f"{int(summary.get('total', 0)):,}")
        self._stats["power"].setText(f"{int(summary.get('power', 0)):,}")
        self._stats["down"].setText(f"{int(summary.get('down', 0)):,}")
        self._stats["door"].setText(f"{int(summary.get('door', 0)):,}")
        if "temp" in self._stats and self._stats["temp"] is not None:
            self._stats["temp"].setText(f"{int(summary.get('temp', 0)):,}")
        self._stats["sites"].setText(f"{int(summary.get('sites', 0)):,}")
        avg_s = float(summary.get("avg_duration_secs", 0.0) or 0.0)
        if avg_s > 0:
            h = int(avg_s // 3600)
            m = int((avg_s % 3600) // 60)
            s = int(avg_s % 60)
            self._stats["avg_dur"].setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self._stats["avg_dur"].setText("—")

    def _refresh_alarm_facets(self):
        if not self._has_query_backed_alarm_data():
            return
        self._set_combo_values(
            self._ui.cb_cat,
            alarm_store.distinct_values(
                "alarm_category",
                self._build_alarm_query(limit=None, offset=0, exclude_columns={"alarm_category"}, ignore_sort=True),
            ),
            self._ui.cb_cat.currentText(),
        )
        self._set_combo_values(
            self._ui.cb_net,
            alarm_store.distinct_values(
                "network_type",
                self._build_alarm_query(limit=None, offset=0, exclude_columns={"network_type"}, ignore_sort=True),
            ),
            self._ui.cb_net.currentText(),
        )
        self._set_combo_values(
            self._ui.cb_vnd,
            alarm_store.distinct_values(
                "vendor",
                self._build_alarm_query(limit=None, offset=0, exclude_columns={"vendor"}, ignore_sort=True),
            ),
            self._ui.cb_vnd.currentText(),
        )

    def _load_alarm_page(self, *, offset: int | None = None, status_message: str | None = None) -> bool:
        if not self._has_query_backed_alarm_data():
            return False
        base_query = self._build_alarm_query(limit=None, offset=0, ignore_sort=True)
        total = alarm_store.count_alarms(base_query)
        page_size = max(int(self._page_size), 1)
        if total <= 0:
            self._alarm_query_active = True
            self._page_total_rows = 0
            self._page_offset = 0
            self._model.clear()
            self._alarm_table_columns = []
            self._refresh_alarm_stats(base_query)
            self._refresh_alarm_facets()
            self._update_pagination_controls()
            if status_message:
                self._sbar.showMessage(status_message)
            return True

        max_offset = ((total - 1) // page_size) * page_size
        page_offset = min(max(int(offset if offset is not None else self._page_offset), 0), max_offset)
        page_query = replace(base_query, limit=page_size, offset=page_offset)
        page_df = alarm_store.query_alarms(page_query)
        ordered = [c for c in ALL_INTERNAL_COLS if c in page_df.columns]
        visible_df = page_df[ordered] if ordered else page_df
        self._model.load_page(visible_df, total_rows=total, offset=page_offset)
        self._alarm_query_active = True
        self._alarm_table_columns = list(visible_df.columns)
        self._page_total_rows = total
        self._page_offset = page_offset
        self._apply_col_widths(list(visible_df.columns))
        self._refresh_alarm_stats(base_query)
        self._refresh_alarm_facets()

        self._update_pagination_controls()
        if status_message:
            self._sbar.showMessage(status_message)
        return True

    def _load_previous_alarm_page(self):
        if self._page_total_rows <= 0:
            return
        self._load_alarm_page(offset=max(self._page_offset - self._page_size, 0))

    def _load_next_alarm_page(self):
        if self._page_total_rows <= 0:
            return
        self._load_alarm_page(offset=self._page_offset + self._page_size)

    def _populate(self, df: pd.DataFrame):
        ordered = [c for c in ALL_INTERNAL_COLS if c in df.columns]
        self._alarm_query_active = False
        self._model.load(df[ordered])
        self._apply_col_widths(ordered)

    def _refresh_stats(self, df: pd.DataFrame):
        self._stats["total"].setText(f"{len(df):,}")
        if "alarm_category" in df.columns:
            cat = df["alarm_category"]
            self._stats["power"].setText(
                f"{(cat == 'Power').sum():,}")
            self._stats["down"].setText(
                f"{(cat == 'Down').sum():,}")
            self._stats["door"].setText(
                f"{(cat == 'Door').sum():,}")
            self._stats["temp"].setText(
                f"{(cat == 'Temp').sum():,}")
        if "site_id" in df.columns:
            self._stats["sites"].setText(
                f"{df['site_id'].nunique():,}")
        # Average duration
        if "_duration_secs" in df.columns and len(df) > 0:
            avg_s = df["_duration_secs"].mean()
            h = int(avg_s // 3600)
            m = int((avg_s % 3600) // 60)
            s = int(avg_s % 60)
            self._stats["avg_dur"].setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self._stats["avg_dur"].setText("—")

    def _show_feature_flags(self):
        dlg = FeatureFlagDialog(self._sync_flags, self)
        if dlg.exec_() == QDialog.Accepted:
            new_flags = dlg.get_flags()
            self._sync_flags.update(new_flags)
            # Persist flags
            s = state.load_state() or {}
            s.update(new_flags)
            state.save_state(s)
            # Apply changes
            if new_flags.get("sync_on") and self._sync_worker is None:
                self._start_sync_worker_if_enabled()
            elif not new_flags.get("sync_on") and self._sync_worker is not None:
                self._stop_sync_worker()

    def _show_settings(self):
        settings = {
            "theme_mode": self._theme_mode,
            "assistant_open": bool(getattr(self, "_assistant_open", True)),
            "skip_photos": self._skip_photos,
            "openrouter_api_key": self._openrouter_api_key,
            "chatgpt_mcp_enabled": self._chatgpt_mcp_enabled,
            "chatgpt_mcp_public_url": self._chatgpt_mcp_public_url,
            "chatgpt_mcp_token": self._chatgpt_mcp_token,
            **self._sync_flags,
        }
        dlg = AppSettingsDialog(settings, self, connector_manager=self._chatgpt_connector_manager)
        if dlg.exec_() != QDialog.Accepted:
            return
        self._apply_app_settings(dlg.get_settings())

    def _apply_app_settings(self, settings: dict):
        previous_sync_on = bool(self._sync_flags.get("sync_on", False))
        theme_mode = str(settings.get("theme_mode") or "auto")
        if theme_mode != self._theme_mode:
            self._set_theme(theme_mode)
        self._skip_photos = bool(settings.get("skip_photos", False))
        self._openrouter_api_key = str(settings.get("openrouter_api_key") or "").strip()
        self._chatgpt_mcp_enabled = bool(settings.get("chatgpt_mcp_enabled", False))
        self._chatgpt_mcp_public_url = str(settings.get("chatgpt_mcp_public_url") or "").strip()
        self._chatgpt_mcp_token = str(settings.get("chatgpt_mcp_token") or "").strip()
        self._sync_flags.update({
            "sync_on": bool(settings.get("sync_on", False)),
            "cloud_read_on": bool(settings.get("cloud_read_on", False)),
            "bootstrap_on": bool(settings.get("bootstrap_on", False)),
        })
        if hasattr(self, "_chat_panel"):
            self._chat_panel.refresh_settings()
        self._set_assistant_panel_open(bool(settings.get("assistant_open", True)), persist=False)
        self._save_ui_state()
        sync_on = bool(self._sync_flags.get("sync_on", False))
        if sync_on and not previous_sync_on:
            self._start_sync_worker_if_enabled()
        elif not sync_on and previous_sync_on and self._sync_worker is not None:
            self._stop_sync_worker()
        self._sbar.showMessage("Settings saved", 2500)

    def openrouter_api_key(self) -> str:
        return self._openrouter_api_key

    def _show_alarm_id_config(self):
        dlg = AlarmIdConfigDialog(parent=self)
        dlg.saved.connect(self._reclassify_alarms)
        dlg.exec_()

    def _reclassify_alarms(self):
        """Re-classify all loaded alarms using current alarm ID config."""
        if not self._has_query_backed_alarm_data():
            if self._full_df.empty:
                return
            alarm_ids = state.load_alarm_ids()
            self._full_df = classify_by_alarm_id(self._full_df, alarm_ids)
            self._full_df = compute_site_down_flag(self._full_df)
            try:
                state.save_dataframe(self._full_df)
            except Exception:
                pass
            view = self._apply_filters(self._full_df)
            self._populate(view)
            self._refresh_stats(view)
            self._refresh_in_memory_count_label(view)
            self._sbar.showMessage("Alarms re-classified by alarm ID config")
            return

        df = alarm_store.load_all_alarms()
        if df.empty:
            QMessageBox.information(self, "No Data", "Load alarm data first.")
            return
        alarm_ids = state.load_alarm_ids()
        df = classify_by_alarm_id(df, alarm_ids)
        df = compute_site_down_flag(df)
        try:
            alarm_store.replace_alarm_table(df)
        except Exception:
            pass
        self._full_df = pd.DataFrame()
        self._load_alarm_page(
            offset=self._page_offset,
            status_message="Alarms re-classified by alarm ID config",
        )
        self._sbar.showMessage("Alarms re-classified by alarm ID config")

    def _reset_date_range(self, df: pd.DataFrame):
        if "occurred_on" in df.columns:
            mn = df["occurred_on"].min()
            mx = df["occurred_on"].max()
            if pd.notna(mn):
                qmn = QDate(mn.year, mn.month, mn.day)
                self._ui.d_from.setMinimumDate(qmn)
                self._ui.d_day.setMinimumDate(qmn)
                self._ui.d_from.setDate(qmn)
            if pd.notna(mx):
                qmx = QDate(mx.year, mx.month, mx.day)
                self._ui.d_to.setMaximumDate(qmx)
                self._ui.d_day.setMaximumDate(qmx)
                self._ui.d_to.setDate(qmx)
                self._ui.d_day.setDate(qmx)

    def _reset_date_range_from_store(self):
        mn, mx = alarm_store.occurred_on_bounds()
        if mn is None or mx is None:
            return
        self._reset_date_range(
            pd.DataFrame({"occurred_on": pd.to_datetime([mn, mx], errors="coerce", format="mixed")})
        )

    def _reference_alarm_sites_df(self) -> pd.DataFrame:
        site_ids = [value for value in alarm_store.distinct_values("site_id") if str(value).strip()]
        return pd.DataFrame({"site_id": site_ids})

    def _toggle_date_filter(self, enabled: bool):
        self._ui.chk_date_range.setEnabled(enabled)
        self._ui.chk_date_days.setEnabled(enabled)
        self._toggle_date_mode_controls()

    def _toggle_date_mode_controls(self):
        date_enabled = self._ui.chk_date.isChecked()
        use_range = date_enabled and self._ui.chk_date_range.isChecked()
        use_days = date_enabled and self._ui.chk_date_days.isChecked()
        self._ui.lbl_from.setEnabled(use_range)
        self._ui.d_from.setEnabled(use_range)
        self._ui.lbl_to.setEnabled(use_range)
        self._ui.d_to.setEnabled(use_range)
        for widget in self._ui.date_quick_widgets:
            widget.setEnabled(use_range)
        self._ui.lbl_day.setEnabled(use_days)
        self._ui.d_day.setEnabled(use_days)
        self._ui.btn_add_day.setEnabled(use_days)
        self._ui.edit_days.setEnabled(use_days)
        self._ui.btn_clear_days.setEnabled(use_days)

    def _set_manual_days_text(self, days: set[pd.Timestamp]):
        ordered = sorted(days)
        self._ui.edit_days.setText(
            ", ".join(d.strftime("%Y-%m-%d") for d in ordered))

    def _add_selected_day(self):
        days, invalid = parse_manual_days(self._ui.edit_days.text())
        days.add(pd.Timestamp(self._ui.d_day.date().toPyDate()).normalize())
        self._set_manual_days_text(days)
        if invalid:
            self._sbar.showMessage("Ignored invalid day value(s) while adding day", 2500)

    def _clear_selected_days(self):
        self._ui.edit_days.clear()

    def _quick_date(self, days: int):
        """Set date range to a quick preset. days=-1 means 'All'."""
        self._ui.chk_date.setChecked(True)
        if not self._ui.chk_date_range.isChecked():
            self._ui.chk_date_range.setChecked(True)
        today = QDate.currentDate()
        if days < 0:
            if self._has_query_backed_alarm_data():
                self._reset_date_range_from_store()
            elif not self._full_df.empty:
                self._reset_date_range(self._full_df)
        elif days == 0:
            self._ui.d_from.setDate(today)
            self._ui.d_to.setDate(today)
        else:
            self._ui.d_from.setDate(today.addDays(-days))
            self._ui.d_to.setDate(today)

    # ── sidebar toggle (Cmd+B) ──────────────────────────────────
    def _toggle_sidebar(self):
        sizes = self._main_splitter.sizes()
        if sizes[0] > 0:
            self._sidebar_width = sizes[0]
            self._main_splitter.setSizes([0, sizes[0] + sizes[1]])
        else:
            max_open = self._max_sidebar_width()
            target = max(self._min_sidebar_width(), min(self._sidebar_width or 260, max_open))
            total = max(1, sizes[0] + sizes[1])
            target = min(target, total - 1)
            self._main_splitter.setSizes([target, total - target])

    def _toggle_assistant_panel(self):
        if not hasattr(self, "_content_splitter"):
            return
        sizes = self._content_splitter.sizes()
        is_open = len(sizes) == 2 and sizes[1] > 0
        self._set_assistant_panel_open(not is_open)

    def _assistant_min_width(self) -> int:
        return 280

    def _assistant_open_min_width(self) -> int:
        recommended = int(getattr(self._chat_panel, "_recommended_min_width", 0) or 0)
        return max(self._assistant_min_width(), recommended)

    def _assistant_max_width(self) -> int:
        if not hasattr(self, "_content_splitter"):
            return 560
        total = self._content_splitter.width() or self.width() or 1
        hard_cap = max(1, total - 1)
        screen_cap = max(1, int(total * 0.6))
        return max(1, min(hard_cap, screen_cap))

    def _set_assistant_panel_open(self, is_open: bool, persist: bool = True):
        if not hasattr(self, "_content_splitter"):
            return
        sizes = self._content_splitter.sizes()
        if len(sizes) != 2:
            return
        total = max(1, sizes[0] + sizes[1])
        if not is_open:
            if sizes[1] > 0:
                self._assistant_width = sizes[1]
            self._assistant_open = False
            self._content_splitter.setSizes([total, 0])
        else:
            max_open = self._assistant_max_width()
            open_min = min(self._assistant_open_min_width(), max_open)
            target = max(open_min, min(self._assistant_width or 320, max_open))
            target = min(target, total - 1)
            self._assistant_open = True
            self._assistant_width = target
            self._content_splitter.setSizes([total - target, target])
        self._apply_assistant_constraints()
        if persist:
            self._save_ui_state()

    def _apply_assistant_constraints(self):
        if not hasattr(self, "_content_splitter"):
            return
        sizes = self._content_splitter.sizes()
        if len(sizes) != 2:
            return
        left, right = sizes
        total = max(1, left + right)
        if right <= 0:
            self._assistant_open = False
        else:
            max_open = self._assistant_max_width()
            max_open = min(max_open, total - 1)
            min_open = min(self._assistant_min_width(), max_open)
            if right > max_open:
                self._content_splitter.setSizes([total - max_open, max_open])
                self._assistant_width = max_open
                self._assistant_open = True
            elif right < min_open:
                self._content_splitter.setSizes([total - min_open, min_open])
                self._assistant_width = min_open
                self._assistant_open = True
            else:
                self._assistant_width = right
                self._assistant_open = True
        if hasattr(self, "_btn_assistant"):
            self._btn_assistant.setChecked(self._assistant_open)
            if hasattr(self, "_refresh_header_button_texts"):
                self._refresh_header_button_texts()
            else:
                self._btn_assistant.setText("Assistant On" if self._assistant_open else "Assistant Off")

    def _on_content_splitter_moved(self, _pos: int, _index: int):
        self._apply_assistant_constraints()

    def _min_sidebar_width(self) -> int:
        current_sidebar = None
        if hasattr(self, "_sidebar_stack"):
            current_sidebar = self._sidebar_stack.currentWidget()
        recommended = int(getattr(current_sidebar, "_recommended_min_width", 0) or 0)
        return max(1, recommended)

    def _max_sidebar_width(self) -> int:
        if not hasattr(self, "_main_splitter"):
            screen = QApplication.primaryScreen()
            if screen:
                return max(1, int(screen.availableGeometry().width() / 3))
            return 500
        total = self._main_splitter.width() or self.width() or 1
        screen = QApplication.primaryScreen()
        if screen:
            screen_cap = max(1, int(screen.availableGeometry().width() / 3))
        else:
            screen_cap = total - 1
        return max(1, min(total - 1, screen_cap))

    def _apply_sidebar_constraints(self):
        if not hasattr(self, "_main_splitter"):
            return
        max_open = self._max_sidebar_width()
        self._sidebar.setMinimumWidth(0)
        self._sidebar.setMaximumWidth(max_open)
        sizes = self._main_splitter.sizes()
        if len(sizes) != 2:
            return
        min_open = min(self._min_sidebar_width(), max_open)
        left, right = sizes
        total = max(1, left + right)
        if left > max_open:
            self._main_splitter.setSizes([max_open, total - max_open])
            self._sidebar_width = max_open
        elif 0 < left < min_open:
            self._main_splitter.setSizes([min_open, total - min_open])
            self._sidebar_width = min_open
        elif left > 0:
            self._sidebar_width = left

    def _on_main_splitter_moved(self, _pos: int, _index: int):
        self._apply_sidebar_constraints()
        self._apply_assistant_constraints()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_btn_settings"):
            self._refresh_header_button_texts()
        if hasattr(self, "_main_splitter"):
            self._apply_sidebar_constraints()
        if hasattr(self, "_content_splitter"):
            self._apply_assistant_constraints()

    def _setup_zoom_shortcuts(self):
        # Deduplicate: QKeySequence.ZoomIn resolves to Ctrl++ on most
        # platforms, so listing it alongside an explicit Ctrl++ creates
        # ambiguous shortcuts that Qt silently drops. Build a unique set
        # keyed by the resolved string representation.
        def _unique_seqs(raw_seqs):
            seen = set()
            out = []
            for seq in raw_seqs:
                ks = QKeySequence(seq) if isinstance(seq, int) else seq
                key = ks.toString()
                if key and key not in seen:
                    seen.add(key)
                    out.append(ks)
            return out

        in_seqs = _unique_seqs([
            QKeySequence.ZoomIn,
            QKeySequence("Ctrl+="),
            QKeySequence("Meta+="),
            QKeySequence("Ctrl++"),
            QKeySequence("Meta++"),
        ])
        out_seqs = _unique_seqs([
            QKeySequence.ZoomOut,
            QKeySequence("Ctrl+-"),
            QKeySequence("Meta+-"),
            QKeySequence("Ctrl+_"),
            QKeySequence("Meta+_"),
        ])
        reset_seqs = _unique_seqs([
            QKeySequence("Ctrl+0"),
            QKeySequence("Meta+0"),
        ])
        for seq in in_seqs:
            sc = QShortcut(seq, self)
            sc.activated.connect(self._zoom_in)
            self._zoom_shortcuts.append(sc)
        for seq in out_seqs:
            sc = QShortcut(seq, self)
            sc.activated.connect(self._zoom_out)
            self._zoom_shortcuts.append(sc)
        for seq in reset_seqs:
            sc = QShortcut(seq, self)
            sc.activated.connect(self._zoom_reset)
            self._zoom_shortcuts.append(sc)

    # ── Theme switching ───────────────────────────────────────────
    def _detect_os_theme(self) -> str:
        """Detect OS dark/light mode. Returns 'dark' or 'light'."""
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and "dark" in result.stdout.lower():
                return "dark"
        except Exception:
            pass
        return "light"

    def _resolve_theme_style(self) -> str:
        """Return the QSS string for the current theme mode."""
        mode = self._theme_mode
        if mode == "auto":
            mode = self._detect_os_theme()
        if mode == "dark":
            return STYLE_DARK
        return STYLE_LIGHT

    def _set_theme(self, mode: str):
        """Switch theme. mode is 'auto', 'dark', or 'light'."""
        self._theme_mode = mode
        for widget in self.findChildren(QWidget):
            widget.setProperty("_zoom_base_style", None)
        self._set_app_zoom(self._app_zoom_pct)
        if hasattr(self, "_bdt_detail_panel_obj"):
            self._bdt_detail_panel_obj.refresh_theme()

    def _toggle_theme(self):
        """Cycle through: auto -> dark -> light -> auto."""
        cycle = {"auto": "dark", "dark": "light", "light": "auto"}
        new_mode = cycle[self._theme_mode]
        self._set_theme(new_mode)
        self._update_theme_button_label()

    def _toggle_skip_photos(self, checked: bool):
        """Toggle skip photos state."""
        self._skip_photos = checked

    def _update_theme_button_label(self):
        self._refresh_header_button_texts()

    def _set_app_zoom(self, pct: int):
        pct = max(self._zoom_min_pct, min(self._zoom_max_pct, int(pct)))
        self._app_zoom_pct = pct
        self.setStyleSheet(self._scale_font_sizes(self._resolve_theme_style(), pct))
        for widget in self.findChildren(QWidget):
            base_ss = widget.property("_zoom_base_style")
            if base_ss is None:
                base_ss = widget.styleSheet()
                widget.setProperty("_zoom_base_style", base_ss)
            if base_ss:
                widget.setStyleSheet(self._scale_font_sizes(str(base_ss), pct))
        app = QApplication.instance()
        if app:
            base = self._base_app_font_size
            if base <= 0:
                base = 13.0
            f = QFont(self._base_app_font)
            f.setPointSizeF(max(7.0, base * (pct / 100.0)))
            app.setFont(f)
        row_h = max(22, int(round(28 * (pct / 100.0))))
        if hasattr(self, "_table"):
            self._table.verticalHeader().setDefaultSectionSize(row_h)
        if hasattr(self, "_bdt_validation_panel") and hasattr(self._bdt_validation_panel, "bdt_table"):
            self._bdt_validation_panel.bdt_table.verticalHeader().setDefaultSectionSize(row_h)
        if hasattr(self, "_btn_settings"):
            self._refresh_compact_buttons()
            self._refresh_header_button_texts()
        if hasattr(self, "_main_splitter"):
            self._apply_sidebar_constraints()
        if hasattr(self, "_chat_panel") and hasattr(self._chat_panel, "_refresh_responsive_metrics"):
            self._chat_panel._refresh_responsive_metrics()
        if hasattr(self, "_content_splitter"):
            self._apply_assistant_constraints()
        if hasattr(self, "_bdt_sidebar") and hasattr(self._bdt_sidebar, "_refresh_responsive_metrics"):
            self._bdt_sidebar._refresh_responsive_metrics()
        if hasattr(self, "_sbar"):
            self._sbar.showMessage(f"UI zoom: {pct}%", 1800)

    def _zoom_in(self):
        self._set_app_zoom(self._app_zoom_pct + 10)

    def _zoom_out(self):
        self._set_app_zoom(self._app_zoom_pct - 10)

    def _zoom_reset(self):
        self._set_app_zoom(100)

    def _scale_font_sizes(self, css: str, pct: int) -> str:
        scale = pct / 100.0

        def repl(match):
            prefix = match.group(1)
            px = float(match.group(2))
            scaled = max(8.0, round(px * scale, 2))
            if scaled.is_integer():
                return f"{prefix}{int(scaled)}px"
            return f"{prefix}{scaled}px"

        return self._font_size_px_re.sub(repl, css)

    # ── slots ────────────────────────────────────────────────────
    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Alarm Data Directory",
            self._ui.edit_dir.text() or str(Path.home()))
        if d:
            self._ui.edit_dir.setText(d)
            self._uploaded_folder_path = d
            self._scan()

    def _browse_bdt(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select BDT Directory",
            self._ui.edit_bdt_dir.text() or self._ui.edit_dir.text() or str(Path.home()))
        if d:
            self._ui.edit_bdt_dir.setText(d)
            self._bdt_uploaded_folder_path = d
            self._scan_bdt()

    def _discover_bdt_files(self, directory: str) -> list[dict]:
        file_infos: list[dict] = []
        root_dir = os.path.abspath(directory)
        for root, _dirs, files in os.walk(root_dir):
            for filename in sorted(files):
                lower = filename.lower()
                if (
                    lower.endswith(".xlsx")
                    and "bdt" in lower
                    and not filename.startswith("~$")
                    and not filename.startswith("._")
                ):
                    path = os.path.join(root, filename)
                    try:
                        size_kb = os.path.getsize(path) / 1024.0
                    except OSError:
                        size_kb = 0.0
                    rel_path = os.path.relpath(path, root_dir)
                    file_infos.append(
                        {
                            "path": path,
                            "filename": filename,
                            "ext": Path(filename).suffix,
                            "size_kb": size_kb,
                            "rel_path": rel_path,
                        }
                    )
        return file_infos

    def _scan_bdt(self):
        directory = self._ui.edit_bdt_dir.text().strip()
        if not directory:
            QMessageBox.warning(
                self, "No Directory",
                "Please enter or browse to a BDT directory first.")
            return
        if not os.path.isdir(directory):
            QMessageBox.critical(
                self, "Invalid Path",
                f"Not a valid directory:\n{directory}")
            return

        self._bdt_uploaded_folder_path = directory
        self._bdt_file_infos = self._discover_bdt_files(directory)
        self._ui.bdt_file_list.clear()

        if not self._bdt_file_infos:
            self._ui.lbl_bdt_file_count.setText("No BDT .xlsx files found")
            self._sbar.showMessage("No BDT files found in the selected directory")
            return

        max_f = min(max(len(f["filename"]) for f in self._bdt_file_infos), 48)
        for info in self._bdt_file_infos:
            line = (
                f"{info['filename']:<{max_f}}  "
                f"{info['ext'].upper().lstrip('.'):<4}  "
                f"{info['size_kb']:>9.1f} KB"
            )
            rel_dir = os.path.dirname(info["rel_path"])
            if rel_dir:
                line += f"   -> {rel_dir}"
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, info)
            item.setForeground(QColor("#6c7086"))
            self._ui.bdt_file_list.addItem(item)

        self._ui.bdt_file_list.selectAll()
        n = len(self._bdt_file_infos)
        self._ui.lbl_bdt_file_count.setText(f"  {n} file{'s' if n != 1 else ''}")
        self._sbar.showMessage(f"Found {n} BDT file(s) in the selected directory")

    def _scan(self):
        directory = self._ui.edit_dir.text().strip()
        if not directory:
            QMessageBox.warning(
                self, "No Directory",
                "Please enter or browse to a directory first.")
            return
        if not os.path.isdir(directory):
            QMessageBox.critical(
                self, "Invalid Path",
                f"Not a valid directory:\n{directory}")
            return

        self._uploaded_folder_path = directory

        self._file_infos = discover_alarm_files(directory)
        self._ui.file_list.clear()

        if not self._file_infos:
            self._ui.lbl_file_count.setText(
                "❌  No .csv / .xlsx files found")
            self._ui.lbl_file_count.setStyleSheet(
                "color:#f38ba8; font-size:11px;")
            self._on_alarm_source_changed()
            return

        max_f = min(
            max(len(f["filename"]) for f in self._file_infos), 48)
        for info in self._file_infos:
            line = (
                f"{info['filename']:<{max_f}}  "
                f"{info['ext'].upper().lstrip('.'):<4}  "
                f"{info['size_kb']:>9.1f} KB")
            rel_dir = os.path.dirname(info["rel_path"])
            if rel_dir:
                line += f"   -> {rel_dir}"
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, info)
            item.setForeground(QColor("#6c7086"))
            self._ui.file_list.addItem(item)

        self._ui.file_list.selectAll()

        n = len(self._file_infos)
        self._ui.lbl_file_count.setText(f"  {n} file{'s' if n != 1 else ''}")
        self._ui.lbl_file_count.setStyleSheet("color:#a6e3a1; font-size:11px;")
        self._on_alarm_source_changed()
        self._sbar.showMessage(
            f"Found {n} file(s) — select files to load, "
            "then click 'Load Selected Files'.")

    def _on_alarm_source_changed(self):
        mode = self._get_alarm_load_mode()
        has_files = bool(getattr(self, "_file_infos", []))
        can_load = (mode == "db") or has_files
        self._ui.btn_load.setEnabled(can_load)
        if mode == "db":
            self._ui.btn_load.setText("Load Cached Alarms")
        elif mode == "both":
            self._ui.btn_load.setText("Load + Verify")
        else:
            self._ui.btn_load.setText("Load Selected Files")

    def _load(self):
        self._pending_alarm_load_mode = self._get_alarm_load_mode()
        if self._pending_alarm_load_mode == "db":
            self._page_offset = 0
            if self._load_alarm_page(
                offset=0,
                status_message="Loaded cached alarm results from local store",
            ) and self._current_alarm_total() > 0:
                total = self._current_alarm_total()
                self._ui.lbl_loaded.setText(f"✓  {total:,} cached records")
                self._ui.lbl_loaded.setStyleSheet("color:#a6e3a1; font-size:11px;")
                return

            df = self._load_alarm_dataframe_from_db()
            if df is not None and not df.empty:
                self._apply_loaded_alarm_dataframe(
                    df,
                    f"Recovered {len(df):,} alarm records from local DB fallback",
                )
                return

            has_selected_files = any(
                self._ui.file_list.item(i).isSelected()
                for i in range(self._ui.file_list.count())
            )
            has_discovered_files = bool(getattr(self, "_file_infos", None))
            if has_selected_files or has_discovered_files:
                self._pending_alarm_load_mode = "directory"
                if has_selected_files:
                    self._sbar.showMessage(
                        "No local cache found — loading selected files from directory instead"
                    )
                else:
                    self._sbar.showMessage(
                        "No local cache found — loading all discovered files from directory instead"
                    )
            else:
                QMessageBox.information(
                    self,
                    "No Alarm Data",
                    "No saved alarm rows were found in the local alarm cache.",
                )
                self._sbar.showMessage("No saved alarm rows found in local cache")
                return

        selected = [
            self._ui.file_list.item(i).data(Qt.UserRole)
            for i in range(self._ui.file_list.count())
            if self._ui.file_list.item(i).isSelected()
        ]
        if (
            self._pending_alarm_load_mode == "directory"
            and not selected
            and getattr(self, "_file_infos", None)
        ):
            selected = list(self._file_infos)
            self._sbar.showMessage(
                f"No local cache found — loading all discovered files ({len(selected)})"
            )
        if not selected:
            QMessageBox.warning(
                self, "Nothing Selected",
                "Select at least one file from the list.")
            return
        self._ui.btn_load.setEnabled(False)
        self._prog.setVisible(True)
        self._prog.setValue(0)
        self._sbar.showMessage(f"Loading {len(selected)} file(s) …")
        self._loader = LoaderThread(selected)
        self._set_alarm_load_running(True)
        self._loader.progress.connect(
            lambda v, m: (
                self._prog.setValue(v),
                self._sbar.showMessage(m),
            ))
        self._loader.finished.connect(self._on_loaded)
        self._loader.error.connect(self._on_error)
        if hasattr(self._loader, "cancelled"):
            self._loader.cancelled.connect(self._on_load_cancelled)
        self._loader.start()

    def _set_alarm_load_running(self, running: bool) -> None:
        self._ui.btn_load.setEnabled(not running)
        btn_cancel = getattr(self._ui, "btn_cancel_load", None)
        if btn_cancel is not None:
            btn_cancel.setVisible(running)
            btn_cancel.setEnabled(running)

    def _cancel_alarm_load(self) -> None:
        loader = getattr(self, "_loader", None)
        if loader is not None and loader.isRunning():
            if hasattr(loader, "cancel"):
                loader.cancel()
            self._sbar.showMessage("Cancelling alarm load …")

    def _on_load_cancelled(self, msg: str):
        self._set_alarm_load_running(False)
        self._prog.setVisible(False)
        self._prog.setValue(0)
        self._sbar.showMessage(msg)

    def _on_loaded(self, df: pd.DataFrame, msg: str):
        if getattr(self, "_pending_alarm_load_mode", "directory") == "both":
            try:
                from alarm_app.data.loaders import deduplicate_alarm_rows
            except ImportError:
                from data.loaders import deduplicate_alarm_rows
            db_df = self._load_alarm_dataframe_from_db()
            if db_df is None:
                db_df = pd.DataFrame()
            if not db_df.empty:
                merged = pd.concat([db_df, df], ignore_index=True)
                df, dropped = deduplicate_alarm_rows(merged)
                msg = (
                    f"{msg}; merged with {len(db_df):,} cached record(s)"
                    f"{f'; dropped {dropped:,} duplicate row(s)' if dropped else ''}"
                )

        self._apply_loaded_alarm_dataframe(df, msg)

    def _on_error(self, msg: str):
        if hasattr(self, "_set_alarm_load_running"):
            self._set_alarm_load_running(False)
        else:
            self._ui.btn_load.setEnabled(True)
        self._prog.setVisible(False)
        QMessageBox.critical(self, "Load Error", msg)
        self._sbar.showMessage(f"Error: {msg}")

    def _get_alarm_load_mode(self) -> str:
        return str(self._ui.cmb_alarm_source.currentData() or "directory")

    def _load_alarm_dataframe_from_db(self) -> pd.DataFrame | None:
        try:
            df = state.load_dataframe()
            return df if df is not None and not df.empty else None
        except Exception:
            return None

    def _apply_loaded_alarm_dataframe(self, df: pd.DataFrame, msg: str):
        for col in ("occurred_on", "cleared_on"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
        prepared_cols = {"alarm_category", "site_down_flag", "duration", "_duration_secs"}
        if not prepared_cols.issubset(df.columns):
            alarm_ids = state.load_alarm_ids()
            df = classify_by_alarm_id(df, alarm_ids)
            df = compute_site_down_flag(df)
        if hasattr(self, "_set_alarm_load_running"):
            self._set_alarm_load_running(False)
        else:
            self._ui.btn_load.setEnabled(True)
        self._prog.setVisible(False)
        self._sbar.showMessage(msg)
        self._ui.lbl_loaded.setText(
            f"✓  {len(df):,} records cached locally")
        self._ui.lbl_loaded.setStyleSheet(
            "color:#a6e3a1; font-size:11px;")
        self._reset_date_range(df)
        self._page_offset = 0
        self._full_df = pd.DataFrame()
        if self._has_query_backed_alarm_data():
            if self._load_alarm_page(offset=0, status_message=msg) and self._current_alarm_total() > 0:
                return

        self._full_df = df.sort_index().reset_index(drop=True)
        view = self._apply_filters(self._full_df)
        self._populate(view)
        self._refresh_stats(view)
        view_total = len(view)
        lbl_count = getattr(self, "_lbl_count", None)
        if lbl_count is not None:
            start = 1 if view_total else 0
            lbl_count.setText(_format_count_label(start, view_total, view_total))
        self._sbar.showMessage(f"{msg}; displaying in-memory results")

    def _refresh_in_memory_count_label(self, view) -> None:
        """Refresh ``_lbl_count`` for the in-memory ``_search`` /
        ``_clear_filters`` / ``_reclassify_alarms`` paths.

        ``_update_pagination_controls`` covers the DB-paginated mode and
        ``_apply_loaded_alarm_dataframe`` covers the initial in-memory load,
        so this helper exists purely so the three filter-mutation paths
        always keep the label in sync with the visible row count.
        """
        lbl_count = getattr(self, "_lbl_count", None)
        if lbl_count is None:
            return
        try:
            n = int(len(view))
        except TypeError:
            n = 0
        start = 1 if n else 0
        lbl_count.setText(_format_count_label(start, n, n))

    def _load_bdt_results_from_db(self) -> list:
        try:
            try:
                from alarm_app.db.engine import create_engine as _ce
            except ImportError:
                from db.engine import create_engine as _ce
            try:
                from alarm_app.db.engine import get_session_factory as _gsf
            except ImportError:
                from db.engine import get_session_factory as _gsf
            try:
                from alarm_app.db.engine import init_db as _idb
            except ImportError:
                from db.engine import init_db as _idb
            try:
                from alarm_app.db.repos.pm_repo import load_all_validation_results
            except ImportError:
                from db.repos.pm_repo import load_all_validation_results
            engine = _ce()
            _idb(engine)
            session = _gsf(engine)()
            try:
                return load_all_validation_results(session)
            finally:
                session.close()
        except Exception:
            return []

    def _apply_bdt_results(self, results: list, status_message: str | None = None):
        self._bdt_results = results
        self._bdt_by_site = {}
        for vr in results:
            if vr.site_code and vr.bdt_data is not None:
                key = vr.site_code.strip().upper()
                self._bdt_by_site.setdefault(key, []).append(vr.bdt_data)
        for _key, items in self._bdt_by_site.items():
            items.sort(key=lambda b: getattr(b, "test_date", None) or datetime.min, reverse=True)
        if hasattr(self, "_bdt_validation_panel"):
            self._bdt_validation_panel.set_results(results)
        if status_message:
            self._sbar.showMessage(status_message)

    def _apply_filters(self, df: pd.DataFrame, exclude_columns: set[str] | None = None) -> pd.DataFrame:
        """Apply current UI filters to *df* and return the subset."""
        exclude_columns = exclude_columns or set()
        f = FilterState.from_viewer(self)

        if f.invalid_manual_days:
            self._sbar.showMessage(
                "Ignored invalid day value(s) in specific days filter",
                2500,
            )

        if f.site_scope_keys and "site_id" in df.columns:
            site_keys = df["site_id"].map(lambda value: "".join(ch for ch in str(value).strip().upper() if ch.isalnum()) if pd.notna(value) else "")
            df = df[site_keys.isin(f.site_scope_keys)]

        # Site ID — supports multiple comma-separated terms
        if f.site_text and "site_id" not in exclude_columns and "alarm_source" not in exclude_columns:
            terms = [t.strip() for t in f.site_text.split(",") if t.strip()]
            if terms:
                site_col = df["site_id"].astype(str).str.upper()
                mask = pd.Series(False, index=df.index)
                for t in terms:
                    tu = t.upper()
                    mask |= site_col.str.contains(tu, na=False)
                    if "alarm_source" in df.columns:
                        mask |= df["alarm_source"].astype(str).str.upper(
                            ).str.contains(tu, na=False)
                df = df[mask]

        # Date filter (range and/or specific days)
        if "occurred_on" not in exclude_columns and (f.date_from is not None or f.date_to is not None or f.manual_days is not None) and "occurred_on" in df.columns:
            mask = compute_date_mask(
                df["occurred_on"],
                use_range=(f.date_from is not None or f.date_to is not None),
                from_date=f.date_from or date.today(),
                to_date=f.date_to or date.today(),
                use_days=(f.manual_days is not None),
                manual_days=f.manual_days,
            )
            if mask is not None:
                df = df[mask]

        # Category
        if "alarm_category" not in exclude_columns and f.category != "All" and "alarm_category" in df.columns:
            df = df[df["alarm_category"] == f.category]

        # Network
        if "network_type" not in exclude_columns and f.network_type != "All" and "network_type" in df.columns:
            df = df[df["network_type"].astype(str) == f.network_type]

        # Vendor
        if "vendor" not in exclude_columns and f.vendor != "All" and "vendor" in df.columns:
            df = df[df["vendor"].astype(str).str.upper()
                    == f.vendor.upper()]

        # Duration ≥ N min filter
        if "_duration_secs" not in exclude_columns and f.min_duration_secs is not None and "_duration_secs" in df.columns:
            df = df[df["_duration_secs"] >= f.min_duration_secs]

        # Per-column filters (from header popup)
        for col, allowed in f.col_filters.items():
            if "*" in exclude_columns or col in exclude_columns:
                continue
            if allowed is not None and col in df.columns:
                df = df[df[col].fillna("").astype(str).isin(allowed)]

        # Both Power + Down: keep only sites that have both categories
        # Check against _full_df so other filters don't hide categories
        if (f.both_pd
                and "site_id" in df.columns
                and "alarm_category" in df.columns):
            full = self._full_df
            cats_per_site = full.groupby("site_id")["alarm_category"].apply(set)
            both_sites = cats_per_site[
                cats_per_site.apply(
                    lambda s: "Power" in s and "Down" in s)
            ].index
            df = df[df["site_id"].isin(both_sites)]

        return df

    def _search(self):
        if self._has_query_backed_alarm_data():
            self._page_offset = 0
            if self._load_alarm_page(offset=0):
                raw = self._ui.edit_site.text().strip()
                total = self._current_alarm_total()
                if raw:
                    summary = alarm_store.stats(
                        self._build_alarm_query(limit=None, offset=0, ignore_sort=True)
                    )
                    u = int(summary.get("sites", 0))
                    self._sbar.showMessage(
                        f"Found {total:,} alarm{'s' if total != 1 else ''} "
                        f"for '{raw}'  —  {u} unique site(s)"
                    )
                else:
                    self._sbar.showMessage(f"Filtered: {total:,} records")
                return

        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data",
                "Please load alarm data first.")
            return

        df = self._apply_filters(self._full_df)

        self._populate(df)
        self._refresh_stats(df)
        self._refresh_in_memory_count_label(df)
        n = len(df)

        raw = self._ui.edit_site.text().strip()
        if raw:
            u = (df["site_id"].nunique()
                 if "site_id" in df.columns else 0)
            self._sbar.showMessage(
                f"Found {n:,} alarm{'s' if n != 1 else ''} "
                f"for '{raw}'  —  {u} unique site(s)")
        else:
            self._sbar.showMessage(f"Filtered: {n:,} records")

    def _activate_both_pd(self):
        """Turn on the Both P+D filter and re-search."""
        if not self._has_query_backed_alarm_data() and self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return
        self._both_pd_active = True
        self._ui.btn_both.setStyleSheet(
            "QPushButton { background:#4a3018; color:#fab387; "
            "border:2px solid #fab387; border-radius:6px; "
            "padding:7px 16px; font-weight:700; font-size:12px; "
            "min-width:72px; }")
        self._search()

    def _clear_filters(self):
        self._ui.edit_site.clear()
        self._ui.cb_cat.setCurrentIndex(0)
        self._ui.cb_net.setCurrentIndex(0)
        self._ui.cb_vnd.setCurrentIndex(0)
        self._ui.chk_date.setChecked(True)
        self._ui.chk_date_range.setChecked(True)
        self._ui.chk_date_days.setChecked(False)
        self._ui.edit_days.clear()
        self._both_pd_active = False
        self._ui.btn_both.setStyleSheet("")  # reset to default theme style
        self._col_filters.clear()
        # Reset sort indicator
        hdr = self._table.horizontalHeader()
        hdr.setSortIndicator(-1, Qt.AscendingOrder)
        self._page_offset = 0
        if self._has_query_backed_alarm_data():
            self._reset_date_range_from_store()
            self._load_alarm_page(offset=0, status_message="Filters cleared")
            return
        if not self._full_df.empty:
            self._reset_date_range(self._full_df)
            # Restore original load order
            self._full_df = self._full_df.sort_index().reset_index(drop=True)
            df = self._full_df
            if self._ui.chk_mindur.isChecked() and "_duration_secs" in df.columns:
                df = df[df["_duration_secs"] >= self._ui.spn_mindur.value() * 60]
            self._populate(df)
            self._refresh_stats(df)
            self._refresh_in_memory_count_label(df)
        self._sbar.showMessage("Filters cleared")

    def _running_background_threads(self) -> list:
        running_threads = []
        iter_threads = getattr(self, "_iter_background_threads", lambda: [])
        for thread in iter_threads():
            try:
                if thread.isRunning():
                    running_threads.append(thread)
            except Exception:
                pass
        return running_threads

    def _block_cache_clear_if_background_work_running(self, scope_label: str) -> bool:
        if not AlarmViewer._running_background_threads(self):
            return False
        QMessageBox.information(
            self,
            "Background Work Running",
            f"Wait for background work to finish or cancel it before clearing {scope_label}.",
        )
        self._sbar.showMessage(
            f"Clear {scope_label} blocked while background work is running",
            5000,
        )
        return True

    @staticmethod
    def _format_clear_summary(summary: dict[str, int]) -> list[str]:
        cleared_lines = []
        for key, value in summary.items():
            if value == -1:
                cleared_lines.append(f"  {key}: ERROR")
            else:
                cleared_lines.append(f"  {key}: {value:,}")
        return cleared_lines

    @staticmethod
    def _clear_summary_total(summary: dict[str, int]) -> int:
        return sum(max(value, 0) for value in summary.values())

    def _reset_alarm_cache_state(self) -> None:
        self._full_df = pd.DataFrame()
        self._page_offset = 0
        self._page_total_rows = 0
        self._alarm_query_active = False
        self._col_filters.clear()
        self._model.clear()

        lbl_count = getattr(self, "_lbl_count", None)
        if lbl_count is not None:
            lbl_count.setText("Alarm cache cleared — click Load Selected Files to re-derive")
        if hasattr(self, "_ui") and getattr(self._ui, "lbl_loaded", None) is not None:
            self._ui.lbl_loaded.setText("Alarm cache cleared")
            self._ui.lbl_loaded.setStyleSheet("color:#f9e2af; font-size:11px;")
        self._refresh_stats(pd.DataFrame())

    def _reset_bdt_cache_state(self) -> None:
        self._bdt_results = []
        self._bdt_by_site = {}
        self._reviewed_bdt_keys = set()
        if hasattr(self, "_bdt_validation_panel") and self._bdt_validation_panel is not None:
            try:
                self._bdt_validation_panel.set_results([])
            except Exception:
                _log.warning("Could not reset BDT validation panel", exc_info=True)

        bdt_ws = getattr(self, "_bdt_workspace_panel", None)
        if bdt_ws is not None and hasattr(bdt_ws, "invalidate_caches"):
            try:
                bdt_ws.invalidate_caches()
            except Exception:
                _log.warning("Could not invalidate BDT workspace caches", exc_info=True)

    def _clear_alarm_caches(self) -> None:
        """Wipe alarm-derived caches and reset alarm UI state only."""
        if AlarmViewer._block_cache_clear_if_background_work_running(self, "alarm cache"):
            return

        confirm = QMessageBox.question(
            self,
            "Clear alarm cache?",
            "This will wipe only the alarm cache: DuckDB alarm files and "
            "SQLite alarm_records.\n\n"
            "PRESERVED: BDT validation results, BDT history, BDT summary "
            "catalog, BDT photo/blob metadata, source files, uploaded-files "
            "dedup index, UI preferences, site catalog, validation rule "
            "definitions, sync queue, daily-review history, photo files.\n\n"
            "Proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            self._sbar.showMessage("Clear alarm cache - cancelled", 5000)
            return

        try:
            summary = clear_alarm_caches()
            _log.info("clear_alarm_caches summary: %s", summary)
        except Exception as exc:
            _log.error("clear_alarm_caches failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Clear Alarm Cache Failed",
                f"Could not clear alarm cache:\n\n{exc}\n\nSee the application log for details.",
            )
            return

        AlarmViewer._reset_alarm_cache_state(self)
        cleared_lines = AlarmViewer._format_clear_summary(summary)
        total = AlarmViewer._clear_summary_total(summary)
        message = (
            f"Cleared alarm cache - {total:,} rows / files removed. "
            "Next alarm load will rebuild from source files."
        )
        _log.info("Alarm cache cleared:\n%s", "\n".join(cleared_lines))
        self._sbar.showMessage(message, 10000)
        QMessageBox.information(
            self,
            "Alarm Cache Cleared",
            "Alarm cache cleared. Use 'Load Selected Files' to re-derive alarms "
            "from source files.\n\nSummary:\n" + "\n".join(cleared_lines),
        )

    def _clear_bdt_caches(self) -> None:
        """Wipe BDT-derived caches and reset BDT UI state only."""
        if AlarmViewer._block_cache_clear_if_background_work_running(self, "BDT cache"):
            return

        confirm = QMessageBox.question(
            self,
            "Clear BDT cache?",
            "This will wipe only BDT-derived cached data: parsed BDT tests, "
            "photo/blob metadata, validation runs, rule results, imported BDT "
            "summary rows, and BDT history files.\n\n"
            "PRESERVED: alarm cache, loaded alarm rows, source files, "
            "uploaded-files dedup index, UI preferences, site catalog, "
            "validation rule definitions, sync queue, daily-review history, "
            "and photo files.\n\n"
            "Proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            self._sbar.showMessage("Clear BDT cache - cancelled", 5000)
            return

        try:
            summary = clear_bdt_caches()
            _log.info("clear_bdt_caches summary: %s", summary)
        except Exception as exc:
            _log.error("clear_bdt_caches failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Clear BDT Cache Failed",
                f"Could not clear BDT cache:\n\n{exc}\n\nSee the application log for details.",
            )
            return

        AlarmViewer._reset_bdt_cache_state(self)
        cleared_lines = AlarmViewer._format_clear_summary(summary)
        total = AlarmViewer._clear_summary_total(summary)
        message = (
            f"Cleared BDT cache - {total:,} rows / files removed. "
            "Next BDT validation will rebuild from source workbooks."
        )
        _log.info("BDT cache cleared:\n%s", "\n".join(cleared_lines))
        self._sbar.showMessage(message, 10000)
        QMessageBox.information(
            self,
            "BDT Cache Cleared",
            "BDT cache cleared. Validate BDT files again to re-derive results "
            "from source workbooks.\n\nSummary:\n" + "\n".join(cleared_lines),
        )

    def _clear_caches(self) -> None:
        """Compatibility path for wiping all derived alarm and BDT caches."""
        if AlarmViewer._block_cache_clear_if_background_work_running(self, "cached data"):
            return

        confirm = QMessageBox.question(
            self,
            "Clear cached data?",
            "This will wipe the alarm cache and BDT data so the next "
            "Load Selected Files does a full re-derive from source files.\n\n"
            "PRESERVED: source files, uploaded-files dedup index, UI "
            "preferences, site catalog, validation rule definitions, "
            "sync queue, daily-review history, photo files.\n\n"
            "Proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            self._sbar.showMessage("Clear cached data - cancelled", 5000)
            return

        try:
            summary = clear_all_caches()
            _log.info("clear_all_caches summary: %s", summary)
        except Exception as exc:
            _log.error("clear_all_caches failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Clear Cached Data Failed",
                f"Could not clear cached data:\n\n{exc}\n\nSee the application log for details.",
            )
            return

        AlarmViewer._reset_alarm_cache_state(self)
        AlarmViewer._reset_bdt_cache_state(self)
        cleared_lines = AlarmViewer._format_clear_summary(summary)
        total = AlarmViewer._clear_summary_total(summary)
        message = (
            f"Cleared cached data - {total:,} rows / files removed. Next "
            "'Load Selected Files' will rebuild from source files."
        )
        _log.info("Cache cleared:\n%s", "\n".join(cleared_lines))
        self._sbar.showMessage(message, 10000)
        QMessageBox.information(
            self,
            "Cached Data Cleared",
            "Cache cleared. Use 'Load Selected Files' to re-derive from the "
            "source alarm and BDT workbooks.\n\nSummary:\n" + "\n".join(cleared_lines),
        )

    def _show_backup_times(self):
        if self._has_query_backed_alarm_data():
            query = self._expand_backup_time_query(
                self._build_alarm_query(limit=None, offset=0, ignore_sort=True)
            )
            if alarm_store.count_alarms(query) == 0:
                QMessageBox.information(
                    self, "No Data",
                    "No records match the current filters.")
                return
            self._ui.btn_backup.setEnabled(False)
            self._sbar.showMessage("Computing backup times …")
            self._bt_thread = BackupTimeThread(alarm_query=query)
            self._bt_thread.progress.connect(
                lambda v, m: self._sbar.showMessage(m))
            self._bt_thread.finished.connect(self._on_bt_done)
            self._bt_thread.error.connect(self._on_bt_error)
            self._bt_thread.start()
            return

        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return
        filtered = self._apply_filters(self._full_df)
        if filtered.empty:
            QMessageBox.information(
                self, "No Data",
                "No records match the current filters.")
            return
        self._ui.btn_backup.setEnabled(False)
        self._sbar.showMessage("Computing backup times …")
        self._bt_thread = BackupTimeThread(filtered.copy())
        self._bt_thread.progress.connect(
            lambda v, m: self._sbar.showMessage(m))
        self._bt_thread.finished.connect(self._on_bt_done)
        self._bt_thread.error.connect(self._on_bt_error)
        self._bt_thread.start()

    def _on_bt_done(self, result, err: str):
        self._ui.btn_backup.setEnabled(True)
        if err:
            QMessageBox.warning(self, "Backup Time", err)
            self._sbar.showMessage("Backup time: " + err)
            return
        self._sbar.showMessage(
            f"Backup time analysis: {len(result):,} pairs found")
        dlg = BackupTimeDialog(result, parent=self)
        dlg.exec_()

    def _on_bt_error(self, msg: str):
        self._ui.btn_backup.setEnabled(True)
        QMessageBox.critical(self, "Backup Time Error", msg)
        self._sbar.showMessage("Backup time computation failed")

    def _show_temp_alarms(self):
        week_label = self._infer_ht_export_week_label()
        if self._has_query_backed_alarm_data():
            result_filter_query = self._build_alarm_query(
                limit=None,
                offset=0,
                exclude_columns={"alarm_category"},
                ignore_sort=True,
            )
            query = self._build_temp_alarm_source_query(result_filter_query)
            if alarm_store.count_alarms(query) == 0:
                QMessageBox.information(
                    self, "No Data",
                    "No records match the current filters.")
                return
            self._ui.btn_temp.setEnabled(False)
            self._sbar.showMessage("Computing HT Meet workbook preview …")
            self._temp_thread = TempAlarmThread(
                alarm_query=query,
                margin_minutes=60,
                result_filter_query=result_filter_query,
                week_label=week_label,
            )
            self._temp_thread.progress.connect(
                lambda v, m: self._sbar.showMessage(m))
            self._temp_thread.finished.connect(self._on_temp_done)
            self._temp_thread.error.connect(self._on_temp_error)
            self._temp_thread.start()
            return

        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return
        result_filter_query = self._build_alarm_query(
            limit=None,
            offset=0,
            exclude_columns={"alarm_category"},
            ignore_sort=True,
        )
        # Include both Temp and Power rows as source for HT Meet computation
        source_for_meet = self._apply_filters(
            self._full_df,
            exclude_columns={"alarm_category"},
        )
        # Keep selected_temp for scope context
        selected_temp = self._apply_filters(
            self._full_df,
            exclude_columns={"alarm_category"},
        )
        if "alarm_category" in selected_temp.columns:
            selected_temp = selected_temp[selected_temp["alarm_category"] == "Temp"]
        if selected_temp.empty:
            QMessageBox.information(
                self, "No Data",
                "No records match the current filters.")
            return
        self._ui.btn_temp.setEnabled(False)
        self._sbar.showMessage("Computing HT Meet workbook preview …")
        self._temp_thread = TempAlarmThread(
            source_for_meet.copy(),
            margin_minutes=60,
            result_filter_query=result_filter_query,
            selected_temp_df=selected_temp.copy(),
            week_label=week_label,
        )
        self._temp_thread.progress.connect(
            lambda v, m: self._sbar.showMessage(m))
        self._temp_thread.finished.connect(self._on_temp_done)
        self._temp_thread.error.connect(self._on_temp_error)
        self._temp_thread.start()

    def _on_temp_done(self, result, err: str, source_df):
        self._ui.btn_temp.setEnabled(True)
        if err:
            QMessageBox.warning(self, "HT Meet Workbook", err)
            self._sbar.showMessage("HT Meet: " + err)
            return
        self._sbar.showMessage(
            f"HT Meet preview: {len(result):,} meet rows found")
        result_filter_query = getattr(self._temp_thread, "_result_filter_query", None)
        week_label = getattr(self._temp_thread, "_week_label", None)
        dlg = TempAlarmDialog(
            result,
            source_df,
            margin_minutes=60,
            result_filter_query=result_filter_query,
            selected_temp_df=getattr(self._temp_thread, "_selected_temp_df", None),
            week_label=week_label,
            parent=self,
        )
        dlg.exec_()

    def _on_temp_error(self, msg: str):
        self._ui.btn_temp.setEnabled(True)
        QMessageBox.critical(self, "HT Meet Workbook Error", msg)
        self._sbar.showMessage("HT Meet computation failed")

    def _infer_ht_export_week_label(self) -> str | None:
        """Infer a Wnn-yy week label from the current date range or source data."""
        try:
            query = self._build_alarm_query(limit=None, offset=0, ignore_sort=True)
            # Try from manual_days first
            if query.manual_days:
                latest = max(
                    pd.Timestamp(day) for day in query.manual_days
                    if not pd.isna(pd.Timestamp(day))
                )
                return ht_export_week_from_date(latest)["week_label"]
            if query.date_to:
                return ht_export_week_from_date(query.date_to)["week_label"]
            if query.date_from:
                return ht_export_week_from_date(query.date_from)["week_label"]
            # Fallback to source_df if loaded
            if not self._full_df.empty and "occurred_on" in self._full_df.columns:
                times = pd.to_datetime(self._full_df["occurred_on"], errors="coerce").dropna()
                if not times.empty:
                    return ht_export_week_from_date(times.max())["week_label"]
        except Exception:
            pass
        return None

    def _upload_site_sheet(self):
        if not self._has_query_backed_alarm_data() and self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return

        in_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Site Sheet",
            self._ui.edit_dir.text().strip() or str(Path.home()),
            "Spreadsheet Files (*.xlsx *.xls *.csv)",
        )
        if not in_path:
            return

        try:
            self._ui.btn_site_sheet.setEnabled(False)
            self._sbar.showMessage("Reading site sheet …")
            alarm_df = self._reference_alarm_sites_df() if self._has_query_backed_alarm_data() else self._full_df
            site_df, sheet_name, site_col = read_site_sheet(in_path, alarm_df)
            site_keys = collect_site_sheet_keys(site_df, site_col)
            if not site_keys:
                raise ValueError("The uploaded site sheet does not contain any usable site IDs.")
        except Exception as exc:
            self._ui.btn_site_sheet.setEnabled(True)
            QMessageBox.critical(self, "Site Sheet Error", str(exc))
            self._sbar.showMessage("Site sheet upload failed")
            return

        self._ui.btn_site_sheet.setEnabled(True)
        self._uploaded_site_df = site_df.copy()
        self._uploaded_site_sheet_name = sheet_name
        self._uploaded_site_id_column = site_col
        self._uploaded_site_keys = site_keys
        self._uploaded_site_path = in_path
        self._uploaded_folder_path = os.path.dirname(in_path)
        try:
            saved = state.load_state() or {}
            saved["uploaded_folder_path"] = self._uploaded_folder_path
            state.save_state(saved)
        except Exception:
            pass
        self._search()
        QMessageBox.information(
            self,
            "Site Sheet Loaded",
            "The alarm table is now limited to the uploaded site sheet.\n\n"
            f"Source sheet: {sheet_name}\n"
            f"Matched by column: {site_col}\n"
            f"Uploaded site rows: {len(site_df)}\n"
            f"Unique site IDs: {len(site_keys)}\n\n"
            "Now apply any extra filters you want, then click Generate Site Report.",
        )
        self._sbar.showMessage(
            f"Loaded site sheet scope: {len(site_keys):,} site IDs from {os.path.basename(in_path)}")

    def _import_network_summary_catalog(self):
        in_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Network Summary Workbook(s)",
            self._ui.edit_dir.text().strip() or str(Path.home()),
            "Excel Files (*.xlsx *.xlsm *.xls)",
        )
        if not in_paths:
            return
        button = getattr(self._ui, "btn_network_summary", None)
        count = 0
        imported_paths: list[str] = []
        failures: list[tuple[str, str]] = []
        try:
            if button is not None:
                button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self._sbar.showMessage("Importing Network Summary catalog …")
            for in_path in in_paths:
                try:
                    count += import_network_summary_db_sheet(in_path)
                    imported_paths.append(in_path)
                except Exception as exc:
                    failures.append((in_path, str(exc)))
        finally:
            QApplication.restoreOverrideCursor()
            if button is not None:
                button.setEnabled(True)
        if failures and not imported_paths:
            QMessageBox.critical(
                self,
                "Network Summary Import Failed",
                "No workbook was imported.\n\n" + "\n".join(f"{path}: {error}" for path, error in failures),
            )
            self._sbar.showMessage("Network Summary import failed")
            return
        if failures:
            QMessageBox.warning(
                self,
                "Network Summary Import Partially Completed",
                f"Merged {count:,} incoming site metadata row(s) from {len(imported_paths):,} workbook(s).\n"
                f"Failed {len(failures):,} workbook(s):\n\n"
                + "\n".join(f"{path}: {error}" for path, error in failures),
            )
            self._sbar.showMessage(
                f"Network Summary catalog partially imported: {count:,} incoming site row(s), {len(failures):,} failed workbook(s)"
            )
            return
        QMessageBox.information(
            self,
            "Network Summary Imported",
            f"Merged {count:,} incoming site metadata row(s) from {len(in_paths):,} workbook(s) into the Site Metadata Catalog.\n\n"
            + "\n".join(in_paths),
        )
        self._sbar.showMessage(f"Network Summary catalog imported: {count:,} site(s), {len(in_paths):,} workbook(s)")

    def _import_bdt_summary_catalog(self):
        in_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import BDT Summary Workbook(s)",
            self._ui.edit_dir.text().strip() or str(Path.home()),
            "Excel Files (*.xlsx *.xlsm *.xls)",
        )
        if not in_paths:
            return
        button = getattr(self._ui, "btn_bdt_summary", None)
        period_counts: dict[str, int] = {}
        imported_paths: list[str] = []
        failures: list[tuple[str, str]] = []
        try:
            if button is not None:
                button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self._sbar.showMessage("Importing BDT Summary catalog …")
            for in_path in in_paths:
                try:
                    imported_counts = import_bdt_summary_workbook(in_path)
                    imported_paths.append(in_path)
                except Exception as exc:
                    failures.append((in_path, str(exc)))
                    continue
                for period, row_count in imported_counts.items():
                    period_counts[period] = int(row_count or 0)
        finally:
            QApplication.restoreOverrideCursor()
            if button is not None:
                button.setEnabled(True)
        period_count = len(period_counts)
        row_count = sum(int(value or 0) for value in period_counts.values())
        if failures and not imported_paths:
            QMessageBox.critical(
                self,
                "BDT Summary Import Failed",
                "No workbook was imported.\n\n" + "\n".join(f"{path}: {error}" for path, error in failures),
            )
            self._sbar.showMessage("BDT Summary import failed")
            return
        if failures:
            QMessageBox.warning(
                self,
                "BDT Summary Import Partially Completed",
                f"Imported {row_count:,} latest row(s) across {period_count:,} period(s) from {len(imported_paths):,} workbook(s).\n"
                f"Failed {len(failures):,} workbook(s):\n\n"
                + "\n".join(f"{path}: {error}" for path, error in failures),
            )
            self._sbar.showMessage(
                f"BDT Summary catalog partially imported: {row_count:,} latest row(s), {period_count:,} period(s), {len(failures):,} failed workbook(s)"
            )
            return
        QMessageBox.information(
            self,
            "BDT Summary Imported",
            f"Imported {row_count:,} latest row(s) across {period_count:,} period(s) from {len(in_paths):,} workbook(s) into the BDT Summary Catalog.\n\n"
            + "\n".join(in_paths),
        )
        self._sbar.showMessage(
            f"BDT Summary catalog imported: {row_count:,} row(s), {period_count:,} period(s), {len(in_paths):,} workbook(s)"
        )

    def _export_site_sheet_report(self):
        if not self._has_query_backed_alarm_data() and self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return
        if self._uploaded_site_df is None or not self._uploaded_site_keys:
            QMessageBox.information(
                self, "No Site Sheet", "Upload a site sheet first.")
            return

        if self._has_query_backed_alarm_data():
            filtered_alarms = alarm_store.query_alarms(
                self._build_alarm_query(limit=None, offset=0, ignore_sort=True)
            )
        else:
            filtered_alarms = self._apply_filters(self._full_df)

        try:
            report_df = build_site_alarm_report(
                self._uploaded_site_df,
                self._uploaded_site_id_column,
                filtered_alarms,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Site Sheet Error", str(exc))
            self._sbar.showMessage("Site sheet export failed")
            return

        default_name = f"site_alarm_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Site Alarm Report",
            os.path.join(os.path.dirname(self._uploaded_site_path or ""), default_name),
            "Excel Files (*.xlsx)",
        )
        if not out_path:
            self._sbar.showMessage("Site sheet export cancelled")
            return

        self._site_sheet_context = {
            "sheet_name": self._uploaded_site_sheet_name,
            "site_column": self._uploaded_site_id_column,
            "row_count": len(report_df),
            "alarm_count": len(filtered_alarms),
            "site_scope_count": len(self._uploaded_site_keys),
        }
        export_sheet_name = (self._uploaded_site_sheet_name or "Sheet1")[:31]
        self._site_sheet_export_thread = ExportThread(
            {export_sheet_name: report_df},
            out_path,
        )
        self._site_sheet_export_thread.progress.connect(
            lambda _v, m: self._sbar.showMessage(m))
        self._site_sheet_export_thread.finished.connect(self._on_site_sheet_export_done)
        self._site_sheet_export_thread.error.connect(self._on_site_sheet_export_error)
        self._site_sheet_export_thread.start()

    def _on_site_sheet_export_done(self, path: str):
        ctx = getattr(self, "_site_sheet_context", {}) or {}
        QMessageBox.information(
            self,
            "Site Report Exported",
            "Saved report with appended alarm columns.\n\n"
            f"Source sheet: {ctx.get('sheet_name', '--')}\n"
            f"Matched by column: {ctx.get('site_column', '--')}\n"
            f"Uploaded site scope: {ctx.get('site_scope_count', 0)}\n"
            f"Filtered alarms used: {ctx.get('alarm_count', 0)}\n"
            f"Rows exported: {ctx.get('row_count', 0)}\n"
            f"File: {path}",
        )
        self._sbar.showMessage(f"Site alarm report exported -> {path}")

    def _on_site_sheet_export_error(self, msg: str):
        QMessageBox.critical(self, "Site Report Export Failed", msg)
        self._sbar.showMessage("Site sheet export failed")

    def _export(self):
        if self._has_query_backed_alarm_data():
            export_df = alarm_store.query_alarms(
                self._build_alarm_query(limit=None, offset=0)
            )
        else:
            export_df = self._model.get_df()

        if export_df.empty:
            QMessageBox.information(
                self, "Nothing to Export",
                "Apply a search first or load data.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel",
            f"alarm_export_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            "Excel Files (*.xlsx)")
        if not fp:
            return
        self._ui.btn_export.setEnabled(False)
        self._sbar.showMessage("Exporting …")
        self._pending_export_row_count = len(export_df)
        self._export_thread = ExportThread(export_df, fp)
        self._export_thread.progress.connect(
            lambda v, m: self._sbar.showMessage(m))
        self._export_thread.finished.connect(self._on_export_done)
        self._export_thread.error.connect(self._on_export_error)
        self._export_thread.start()

    def _on_export_done(self, fp: str):
        self._ui.btn_export.setEnabled(True)
        row_count = int(getattr(self, "_pending_export_row_count", self._model.rowCount()) or 0)
        QMessageBox.information(
            self, "Export OK",
            f"Exported {row_count:,} records to:\n{fp}")
        self._sbar.showMessage(f"Exported → {fp}")

    def _on_export_error(self, msg: str):
        self._ui.btn_export.setEnabled(True)
        QMessageBox.critical(self, "Export Failed", msg)
        self._sbar.showMessage("Export failed")

    # ── Column filter popup slots ─────────────────────────────────
    def _on_header_clicked(self, logical_index: int):
        """Open the column filter popup under the clicked header section."""
        if self._full_df.empty and not self._has_query_backed_alarm_data():
            return
        cols = self._current_alarm_columns()
        if logical_index >= len(cols):
            return

        col_name = cols[logical_index]
        display_map = dict(DISPLAY_COLUMNS)
        display_name = display_map.get(
            col_name, col_name.replace("_", " ").title())

        # Gather unique display values from the *full* data
        if self._has_query_backed_alarm_data():
            facet_query = self._build_alarm_query(
                limit=None,
                offset=0,
                exclude_columns={col_name},
                ignore_sort=True,
            )
            unique = alarm_store.distinct_values(col_name, facet_query)
        else:
            unique = sorted(
                self._full_df[col_name].fillna("").astype(str).unique(),
                key=lambda x: x.lower() if x else "",
            )

        # Current selection for this column (None = all selected)
        selected = self._col_filters.get(col_name)

        popup = ColumnFilterPopup(
            col_name, display_name, unique, selected,
            self._sort_column, parent=self,
        )
        popup.applied.connect(self._on_col_filter_applied)

        # Position below the header section
        hdr = self._table.horizontalHeader()
        x = hdr.sectionViewportPosition(logical_index)
        header_pos = hdr.mapToGlobal(hdr.rect().bottomLeft())
        popup.move(header_pos.x() + x, header_pos.y())
        popup.show()

    def _sort_column(self, col_name: str, order):
        """Sort the table by the given column (called from popup)."""
        cols = self._current_alarm_columns()
        if col_name not in cols:
            return
        col_index = cols.index(col_name)
        self._table.horizontalHeader().setSortIndicator(col_index, order)
        if self._has_query_backed_alarm_data():
            self._page_offset = 0
            self._load_alarm_page(offset=0)
            return
        self._model.sort(col_index, order)

    def _on_col_filter_applied(self, col_name: str, selected):
        """Store the column filter and re-apply all filters."""
        if selected is None:
            self._col_filters.pop(col_name, None)
        else:
            self._col_filters[col_name] = selected
        self._search()
