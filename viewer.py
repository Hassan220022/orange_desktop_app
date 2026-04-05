"""
AlarmViewer — main window.
All UI construction and slot logic lives here.
"""

import os
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
    QDialog, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QGridLayout,
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPixmap, QTextCharFormat, QDesktopServices

try:
    from .constants import (APP_NAME, APP_VERSION, ALL_INTERNAL_COLS,
                            COL_WIDTHS, DISPLAY_COLUMNS,
                            BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS)
    from .styles import STYLE
    from .models import AlarmTableModel
    from .parsers import discover_alarm_files, LoaderThread, ExportThread, classify_by_alarm_id, compute_site_down_flag, BDTValidationThread
    from .backup_time import BackupTimeDialog, BackupTimeThread
    from .bdt_parser import parse_bdt_file, BDTData, load_bdt_photos
    from .bdt_validator import validate_bdt, ValidationResult
    from .bdt_export import build_bdt_export_sheets
    from . import state
except ImportError:
    from constants import (APP_NAME, APP_VERSION, ALL_INTERNAL_COLS,
                           COL_WIDTHS, DISPLAY_COLUMNS,
                           BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS)
    from styles import STYLE
    from models import AlarmTableModel
    from parsers import discover_alarm_files, LoaderThread, ExportThread, classify_by_alarm_id, compute_site_down_flag, BDTValidationThread
    from backup_time import BackupTimeDialog, BackupTimeThread
    from bdt_parser import parse_bdt_file, BDTData, load_bdt_photos
    from bdt_validator import validate_bdt, ValidationResult
    from bdt_export import build_bdt_export_sheets
    import state



class ColumnFilterPopup(QDialog):
    """Google-Sheets-style column filter popup with sort + value checkboxes."""

    applied = pyqtSignal(str, object)  # (column_name, selected_values_set_or_None)

    _STYLE = """
    QDialog { background:#1a1a2a; border:1px solid #2a2a3e; border-radius:8px; }
    QLabel { color:#cdd6f4; background:transparent; }
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
    QScrollArea { border:none; background:transparent; }
    """

    def __init__(self, col_name: str, display_name: str,
                 unique_values: list[str],
                 selected: set | None,
                 sort_callback, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setStyleSheet(self._STYLE)
        self._col = col_name
        self._sort_cb = sort_callback
        self._checks: list[tuple[QCheckBox, str]] = []
        self.setFixedWidth(280)
        self.setMaximumHeight(440)
        self._build(display_name, unique_values, selected)

    def _build(self, display_name, values, selected):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # ── Sort buttons ──
        sort_row = QHBoxLayout(); sort_row.setSpacing(6)
        btn_asc = QPushButton("\u2191 Ascending")
        btn_asc.setObjectName("btn_sort_asc")
        btn_asc.clicked.connect(lambda: (self._sort_cb(self._col, Qt.AscendingOrder), self.close()))
        btn_desc = QPushButton("\u2193 Descending")
        btn_desc.setObjectName("btn_sort_desc")
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
        btn_apply.clicked.connect(self._apply)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.close)
        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("btn_clear")
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


class RestoreThread(QThread):
    """Load cached DataFrame from Parquet in a background thread."""
    finished = pyqtSignal(object)  # DataFrame or None
    error = pyqtSignal(str)

    def run(self):
        try:
            df = state.load_dataframe()
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))


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


class AlarmViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self._full_df    = pd.DataFrame()
        self._file_infos: list[dict] = []
        self._loader     = None
        self._col_filters: dict[str, set | None] = {}  # col -> selected values
        self._both_pd_active = False  # "Both P+D" filter flag
        self._last_bdt_health_pct: float | None = None
        self._build_ui()
        self.setStyleSheet(STYLE)
        self._restore_ui_state()

    # ── UI construction ──────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.setMinimumSize(1440, 820)
        self.resize(1680, 980)

        root = QWidget(); self.setCentralWidget(root)
        root.setObjectName("root")
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Horizontal splitter: sidebar | content
        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.setHandleWidth(3)
        self._main_splitter.setStyleSheet(
            "QSplitter::handle { background:#1e1e2e; }")

        # Left sidebar
        self._sidebar = self._make_left_panel()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setMinimumWidth(50)
        self._sidebar.setMaximumWidth(500)
        self._main_splitter.addWidget(self._sidebar)
        self._sidebar_width = 260  # remembered width for toggle

        # Right content area
        right_wrap = QWidget()
        right_wrap.setObjectName("right_wrap")
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

        # Tab 1: Alarms (existing content)
        alarms_tab = QWidget()
        al = QVBoxLayout(alarms_tab)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._make_search_panel())
        splitter.addWidget(self._make_table())
        splitter.setSizes([130, 800])
        al.addWidget(splitter, 1)
        self._tabs.addTab(alarms_tab, "Alarms")

        # Tab 2: Test Validation
        validation_tab = self._make_validation_tab()
        self._tabs.addTab(validation_tab, "Test Validation")

        rl.addWidget(self._tabs, 1)

        self._main_splitter.addWidget(right_wrap)
        self._main_splitter.setSizes([260, 1420])
        self._main_splitter.setCollapsible(0, True)
        self._main_splitter.setCollapsible(1, False)

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

        l.addStretch()

        btn_config = QPushButton("Configure Alarm IDs")
        btn_config.setObjectName("btn_dir")
        btn_config.clicked.connect(self._show_alarm_id_config)
        l.addWidget(btn_config)

        self._lbl_count = QLabel("")
        self._lbl_count.setObjectName("lbl_green")
        l.addWidget(self._lbl_count)

        return w

    # ── validation tab ────────────────────────────────────────────
    def _make_validation_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        # ── Top bar (uses sidebar directory) ─────────────
        top = QHBoxLayout()
        top.setSpacing(10)

        btn_validate = QPushButton("Validate")
        btn_validate.setObjectName("btn_search")
        btn_validate.clicked.connect(self._run_validation)
        top.addWidget(btn_validate)

        top.addWidget(self._vline())

        lbl_tol = QLabel("Tolerance")
        lbl_tol.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        top.addWidget(lbl_tol)

        self._spn_tolerance = QSpinBox()
        self._spn_tolerance.setRange(10, 20)
        self._spn_tolerance.setValue(15)
        self._spn_tolerance.setSuffix("%")
        self._spn_tolerance.setFixedWidth(70)
        top.addWidget(self._spn_tolerance)

        top.addWidget(self._vline())

        lbl_health = QLabel("Health %")
        lbl_health.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        top.addWidget(lbl_health)

        self._spn_health = QSpinBox()
        self._spn_health.setRange(50, 100)
        self._spn_health.setValue(80)
        self._spn_health.setSuffix("%")
        self._spn_health.setFixedWidth(70)
        top.addWidget(self._spn_health)

        top.addStretch()
        lay.addLayout(top)

        # ── Search bar ────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        lbl_search = QLabel("🔍")
        lbl_search.setStyleSheet(
            "color:#7f849c; font-size:14px; background:transparent;")
        search_row.addWidget(lbl_search)

        self._bdt_search = QLineEdit()
        self._bdt_search.setPlaceholderText(
            "Search by site ID or date (e.g. ABC123, 2025-01-12, 2025)…")
        self._bdt_search.setClearButtonEnabled(True)
        self._bdt_search.textChanged.connect(self._filter_bdt_table)
        search_row.addWidget(self._bdt_search)

        lay.addLayout(search_row)

        # ── Vertical splitter: results table + detail panel ──
        self._bdt_splitter = QSplitter(Qt.Vertical)
        self._bdt_splitter.setHandleWidth(1)

        # -- Results table (top pane) --
        cols = BDT_RESULT_HEADERS
        self._bdt_table = QTableWidget(0, len(cols))
        self._bdt_table.setHorizontalHeaderLabels(cols)
        self._bdt_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._bdt_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._bdt_table.setAlternatingRowColors(True)
        self._bdt_table.verticalHeader().setVisible(False)
        self._bdt_table.verticalHeader().setDefaultSectionSize(28)
        hdr = self._bdt_table.horizontalHeader()
        # Rule columns (R1-R11) use compact auto-fit; others use fixed widths.
        rule_cols = {c for c in cols if c.startswith("R") and c[1:].isdigit()}
        for i, col in enumerate(cols):
            if col in rule_cols:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                hdr.resizeSection(i, BDT_RESULT_WIDTHS.get(col, 80))
        hdr.setStretchLastSection(True)
        self._bdt_table.clicked.connect(self._on_bdt_row_clicked)
        self._bdt_splitter.addWidget(self._bdt_table)

        # -- Detail panel (bottom pane) --
        self._bdt_detail_panel = self._make_bdt_detail_panel()
        self._bdt_detail_panel.setVisible(False)
        self._bdt_splitter.addWidget(self._bdt_detail_panel)
        self._bdt_splitter.setSizes([250, 550])
        # Let the detail panel stretch more than the table
        self._bdt_splitter.setStretchFactor(0, 0)  # table: don't stretch
        self._bdt_splitter.setStretchFactor(1, 1)  # detail: take remaining space

        lay.addWidget(self._bdt_splitter, 1)

        # ── Bottom bar ───────────────────────────────────
        bot = QHBoxLayout()
        self._bdt_summary = QLabel("")
        self._bdt_summary.setStyleSheet(
            "color:#6c7086; font-size:12px; background:transparent;")
        bot.addWidget(self._bdt_summary)
        bot.addStretch()

        self._btn_bdt_export = QPushButton("Export Results XLSX")
        self._btn_bdt_export.setObjectName("btn_export")
        self._btn_bdt_export.clicked.connect(self._export_bdt_results)
        bot.addWidget(self._btn_bdt_export)

        lay.addLayout(bot)

        # Store validation results for detail view & export
        self._bdt_results: list[ValidationResult] = []
        self._bdt_by_site: dict[str, list[BDTData]] = {}
        self._current_bdt: BDTData | None = None

        return w

    def _make_bdt_detail_panel(self) -> QWidget:
        """Build BDT detail panel: info+discharge (left) | rules (center) | photos (right)."""
        panel = QWidget()
        panel.setObjectName("bdt_detail_panel")
        outer = QHBoxLayout(panel)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(0)

        # Horizontal splitter for resizable sections
        self._bdt_detail_splitter = QSplitter(Qt.Horizontal)
        self._bdt_detail_splitter.setHandleWidth(3)

        # ═══ LEFT — info grid + discharge table ═══
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        lbl_info = QLabel("FILE INFO")
        lbl_info.setObjectName("bdt_section_title")
        left_lay.addWidget(lbl_info)

        # Info grid
        info_frame = QFrame()
        info_frame.setObjectName("bdt_info_frame")
        grid = QGridLayout(info_frame)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self._bdt_info_labels = {}
        info_fields = [
            ("Site Code",         "site_code"),
            ("Site Name",         "site_name"),
            ("Test Date",         "test_date"),
            ("Time In",           "time_in"),
            ("Time Out",          "time_out"),
            ("Discharge Duration","discharge_minutes"),
            ("Starting I-Battery ampere", "starting_ibattery_ampere"),
            ("End Rectifier Voltage (V)", "end_rectifier_voltage"),
            ("Lead-acid SOH (%)", "lead_acid_soh"),
            ("Battery Brand",     "battery_brand"),
            ("Battery AH",        "battery_ah"),
            ("Battery Voltage",   "battery_voltage"),
            ("Strings",           "num_strings"),
            ("Photo Count",       "photo_count"),
        ]
        for row_idx, (display, key) in enumerate(info_fields):
            k = QLabel(display)
            k.setObjectName("bdt_info_key")
            v = QLabel("--")
            v.setObjectName("bdt_info_val")
            grid.addWidget(k, row_idx, 0)
            grid.addWidget(v, row_idx, 1)
            self._bdt_info_labels[key] = v

        left_lay.addWidget(info_frame)

        btn_open_bdt = QPushButton("Open BDT File")
        btn_open_bdt.setObjectName("btn_search")
        btn_open_bdt.setFixedHeight(28)
        btn_open_bdt.clicked.connect(self._open_current_bdt_file)
        left_lay.addWidget(btn_open_bdt)
        self._btn_open_bdt = btn_open_bdt

        lbl_dis = QLabel("DISCHARGE READINGS")
        lbl_dis.setObjectName("bdt_section_title")
        left_lay.addWidget(lbl_dis)

        # Discharge table
        self._bdt_discharge_table = QTableWidget(0, 3)
        self._bdt_discharge_table.setHorizontalHeaderLabels(
            ["Time", "Voltage (V)", "Ampere (A)"])
        self._bdt_discharge_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self._bdt_discharge_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self._bdt_discharge_table.setAlternatingRowColors(True)
        self._bdt_discharge_table.verticalHeader().setVisible(False)
        self._bdt_discharge_table.verticalHeader().setDefaultSectionSize(24)
        dis_hdr = self._bdt_discharge_table.horizontalHeader()
        dis_hdr.resizeSection(0, 110)
        dis_hdr.resizeSection(1, 100)
        dis_hdr.setStretchLastSection(True)
        left_lay.addWidget(self._bdt_discharge_table, 1)

        self._bdt_detail_splitter.addWidget(left)

        # ═══ CENTER — validation rules ═══
        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(6)

        lbl_rules = QLabel("VALIDATION RULES")
        lbl_rules.setObjectName("bdt_section_title")
        center_lay.addWidget(lbl_rules)

        # Rules table
        self._bdt_rules_table = QTableWidget(0, 4)
        self._bdt_rules_table.setHorizontalHeaderLabels(
            ["Rule", "Name", "Verdict", "Detail"])
        self._bdt_rules_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self._bdt_rules_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self._bdt_rules_table.setAlternatingRowColors(True)
        self._bdt_rules_table.verticalHeader().setVisible(False)
        self._bdt_rules_table.verticalHeader().setDefaultSectionSize(24)
        rules_hdr = self._bdt_rules_table.horizontalHeader()
        rules_hdr.resizeSection(0, 50)
        rules_hdr.resizeSection(1, 140)
        rules_hdr.resizeSection(2, 80)
        rules_hdr.setStretchLastSection(True)
        center_lay.addWidget(self._bdt_rules_table, 1)

        # Parse errors label (hidden by default)
        self._bdt_parse_errors_lbl = QLabel("")
        self._bdt_parse_errors_lbl.setStyleSheet(
            "color:#f38ba8; font-size:11px; background:transparent; padding:4px;")
        self._bdt_parse_errors_lbl.setWordWrap(True)
        self._bdt_parse_errors_lbl.setVisible(False)
        center_lay.addWidget(self._bdt_parse_errors_lbl)

        # ── Door Alarm History ──────────────────────────────────
        lbl_door = QLabel("DOOR ALARM HISTORY")
        lbl_door.setObjectName("section_label")
        lbl_door.setStyleSheet("font-weight: bold; font-size: 11px; color: #89dceb; margin-top: 12px;")
        center_lay.addWidget(lbl_door)

        self._bdt_door_table = QTableWidget(0, 4)
        self._bdt_door_table.setHorizontalHeaderLabels(["Site", "Occurred", "Cleared", "Alarm Name"])
        self._bdt_door_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._bdt_door_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._bdt_door_table.setAlternatingRowColors(True)
        self._bdt_door_table.verticalHeader().setVisible(False)
        self._bdt_door_table.verticalHeader().setDefaultSectionSize(24)
        self._bdt_door_table.setColumnWidth(0, 90)
        self._bdt_door_table.setColumnWidth(1, 150)
        self._bdt_door_table.setColumnWidth(2, 150)
        self._bdt_door_table.horizontalHeader().setStretchLastSection(True)
        self._bdt_door_table.setMinimumHeight(80)
        center_lay.addWidget(self._bdt_door_table)

        # ── Test History Comparison ────────────────────────────
        lbl_hist = QLabel("TEST HISTORY COMPARISON")
        lbl_hist.setObjectName("section_label")
        lbl_hist.setStyleSheet("font-weight: bold; font-size: 11px; color: #cba6f7; margin-top: 12px;")
        center_lay.addWidget(lbl_hist)

        self._bdt_history_table = QTableWidget(0, 3)
        self._bdt_history_table.setHorizontalHeaderLabels(["Field", "Previous", "Current"])
        self._bdt_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._bdt_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._bdt_history_table.setAlternatingRowColors(True)
        self._bdt_history_table.verticalHeader().setVisible(False)
        self._bdt_history_table.verticalHeader().setDefaultSectionSize(24)
        self._bdt_history_table.setColumnWidth(0, 130)
        self._bdt_history_table.setColumnWidth(1, 130)
        self._bdt_history_table.horizontalHeader().setStretchLastSection(True)
        self._bdt_history_table.setMinimumHeight(80)
        center_lay.addWidget(self._bdt_history_table)

        self._bdt_history_label = QLabel("")
        self._bdt_history_label.setWordWrap(True)
        self._bdt_history_label.setStyleSheet("color: #6c7086; font-size: 10px;")
        center_lay.addWidget(self._bdt_history_label)

        self._bdt_detail_splitter.addWidget(center)

        # ═══ RIGHT — photo gallery ═══
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        lbl_photos = QLabel("PHOTOS")
        lbl_photos.setObjectName("bdt_section_title")
        right_lay.addWidget(lbl_photos)

        scroll = QScrollArea()
        scroll.setObjectName("bdt_photo_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._bdt_photo_container = QWidget()
        self._bdt_photo_container.setObjectName("bdt_photo_container")
        self._bdt_photo_grid = QGridLayout(self._bdt_photo_container)
        self._bdt_photo_grid.setContentsMargins(4, 4, 4, 4)
        self._bdt_photo_grid.setSpacing(8)
        scroll.setWidget(self._bdt_photo_container)

        right_lay.addWidget(scroll, 1)

        # ── Photo comparison section ──
        self._bdt_compare_section = QWidget()
        self._bdt_compare_section.setVisible(False)
        compare_outer = QVBoxLayout(self._bdt_compare_section)
        compare_outer.setContentsMargins(0, 6, 0, 0)
        compare_outer.setSpacing(4)

        # Compare header with buttons and year selector
        compare_hdr = QHBoxLayout()
        compare_hdr.setSpacing(8)

        lbl_compare = QLabel("COMPARE PHOTOS")
        lbl_compare.setObjectName("bdt_section_title")
        compare_hdr.addWidget(lbl_compare)

        self._btn_compare_key = QPushButton("Key Slots")
        self._btn_compare_key.setObjectName("btn_search")
        self._btn_compare_key.setFixedHeight(26)
        self._btn_compare_key.clicked.connect(
            lambda: self._show_photo_comparison(all_slots=False))
        compare_hdr.addWidget(self._btn_compare_key)

        self._btn_compare_all = QPushButton("All Slots")
        self._btn_compare_all.setObjectName("btn_clear")
        self._btn_compare_all.setFixedHeight(26)
        self._btn_compare_all.clicked.connect(
            lambda: self._show_photo_comparison(all_slots=True))
        compare_hdr.addWidget(self._btn_compare_all)

        self._cmb_compare_year = QComboBox()
        self._cmb_compare_year.setFixedWidth(100)
        self._cmb_compare_year.currentIndexChanged.connect(
            self._on_compare_year_changed)
        compare_hdr.addWidget(self._cmb_compare_year)

        compare_hdr.addStretch()
        compare_outer.addLayout(compare_hdr)

        # Scrollable comparison grid
        compare_scroll = QScrollArea()
        compare_scroll.setObjectName("bdt_photo_scroll")
        compare_scroll.setWidgetResizable(True)
        compare_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._bdt_compare_container = QWidget()
        self._bdt_compare_container.setObjectName("bdt_photo_container")
        self._bdt_compare_grid = QGridLayout(self._bdt_compare_container)
        self._bdt_compare_grid.setContentsMargins(4, 4, 4, 4)
        self._bdt_compare_grid.setSpacing(6)
        compare_scroll.setWidget(self._bdt_compare_container)

        compare_outer.addWidget(compare_scroll, 1)
        right_lay.addWidget(self._bdt_compare_section, 1)

        self._bdt_detail_splitter.addWidget(right)

        # Set initial proportions (left:center:right = 1:1:2)
        self._bdt_detail_splitter.setSizes([280, 420, 400])

        outer.addWidget(self._bdt_detail_splitter)

        return panel

    # ── left panel ───────────────────────────────────────────────
    def _make_left_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(12)

        # App brand in sidebar
        brand_row = QHBoxLayout()
        icon_lbl = QLabel("📡")
        icon_lbl.setStyleSheet(
            "font-size:18px; background:transparent;")
        brand_row.addWidget(icon_lbl)
        brand_row.addSpacing(4)
        t = QLabel("Alarm Viewer")
        t.setObjectName("lbl_app_name")
        brand_row.addWidget(t)
        brand_row.addStretch()
        lay.addLayout(brand_row)
        lay.addSpacing(4)

        sec1 = QLabel("DIRECTORY")
        sec1.setObjectName("lbl_section")
        lay.addWidget(sec1)

        self._edit_dir = QLineEdit()
        self._edit_dir.setPlaceholderText("Select or paste path…")
        lay.addWidget(self._edit_dir)

        dir_row = QHBoxLayout(); dir_row.setSpacing(6)
        b_br = QPushButton("Browse")
        b_br.setObjectName("btn_dir")
        b_br.clicked.connect(self._browse)
        b_sc = QPushButton("⟳  Scan")
        b_sc.setObjectName("btn_dir")
        b_sc.clicked.connect(self._scan)
        dir_row.addWidget(b_br); dir_row.addWidget(b_sc)
        lay.addLayout(dir_row)

        # ── Files sub-section ─────────────────────────────
        sec2 = QLabel("FILES")
        sec2.setObjectName("lbl_section")
        lay.addWidget(sec2)

        self._lbl_file_count = QLabel("No directory scanned")
        self._lbl_file_count.setStyleSheet(
            "color:#45475a; font-size:11px; background:transparent;")
        lay.addWidget(self._lbl_file_count)

        self._file_list = QListWidget()
        self._file_list.setSelectionMode(
            QAbstractItemView.MultiSelection)
        self._file_list.setMinimumHeight(180)
        lay.addWidget(self._file_list, 1)

        sel_row = QHBoxLayout(); sel_row.setSpacing(5)
        b_all  = QPushButton("All")
        b_all.setObjectName("btn_small")
        b_none = QPushButton("None")
        b_none.setObjectName("btn_small")
        b_all.setFixedWidth(44); b_none.setFixedWidth(44)
        b_all.clicked.connect(self._file_list.selectAll)
        b_none.clicked.connect(self._file_list.clearSelection)
        sel_row.addWidget(b_all)
        sel_row.addWidget(b_none)
        sel_row.addStretch()
        lay.addLayout(sel_row)

        self._btn_load = QPushButton("Load Selected Files")
        self._btn_load.setObjectName("btn_load")
        self._btn_load.setEnabled(False)
        self._btn_load.clicked.connect(self._load)
        lay.addWidget(self._btn_load)

        self._lbl_loaded = QLabel("")
        self._lbl_loaded.setAlignment(Qt.AlignCenter)
        self._lbl_loaded.setStyleSheet(
            "color:#45475a; font-size:11px; background:transparent;")
        lay.addWidget(self._lbl_loaded)

        return w

    # ── search panel (top-right) ─────────────────────────────────
    def _make_search_panel(self):
        w = QWidget()
        outer = QHBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        grp = QGroupBox("Search & Filter")
        grp.setStyleSheet(
            "QGroupBox { font-size:11px; font-weight:600; color:#45475a; "
            "border:1px solid #1e1e2e; border-radius:8px; "
            "margin-top:4px; padding-top:10px; } "
            "QGroupBox::title { subcontrol-origin:margin; "
            "left:10px; color:#45475a; }")
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(14, 8, 14, 10)
        gl.setSpacing(8)

        # ── Row 1: Site ID ────────────────────────────────────
        row1 = QHBoxLayout(); row1.setSpacing(10)

        lbl_site = QLabel("Site ID")
        lbl_site.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent; "
            "min-width:42px;")
        row1.addWidget(lbl_site)

        self._edit_site = QLineEdit()
        self._edit_site.setPlaceholderText(
            "Comma-separated  (e.g. 3420, 0813, KONA)")
        self._edit_site.returnPressed.connect(self._search)
        row1.addWidget(self._edit_site, 3)

        gl.addLayout(row1)

        # ── Row 1b: Date range with toggle + quick picks ──
        row_date = QHBoxLayout(); row_date.setSpacing(8)

        self._chk_date = QCheckBox("Date")
        self._chk_date.setChecked(True)
        self._chk_date.setToolTip("Enable / disable date range filter")
        self._chk_date.setStyleSheet(
            "QCheckBox { color:#7f849c; font-size:12px; "
            "background:transparent; spacing:5px; } "
            "QCheckBox::indicator { width:16px; height:16px; "
            "border-radius:4px; border:1px solid #3a3a52; "
            "background:#1a1a2a; } "
            "QCheckBox::indicator:checked { "
            "background:#1a2744; border-color:#89b4fa; }")
        self._chk_date.toggled.connect(self._toggle_date_filter)
        row_date.addWidget(self._chk_date)

        lbl_from = QLabel("From")
        lbl_from.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        row_date.addWidget(lbl_from)

        self._d_from = QDateEdit(calendarPopup=True)
        self._d_from.setDate(QDate(2025, 12, 1))
        self._d_from.setDisplayFormat("yyyy-MM-dd")
        self._d_from.setMinimumWidth(130)
        self._style_calendar(self._d_from)
        row_date.addWidget(self._d_from)

        lbl_to = QLabel("To")
        lbl_to.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        row_date.addWidget(lbl_to)

        self._d_to = QDateEdit(calendarPopup=True)
        self._d_to.setDate(QDate.currentDate())
        self._d_to.setDisplayFormat("yyyy-MM-dd")
        self._d_to.setMinimumWidth(130)
        self._style_calendar(self._d_to)
        row_date.addWidget(self._d_to)

        row_date.addWidget(self._vline())

        # Quick-pick buttons
        for label, days, obj_name in [
            ("Today", 0, "btn_small"),
            ("7d", 7, "btn_small"),
            ("30d", 30, "btn_small"),
            ("All", -1, "btn_small"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.clicked.connect(
                lambda checked, d=days: self._quick_date(d))
            row_date.addWidget(btn)

        row_date.addStretch()
        gl.addLayout(row_date)

        # ── Row 2: combo filters + action buttons ───────────
        row2 = QHBoxLayout(); row2.setSpacing(10)

        lbl_cat = QLabel("Category")
        lbl_cat.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        row2.addWidget(lbl_cat)

        self._cb_cat = QComboBox()
        self._cb_cat.addItems(["All", "Power", "Down", "Door"])
        self._cb_cat.setMinimumWidth(88)
        row2.addWidget(self._cb_cat)

        lbl_net = QLabel("Network")
        lbl_net.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        row2.addWidget(lbl_net)

        self._cb_net = QComboBox()
        self._cb_net.addItems(["All", "2G", "3G", "4G", "5G"])
        self._cb_net.setMinimumWidth(72)
        row2.addWidget(self._cb_net)

        lbl_vnd = QLabel("Vendor")
        lbl_vnd.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        row2.addWidget(lbl_vnd)

        self._cb_vnd = QComboBox()
        self._cb_vnd.addItems(["All", "HUAWEI", "Nokia"])
        self._cb_vnd.setMinimumWidth(88)
        row2.addWidget(self._cb_vnd)

        row2.addWidget(self._vline())

        self._chk_mindur = QCheckBox("≥")
        self._chk_mindur.setChecked(True)
        self._chk_mindur.setToolTip(
            "Hide alarms shorter than the specified duration")
        self._chk_mindur.setStyleSheet(
            "QCheckBox { color:#7f849c; font-size:12px; "
            "background:transparent; spacing:5px; } "
            "QCheckBox::indicator { width:16px; height:16px; "
            "border-radius:4px; border:1px solid #3a3a52; "
            "background:#1a1a2a; } "
            "QCheckBox::indicator:checked { "
            "background:#1a2744; border-color:#89b4fa; "
            "image:none; } "
            "QCheckBox::indicator:checked::after { "
            "color:#89b4fa; }")
        row2.addWidget(self._chk_mindur)

        self._spn_mindur = QSpinBox()
        self._spn_mindur.setRange(0, 1440)
        self._spn_mindur.setValue(15)
        self._spn_mindur.setSuffix(" min")
        self._spn_mindur.setToolTip("Minimum duration in minutes")
        self._spn_mindur.setFixedWidth(80)
        row2.addWidget(self._spn_mindur)

        row2.addStretch()

        btn_search = QPushButton("Search")
        btn_search.setObjectName("btn_search")
        btn_search.clicked.connect(self._search)
        row2.addWidget(btn_search)

        btn_cl = QPushButton("Clear")
        btn_cl.setObjectName("btn_clear")
        btn_cl.clicked.connect(self._clear_filters)
        row2.addWidget(btn_cl)

        row2.addWidget(self._vline())

        self._btn_export = QPushButton("Export XLSX")
        self._btn_export.setObjectName("btn_export")
        self._btn_export.clicked.connect(self._export)
        row2.addWidget(self._btn_export)

        self._btn_backup = QPushButton("Backup Time")
        self._btn_backup.setObjectName("btn_backup")
        self._btn_backup.clicked.connect(self._show_backup_times)
        row2.addWidget(self._btn_backup)

        self._btn_both = QPushButton("Both P+D")
        self._btn_both.setObjectName("btn_both")
        self._btn_both.setToolTip(
            "Show only sites that have both Power and Down alarms")
        self._btn_both.clicked.connect(self._activate_both_pd)
        row2.addWidget(self._btn_both)

        gl.addLayout(row2)
        outer.addWidget(grp, 1)

        # ── Stats panel (right of search) ─────────────────
        stats_frame = QFrame()
        stats_frame.setFixedWidth(220)
        stats_frame.setStyleSheet(
            "QFrame { background:#0a0a14; border:1px solid #1e1e2e; "
            "border-radius:8px; }")
        sf = QVBoxLayout(stats_frame)
        sf.setContentsMargins(12, 10, 12, 10)
        sf.setSpacing(7)

        sec_lbl = QLabel("STATISTICS")
        sec_lbl.setObjectName("lbl_section")
        sec_lbl.setStyleSheet(
            "color:#45475a; font-size:10px; font-weight:700; "
            "letter-spacing:2px; background:transparent;")
        sf.addWidget(sec_lbl)

        self._stats: dict[str, QLabel] = {}
        for key, label, color in (
            ("total",    "Total Records",  "#89b4fa"),
            ("power",    "Power Alarms",   "#f38ba8"),
            ("down",     "Down Alarms",    "#fab387"),
            ("door",     "Door Alarms",    "#89dceb"),
            ("sites",    "Unique Sites",   "#a6e3a1"),
            ("avg_dur",  "Avg Duration",   "#cba6f7"),
        ):
            row_h = QHBoxLayout(); row_h.setSpacing(4)
            lt = QLabel(label)
            lt.setStyleSheet(
                "color:#45475a; font-size:11px; background:transparent;")
            lv = QLabel("—")
            lv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lv.setFont(QFont("Segoe UI", 12, QFont.Bold))
            lv.setStyleSheet(
                f"color:{color}; background:transparent;")
            self._stats[key] = lv
            row_h.addWidget(lt); row_h.addWidget(lv)
            sf.addLayout(row_h)

            if key != "avg_dur":
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(
                    "color:#1e1e2e; background:#1e1e2e; max-height:1px;")
                sf.addWidget(sep)

        outer.addWidget(stats_frame)
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

    # ── BDT validation slots ─────────────────────────────────
    def _run_validation(self):
        directory = self._edit_dir.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(
                self, "No Directory",
                "Set a directory in the sidebar first.")
            return

        # Find BDT xlsx files (recursive, name must contain "bdt")
        bdt_files = []
        for root, _dirs, files in os.walk(directory):
            for f in files:
                fl = f.lower()
                if (fl.endswith(".xlsx") and "bdt" in fl
                        and not f.startswith("~$") and not f.startswith("._")):
                    bdt_files.append(os.path.join(root, f))

        if not bdt_files:
            QMessageBox.information(
                self, "No BDT Files",
                "No BDT .xlsx files found in directory.\n"
                "BDT filenames must contain 'BDT'.")
            return

        alarm_df = self._full_df if not self._full_df.empty else None
        tolerance = self._spn_tolerance.value() / 100.0
        health_pct = self._spn_health.value() / 100.0
        self._last_bdt_health_pct = health_pct

        self._sbar.showMessage(
            f"Validating {len(bdt_files)} BDT file(s)…")
        self._bdt_results = []
        self._bdt_by_site = {}
        self._bdt_detail_panel.setVisible(False)
        self._prog.setVisible(True)
        self._prog.setValue(0)

        self._bdt_thread = BDTValidationThread(
            bdt_files, alarm_df, tolerance, health_pct)
        self._bdt_thread.progress.connect(
            lambda v, m: (self._prog.setValue(v),
                          self._sbar.showMessage(m)))
        self._bdt_thread.finished.connect(self._on_validation_done)
        self._bdt_thread.error.connect(self._on_validation_error)
        self._bdt_thread.start()

    def _on_validation_done(self, results, by_site):
        self._bdt_results = results
        self._bdt_by_site = by_site
        self._prog.setVisible(False)
        self._populate_bdt_table()
        self._sbar.showMessage(
            f"Validated {len(self._bdt_results)} BDT file(s)")

    def _on_validation_error(self, msg):
        self._prog.setVisible(False)
        QMessageBox.critical(self, "Validation Error", msg)
        self._sbar.showMessage("Validation failed")

    def _populate_bdt_table(self):
        results = self._bdt_results
        self._bdt_table.setRowCount(len(results))

        colors = {
            "Accepted":      QColor("#a6e3a1"),
            "Rejected":      QColor("#f38ba8"),
            "Revise":        QColor("#fab387"),
            "N/A":           QColor("#45475a"),
            "No alarm data": QColor("#45475a"),
        }

        for r, res in enumerate(results):
            row_map = {
                "File": res.filename,
                "Site Code": res.site_code or "--",
                "Test Date": res.test_date,
                "Verdict": res.overall,
                "End Rectifier Voltage (V)": self._format_end_rectifier_voltage(
                    res.bdt_data),
                "Lead-acid SOH (%)": self._format_lead_acid_soh(res.bdt_data),
            }
            for rule in res.rules:
                row_map[rule.rule_id] = self._rule_cell_text(rule)

            for c, col_name in enumerate(BDT_RESULT_HEADERS):
                val = row_map.get(col_name, "--")
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col_name == "Verdict" or col_name.startswith("R"):
                    item.setForeground(colors.get(val, QColor("#cdd6f4")))
                self._bdt_table.setItem(r, c, item)

        # Summary — count individual rule verdicts across all files
        all_rules = [rule for r in results for rule in r.rules]
        n_acc = sum(1 for r in all_rules if r.verdict == "Accepted")
        n_rej = sum(1 for r in all_rules if r.verdict == "Rejected")
        n_rev = sum(1 for r in all_rules if r.verdict == "Revise")
        self._bdt_summary.setText(
            f"<span style='color:#a6e3a1;'>{n_acc} Accepted</span>"
            f" &middot; <span style='color:#f38ba8;'>{n_rej} Rejected</span>"
            f" &middot; <span style='color:#fab387;'>{n_rev} Revise</span>"
            f" &middot; <span style='color:#6c7086;'>"
            f"{len(results)} files</span>")

        # Re-apply current search text so row visibility is always consistent
        # after rebuilding the table.
        self._filter_bdt_table(self._bdt_search.text())

    @staticmethod
    def _rule_cell_text(rule) -> str:
        if (rule.verdict == "N/A"
                and "no alarm data" in str(rule.detail).lower()):
            return "No alarm data"
        return rule.verdict

    @staticmethod
    def _is_lithium_brand(brand: str | None) -> bool:
        return "lith" in (brand or "").lower()

    def _lead_acid_soh_percent(self, bdt: BDTData | None) -> float | None:
        if not bdt or self._is_lithium_brand(bdt.battery_brand):
            return None
        if self._last_bdt_health_pct is None:
            return None
        return self._last_bdt_health_pct * 100.0

    @staticmethod
    def _format_end_rectifier_voltage(bdt: BDTData | None) -> str:
        if not bdt or bdt.end_voltage is None:
            return "--"
        return f"{bdt.end_voltage:.2f}"

    def _format_lead_acid_soh(self, bdt: BDTData | None) -> str:
        soh = self._lead_acid_soh_percent(bdt)
        if soh is None:
            return "--"
        return f"{soh:.0f}"

    def _filter_bdt_table(self, text: str):
        """Live-filter the BDT results table by site ID or date."""
        import re
        text = text.strip()
        if not text:
            for r in range(self._bdt_table.rowCount()):
                self._bdt_table.setRowHidden(r, False)
            return

        text_lower = text.lower()

        # Detect date patterns
        is_year = re.fullmatch(r"\d{4}", text)
        is_date = re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)

        for r in range(self._bdt_table.rowCount()):
            if r >= len(self._bdt_results):
                break
            res = self._bdt_results[r]
            show = False

            if is_year:
                show = res.test_date.startswith(text)
            elif is_date:
                show = res.test_date == text
            else:
                # Substring match on site code or filename
                show = (text_lower in (res.site_code or "").lower()
                        or text_lower in (res.filename or "").lower())

            self._bdt_table.setRowHidden(r, not show)

    def _on_bdt_row_clicked(self, index):
        row = index.row()
        if row >= len(self._bdt_results):
            return
        res = self._bdt_results[row]

        if not self._bdt_detail_panel.isVisible():
            self._bdt_detail_panel.setVisible(True)
            # Size the results table to fit its rows (header + rows + margin)
            row_count = self._bdt_table.rowCount()
            header_h = self._bdt_table.horizontalHeader().height()
            row_h = self._bdt_table.verticalHeader().defaultSectionSize()
            table_h = header_h + (row_count * row_h) + 6
            table_h = min(table_h, 250)  # cap so detail always gets space
            total = self._bdt_splitter.height() or 800
            self._bdt_splitter.setSizes([table_h, total - table_h])

        self._populate_bdt_detail(res)

    def _populate_bdt_detail(self, res: ValidationResult):
        """Fill the detail panel from the selected validation result."""
        bdt = res.bdt_data

        # ── Info grid ──
        if bdt:
            start_ibat = bdt.starting_ibattery_ampere
            if start_ibat is None:
                start_ibat = bdt.ibat_before_test
            vals = {
                "site_code":         bdt.site_code or "--",
                "site_name":         bdt.site_name or "--",
                "test_date":         (bdt.test_date.strftime("%Y-%m-%d")
                                      if bdt.test_date else "--"),
                "time_in":           bdt.time_in or "--",
                "time_out":          bdt.time_out or "--",
                "discharge_minutes": (f"{bdt.discharge_minutes:.0f} min"
                                      if bdt.discharge_minutes else "--"),
                "starting_ibattery_ampere": (
                    f"{start_ibat} A" if start_ibat is not None else "--"),
                "end_rectifier_voltage": self._format_end_rectifier_voltage(bdt),
                "lead_acid_soh": self._format_lead_acid_soh(bdt),
                "battery_brand":     bdt.battery_brand or "--",
                "battery_ah":        (f"{bdt.battery_ah} AH"
                                      if bdt.battery_ah else "--"),
                "battery_voltage":   (f"{bdt.battery_voltage}V"
                                      if bdt.battery_voltage else "--"),
                "num_strings":       (str(bdt.num_strings)
                                      if bdt.num_strings else "--"),
                "photo_count":       str(bdt.photo_count),
            }
        else:
            vals = {k: "--" for k in self._bdt_info_labels}

        for key, lbl in self._bdt_info_labels.items():
            lbl.setText(vals.get(key, "--"))

        # ── Discharge table ──
        self._bdt_discharge_table.setRowCount(0)
        if bdt:
            readings = []
            if bdt.start_voltage is not None or bdt.start_ampere is not None:
                readings.append(("Before disconnect",
                                 bdt.start_voltage, bdt.start_ampere))
            readings.extend(bdt.discharge_readings)
            if (bdt.after_reconnect_voltage is not None
                    or bdt.after_reconnect_ampere is not None):
                readings.append(("After reconnect",
                                 bdt.after_reconnect_voltage,
                                 bdt.after_reconnect_ampere))

            self._bdt_discharge_table.setRowCount(len(readings))
            start_bg = QColor("#1a2744")
            end_bg = QColor("#2e1a22")

            for r, (time_lbl, voltage, ampere) in enumerate(readings):
                items = [
                    QTableWidgetItem(str(time_lbl)),
                    QTableWidgetItem(f"{voltage:.2f}"
                                     if voltage is not None else "--"),
                    QTableWidgetItem(f"{ampere:.2f}"
                                     if ampere is not None else "--"),
                ]
                for c, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    if r == 0 and readings[0][0] == "Before disconnect":
                        item.setBackground(start_bg)
                    elif (r == len(readings) - 1
                          and readings[-1][0] == "After reconnect"):
                        item.setBackground(end_bg)
                    self._bdt_discharge_table.setItem(r, c, item)

        # ── Rules table ──
        verdict_colors = {
            "Accepted": QColor("#a6e3a1"),
            "Rejected": QColor("#f38ba8"),
            "Revise":   QColor("#fab387"),
            "N/A":      QColor("#45475a"),
        }
        self._bdt_rules_table.setRowCount(len(res.rules))
        for r, rule in enumerate(res.rules):
            items = [
                QTableWidgetItem(rule.rule_id),
                QTableWidgetItem(rule.rule_name),
                QTableWidgetItem(rule.verdict),
                QTableWidgetItem(rule.detail),
            ]
            for c, item in enumerate(items):
                if c < 3:
                    item.setTextAlignment(Qt.AlignCenter)
                if c == 2:
                    item.setForeground(
                        verdict_colors.get(rule.verdict, QColor("#cdd6f4")))
                self._bdt_rules_table.setItem(r, c, item)

        # ── Parse errors ──
        if res.parse_errors:
            self._bdt_parse_errors_lbl.setText(
                "Parse errors: " + "; ".join(res.parse_errors))
            self._bdt_parse_errors_lbl.setVisible(True)
        else:
            self._bdt_parse_errors_lbl.setVisible(False)

        # ── Populate door alarm history ──────────────────────────
        self._bdt_door_table.setRowCount(0)
        if bdt and bdt.test_date and self._full_df is not None and not self._full_df.empty:
            try:
                try:
                    from .bdt_validator import _find_door_alarms
                except ImportError:
                    from bdt_validator import _find_door_alarms
                import pandas as pd
                test_date_ts = pd.Timestamp(bdt.test_date).normalize()
                doors = _find_door_alarms(self._full_df, bdt.site_code, test_date_ts)
                if not doors.empty:
                    self._bdt_door_table.setRowCount(len(doors))
                    for i, (_, row) in enumerate(doors.iterrows()):
                        self._bdt_door_table.setItem(i, 0, QTableWidgetItem(str(row.get("site_id", ""))))
                        occ = row.get("occurred_on", "")
                        self._bdt_door_table.setItem(i, 1, QTableWidgetItem(
                            str(occ.strftime("%Y-%m-%d %H:%M") if hasattr(occ, "strftime") else occ)))
                        clr = row.get("cleared_on", "")
                        self._bdt_door_table.setItem(i, 2, QTableWidgetItem(
                            str(clr.strftime("%Y-%m-%d %H:%M") if hasattr(clr, "strftime") else clr)))
                        self._bdt_door_table.setItem(i, 3, QTableWidgetItem(str(row.get("alarm_name", ""))))
            except Exception:
                pass  # Graceful fallback if alarm data unavailable

        # ── Populate test history comparison ──────────────────
        self._bdt_history_table.setRowCount(0)
        self._bdt_history_label.setText("")
        if bdt and bdt.test_date and bdt.site_code:
            try:
                try:
                    from .bdt_history import load_previous_test, compare_tests
                except ImportError:
                    from bdt_history import load_previous_test, compare_tests
                from datetime import date as date_type
                test_date = (bdt.test_date.date() if hasattr(bdt.test_date, "date")
                             else bdt.test_date)
                if isinstance(test_date, date_type):
                    prev = load_previous_test(bdt.site_code, test_date)
                    if prev:
                        comp = compare_tests(bdt, prev)
                        fields = [
                            ("Battery Brand", prev.battery_brand, str(bdt.battery_brand or "")),
                            ("Battery AH", str(prev.battery_ah or ""), str(bdt.battery_ah or "")),
                            ("Battery Voltage", str(prev.battery_voltage or ""), str(bdt.battery_voltage or "")),
                            ("# Strings", str(prev.num_strings or ""), str(bdt.num_strings or "")),
                            ("# Batteries", str(prev.num_batteries or ""), str(getattr(bdt, "num_batteries", "") or "")),
                            ("# Modules", str(prev.num_modules or ""), str(getattr(bdt, "num_modules", "") or "")),
                            ("Rectifier", str(prev.rectifier_brand or ""), str(getattr(bdt, "rectifier_brand", "") or "")),
                        ]
                        self._bdt_history_table.setRowCount(len(fields))
                        for i, (label, prev_val, curr_val) in enumerate(fields):
                            self._bdt_history_table.setItem(i, 0, QTableWidgetItem(label))
                            item_prev = QTableWidgetItem(prev_val)
                            item_curr = QTableWidgetItem(curr_val)
                            # Highlight changes in red
                            if prev_val.strip().lower() != curr_val.strip().lower() and prev_val and curr_val:
                                item_prev.setForeground(QColor("#f38ba8"))
                                item_curr.setForeground(QColor("#f38ba8"))
                            self._bdt_history_table.setItem(i, 1, item_prev)
                            self._bdt_history_table.setItem(i, 2, item_curr)

                        if comp.has_critical_change:
                            self._bdt_history_label.setText(
                                f"<span style='color:#f38ba8;'>Equipment change detected vs {prev.test_date}</span>")
                        else:
                            self._bdt_history_label.setText(
                                f"<span style='color:#a6e3a1;'>No critical changes vs {prev.test_date}</span>")
                    else:
                        self._bdt_history_label.setText(
                            "<span style='color:#6c7086;'>No previous test history found</span>")
            except ImportError:
                self._bdt_history_label.setText(
                    "<span style='color:#6c7086;'>History module not available</span>")
            except Exception:
                pass

        # ── Photos (lazy-load if skipped during batch validation) ──
        if bdt:
            load_bdt_photos(bdt)
        self._populate_bdt_photos(bdt)

        # ── Photo comparison setup ──
        self._current_bdt = bdt
        self._setup_photo_comparison(bdt)

    def _open_current_bdt_file(self):
        """Open the currently selected BDT file with the OS default application."""
        if not self._current_bdt or not self._current_bdt.file_path:
            return
        url = QUrl.fromLocalFile(self._current_bdt.file_path)
        QDesktopServices.openUrl(url)

    def _show_photo_fullsize(self, image_data: bytes, label: str):
        """Open a modal dialog with zoom (scroll wheel, +/- buttons, fit)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(label)
        dlg.setMinimumSize(800, 600)
        dlg.resize(1000, 750)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Original pixmap (never mutated)
        original_pix = QPixmap()
        original_pix.loadFromData(image_data)

        # State shared by closures
        state = {"zoom": 100}  # percentage

        # Scroll area with the image
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet("background: #11111b; border: none;")

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)

        def _apply_zoom():
            z = state["zoom"]
            w = int(original_pix.width() * z / 100)
            scaled = original_pix.scaledToWidth(
                max(w, 50), Qt.SmoothTransformation)
            img_lbl.setPixmap(scaled)
            img_lbl.resize(scaled.size())
            zoom_lbl.setText(f"{z}%")

        scroll.setWidget(img_lbl)
        layout.addWidget(scroll, 1)

        # Toolbar: Zoom -, zoom level, Zoom +, Fit, label
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #1e1e2e;")
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(8, 4, 8, 4)
        tb_lay.setSpacing(6)

        btn_out = QPushButton("-")
        btn_out.setFixedSize(32, 28)
        btn_out.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #cdd6f4; "
            "background: #313244; border: 1px solid #45475a; border-radius: 4px;")
        tb_lay.addWidget(btn_out)

        zoom_lbl = QLabel("100%")
        zoom_lbl.setFixedWidth(50)
        zoom_lbl.setAlignment(Qt.AlignCenter)
        zoom_lbl.setStyleSheet("font-size: 12px; color: #cdd6f4;")
        tb_lay.addWidget(zoom_lbl)

        btn_in = QPushButton("+")
        btn_in.setFixedSize(32, 28)
        btn_in.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #cdd6f4; "
            "background: #313244; border: 1px solid #45475a; border-radius: 4px;")
        tb_lay.addWidget(btn_in)

        btn_fit = QPushButton("Fit")
        btn_fit.setFixedSize(40, 28)
        btn_fit.setStyleSheet(
            "font-size: 11px; color: #cdd6f4; "
            "background: #313244; border: 1px solid #45475a; border-radius: 4px;")
        tb_lay.addWidget(btn_fit)

        btn_full = QPushButton("1:1")
        btn_full.setFixedSize(40, 28)
        btn_full.setStyleSheet(
            "font-size: 11px; color: #cdd6f4; "
            "background: #313244; border: 1px solid #45475a; border-radius: 4px;")
        tb_lay.addWidget(btn_full)

        tb_lay.addStretch()

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #89b4fa;")
        tb_lay.addWidget(name_lbl)

        layout.addWidget(toolbar)

        # Zoom actions
        def _zoom_in():
            state["zoom"] = min(state["zoom"] + 25, 500)
            _apply_zoom()

        def _zoom_out():
            state["zoom"] = max(state["zoom"] - 25, 25)
            _apply_zoom()

        def _zoom_fit():
            vp = scroll.viewport().size()
            fw = int(vp.width() / original_pix.width() * 100) if original_pix.width() > 0 else 100
            fh = int(vp.height() / original_pix.height() * 100) if original_pix.height() > 0 else 100
            state["zoom"] = max(min(fw, fh), 25)
            _apply_zoom()

        def _zoom_full():
            state["zoom"] = 100
            _apply_zoom()

        btn_in.clicked.connect(_zoom_in)
        btn_out.clicked.connect(_zoom_out)
        btn_fit.clicked.connect(_zoom_fit)
        btn_full.clicked.connect(_zoom_full)

        # Scroll wheel zoom
        def _wheel(event):
            delta = event.angleDelta().y()
            if delta > 0:
                _zoom_in()
            elif delta < 0:
                _zoom_out()

        scroll.wheelEvent = _wheel

        # Start at fit-to-window
        dlg.showEvent = lambda _: _zoom_fit()

        dlg.exec_()

    # Band layout: name, start slot index, number of columns in this band
    _PHOTO_BANDS = [
        ("Rectifier",               0,  3),
        ("Batteries",               4,  3),
        ("CBs / Rack / LVD",        8,  3),
        ("Current / Load / PLVD",  12,  3),
        ("Charging / Disconnect",  16,  4),
    ]

    def _populate_bdt_photos(self, bdt: BDTData | None):
        """Fill the photo gallery grid with band headings matching the BDT template."""
        # Clear existing widgets
        while self._bdt_photo_grid.count():
            item = self._bdt_photo_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not bdt or not bdt.photo_slots:
            lbl = QLabel("No photo data")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_photo_grid.addWidget(lbl, 0, 0)
            return

        grid_row = 0
        max_cols = 4  # widest band has 4 columns

        for band_name, start_idx, band_cols in self._PHOTO_BANDS:
            # Band heading
            heading = QLabel(band_name.upper())
            heading.setStyleSheet(
                "font-weight: bold; font-size: 11px; color: #89b4fa; "
                "padding: 6px 0 2px 0; border-bottom: 1px solid #313244;")
            heading.setAlignment(Qt.AlignLeft)
            self._bdt_photo_grid.addWidget(heading, grid_row, 0, 1, max_cols)
            grid_row += 1

            # Photo cards for this band
            for ci in range(band_cols):
                slot_idx = start_idx + ci
                if slot_idx >= len(bdt.photo_slots):
                    continue
                slot = bdt.photo_slots[slot_idx]

                card = QFrame()
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(4, 4, 4, 4)
                card_lay.setSpacing(2)

                if slot.image_data:
                    card.setObjectName("bdt_photo_card")
                    card.setCursor(Qt.PointingHandCursor)
                    pix = QPixmap()
                    pix.loadFromData(slot.image_data)
                    thumb = pix.scaledToWidth(
                        200, Qt.SmoothTransformation)
                    img_lbl = QLabel()
                    img_lbl.setPixmap(thumb)
                    img_lbl.setAlignment(Qt.AlignCenter)
                    card_lay.addWidget(img_lbl)
                    # Click to view full size
                    _data = slot.image_data
                    _label = slot.label
                    card.mousePressEvent = lambda _, d=_data, l=_label: self._show_photo_fullsize(d, l)
                else:
                    card.setObjectName("bdt_photo_missing")
                    na_lbl = QLabel("Not Available")
                    na_lbl.setObjectName("bdt_photo_missing_label")
                    na_lbl.setAlignment(Qt.AlignCenter)
                    card_lay.addWidget(na_lbl, 1)

                name_lbl = QLabel(slot.label)
                name_lbl.setObjectName("bdt_photo_label")
                name_lbl.setAlignment(Qt.AlignCenter)
                name_lbl.setWordWrap(True)
                card_lay.addWidget(name_lbl)

                self._bdt_photo_grid.addWidget(card, grid_row, ci)

            grid_row += 1

    _COMPARE_KEY_CATEGORIES = {"rectifier", "batteries", "modules"}

    @staticmethod
    def _slot_category(slot) -> str:
        category = getattr(slot, "category", "")
        if category:
            return str(category).lower()
        return "other"

    def _build_compare_category_summary(self, slots) -> dict[str, int]:
        summary = {cat: 0 for cat in sorted(self._COMPARE_KEY_CATEGORIES)}
        for slot in slots:
            cat = self._slot_category(slot)
            if cat in summary and slot.image_data:
                summary[cat] += 1
        return summary

    @staticmethod
    def _category_summary_text(prefix: str, summary: dict[str, int]) -> str:
        return (
            f"{prefix}: "
            f"Rectifier {summary.get('rectifier', 0)} · "
            f"Batteries {summary.get('batteries', 0)} · "
            f"Modules {summary.get('modules', 0)}"
        )

    def _comparison_slot_indices(self, bdt: BDTData, other: BDTData,
                                 all_slots: bool) -> list[int]:
        if all_slots:
            return list(range(min(len(bdt.photo_slots), len(other.photo_slots))))
        indices: list[int] = []
        limit = min(len(bdt.photo_slots), len(other.photo_slots))
        for idx in range(limit):
            cur_cat = self._slot_category(bdt.photo_slots[idx])
            oth_cat = self._slot_category(other.photo_slots[idx])
            if (cur_cat in self._COMPARE_KEY_CATEGORIES
                    or oth_cat in self._COMPARE_KEY_CATEGORIES):
                indices.append(idx)
        return indices

    @staticmethod
    def _normalize_site_token(text: str) -> str:
        """Normalize site/file text to alphanumeric uppercase for robust matching."""
        return "".join(ch for ch in str(text).upper() if ch.isalnum())

    @classmethod
    def _filename_contains_site_code(cls, site_code: str, file_name: str) -> bool:
        """Check whether filename likely belongs to a site code."""
        site_token = cls._normalize_site_token(site_code)
        if len(site_token) < 3:
            return False
        file_token = cls._normalize_site_token(file_name)
        return bool(file_token) and site_token in file_token

    def _comparison_candidates_for_site(self, bdt: BDTData) -> list[BDTData]:
        """Collect comparison candidates from exact site map + filename fallback."""
        key = (bdt.site_code or "").strip().upper()
        if not key:
            return []

        seen_paths: set[str] = set()
        candidates: list[BDTData] = []

        def _add_candidate(candidate: BDTData | None):
            if not candidate:
                return
            fp = candidate.file_path or ""
            if not fp or fp == bdt.file_path or fp in seen_paths:
                return
            seen_paths.add(fp)
            candidates.append(candidate)

        # Primary source: parsed site_code grouping.
        for candidate in self._bdt_by_site.get(key, []):
            _add_candidate(candidate)

        # Fallback source: filename contains current site code token.
        for res in self._bdt_results:
            candidate = res.bdt_data
            if not candidate:
                continue
            if self._filename_contains_site_code(
                    key, candidate.filename or candidate.file_path):
                _add_candidate(candidate)

        candidates.sort(
            key=lambda c: c.test_date or datetime.min,
            reverse=True,
        )
        return candidates

    def _setup_photo_comparison(self, bdt: BDTData | None):
        """Check if comparison data is available and configure the UI."""
        # Clear comparison grid
        while self._bdt_compare_grid.count():
            item = self._bdt_compare_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not bdt or not bdt.site_code:
            self._bdt_compare_section.setVisible(False)
            return

        others = self._comparison_candidates_for_site(bdt)

        if not others:
            self._bdt_compare_section.setVisible(False)
            return

        # Populate year selector
        self._cmb_compare_year.blockSignals(True)
        self._cmb_compare_year.clear()
        for other in others:
            year = (other.test_date.strftime("%Y")
                    if other.test_date else "Unknown")
            self._cmb_compare_year.addItem(
                year, other)  # store BDTData as userData
        self._cmb_compare_year.blockSignals(False)

        self._bdt_compare_section.setVisible(True)
        self._show_photo_comparison(all_slots=False)

    def _on_compare_year_changed(self, _idx):
        """Re-render comparison when user selects a different year."""
        if self._bdt_compare_section.isVisible():
            self._show_photo_comparison(all_slots=False)

    def _show_photo_comparison(self, all_slots: bool = False):
        """Render side-by-side photo comparison grid."""
        # Clear
        while self._bdt_compare_grid.count():
            item = self._bdt_compare_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        bdt = self._current_bdt
        if not bdt or not bdt.photo_slots:
            return

        other = self._cmb_compare_year.currentData()
        if not other:
            lbl = QLabel("No comparison data available")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_compare_grid.addWidget(lbl, 0, 0, 1, 3)
            return

        # Lazy-load photos for comparison target
        load_bdt_photos(other)
        if not other.photo_slots:
            lbl = QLabel("No comparison data available")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_compare_grid.addWidget(lbl, 0, 0, 1, 3)
            return

        current_year = (bdt.test_date.strftime("%Y")
                        if bdt.test_date else "Current")
        other_year = (other.test_date.strftime("%Y")
                      if other.test_date else "Other")

        slot_indices = self._comparison_slot_indices(bdt, other, all_slots)

        # Header row
        hdr_slot = QLabel("Slot")
        hdr_slot.setObjectName("bdt_info_key")
        hdr_slot.setAlignment(Qt.AlignCenter)
        hdr_cur = QLabel(current_year)
        hdr_cur.setObjectName("bdt_section_title")
        hdr_cur.setAlignment(Qt.AlignCenter)
        hdr_oth = QLabel(other_year)
        hdr_oth.setObjectName("bdt_section_title")
        hdr_oth.setAlignment(Qt.AlignCenter)
        self._bdt_compare_grid.addWidget(hdr_slot, 0, 0)
        self._bdt_compare_grid.addWidget(hdr_cur, 0, 1)
        self._bdt_compare_grid.addWidget(hdr_oth, 0, 2)

        grid_row = 1
        if not all_slots:
            cur_summary = self._build_compare_category_summary(
                [bdt.photo_slots[idx] for idx in slot_indices])
            oth_summary = self._build_compare_category_summary(
                [other.photo_slots[idx] for idx in slot_indices])
            summary_slot = QLabel("Category photos")
            summary_slot.setObjectName("bdt_info_key")
            summary_slot.setAlignment(Qt.AlignCenter)
            summary_cur = QLabel(self._category_summary_text("Current", cur_summary))
            summary_cur.setObjectName("bdt_photo_label")
            summary_cur.setAlignment(Qt.AlignCenter)
            summary_oth = QLabel(self._category_summary_text(other_year, oth_summary))
            summary_oth.setObjectName("bdt_photo_label")
            summary_oth.setAlignment(Qt.AlignCenter)
            self._bdt_compare_grid.addWidget(summary_slot, grid_row, 0)
            self._bdt_compare_grid.addWidget(summary_cur, grid_row, 1)
            self._bdt_compare_grid.addWidget(summary_oth, grid_row, 2)
            grid_row += 1

        if not slot_indices:
            lbl = QLabel("No matching slots for this comparison mode")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_compare_grid.addWidget(lbl, grid_row, 0, 1, 3)
            return

        for idx in slot_indices:
            if idx >= len(bdt.photo_slots) or idx >= len(other.photo_slots):
                continue

            cur_slot = bdt.photo_slots[idx]
            oth_slot = other.photo_slots[idx]

            # Slot label
            name_lbl = QLabel(cur_slot.label)
            name_lbl.setObjectName("bdt_photo_label")
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setWordWrap(True)
            self._bdt_compare_grid.addWidget(name_lbl, grid_row, 0)

            # Current year photo
            self._bdt_compare_grid.addWidget(
                self._make_compare_photo_widget(cur_slot),
                grid_row, 1)

            # Other year photo
            self._bdt_compare_grid.addWidget(
                self._make_compare_photo_widget(oth_slot),
                grid_row, 2)

            grid_row += 1

    def _make_compare_photo_widget(self, slot) -> QFrame:
        """Create a photo card for the comparison grid."""
        card = QFrame()
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(2, 2, 2, 2)
        card_lay.setSpacing(1)

        if slot.image_data:
            card.setObjectName("bdt_photo_card")
            pix = QPixmap()
            pix.loadFromData(slot.image_data)
            thumb = pix.scaledToWidth(160, Qt.SmoothTransformation)
            img_lbl = QLabel()
            img_lbl.setPixmap(thumb)
            img_lbl.setAlignment(Qt.AlignCenter)
            card_lay.addWidget(img_lbl)
        else:
            card.setObjectName("bdt_photo_missing")
            na_lbl = QLabel("N/A")
            na_lbl.setObjectName("bdt_photo_missing_label")
            na_lbl.setAlignment(Qt.AlignCenter)
            card_lay.addWidget(na_lbl, 1)

        return card

    def _export_bdt_results(self):
        if not self._bdt_results:
            QMessageBox.information(
                self, "Nothing to Export", "Run validation first.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Validation Results",
            f"bdt_validation_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            "Excel Files (*.xlsx)")
        if not fp:
            return
        sheets = build_bdt_export_sheets(
            self._bdt_results,
            health_pct=self._last_bdt_health_pct,
        )
        self._btn_bdt_export.setEnabled(False)
        self._sbar.showMessage("Exporting BDT results …")
        self._bdt_export_thread = ExportThread(sheets, fp)
        self._bdt_export_thread.progress.connect(
            lambda v, m: self._sbar.showMessage(m))
        self._bdt_export_thread.finished.connect(self._on_bdt_export_done)
        self._bdt_export_thread.error.connect(self._on_bdt_export_error)
        self._bdt_export_thread.start()

    def _on_bdt_export_done(self, fp: str):
        self._btn_bdt_export.setEnabled(True)
        QMessageBox.information(
            self, "Export OK", f"Saved to:\n{fp}")
        self._sbar.showMessage(f"BDT export → {fp}")

    def _on_bdt_export_error(self, msg: str):
        self._btn_bdt_export.setEnabled(True)
        QMessageBox.critical(self, "Export Failed", msg)
        self._sbar.showMessage("BDT export failed")

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
            "site_filter": self._edit_site.text(),
            "date_enabled": self._chk_date.isChecked(),
            "date_from": self._d_from.date().toString("yyyy-MM-dd"),
            "date_to": self._d_to.date().toString("yyyy-MM-dd"),
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
        }
        state.save_state(d)

    def _restore_ui_state(self):
        """Restore UI settings from state.json and kick off cache load."""
        s = state.load_state()
        if s is None:
            return

        # Window geometry
        geo = s.get("window_geometry")
        if geo and len(geo) == 4:
            self.setGeometry(*geo)

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

        # Kick off background Parquet restore
        if state.CACHE_FILE.exists():
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
                df[col] = pd.to_datetime(df[col], errors="coerce")

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

    def closeEvent(self, event):
        """Always warn before closing."""
        dlg = QDialog(self, Qt.FramelessWindowHint)
        dlg.setFixedWidth(380)
        dlg.setStyleSheet("""
            QDialog {
                background: #1a1a2a;
                border: 1px solid #2a2a3e;
                border-radius: 12px;
            }
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)

        # Icon + title row
        title_row = QHBoxLayout()
        icon = QLabel("⚠")
        icon.setStyleSheet(
            "font-size:28px; background:transparent; color:#fab387;")
        title_row.addWidget(icon)
        title_row.addSpacing(8)
        title = QLabel("Close Alarm Viewer?")
        title.setStyleSheet(
            "color:#cdd6f4; font-size:16px; font-weight:700;"
            "background:transparent;")
        title_row.addWidget(title)
        title_row.addStretch()
        lay.addLayout(title_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#2a2a3e;")
        lay.addWidget(sep)

        # Message adapts to whether data is loaded
        if not self._full_df.empty:
            n_rec = len(self._full_df)
            n_sites = (self._full_df["site_id"].nunique()
                       if "site_id" in self._full_df.columns else 0)
            n_files = len(self._file_infos)
            msg = (
                f"<span style='color:#6c7086;'>"
                f"You currently have data in memory:</span><br><br>"
                f"<span style='color:#89b4fa;'>{n_rec:,}</span>"
                f"<span style='color:#6c7086;'> records</span>"
                f"&nbsp;&nbsp;&middot;&nbsp;&nbsp;"
                f"<span style='color:#a6e3a1;'>{n_sites:,}</span>"
                f"<span style='color:#6c7086;'> sites</span>"
                f"&nbsp;&nbsp;&middot;&nbsp;&nbsp;"
                f"<span style='color:#fab387;'>{n_files}</span>"
                f"<span style='color:#6c7086;'> files</span><br><br>"
                f"<span style='color:#a6e3a1;'>"
                f"Your session will be saved and restored next time.</span>")
        else:
            msg = ("<span style='color:#6c7086;'>"
                   "Are you sure you want to exit?</span>")

        info = QLabel(msg)
        info.setStyleSheet(
            "color:#cdd6f4; font-size:13px; background:transparent;"
            "line-height:1.5;")
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addSpacing(8)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_cancel = QPushButton("Stay")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #1a2744; color: #89b4fa;
                border: 1px solid #2a4070; border-radius: 6px;
                padding: 8px 24px; font-size: 13px; font-weight: 600;
                min-width: 80px;
            }
            QPushButton:hover {
                background: #1f3258; border-color: #89b4fa;
            }
        """)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)

        btn_exit = QPushButton("Exit")
        btn_exit.setStyleSheet("""
            QPushButton {
                background: #3d1e2c; color: #f38ba8;
                border: 1px solid #5a2030; border-radius: 6px;
                padding: 8px 24px; font-size: 13px; font-weight: 600;
                min-width: 80px;
            }
            QPushButton:hover {
                background: #4d2838; border-color: #f38ba8;
            }
        """)
        btn_exit.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_exit)

        lay.addLayout(btn_row)

        if dlg.exec_() != QDialog.Accepted:
            event.ignore()
            return

        # Save session state before closing
        try:
            self._save_ui_state()
            if not self._full_df.empty:
                state.save_dataframe(self._full_df)
        except Exception as e:
            print(f"[AlarmViewer] save error: {e}")

        event.accept()

    def keyPressEvent(self, event):
        """Keyboard shortcuts: Ctrl+B toggle sidebar, Ctrl+C copy."""
        if (event.modifiers() == Qt.ControlModifier
                and event.key() == Qt.Key_B):
            self._toggle_sidebar()
            return
        if (event.modifiers() == Qt.ControlModifier
                and event.key() == Qt.Key_C):
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

    @staticmethod
    def _style_calendar(date_edit: QDateEdit):
        """Fix weekend/holiday text colours on the calendar popup."""
        cal = date_edit.calendarWidget()
        if cal is None:
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#cdd6f4"))       # same as weekday text
        cal.setWeekdayTextFormat(Qt.Saturday, fmt)
        cal.setWeekdayTextFormat(Qt.Sunday, fmt)

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
                self._d_from.setDate(qmn)
            if pd.notna(mx):
                qmx = QDate(mx.year, mx.month, mx.day)
                self._d_to.setMaximumDate(qmx)
                self._d_to.setDate(qmx)

    def _toggle_date_filter(self, enabled: bool):
        self._d_from.setEnabled(enabled)
        self._d_to.setEnabled(enabled)

    def _quick_date(self, days: int):
        """Set date range to a quick preset. days=-1 means 'All'."""
        self._chk_date.setChecked(True)
        if days < 0 and not self._full_df.empty:
            self._reset_date_range(self._full_df)
        elif days == 0:
            today = QDate.currentDate()
            self._d_from.setDate(today)
            self._d_to.setDate(today)
        else:
            today = QDate.currentDate()
            self._d_from.setDate(today.addDays(-days))
            self._d_to.setDate(today)

    # ── sidebar toggle (Cmd+B) ──────────────────────────────────
    def _toggle_sidebar(self):
        sizes = self._main_splitter.sizes()
        if sizes[0] > 0:
            self._sidebar_width = sizes[0]
            self._main_splitter.setSizes([0, sizes[0] + sizes[1]])
        else:
            self._main_splitter.setSizes(
                [self._sidebar_width, sizes[1] - self._sidebar_width])

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

        # Apply the ≥15 min filter if enabled on initial load
        view = df
        if self._chk_mindur.isChecked() and "_duration_secs" in df.columns:
            view = df[df["_duration_secs"] >= self._spn_mindur.value() * 60]

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

        # Date range — only if checkbox is ON
        if self._chk_date.isChecked() and "occurred_on" in df.columns:
            fd = pd.Timestamp(self._d_from.date().toPyDate())
            td = pd.Timestamp(self._d_to.date().toPyDate()) + pd.Timedelta(
                hours=23, minutes=59, seconds=59)
            notna = df["occurred_on"].notna()
            df = df[notna
                    & (df["occurred_on"] >= fd)
                    & (df["occurred_on"] <= td)]

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
