"""
AlarmViewer — main window.
All UI construction and slot logic lives here.
"""

import getpass
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTableView, QFileDialog,
    QDateEdit, QGroupBox, QSplitter, QStatusBar, QComboBox,
    QMessageBox, QFrame, QHeaderView, QAbstractItemView,
    QProgressBar, QListWidget, QListWidgetItem,
    QCheckBox, QSpinBox, QMenu, QAction, QApplication,
    QDialog, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QShortcut,
    QGridLayout, QSizePolicy,
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QKeySequence, QTextCharFormat

try:
    from ..constants import (APP_NAME, APP_VERSION, ALL_INTERNAL_COLS,
                             COL_WIDTHS, DISPLAY_COLUMNS,
                             BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS)
    from ..styles import STYLE, STYLE_DARK, STYLE_LIGHT
    from .model import AlarmTableModel
    from .threads import (RestoreThread, LoaderThread, ExportThread,
                          BDTValidationThread, BackupTimeThread)
    from .dialogs import (ColumnFilterPopup, DailyReviewReportDialog,
                          AlarmIdConfigDialog, BackupTimeDialog,
                          FeatureFlagDialog)
    from .panels.search_panel import SearchPanel
    from .panels.left_panel import LeftPanel
    from .panels.bdt_validation_panel import BdtValidationPanel
    from .panels.bdt_detail_panel import BdtDetailPanel
    from ..core.filters import compute_date_mask, parse_manual_days
    from ..core.classify import classify_by_alarm_id, compute_site_down_flag
    from ..data.loaders import discover_alarm_files
    from ..data import state
    from ..data.sync import LocalSyncWorker
    from ..data.site_report import (
        read_site_sheet,
        build_site_alarm_report,
        collect_site_sheet_keys,
    )
    from ..bdt.parser import parse_bdt_file, BDTData, load_bdt_photos
    from ..bdt.validator import validate_bdt, ValidationResult
    from ..bdt.export import build_bdt_export_sheets
except ImportError:
    from alarm_app.constants import (APP_NAME, APP_VERSION, ALL_INTERNAL_COLS,
                                     COL_WIDTHS, DISPLAY_COLUMNS,
                                     BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS)
    from alarm_app.styles import STYLE, STYLE_DARK, STYLE_LIGHT
    from alarm_app.ui.model import AlarmTableModel
    from alarm_app.ui.threads import (RestoreThread, LoaderThread, ExportThread,
                                      BDTValidationThread, BackupTimeThread)
    from alarm_app.ui.dialogs import (ColumnFilterPopup, DailyReviewReportDialog,
                                      AlarmIdConfigDialog, BackupTimeDialog,
                                      FeatureFlagDialog)
    from alarm_app.ui.panels.search_panel import SearchPanel
    from alarm_app.ui.panels.left_panel import LeftPanel
    from alarm_app.ui.panels.bdt_validation_panel import BdtValidationPanel
    from alarm_app.ui.panels.bdt_detail_panel import BdtDetailPanel
    from alarm_app.core.filters import compute_date_mask, parse_manual_days
    from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
    from alarm_app.data.loaders import discover_alarm_files
    from alarm_app.data import state
    from alarm_app.data.sync import LocalSyncWorker
    from alarm_app.data.site_report import (
        read_site_sheet,
        build_site_alarm_report,
        collect_site_sheet_keys,
    )
    from alarm_app.bdt.parser import parse_bdt_file, BDTData, load_bdt_photos
    from alarm_app.bdt.validator import validate_bdt, ValidationResult
    from alarm_app.bdt.export import build_bdt_export_sheets


class AlarmViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_user = getpass.getuser() or "desktop"
        self._full_df    = pd.DataFrame()
        self._file_infos: list[dict] = []
        self._loader     = None
        self._col_filters: dict[str, set | None] = {}  # col -> selected values
        self._both_pd_active = False  # "Both P+D" filter flag
        self._uploaded_site_df: pd.DataFrame | None = None
        self._uploaded_site_sheet_name = ""
        self._uploaded_site_id_column = ""
        self._uploaded_site_keys: set[str] = set()
        self._uploaded_site_path = ""
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

        # Horizontal splitter: sidebar | content
        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.setHandleWidth(8)
        self._main_splitter.setStyleSheet(
            "QSplitter::handle { background:#1e1e2e; } "
            "QSplitter::handle:horizontal { width: 8px; }")

        # Left sidebar
        self._left_panel = LeftPanel(self)
        # Bridge: existing code references self._xxx etc.
        self._edit_dir = self._left_panel.edit_dir
        self._lbl_file_count = self._left_panel.lbl_file_count
        self._file_list = self._left_panel.file_list
        self._btn_load = self._left_panel.btn_load
        self._lbl_loaded = self._left_panel.lbl_loaded
        self._sidebar = self._left_panel
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

        # Tab 1: Alarms (existing content)
        alarms_tab = QWidget()
        al = QVBoxLayout(alarms_tab)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        self._search_panel = SearchPanel(self)
        # Bridge: existing code references self._xxx etc.
        self._edit_site = self._search_panel.edit_site
        self._cb_cat = self._search_panel.cb_cat
        self._cb_net = self._search_panel.cb_net
        self._cb_vnd = self._search_panel.cb_vnd
        self._chk_mindur = self._search_panel.chk_mindur
        self._spn_mindur = self._search_panel.spn_mindur
        self._chk_date = self._search_panel.chk_date
        self._chk_date_range = self._search_panel.chk_date_range
        self._d_from = self._search_panel.d_from
        self._d_to = self._search_panel.d_to
        self._lbl_from = self._search_panel.lbl_from
        self._lbl_to = self._search_panel.lbl_to
        self._date_quick_widgets = self._search_panel.date_quick_widgets
        self._chk_date_days = self._search_panel.chk_date_days
        self._lbl_day = self._search_panel.lbl_day
        self._d_day = self._search_panel.d_day
        self._btn_add_day = self._search_panel.btn_add_day
        self._edit_days = self._search_panel.edit_days
        self._btn_clear_days = self._search_panel.btn_clear_days
        self._btn_export = self._search_panel.btn_export
        self._btn_backup = self._search_panel.btn_backup
        self._btn_site_sheet = self._search_panel.btn_site_sheet
        self._btn_site_report = self._search_panel.btn_site_report
        self._btn_both = self._search_panel.btn_both
        self._stats = self._search_panel.stats
        # Deferred: trigger date filter state now that bridge refs are assigned
        self._toggle_date_filter(self._chk_date.isChecked())
        splitter.addWidget(self._search_panel)
        splitter.addWidget(self._make_table())
        splitter.setSizes([130, 800])
        al.addWidget(splitter, 1)
        self._tabs.addTab(alarms_tab, "Alarms")

        # Tab 2: Test Validation
        self._bdt_validation_panel = BdtValidationPanel(self)
        # Bridge: existing code references self._xxx etc.
        self._spn_tolerance = self._bdt_validation_panel.spn_tolerance
        self._spn_health = self._bdt_validation_panel.spn_health
        self._bdt_search = self._bdt_validation_panel.bdt_search
        self._bdt_table = self._bdt_validation_panel.bdt_table
        self._bdt_splitter = self._bdt_validation_panel.bdt_splitter
        self._bdt_summary = self._bdt_validation_panel.bdt_summary
        self._btn_bdt_export = self._bdt_validation_panel.btn_bdt_export
        self._btn_bdt_report = self._bdt_validation_panel.btn_bdt_report
        # Wire the detail panel into the validation tab splitter
        self._bdt_detail_panel_obj = BdtDetailPanel(self)
        self._bdt_detail_panel = self._bdt_detail_panel_obj
        self._bdt_validation_panel.set_detail_panel(self._bdt_detail_panel)
        self._bdt_validation_panel.row_selected.connect(self._bdt_detail_panel_obj.populate)
        self._tabs.addTab(self._bdt_validation_panel, "Test Validation")

        rl.addWidget(self._tabs, 1)

        self._main_splitter.addWidget(right_wrap)
        self._main_splitter.setSizes([260, 1420])
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setCollapsible(0, True)
        self._main_splitter.setCollapsible(1, True)
        self._main_splitter.splitterMoved.connect(self._on_main_splitter_moved)
        self._apply_sidebar_constraints()

        main.addWidget(self._main_splitter)

        # Status bar
        self._sbar = QStatusBar()
        self.setStatusBar(self._sbar)
        self._sbar.showMessage(
            "Browse to a directory, then scan for alarm files.")

        self._prog = QProgressBar()
        self._prog.setFixedSize(260, 4)
        self._prog.setVisible(False)
        self._sbar.addPermanentWidget(self._prog)

    # ── top header strip ─────────────────────────────────────────
    def _make_header_strip(self):
        w = QWidget(); w.setFixedHeight(48)
        l = QHBoxLayout(w)
        l.setContentsMargins(20, 0, 20, 0)
        l.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(
            "color:#89b4fa; font-size:14px; background:transparent;")
        l.addWidget(dot)

        name = QLabel(APP_NAME)
        name.setObjectName("lbl_app_name")
        l.addWidget(name)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("lbl_app_ver")
        l.addWidget(ver)

        btn_review = QPushButton("Daily Report")
        btn_review.setObjectName("btn_dir")
        btn_review.clicked.connect(
            lambda: DailyReviewReportDialog(self).exec_())
        l.addWidget(btn_review)

        l.addStretch()

        btn_config = QPushButton("Configure Alarm IDs")
        btn_config.setObjectName("btn_dir")
        btn_config.clicked.connect(self._show_alarm_id_config)
        l.addWidget(btn_config)

        btn_flags = QPushButton("Feature Flags")
        btn_flags.setObjectName("btn_dir")
        btn_flags.clicked.connect(self._show_feature_flags)
        l.addWidget(btn_flags)

        self._btn_theme = QPushButton("Theme: Auto")
        self._btn_theme.setObjectName("btn_theme")
        self._btn_theme.clicked.connect(self._toggle_theme)
        l.addWidget(self._btn_theme)

        # Skip photos toggle
        self._chk_skip_photos = QCheckBox("Skip Photos")
        self._chk_skip_photos.setObjectName("chk_skip_photos")
        self._chk_skip_photos.setChecked(self._skip_photos)
        self._chk_skip_photos.toggled.connect(self._toggle_skip_photos)
        l.addWidget(self._chk_skip_photos)

        self._lbl_count = QLabel("")
        self._lbl_count.setObjectName("lbl_green")
        l.addWidget(self._lbl_count)

        return w

    # ── table ────────────────────────────────────────────────────
    def _make_table(self):
        w = QWidget(); vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)

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
        hdr = self._table.horizontalHeader()
        sort_section = hdr.sortIndicatorSection()
        sort_order = int(hdr.sortIndicatorOrder())

        # Serialise col_filters: convert sets to lists for JSON
        col_filters_json = {}
        for col, vals in self._col_filters.items():
            col_filters_json[col] = sorted(vals) if vals is not None else None

        geo = self.geometry()
        file_paths = [info["path"] for info in self._file_infos]
        d = {
            "directory": self._edit_dir.text(),
            "file_paths": file_paths,
            "file_hashes": state.compute_file_hashes(file_paths),
            "sync_on": self._sync_flags.get("sync_on", False),
            "cloud_read_on": self._sync_flags.get("cloud_read_on", False),
            "bootstrap_on": self._sync_flags.get("bootstrap_on", False),
            "site_filter": self._edit_site.text(),
            "date_enabled": self._chk_date.isChecked(),
            "date_use_range": self._chk_date_range.isChecked(),
            "date_use_days": self._chk_date_days.isChecked(),
            "date_from": self._d_from.date().toString("yyyy-MM-dd"),
            "date_to": self._d_to.date().toString("yyyy-MM-dd"),
            "date_day": self._d_day.date().toString("yyyy-MM-dd"),
            "date_days": self._edit_days.text().strip(),
            "category": self._cb_cat.currentIndex(),
            "network": self._cb_net.currentIndex(),
            "vendor": self._cb_vnd.currentIndex(),
            "dur_enabled": self._chk_mindur.isChecked(),
            "dur_minutes": self._spn_mindur.value(),
            "both_pd": self._both_pd_active,
            "col_filters": col_filters_json,
            "sort_column": sort_section if sort_section >= 0 else None,
            "sort_order": sort_order,
            "window_geometry": [geo.x(), geo.y(), geo.width(), geo.height()],
            "ui_zoom_pct": self._app_zoom_pct,
            "theme_mode": self._theme_mode,
        }
        state.save_state(d)

    def _restore_ui_state(self):
        """Restore UI settings from state.json and kick off cache load."""
        s = state.load_state()
        if s is None:
            self._sync_flags = state.load_feature_flags({})
            return
        self._sync_flags = state.load_feature_flags(s)

        # Window geometry
        geo = s.get("window_geometry")
        if geo and len(geo) == 4:
            self.setGeometry(*geo)
        if "ui_zoom_pct" in s:
            self._set_app_zoom(s["ui_zoom_pct"])

        if "theme_mode" in s:
            self._theme_mode = s["theme_mode"]
            self._update_theme_button_label()

        # Directory & site filter
        if s.get("directory"):
            self._edit_dir.setText(s["directory"])
        if s.get("site_filter"):
            self._edit_site.setText(s["site_filter"])

        # Date filter
        if "date_enabled" in s:
            self._chk_date.setChecked(s["date_enabled"])
        if s.get("date_from"):
            d = QDate.fromString(s["date_from"], "yyyy-MM-dd")
            if d.isValid():
                self._d_from.setDate(d)
        if s.get("date_to"):
            d = QDate.fromString(s["date_to"], "yyyy-MM-dd")
            if d.isValid():
                self._d_to.setDate(d)
        use_range = s.get("date_use_range")
        use_days = s.get("date_use_days")
        if use_range is not None:
            self._chk_date_range.setChecked(use_range)
        if use_days is not None:
            self._chk_date_days.setChecked(use_days)
        if use_range is None and use_days is None and "day_only" in s:
            self._chk_date_range.setChecked(not s["day_only"])
            self._chk_date_days.setChecked(s["day_only"])
        if s.get("date_day"):
            d = QDate.fromString(s["date_day"], "yyyy-MM-dd")
            if d.isValid():
                self._d_day.setDate(d)
        if s.get("date_days"):
            self._edit_days.setText(str(s["date_days"]))
        elif s.get("day_only") and s.get("date_day"):
            self._edit_days.setText(str(s["date_day"]))
        self._toggle_date_mode_controls()

        # Combo filters
        if "category" in s:
            self._cb_cat.setCurrentIndex(s["category"])
        if "network" in s:
            self._cb_net.setCurrentIndex(s["network"])
        if "vendor" in s:
            self._cb_vnd.setCurrentIndex(s["vendor"])

        # Duration filter
        if "dur_enabled" in s:
            self._chk_mindur.setChecked(s["dur_enabled"])
        if "dur_minutes" in s:
            self._spn_mindur.setValue(s["dur_minutes"])

        # Both P+D filter
        if s.get("both_pd"):
            self._both_pd_active = True
            self._btn_both.setStyleSheet(
                "QPushButton { background:#4a3018; color:#fab387; "
                "border:2px solid #fab387; border-radius:6px; "
                "padding:7px 16px; font-weight:700; font-size:12px; "
                "min-width:72px; }")

        # Column filters — convert lists back to sets
        cf = s.get("col_filters", {})
        for col, vals in cf.items():
            self._col_filters[col] = set(vals) if vals is not None else None

        # Stash sort info for after data loads
        self._pending_sort_col = s.get("sort_column")
        self._pending_sort_order = s.get("sort_order", 0)

        # Stash file_paths for reference
        self._restored_file_paths = s.get("file_paths", [])

        # Kick off background data restore (DB preferred, Parquet fallback)
        from alarm_app.db.engine import DB_PATH as _db_path
        if state.ALARM_DB_FILE.exists() or state.CACHE_FILE.exists() or _db_path.exists():
            self._sbar.showMessage("Restoring previous session...")
            self._restore_thread = RestoreThread()
            self._restore_thread.finished.connect(self._on_cache_restored)
            self._restore_thread.error.connect(
                lambda msg: self._sbar.showMessage("Cache restore failed — start fresh"))
            self._restore_thread.start()

    def _on_cache_restored(self, df):
        """Called when background Parquet load completes."""
        if df is None or df.empty or "site_id" not in df.columns:
            self._sbar.showMessage("No cached data found — start fresh")
            state.clear_cache()
            return

        # Check if source files changed since cache was saved
        saved_state = state.load_state() or {}
        saved_hashes = saved_state.get("file_hashes", {})
        file_paths = getattr(self, "_restored_file_paths", [])
        if state.files_changed(saved_hashes, file_paths):
            self._sbar.showMessage(
                "Source files changed — reloading from disk…")
            state.clear_cache()
            # Populate file list and auto-load
            directory = self._edit_dir.text().strip()
            if directory and os.path.isdir(directory):
                self._scan()
                self._file_list.selectAll()
                self._load()
            return

        # Ensure datetime columns are proper dtype
        for col in ("occurred_on", "cleared_on"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")

        alarm_ids = state.load_alarm_ids()
        df = classify_by_alarm_id(df, alarm_ids)
        df = compute_site_down_flag(df)
        self._full_df = df

        # Rebuild file_infos from restored paths so close-save works
        self._file_infos = [
            {"path": p, "filename": os.path.basename(p)}
            for p in file_paths
        ]

        self._lbl_loaded.setText(f"✓  {len(df):,} records (restored)")
        self._lbl_loaded.setStyleSheet("color:#a6e3a1; font-size:11px;")

        # Apply saved filters and populate
        view = self._apply_filters(df)
        self._populate(view)
        self._refresh_stats(view)
        self._lbl_count.setText(
            f"Showing  {len(view):,}  of  {len(df):,} records")

        # Restore sort indicator
        sort_col = getattr(self, "_pending_sort_col", None)
        if sort_col is not None and sort_col >= 0:
            order = (Qt.AscendingOrder if getattr(self, "_pending_sort_order", 0) == 0
                     else Qt.DescendingOrder)
            self._model.sort(sort_col, order)
            self._table.horizontalHeader().setSortIndicator(sort_col, order)

        # Populate sidebar file list so it's not blank after restore
        directory = self._edit_dir.text().strip()
        if directory and os.path.isdir(directory):
            self._scan()

        self._sbar.showMessage(
            f"Session restored — {len(view):,} of {len(df):,} records")

        # Restore BDT validation results from DB
        self._restore_bdt_results()

    def _restore_bdt_results(self):
        """Load previous BDT validation results from the DB into the UI."""
        try:
            from alarm_app.db.engine import create_engine as _ce, init_db as _idb, get_session_factory as _gsf
            from alarm_app.db.repos.pm_repo import load_all_validation_results
            engine = _ce()
            _idb(engine)
            session = _gsf(engine)()
            try:
                results = load_all_validation_results(session)
            finally:
                session.close()

            if not results:
                return

            self._bdt_results = results
            self._bdt_by_site = {}
            for vr in results:
                if vr.site_code:
                    key = vr.site_code.strip().upper()
                    self._bdt_by_site.setdefault(key, []).append(
                        vr.bdt_data if vr.bdt_data else vr)

            # Populate the validation table if the panel exists
            if hasattr(self, "_bdt_validation_panel"):
                self._bdt_validation_panel.set_results(results)

            self._sbar.showMessage(
                f"Session restored — {len(self._full_df):,} alarms, "
                f"{len(results)} BDT validations")
        except Exception:
            pass  # BDT restore is best-effort

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
                    from alarm_app.data.sync_client import http_send_batch
                    sender = http_send_batch
                except ImportError:
                    pass
            self._sync_worker = LocalSyncWorker(send_batch=sender)
            self._sync_worker.start()
        except Exception:
            self._sync_worker = None

    def _run_bootstrap_if_enabled(self):
        if not self._sync_flags.get("bootstrap_on"):
            return
        from PyQt5.QtCore import QThread

        class _BootstrapThread(QThread):
            def run(self_thread):
                try:
                    from alarm_app.data.bootstrap import run_bootstrap
                    from alarm_app.db.engine import (
                        create_engine,
                        init_db,
                        get_session_factory,
                    )

                    engine = create_engine()
                    init_db(engine)
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
            pass

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
            return dict(
                bg="#1a1a2a", border="#2a2a3e", text="#cdd6f4",
                muted="#6c7086", warn="#fab387", blue="#89b4fa",
                green="#a6e3a1", red="#f38ba8",
                stay_bg="#1a2744", stay_border="#2a4070", stay_hover="#1f3258",
                exit_bg="#3d1e2c", exit_border="#5a2030", exit_hover="#4d2838",
            )
        return dict(
            bg="#e6e9ef", border="#ccd0da", text="#4c4f69",
            muted="#6c6f85", warn="#fe640b", blue="#1e66f5",
            green="#40a02b", red="#d20f39",
            stay_bg="#d5e0fc", stay_border="#a8bff8", stay_hover="#c0d0fa",
            exit_bg="#f5d5da", exit_border="#e8a0b0", exit_hover="#f0c0c8",
        )

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

        # Message adapts to whether data is loaded
        if not self._full_df.empty:
            n_rec = len(self._full_df)
            n_sites = (self._full_df["site_id"].nunique()
                       if "site_id" in self._full_df.columns else 0)
            n_files = len(self._file_infos)
            msg = (
                f"<span style='color:{c['muted']};'>"
                f"You currently have data in memory:</span><br><br>"
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

        # Save session state before closing
        try:
            self._save_ui_state()
            if not self._full_df.empty:
                state.save_dataframe(self._full_df)
        except Exception as e:
            print(f"[AlarmViewer] save error: {e}")

        event.accept()

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

    def _populate(self, df: pd.DataFrame):
        ordered = [c for c in ALL_INTERNAL_COLS if c in df.columns]
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

    def _show_alarm_id_config(self):
        dlg = AlarmIdConfigDialog(parent=self)
        dlg.saved.connect(self._reclassify_alarms)
        dlg.exec_()

    def _reclassify_alarms(self):
        """Re-classify all loaded alarms using current alarm ID config."""
        if self._full_df.empty:
            return
        alarm_ids = state.load_alarm_ids()
        self._full_df = classify_by_alarm_id(self._full_df, alarm_ids)
        self._full_df = compute_site_down_flag(self._full_df)
        view = self._apply_filters(self._full_df)
        self._populate(view)
        self._refresh_stats(view)
        self._lbl_count.setText(
            f"Showing  {len(view):,}  of  {len(self._full_df):,} records")
        self._sbar.showMessage("Alarms re-classified by alarm ID config")

    def _reset_date_range(self, df: pd.DataFrame):
        if "occurred_on" in df.columns:
            mn = df["occurred_on"].min()
            mx = df["occurred_on"].max()
            if pd.notna(mn):
                qmn = QDate(mn.year, mn.month, mn.day)
                self._d_from.setMinimumDate(qmn)
                self._d_day.setMinimumDate(qmn)
                self._d_from.setDate(qmn)
            if pd.notna(mx):
                qmx = QDate(mx.year, mx.month, mx.day)
                self._d_to.setMaximumDate(qmx)
                self._d_day.setMaximumDate(qmx)
                self._d_to.setDate(qmx)
                self._d_day.setDate(qmx)

    def _toggle_date_filter(self, enabled: bool):
        self._chk_date_range.setEnabled(enabled)
        self._chk_date_days.setEnabled(enabled)
        self._toggle_date_mode_controls()

    def _toggle_date_mode_controls(self):
        date_enabled = self._chk_date.isChecked()
        use_range = date_enabled and self._chk_date_range.isChecked()
        use_days = date_enabled and self._chk_date_days.isChecked()
        self._lbl_from.setEnabled(use_range)
        self._d_from.setEnabled(use_range)
        self._lbl_to.setEnabled(use_range)
        self._d_to.setEnabled(use_range)
        for widget in self._date_quick_widgets:
            widget.setEnabled(use_range)
        self._lbl_day.setEnabled(use_days)
        self._d_day.setEnabled(use_days)
        self._btn_add_day.setEnabled(use_days)
        self._edit_days.setEnabled(use_days)
        self._btn_clear_days.setEnabled(use_days)

    def _set_manual_days_text(self, days: set[pd.Timestamp]):
        ordered = sorted(days)
        self._edit_days.setText(
            ", ".join(d.strftime("%Y-%m-%d") for d in ordered))

    def _add_selected_day(self):
        days, invalid = parse_manual_days(self._edit_days.text())
        days.add(pd.Timestamp(self._d_day.date().toPyDate()).normalize())
        self._set_manual_days_text(days)
        if invalid:
            self._sbar.showMessage("Ignored invalid day value(s) while adding day", 2500)

    def _clear_selected_days(self):
        self._edit_days.clear()

    def _quick_date(self, days: int):
        """Set date range to a quick preset. days=-1 means 'All'."""
        self._chk_date.setChecked(True)
        if not self._chk_date_range.isChecked():
            self._chk_date_range.setChecked(True)
        today = QDate.currentDate()
        if days < 0 and not self._full_df.empty:
            self._reset_date_range(self._full_df)
        elif days == 0:
            self._d_from.setDate(today)
            self._d_to.setDate(today)
        else:
            self._d_from.setDate(today.addDays(-days))
            self._d_to.setDate(today)

    # ── sidebar toggle (Cmd+B) ──────────────────────────────────
    def _toggle_sidebar(self):
        sizes = self._main_splitter.sizes()
        if sizes[0] > 0:
            self._sidebar_width = sizes[0]
            self._main_splitter.setSizes([0, sizes[0] + sizes[1]])
        else:
            max_open = self._max_sidebar_width()
            target = max(1, min(self._sidebar_width or 260, max_open))
            total = max(1, sizes[0] + sizes[1])
            target = min(target, total - 1)
            self._main_splitter.setSizes([target, total - target])

    def _min_sidebar_width(self) -> int:
        return 1

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
        left, right = sizes
        total = max(1, left + right)
        if left > max_open:
            self._main_splitter.setSizes([max_open, total - max_open])
            self._sidebar_width = max_open
        elif left > 0:
            self._sidebar_width = left

    def _on_main_splitter_moved(self, _pos: int, _index: int):
        self._apply_sidebar_constraints()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_main_splitter"):
            self._apply_sidebar_constraints()

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
        labels = {"auto": "Theme: Auto", "dark": "Theme: Dark", "light": "Theme: Light"}
        self._btn_theme.setText(labels.get(self._theme_mode, "Theme: Auto"))

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
        if hasattr(self, "_bdt_table"):
            self._bdt_table.verticalHeader().setDefaultSectionSize(row_h)
        if hasattr(self, "_main_splitter"):
            self._apply_sidebar_constraints()
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
            self._edit_dir.text() or str(Path.home()))
        if d:
            self._edit_dir.setText(d)
            self._scan()

    def _scan(self):
        directory = self._edit_dir.text().strip()
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

        self._file_infos = discover_alarm_files(directory)
        self._file_list.clear()

        if not self._file_infos:
            self._lbl_file_count.setText(
                "❌  No .csv / .xlsx files found")
            self._lbl_file_count.setStyleSheet(
                "color:#f38ba8; font-size:11px;")
            self._btn_load.setEnabled(False)
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
            self._file_list.addItem(item)

        self._file_list.selectAll()

        n = len(self._file_infos)
        self._lbl_file_count.setText(f"  {n} file{'s' if n != 1 else ''}")
        self._lbl_file_count.setStyleSheet("color:#a6e3a1; font-size:11px;")
        self._btn_load.setEnabled(True)
        self._sbar.showMessage(
            f"Found {n} file(s) — select files to load, "
            "then click 'Load Selected Files'.")

    def _load(self):
        selected = [
            self._file_list.item(i).data(Qt.UserRole)
            for i in range(self._file_list.count())
            if self._file_list.item(i).isSelected()
        ]
        if not selected:
            QMessageBox.warning(
                self, "Nothing Selected",
                "Select at least one file from the list.")
            return
        self._btn_load.setEnabled(False)
        self._prog.setVisible(True)
        self._prog.setValue(0)
        self._sbar.showMessage(f"Loading {len(selected)} file(s) …")
        self._loader = LoaderThread(selected)
        self._loader.progress.connect(
            lambda v, m: (
                self._prog.setValue(v),
                self._sbar.showMessage(m),
            ))
        self._loader.finished.connect(self._on_loaded)
        self._loader.error.connect(self._on_error)
        self._loader.start()

    def _on_loaded(self, df: pd.DataFrame, msg: str):
        # Classify by alarm ID config
        alarm_ids = state.load_alarm_ids()
        df = classify_by_alarm_id(df, alarm_ids)
        df = compute_site_down_flag(df)
        self._full_df = df
        self._btn_load.setEnabled(True)
        self._prog.setVisible(False)
        self._sbar.showMessage(msg)
        self._lbl_loaded.setText(
            f"✓  {len(df):,} records in memory")
        self._lbl_loaded.setStyleSheet(
            "color:#a6e3a1; font-size:11px;")
        self._refresh_stats(df)
        self._reset_date_range(df)

        # Respect the full current UI filter state immediately after load.
        view = self._apply_filters(df)
        self._populate(view)
        self._refresh_stats(view)
        n = len(view)
        self._lbl_count.setText(
            f"Showing  {n:,}  of  {len(df):,} records")

    def _on_error(self, msg: str):
        self._btn_load.setEnabled(True)
        self._prog.setVisible(False)
        QMessageBox.critical(self, "Load Error", msg)
        self._sbar.showMessage(f"Error: {msg}")

    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply current UI filters to *df* and return the subset."""
        if self._uploaded_site_keys and "site_id" in df.columns:
            site_keys = df["site_id"].map(lambda value: "".join(ch for ch in str(value).strip().upper() if ch.isalnum()) if pd.notna(value) else "")
            df = df[site_keys.isin(self._uploaded_site_keys)]

        # Site ID — supports multiple comma-separated terms
        raw = self._edit_site.text().strip()
        if raw:
            terms = [t.strip() for t in raw.split(",") if t.strip()]
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
        if self._chk_date.isChecked() and "occurred_on" in df.columns:
            use_range = self._chk_date_range.isChecked()
            use_days = self._chk_date_days.isChecked()

            manual_days: set[pd.Timestamp] = set()
            if use_days:
                manual_days, invalid = parse_manual_days(
                    self._edit_days.text())
                if invalid:
                    self._sbar.showMessage(
                        "Ignored invalid day value(s) in specific days filter",
                        2500)

            mask = compute_date_mask(
                df["occurred_on"],
                use_range=use_range,
                from_date=self._d_from.date().toPyDate(),
                to_date=self._d_to.date().toPyDate(),
                use_days=use_days,
                manual_days=manual_days,
            )
            if mask is not None:
                df = df[mask]

        # Category
        cat = self._cb_cat.currentText()
        if cat != "All" and "alarm_category" in df.columns:
            df = df[df["alarm_category"] == cat]

        # Network
        net = self._cb_net.currentText()
        if net != "All" and "network_type" in df.columns:
            df = df[df["network_type"].astype(str) == net]

        # Vendor
        vnd = self._cb_vnd.currentText()
        if vnd != "All" and "vendor" in df.columns:
            df = df[df["vendor"].astype(str).str.upper()
                    == vnd.upper()]

        # Duration ≥ N min filter
        if self._chk_mindur.isChecked() and "_duration_secs" in df.columns:
            df = df[df["_duration_secs"] >= self._spn_mindur.value() * 60]

        # Per-column filters (from header popup)
        for col, allowed in self._col_filters.items():
            if allowed is not None and col in df.columns:
                df = df[df[col].fillna("").astype(str).isin(allowed)]

        # Both Power + Down: keep only sites that have both categories
        # Check against _full_df so other filters don't hide categories
        if (self._both_pd_active
                and "site_id" in df.columns
                and "alarm_category" in self._full_df.columns):
            full = self._full_df
            cats_per_site = full.groupby("site_id")["alarm_category"].apply(set)
            both_sites = cats_per_site[
                cats_per_site.apply(
                    lambda s: "Power" in s and "Down" in s)
            ].index
            df = df[df["site_id"].isin(both_sites)]

        return df

    def _search(self):
        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data",
                "Please load alarm data first.")
            return

        df = self._apply_filters(self._full_df)

        self._populate(df)
        self._refresh_stats(df)
        n = len(df)
        self._lbl_count.setText(
            f"Showing  {n:,}  of  {len(self._full_df):,} records")

        raw = self._edit_site.text().strip()
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
        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return
        self._both_pd_active = True
        self._btn_both.setStyleSheet(
            "QPushButton { background:#4a3018; color:#fab387; "
            "border:2px solid #fab387; border-radius:6px; "
            "padding:7px 16px; font-weight:700; font-size:12px; "
            "min-width:72px; }")
        self._search()

    def _clear_filters(self):
        self._edit_site.clear()
        self._cb_cat.setCurrentIndex(0)
        self._cb_net.setCurrentIndex(0)
        self._cb_vnd.setCurrentIndex(0)
        self._chk_date.setChecked(True)
        self._chk_date_range.setChecked(True)
        self._chk_date_days.setChecked(False)
        self._edit_days.clear()
        self._both_pd_active = False
        self._btn_both.setStyleSheet("")  # reset to default theme style
        self._col_filters.clear()
        # Reset sort indicator
        hdr = self._table.horizontalHeader()
        hdr.setSortIndicator(-1, Qt.AscendingOrder)
        if not self._full_df.empty:
            self._reset_date_range(self._full_df)
            # Restore original load order
            self._full_df = self._full_df.sort_index().reset_index(drop=True)
            df = self._full_df
            if self._chk_mindur.isChecked() and "_duration_secs" in df.columns:
                df = df[df["_duration_secs"] >= self._spn_mindur.value() * 60]
            self._populate(df)
            self._refresh_stats(df)
            self._lbl_count.setText(
                f"Showing  {len(df):,}  of  "
                f"{len(self._full_df):,} records")
        self._sbar.showMessage("Filters cleared")

    def _show_backup_times(self):
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
        self._btn_backup.setEnabled(False)
        self._sbar.showMessage("Computing backup times …")
        self._bt_thread = BackupTimeThread(filtered.copy())
        self._bt_thread.progress.connect(
            lambda v, m: self._sbar.showMessage(m))
        self._bt_thread.finished.connect(self._on_bt_done)
        self._bt_thread.error.connect(self._on_bt_error)
        self._bt_thread.start()

    def _on_bt_done(self, result, err: str):
        self._btn_backup.setEnabled(True)
        if err:
            QMessageBox.warning(self, "Backup Time", err)
            self._sbar.showMessage("Backup time: " + err)
            return
        self._sbar.showMessage(
            f"Backup time analysis: {len(result):,} pairs found")
        dlg = BackupTimeDialog(result, parent=self)
        dlg.exec_()

    def _on_bt_error(self, msg: str):
        self._btn_backup.setEnabled(True)
        QMessageBox.critical(self, "Backup Time Error", msg)
        self._sbar.showMessage("Backup time computation failed")

    def _upload_site_sheet(self):
        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return

        in_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Site Sheet",
            self._edit_dir.text().strip() or str(Path.home()),
            "Spreadsheet Files (*.xlsx *.xls *.csv)",
        )
        if not in_path:
            return

        try:
            self._btn_site_sheet.setEnabled(False)
            self._sbar.showMessage("Reading site sheet …")
            site_df, sheet_name, site_col = read_site_sheet(in_path, self._full_df)
            site_keys = collect_site_sheet_keys(site_df, site_col)
            if not site_keys:
                raise ValueError("The uploaded site sheet does not contain any usable site IDs.")
        except Exception as exc:
            self._btn_site_sheet.setEnabled(True)
            QMessageBox.critical(self, "Site Sheet Error", str(exc))
            self._sbar.showMessage("Site sheet upload failed")
            return

        self._btn_site_sheet.setEnabled(True)
        self._uploaded_site_df = site_df.copy()
        self._uploaded_site_sheet_name = sheet_name
        self._uploaded_site_id_column = site_col
        self._uploaded_site_keys = site_keys
        self._uploaded_site_path = in_path
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

    def _export_site_sheet_report(self):
        if self._full_df.empty:
            QMessageBox.information(
                self, "No Data", "Load alarm data first.")
            return
        if self._uploaded_site_df is None or not self._uploaded_site_keys:
            QMessageBox.information(
                self, "No Site Sheet", "Upload a site sheet first.")
            return

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
        if self._model.rowCount() == 0:
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
        self._btn_export.setEnabled(False)
        self._sbar.showMessage("Exporting …")
        self._export_thread = ExportThread(self._model.get_df(), fp)
        self._export_thread.progress.connect(
            lambda v, m: self._sbar.showMessage(m))
        self._export_thread.finished.connect(self._on_export_done)
        self._export_thread.error.connect(self._on_export_error)
        self._export_thread.start()

    def _on_export_done(self, fp: str):
        self._btn_export.setEnabled(True)
        QMessageBox.information(
            self, "Export OK",
            f"Exported {self._model.rowCount():,} records to:\n{fp}")
        self._sbar.showMessage(f"Exported → {fp}")

    def _on_export_error(self, msg: str):
        self._btn_export.setEnabled(True)
        QMessageBox.critical(self, "Export Failed", msg)
        self._sbar.showMessage("Export failed")

    # ── Column filter popup slots ─────────────────────────────────
    def _on_header_clicked(self, logical_index: int):
        """Open the column filter popup under the clicked header section."""
        if self._full_df.empty:
            return
        cols = [c for c in ALL_INTERNAL_COLS if c in self._full_df.columns]
        if logical_index >= len(cols):
            return

        col_name = cols[logical_index]
        display_map = dict(DISPLAY_COLUMNS)
        display_name = display_map.get(
            col_name, col_name.replace("_", " ").title())

        # Gather unique display values from the *full* data
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
        cols = [c for c in ALL_INTERNAL_COLS if c in self._full_df.columns]
        if col_name not in cols:
            return
        col_index = cols.index(col_name)
        self._model.sort(col_index, order)
        self._table.horizontalHeader().setSortIndicator(col_index, order)

    def _on_col_filter_applied(self, col_name: str, selected):
        """Store the column filter and re-apply all filters."""
        if selected is None:
            self._col_filters.pop(col_name, None)
        else:
            self._col_filters[col_name] = selected
        self._search()
