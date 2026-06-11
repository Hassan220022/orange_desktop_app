"""
BdtDetailPanel — BDT detail/photo gallery panel extracted from AlarmViewer.
"""

import os
from datetime import datetime

import pandas as pd
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from alarm_app.bdt.parser import BDTData, load_bdt_photos
    from alarm_app.bdt.photo_auth import verify_photo_slots
    from alarm_app.bdt.validator import ValidationResult
    from alarm_app.constants import format_bdt_rule_label
    from alarm_app.data import state
    from alarm_app.data.alarm_store import load_alarm_slice_for_bdt
except ImportError:
    from bdt.parser import BDTData, load_bdt_photos
    from bdt.photo_auth import verify_photo_slots
    from bdt.validator import ValidationResult
    from constants import format_bdt_rule_label
    from data import state
    from data.alarm_store import load_alarm_slice_for_bdt


class _VerticalExpandButton(QPushButton):
    """Vertical expand/collapse button that fills the table height."""

    def sizeHint(self):
        size = super().sizeHint()
        return size.transposed()

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        return size.transposed()

    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.rotate(-90)
        painter.translate(-self.height(), 0)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.rect = self.rect().transposed()
        painter.drawControl(QStyle.CE_PushButton, option)


class BdtDetailPanel(QWidget):
    """BDT detail panel: info+discharge (left) | rules (center) | photos (right)."""

    # Adaptive section order for structural parser categories.
    _PHOTO_CATEGORY_ORDER = [
        "rectifier",
        "batteries",
        "modules",
        "load",
        "charging",
        "alarms",
        "other",
    ]
    _PHOTO_CATEGORY_TITLE = {
        "rectifier": "Rectifier",
        "batteries": "Batteries",
        "modules": "Modules / Settings",
        "load": "Load / Measurements",
        "charging": "Charging",
        "alarms": "Alarms",
        "other": "Other",
    }

    # Responsive thumbnail sizing bounds.
    _PHOTO_THUMB_MIN = 140
    _PHOTO_THUMB_MAX = 260

    _PHOTO_SUMMARY_CATEGORIES = {"rectifier", "batteries", "modules"}
    _DISCHARGE_FIXED_HEADERS = [
        "Time: min (h)",
        "Rec Bus V",
        "Rec Bus A",
        "Σ String A",
        "Δ Σ-Bus",
    ]
    _DISCHARGE_MAX_STRINGS = 8

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._current_bdt = None
        self._current_bdt_photos = None
        self._bdt_photo_last_viewport_w = 0
        self._bdt_discharge_expanded = False
        self._bdt_active_discharge_strings = 0
        self._build()

    @staticmethod
    def _mark_compact(button: QPushButton):
        button.setProperty("compact", True)
        button.setMinimumWidth(0)
        button.setMinimumHeight(max(26, button.fontMetrics().height() + 8))
        button.setMaximumHeight(16777215)
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    @staticmethod
    def _display_rule_verdict(rule) -> str:
        verdict = str(getattr(rule, "verdict", "") or "").strip()
        if verdict in {"Accepted", "Rejected", "Revise"}:
            return verdict
        return "No data"

    @staticmethod
    def _photo_verification_text(slot) -> str:
        verification = dict(getattr(slot, "verification", {}) or {})
        synthid_info = dict(verification.get("synthid") or {})
        synthid_status = str(synthid_info.get("status") or "")
        synthid_conf = synthid_info.get("confidence")
        if synthid_status == "detected":
            conf_txt = f" ({float(synthid_conf):.2f})" if synthid_conf is not None else ""
            return f"<span style='color:#f38ba8;'>AI flag: SynthID detected{conf_txt}</span>"
        return ""

    # ------------------------------------------------------------------
    def _build(self):
        """Build BDT detail panel: info+discharge (left) | rules (center) | photos (right)."""
        self.setObjectName("bdt_detail_panel")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 0)
        outer.setSpacing(0)

        # Horizontal splitter for resizable sections
        self._bdt_detail_splitter = QSplitter(Qt.Horizontal)
        self._bdt_detail_splitter.setHandleWidth(3)
        self._bdt_detail_splitter.setChildrenCollapsible(False)

        # ═══ LEFT — info grid + discharge table ═══
        left = QWidget()
        left.setMinimumWidth(220)
        left.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setHandleWidth(3)
        left_splitter.setChildrenCollapsible(False)
        self._bdt_left_splitter = left_splitter
        left_lay.addWidget(left_splitter, 1)

        info_section = QWidget()
        info_section_lay = QVBoxLayout(info_section)
        info_section_lay.setContentsMargins(0, 0, 0, 0)
        info_section_lay.setSpacing(4)

        lbl_info = QLabel("FILE INFO")
        lbl_info.setObjectName("bdt_section_title")
        info_section_lay.addWidget(lbl_info)

        # Info grid
        info_frame = QFrame()
        info_frame.setObjectName("bdt_info_frame")
        grid = QGridLayout(info_frame)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)

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
            v.setMinimumWidth(90)
            v.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            grid.addWidget(k, row_idx, 0)
            grid.addWidget(v, row_idx, 1)
            self._bdt_info_labels[key] = v
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        # Push the grid rows to the top of the frame so a tall scroll
        # area doesn't leave a huge empty strip below the last field.
        grid.setRowStretch(len(info_fields), 1)

        # Wrap the info grid in a scroll area so the File Info section
        # can shrink and scroll internally instead of hogging all the
        # left-column space. The stretch factor below (added to
        # left_lay) makes it share vertical room evenly with the
        # Discharge Readings table.
        info_scroll = QScrollArea()
        info_scroll.setObjectName("bdt_info_scroll")
        info_scroll.setWidget(info_frame)
        info_scroll.setWidgetResizable(True)
        info_scroll.setFrameShape(QFrame.NoFrame)
        info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        info_scroll.setMinimumHeight(110)
        info_section_lay.addWidget(info_scroll, 1)

        btn_open_bdt = QPushButton("Open BDT File")
        btn_open_bdt.setObjectName("btn_search")
        self._mark_compact(btn_open_bdt)
        btn_open_bdt.clicked.connect(self._open_current_bdt_file)
        info_section_lay.addWidget(btn_open_bdt)
        self._btn_open_bdt = btn_open_bdt

        left_splitter.addWidget(info_section)

        discharge_section = QWidget()
        discharge_section_lay = QVBoxLayout(discharge_section)
        discharge_section_lay.setContentsMargins(0, 0, 0, 0)
        discharge_section_lay.setSpacing(4)

        lbl_dis = QLabel("DISCHARGE READINGS")
        lbl_dis.setObjectName("bdt_section_title")
        discharge_section_lay.addWidget(lbl_dis)

        discharge_wrap = QWidget()
        discharge_wrap_lay = QHBoxLayout(discharge_wrap)
        discharge_wrap_lay.setContentsMargins(0, 0, 0, 0)
        discharge_wrap_lay.setSpacing(8)

        self._bdt_discharge_table = QTableWidget(0, len(self._discharge_headers(0)))
        self._apply_discharge_header_items(self._bdt_discharge_table, 0)
        self._bdt_discharge_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self._bdt_discharge_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self._bdt_discharge_table.setAlternatingRowColors(True)
        self._bdt_discharge_table.verticalHeader().setVisible(False)
        self._bdt_discharge_table.verticalHeader().setDefaultSectionSize(24)
        self._bdt_discharge_table.setMinimumHeight(120)
        self._bdt_discharge_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._bdt_discharge_table.setStyleSheet(
            "QTableWidget { gridline-color: #c7cfdf; }"
            "QTableWidget::item { padding: 6px 8px; }"
        )
        dis_hdr = self._bdt_discharge_table.horizontalHeader()
        dis_hdr.setDefaultAlignment(Qt.AlignCenter)
        dis_hdr.setMinimumHeight(56)
        dis_hdr.setFixedHeight(74)
        dis_hdr.resizeSection(0, 190)
        dis_hdr.resizeSection(1, 122)
        dis_hdr.resizeSection(2, 122)
        dis_hdr.resizeSection(3, 132)
        dis_hdr.resizeSection(4, 118)
        dis_hdr.setStretchLastSection(True)
        discharge_wrap_lay.addWidget(self._bdt_discharge_table, 1)

        self._btn_discharge_expand = _VerticalExpandButton("EXPAND STRINGS ⇲")
        self._btn_discharge_expand.setObjectName("btn_discharge_expand")
        self._btn_discharge_expand.setMinimumWidth(54)
        self._btn_discharge_expand.setMaximumWidth(54)
        self._btn_discharge_expand.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._btn_discharge_expand.setCursor(Qt.PointingHandCursor)
        self._btn_discharge_expand.setToolTip("Show or hide per-string discharge columns")
        self._btn_discharge_expand.setStyleSheet(
            "QPushButton#btn_discharge_expand {"
            "background-color: #274060; color: #ffffff; border: 1px solid #36557e; "
            "border-radius: 14px; padding: 12px 8px; font-weight: 800; font-size: 11px; "
            "letter-spacing: 1px; }"
            "QPushButton#btn_discharge_expand:hover {"
            "background-color: #36557e; border-color: #4a6fa5; }"
        )
        self._btn_discharge_expand.clicked.connect(self._toggle_discharge_table_expanded)
        discharge_wrap_lay.addWidget(self._btn_discharge_expand)
        discharge_section_lay.addWidget(discharge_wrap, 1)
        left_splitter.addWidget(discharge_section)
        left_splitter.setSizes([280, 320])
        self._apply_discharge_column_visibility()

        self._bdt_detail_splitter.addWidget(left)

        # ═══ CENTER — validation rules ═══
        center = QWidget()
        center.setMinimumWidth(220)
        center.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(4)

        center_splitter = QSplitter(Qt.Vertical)
        center_splitter.setHandleWidth(3)
        center_splitter.setChildrenCollapsible(False)
        self._bdt_center_splitter = center_splitter
        center_lay.addWidget(center_splitter, 1)

        rules_section = QWidget()
        rules_section_lay = QVBoxLayout(rules_section)
        rules_section_lay.setContentsMargins(0, 0, 0, 0)
        rules_section_lay.setSpacing(4)

        lbl_rules = QLabel("VALIDATION RULES")
        lbl_rules.setObjectName("bdt_section_title")
        rules_section_lay.addWidget(lbl_rules)

        # Rules table — THE primary content of the detail panel, so it
        # always claims the leftover vertical space (stretch=1) and has a
        # real minimum height so empty history sections can't squish it.
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
        self._bdt_rules_table.setMinimumHeight(170)
        rules_hdr = self._bdt_rules_table.horizontalHeader()
        rules_hdr.resizeSection(0, 50)
        rules_hdr.resizeSection(1, 140)
        rules_hdr.resizeSection(2, 80)
        rules_hdr.setStretchLastSection(True)
        rules_section_lay.addWidget(self._bdt_rules_table, 1)

        # Parse errors label (hidden by default)
        self._bdt_parse_errors_lbl = QLabel("")
        self._bdt_parse_errors_lbl.setStyleSheet(
            "color:#f38ba8; font-size:11px; background:transparent; padding:4px;")
        self._bdt_parse_errors_lbl.setWordWrap(True)
        self._bdt_parse_errors_lbl.setVisible(False)
        rules_section_lay.addWidget(self._bdt_parse_errors_lbl)
        center_splitter.addWidget(rules_section)

        history_section = QWidget()
        history_section_lay = QVBoxLayout(history_section)
        history_section_lay.setContentsMargins(0, 0, 0, 0)
        history_section_lay.setSpacing(4)

        # ── Door Alarm History ─────────────────────────────────────
        # Kept visually minimal when empty — section cap + single-line
        # placeholder. Only expands to a real table when door alarms
        # actually exist, so the Validation Rules section above keeps
        # the vertical real estate.
        self._bdt_door_section_label = QLabel("DOOR ALARM HISTORY")
        self._bdt_door_section_label.setObjectName("bdt_section_title")
        self._bdt_door_section_label.setVisible(False)
        history_section_lay.addWidget(self._bdt_door_section_label)

        self._bdt_door_window_hint = QLabel("")
        self._bdt_door_window_hint.setObjectName("bdt_empty_hint")
        self._bdt_door_window_hint.setWordWrap(True)
        self._bdt_door_window_hint.setVisible(False)
        history_section_lay.addWidget(self._bdt_door_window_hint)

        self._bdt_door_table = QTableWidget(0, 6)
        self._bdt_door_table.setHorizontalHeaderLabels(
            ["Site", "Occurred", "Cleared", "Alarm", "R10 Status", "Overlap"])
        self._bdt_door_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._bdt_door_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._bdt_door_table.setAlternatingRowColors(True)
        self._bdt_door_table.verticalHeader().setVisible(False)
        self._bdt_door_table.verticalHeader().setDefaultSectionSize(24)
        self._bdt_door_table.setColumnWidth(0, 80)
        self._bdt_door_table.setColumnWidth(1, 130)
        self._bdt_door_table.setColumnWidth(2, 130)
        self._bdt_door_table.setColumnWidth(3, 120)
        self._bdt_door_table.setColumnWidth(4, 90)
        self._bdt_door_table.setColumnWidth(5, 70)
        self._bdt_door_table.horizontalHeader().setStretchLastSection(True)
        self._bdt_door_table.setMaximumHeight(160)
        self._bdt_door_table.setVisible(False)
        history_section_lay.addWidget(self._bdt_door_table)

        self._bdt_door_empty = QLabel("—  no door alarms for this test date")
        self._bdt_door_empty.setObjectName("bdt_empty_hint")
        self._bdt_door_empty.setVisible(False)
        history_section_lay.addWidget(self._bdt_door_empty)

        # ── Test History Comparison ────────────────────────────────
        self._bdt_hist_section_label = QLabel("TEST HISTORY COMPARISON")
        self._bdt_hist_section_label.setObjectName("bdt_section_title")
        self._bdt_hist_section_label.setVisible(False)
        history_section_lay.addWidget(self._bdt_hist_section_label)

        self._bdt_history_table = QTableWidget(0, 3)
        self._bdt_history_table.setHorizontalHeaderLabels(
            ["Field", "Previous", "Current"])
        self._bdt_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._bdt_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._bdt_history_table.setAlternatingRowColors(True)
        self._bdt_history_table.verticalHeader().setVisible(False)
        self._bdt_history_table.verticalHeader().setDefaultSectionSize(24)
        self._bdt_history_table.setColumnWidth(0, 130)
        self._bdt_history_table.setColumnWidth(1, 130)
        self._bdt_history_table.horizontalHeader().setStretchLastSection(True)
        self._bdt_history_table.setMaximumHeight(200)
        self._bdt_history_table.setVisible(False)
        history_section_lay.addWidget(self._bdt_history_table)

        self._bdt_history_label = QLabel(
            "—  no previous test history found")
        self._bdt_history_label.setObjectName("bdt_empty_hint")
        self._bdt_history_label.setWordWrap(True)
        self._bdt_history_label.setVisible(False)
        history_section_lay.addWidget(self._bdt_history_label)
        center_splitter.addWidget(history_section)
        center_splitter.setSizes([420, 220])

        self._bdt_detail_splitter.addWidget(center)

        # ═══ RIGHT — photo gallery ═══
        right = QWidget()
        right.setMinimumWidth(260)
        right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)

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
        self._bdt_photo_grid.setContentsMargins(3, 3, 3, 3)
        self._bdt_photo_grid.setSpacing(6)
        scroll.setWidget(self._bdt_photo_container)

        right_lay.addWidget(scroll, 1)

        self._bdt_detail_splitter.addWidget(right)

        # Initial proportions favor photos (left:center:right ≈ 1:1.4:2.8)
        self._bdt_detail_splitter.setSizes([260, 360, 720])
        # On window resize, give photos most of the new space.
        self._bdt_detail_splitter.setStretchFactor(0, 0)  # file info
        self._bdt_detail_splitter.setStretchFactor(1, 1)  # rules
        self._bdt_detail_splitter.setStretchFactor(2, 3)  # photos
        self._bdt_detail_splitter.setCollapsible(0, False)
        self._bdt_detail_splitter.setCollapsible(1, False)
        self._bdt_detail_splitter.setCollapsible(2, False)
        # Hold a reference to the photo scroll so we can size thumbnails
        # against its viewport width when laying out.
        self._bdt_photo_scroll = scroll

        # Debounced re-layout on splitter drag so thumbnails grow / shrink
        # to fit the new column width.
        self._bdt_photo_relayout_timer = QTimer(self)
        self._bdt_photo_relayout_timer.setSingleShot(True)
        self._bdt_photo_relayout_timer.setInterval(120)
        self._bdt_photo_relayout_timer.timeout.connect(
            self._relayout_bdt_photos_if_needed)
        self._bdt_detail_splitter.splitterMoved.connect(
            lambda *_: self._bdt_photo_relayout_timer.start())

        outer.addWidget(self._bdt_detail_splitter)
        self._apply_responsive_splitters()

    # ------------------------------------------------------------------
    # Data population
    # ------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_splitters()
        if hasattr(self, "_bdt_photo_relayout_timer"):
            self._bdt_photo_relayout_timer.start()

    def _apply_responsive_splitters(self):
        if not hasattr(self, "_bdt_detail_splitter"):
            return
        total = max(1, self._bdt_detail_splitter.width())
        left = int(total * 0.26)
        center = int(total * 0.25)
        right = max(1, total - left - center)
        self._bdt_detail_splitter.setSizes([left, center, max(1, right)])

        if hasattr(self, "_bdt_left_splitter"):
            left_total = max(1, self._bdt_left_splitter.height())
            info_h = max(90, int(left_total * 0.48))
            self._bdt_left_splitter.setSizes([info_h, max(1, left_total - info_h)])
        if hasattr(self, "_bdt_center_splitter"):
            center_total = max(1, self._bdt_center_splitter.height())
            rules_h = max(120, int(center_total * 0.68))
            self._bdt_center_splitter.setSizes([rules_h, max(1, center_total - rules_h)])

    def populate(self, res: ValidationResult):
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
                "end_rectifier_voltage": self._viewer._bdt_validation_panel._format_end_rectifier_voltage(bdt),
                "lead_acid_soh": self._viewer._bdt_validation_panel._format_lead_acid_soh(bdt),
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
            vals = dict.fromkeys(self._bdt_info_labels, "--")

        for key, lbl in self._bdt_info_labels.items():
            lbl.setText(vals.get(key, "--"))

        # ── Discharge table ──
        self._bdt_discharge_table.setRowCount(0)
        self._bdt_active_discharge_strings = 0
        self._bdt_discharge_table.setColumnCount(len(self._discharge_headers(0)))
        self._apply_discharge_header_items(self._bdt_discharge_table, 0)
        self._apply_discharge_column_visibility()
        if bdt:
            rows = self._build_discharge_detail_rows(bdt)
            theme_mode = self._resolved_theme_mode()
            self._bdt_active_discharge_strings = max(
                (len(row["strings"]) for row in rows),
                default=0,
            )
            self._bdt_discharge_table.setRowCount(len(rows))
            start_bg = QColor("#1a2744")
            end_bg = QColor("#2e1a22")
            string_headers = self._discharge_display_headers(self._bdt_active_discharge_strings)
            if self._bdt_discharge_table.columnCount() != len(string_headers):
                self._bdt_discharge_table.setColumnCount(len(string_headers))
            self._apply_discharge_header_items(
                self._bdt_discharge_table,
                self._bdt_active_discharge_strings,
            )
            dis_hdr = self._bdt_discharge_table.horizontalHeader()
            dis_hdr.setStretchLastSection(False)
            for col in range(self._bdt_discharge_table.columnCount()):
                if col == 0:
                    dis_hdr.resizeSection(col, 270)
                elif col < len(self._DISCHARGE_FIXED_HEADERS):
                    dis_hdr.resizeSection(col, 160)
                else:
                    dis_hdr.resizeSection(col, 138)

            for r, row in enumerate(rows):
                values = [
                    row["label"],
                    self._format_discharge_value(row["bus_v"]),
                    self._format_discharge_value(row["bus_a"]),
                    self._format_discharge_value(row["sum_string_a"]),
                    self._format_discharge_value(row["delta_sum_minus_bus"]),
                ]
                for string_v, string_a in row["strings"]:
                    values.extend([
                        self._format_discharge_value(string_v),
                        self._format_discharge_value(string_a),
                    ])

                for c, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if c == 0:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    else:
                        item.setTextAlignment(Qt.AlignCenter)
                    _, section_bg = self._discharge_section_palette(
                        self._discharge_section_index_for_column(c),
                        theme_mode,
                    )
                    if row["row_kind"] == "before":
                        item.setBackground(start_bg)
                    elif row["row_kind"] == "after":
                        item.setBackground(end_bg)
                    else:
                        item.setBackground(section_bg)
                    if c == 4 and row["delta_sum_minus_bus"] is not None:
                        delta = float(row["delta_sum_minus_bus"])
                        if -3.0 <= delta <= 0.0:
                            item.setForeground(QColor("#a6e3a1"))
                        else:
                            item.setForeground(QColor("#f38ba8"))
                    self._bdt_discharge_table.setItem(r, c, item)

            self._apply_discharge_column_visibility()

        # ── Rules table ──
        verdict_colors = {
            "Accepted": QColor("#a6e3a1"),
            "Rejected": QColor("#f38ba8"),
            "Revise":   QColor("#fab387"),
            "No data":  QColor("#45475a"),
        }
        self._bdt_rules_table.setRowCount(len(res.rules))
        for r, rule in enumerate(res.rules):
            visible_verdict = self._display_rule_verdict(rule)
            items = [
                QTableWidgetItem(rule.rule_id),
                QTableWidgetItem(format_bdt_rule_label(rule.rule_id, rule.rule_name)),
                QTableWidgetItem(visible_verdict),
                QTableWidgetItem(rule.detail),
            ]
            for c, item in enumerate(items):
                if c < 3:
                    item.setTextAlignment(Qt.AlignCenter)
                if c == 2:
                    item.setForeground(
                        verdict_colors.get(visible_verdict, QColor("#cdd6f4")))
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
        self._bdt_door_window_hint.setText("")
        self._bdt_door_window_hint.setVisible(False)
        if bdt and bdt.test_date:
            try:
                try:
                    from alarm_app.bdt.validator import _evaluate_door_evidence
                except ImportError:
                    from bdt.validator import _evaluate_door_evidence
                test_date_ts = pd.Timestamp(bdt.test_date).normalize()
                alarm_df = self._load_door_alarm_subset(bdt.site_code, test_date_ts)
                if not alarm_df.empty:
                    evidence = _evaluate_door_evidence(bdt, alarm_df)
                    if evidence.window_start is not None and evidence.window_end is not None:
                        window_text = (
                            f"Onsite window: {evidence.window_start.strftime('%H:%M')} → "
                            f"{evidence.window_end.strftime('%H:%M')}"
                        )
                        if evidence.best is not None and evidence.best.status_label == "Revise":
                            window_text += (
                                " — door evidence overlaps the visit but extends outside "
                                "recorded time_in/time_out; reviewer decision"
                            )
                        self._bdt_door_window_hint.setText(window_text)
                        self._bdt_door_window_hint.setVisible(True)

                    if evidence.rows:
                        sorted_rows = sorted(
                            evidence.rows,
                            key=lambda row: (
                                0 if evidence.best is not None and row.row_index == evidence.best.row_index else 1,
                                -row.overlap_min,
                            ),
                        )
                        status_colors = {
                            "Accepted": QColor("#a6e3a1"),
                            "Revise": QColor("#fab387"),
                            "No overlap": QColor("#f38ba8"),
                        }
                        self._bdt_door_table.setRowCount(len(sorted_rows))
                        for i, door_row in enumerate(sorted_rows):
                            occ = door_row.occurred_on
                            clr = door_row.cleared_on
                            self._bdt_door_table.setItem(
                                i, 0, QTableWidgetItem(door_row.site_id))
                            self._bdt_door_table.setItem(
                                i, 1, QTableWidgetItem(occ.strftime("%Y-%m-%d %H:%M")))
                            cleared_text = (
                                clr.strftime("%Y-%m-%d %H:%M")
                                if clr is not None and hasattr(clr, "strftime")
                                else "—"
                            )
                            self._bdt_door_table.setItem(
                                i, 2, QTableWidgetItem(cleared_text))
                            self._bdt_door_table.setItem(
                                i, 3, QTableWidgetItem(door_row.alarm_name))
                            status_item = QTableWidgetItem(door_row.status_label)
                            status_item.setForeground(
                                status_colors.get(door_row.status_label, QColor("#cdd6f4"))
                            )
                            self._bdt_door_table.setItem(i, 4, status_item)
                            overlap_text = (
                                f"{door_row.overlap_min:.0f}m"
                                if door_row.overlap_min > 0
                                else "—"
                            )
                            self._bdt_door_table.setItem(
                                i, 5, QTableWidgetItem(overlap_text))
            except Exception:
                pass  # Graceful fallback if alarm data unavailable

        has_doors = self._bdt_door_table.rowCount() > 0
        self._sync_optional_sections(has_doors=has_doors, has_history=False)

        # ── Populate test history comparison ──────────────────
        self._bdt_history_table.setRowCount(0)
        self._bdt_history_label.setText("—  no previous test history found")
        if bdt and bdt.site_code:
            try:
                from datetime import date as date_type

                try:
                    from alarm_app.bdt.history import (
                        compare_tests,
                        load_previous_test,
                        load_second_most_recent_test,
                    )
                except ImportError:
                    from bdt.history import (
                        compare_tests,
                        load_previous_test,
                        load_second_most_recent_test,
                    )
                test_date = None
                if bdt.test_date:
                    test_date = (bdt.test_date.date()
                                 if hasattr(bdt.test_date, "date")
                                 else bdt.test_date)

                prev = None
                if isinstance(test_date, date_type):
                    prev = load_previous_test(bdt.site_code, test_date)

                # Fallback: when test_date is missing or no earlier test
                # exists, grab the second most recent test for this site.
                if prev is None:
                    prev = load_second_most_recent_test(bdt.site_code)

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

                    if getattr(comp, "upgrade_detected", False):
                        self._bdt_history_label.setText(
                            f"<span style='color:#89b4fa;'>{comp.change_status} vs {prev.test_date}</span>")
                    elif comp.has_critical_change:
                        self._bdt_history_label.setText(
                            f"<span style='color:#f38ba8;'>Equipment change detected vs {prev.test_date}</span>")
                    else:
                        self._bdt_history_label.setText(
                            f"<span style='color:#a6e3a1;'>No critical changes vs {prev.test_date}</span>")
                else:
                    self._bdt_history_label.setText(
                        "—  no previous test history found")
            except ImportError:
                self._bdt_history_label.setText(
                    "—  history module not available")
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    "History comparison failed for site %s", bdt.site_code, exc_info=True)

        has_history = self._bdt_history_table.rowCount() > 0
        self._sync_optional_sections(has_doors=has_doors, has_history=has_history)

        # ── Photos (lazy-load if skipped during batch validation) ──
        if bdt:
            load_bdt_photos(bdt)
        self._populate_bdt_photos(bdt)
        self._current_bdt = bdt

    @classmethod
    def _discharge_headers(cls, active_strings: int | None = None) -> list[str]:
        headers = list(cls._DISCHARGE_FIXED_HEADERS)
        limit = cls._DISCHARGE_MAX_STRINGS if active_strings is None else max(0, min(cls._DISCHARGE_MAX_STRINGS, int(active_strings)))
        for idx in range(1, limit + 1):
            headers.extend([f"S{idx} V", f"S{idx} A"])
        return headers

    @classmethod
    def _discharge_display_headers(cls, active_strings: int | None = None) -> list[str]:
        headers = [
            "TIME: MIN (H)",
            "REC BUS\nV",
            "REC BUS\nA",
            "Σ STRING\nA",
            "Δ Σ-BUS",
        ]
        limit = cls._DISCHARGE_MAX_STRINGS if active_strings is None else max(0, min(cls._DISCHARGE_MAX_STRINGS, int(active_strings)))
        for idx in range(1, limit + 1):
            headers.extend([f"STRING {idx}\nV", f"STRING {idx}\nA"])
        return headers

    @classmethod
    def _discharge_section_index_for_column(cls, col: int) -> int:
        if col <= 4:
            return col
        return 5 + ((col - 5) // 2)

    @classmethod
    def _discharge_section_palette(cls, section_index: int, theme_mode: str = "dark") -> tuple[QColor, QColor]:
        if theme_mode == "light":
            header_palette = [
                QColor("#edf2ff"),
                QColor("#eaf2ff"),
                QColor("#eef4ff"),
                QColor("#f4efff"),
                QColor("#fff0f6"),
                QColor("#eef5ff"),
                QColor("#f4f9ff"),
                QColor("#eef5ff"),
                QColor("#f4f9ff"),
                QColor("#eef5ff"),
                QColor("#f4f9ff"),
            ]
            body_palette = [
                QColor("#fbfcff"),
                QColor("#f6f9ff"),
                QColor("#f8faff"),
                QColor("#faf8ff"),
                QColor("#fff8fb"),
                QColor("#f4f8ff"),
                QColor("#f8fbff"),
                QColor("#f4f8ff"),
                QColor("#f8fbff"),
                QColor("#f4f8ff"),
                QColor("#f8fbff"),
                QColor("#f4f8ff"),
                QColor("#f8fbff"),
            ]
            header = header_palette[section_index] if section_index < len(header_palette) else QColor("#eef5ff" if section_index % 2 == 0 else "#f4f9ff")
            body = body_palette[section_index] if section_index < len(body_palette) else QColor("#f4f8ff" if section_index % 2 == 0 else "#f8fbff")
            return header, body

        header_palette = [
            QColor("#1f2134"),
            QColor("#18263d"),
            QColor("#1d2940"),
            QColor("#2a2240"),
            QColor("#3a2230"),
            QColor("#15283d"),
            QColor("#1b3143"),
            QColor("#15283d"),
            QColor("#1b3143"),
            QColor("#15283d"),
            QColor("#1b3143"),
        ]
        body_palette = [
            QColor("#171825"),
            QColor("#121d2f"),
            QColor("#152235"),
            QColor("#1e1930"),
            QColor("#281720"),
            QColor("#101d2c"),
            QColor("#142430"),
            QColor("#101d2c"),
            QColor("#142430"),
            QColor("#101d2c"),
            QColor("#142430"),
            QColor("#101d2c"),
            QColor("#142430"),
        ]
        header = header_palette[section_index] if section_index < len(header_palette) else QColor("#15283d" if section_index % 2 == 0 else "#1b3143")
        body = body_palette[section_index] if section_index < len(body_palette) else QColor("#101d2c" if section_index % 2 == 0 else "#142430")
        return header, body

    def _resolved_theme_mode(self) -> str:
        mode = str(getattr(self._viewer, "_theme_mode", "dark") or "dark")
        if mode == "auto" and hasattr(self._viewer, "_detect_os_theme"):
            try:
                return str(self._viewer._detect_os_theme() or "dark")
            except Exception:
                return "dark"
        return mode

    def _apply_discharge_header_items(self, table: QTableWidget, active_strings: int):
        theme_mode = self._resolved_theme_mode()
        header_fg = QColor("#5c6784") if theme_mode == "light" else QColor("#a6c8ff")
        for col, text in enumerate(self._discharge_display_headers(active_strings)):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            header_bg, _ = self._discharge_section_palette(
                self._discharge_section_index_for_column(col),
                theme_mode,
            )
            item.setBackground(header_bg)
            item.setForeground(header_fg)
            font = item.font()
            font.setBold(True)
            font.setPointSize(max(font.pointSize(), 10))
            item.setFont(font)
            table.setHorizontalHeaderItem(col, item)

    @staticmethod
    def _format_discharge_value(value) -> str:
        if value is None:
            return "--"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            text = str(value).strip()
            return text or "--"

    @classmethod
    def _detect_active_discharge_strings(cls, string_rows) -> int:
        active = 0
        for row in list(string_rows or []):
            for idx, pair in enumerate(list(row or [])[: cls._DISCHARGE_MAX_STRINGS]):
                try:
                    string_v, string_a = pair
                except (TypeError, ValueError):
                    continue
                if string_v is not None or string_a is not None:
                    active = max(active, idx + 1)
        return active

    @classmethod
    def _build_discharge_detail_rows(cls, bdt: BDTData) -> list[dict]:
        rows: list[dict] = []
        string_rows = list(getattr(bdt, "string_discharge_readings", []) or [])
        active_strings = cls._detect_active_discharge_strings(string_rows)

        before_strings = string_rows[0] if string_rows else []
        if (
            bdt.start_voltage is not None
            or bdt.start_ampere is not None
            or before_strings
        ):
            rows.append(
                cls._make_discharge_row(
                    "Before disconnecting Rectifier",
                    bdt.start_voltage,
                    bdt.start_ampere,
                    before_strings,
                    row_kind="before",
                    active_strings=active_strings,
                )
            )

        timed_string_rows = string_rows[1:] if len(string_rows) > 1 else []
        for idx, (label, bus_v, bus_a) in enumerate(getattr(bdt, "discharge_readings", []) or []):
            rows.append(
                cls._make_discharge_row(
                    str(label),
                    bus_v,
                    bus_a,
                    timed_string_rows[idx] if idx < len(timed_string_rows) else [],
                    row_kind="timed",
                    active_strings=active_strings,
                )
            )

        if (
            bdt.after_reconnect_voltage is not None
            or bdt.after_reconnect_ampere is not None
        ):
            rows.append(
                cls._make_discharge_row(
                    "After Connecting power",
                    bdt.after_reconnect_voltage,
                    bdt.after_reconnect_ampere,
                    [],
                    row_kind="after",
                    active_strings=active_strings,
                )
            )
        return rows

    @classmethod
    def _make_discharge_row(
        cls,
        label: str,
        bus_v: float | None,
        bus_a: float | None,
        strings: list[tuple[float | None, float | None]] | None,
        *,
        row_kind: str,
        active_strings: int | None = None,
    ) -> dict:
        pairs = list(strings or [])
        limit = cls._DISCHARGE_MAX_STRINGS if active_strings is None else max(0, min(cls._DISCHARGE_MAX_STRINGS, int(active_strings)))
        if len(pairs) < limit:
            pairs.extend([(None, None)] * (limit - len(pairs)))
        else:
            pairs = pairs[:limit]

        sum_string_a = None
        delta_sum_minus_bus = None
        if row_kind != "before":
            amps = [amp for _, amp in pairs if amp is not None]
            sum_string_a = sum(amps) if amps else None
            if sum_string_a is not None and bus_a is not None:
                delta_sum_minus_bus = float(sum_string_a) - float(bus_a)

        return {
            "label": label,
            "bus_v": bus_v,
            "bus_a": bus_a,
            "sum_string_a": sum_string_a,
            "delta_sum_minus_bus": delta_sum_minus_bus,
            "strings": pairs,
            "row_kind": row_kind,
        }

    def _toggle_discharge_table_expanded(self):
        self._bdt_discharge_expanded = not getattr(self, "_bdt_discharge_expanded", False)
        self._apply_discharge_column_visibility()

    def _apply_discharge_column_visibility(self):
        expanded = getattr(self, "_bdt_discharge_expanded", False)
        first_string_col = len(self._DISCHARGE_FIXED_HEADERS)
        active_strings = max(0, min(self._DISCHARGE_MAX_STRINGS, int(getattr(self, "_bdt_active_discharge_strings", 0) or 0)))
        total_string_cols = max(0, self._bdt_discharge_table.columnCount() - first_string_col)
        for idx in range(total_string_cols):
            self._bdt_discharge_table.setColumnHidden(first_string_col + idx, not expanded)
        self._btn_discharge_expand.setText("COLLAPSE ⇱" if expanded else "EXPAND STRINGS ⇲")
        self._btn_discharge_expand.setVisible(active_strings > 0)

    def _sync_optional_sections(self, *, has_doors: bool, has_history: bool):
        self._bdt_door_section_label.setVisible(has_doors)
        self._bdt_door_window_hint.setVisible(
            has_doors and bool(self._bdt_door_window_hint.text().strip())
        )
        self._bdt_door_table.setVisible(has_doors)
        self._bdt_door_empty.setVisible(False)
        self._bdt_hist_section_label.setVisible(has_history)
        self._bdt_history_table.setVisible(has_history)
        self._bdt_history_label.setVisible(has_history)

    @staticmethod
    def _load_door_alarm_subset(site_code: str, test_date: pd.Timestamp) -> pd.DataFrame:
        if not site_code or pd.isna(test_date):
            return pd.DataFrame()
        date_from = (pd.Timestamp(test_date) - pd.Timedelta(days=1)).to_pydatetime()
        date_to = (pd.Timestamp(test_date) + pd.Timedelta(days=1)).to_pydatetime()
        return load_alarm_slice_for_bdt([site_code], date_from, date_to)

    # ------------------------------------------------------------------
    # File opener
    # ------------------------------------------------------------------
    def _open_current_bdt_file(self):
        """Open the currently selected BDT file with the OS default application."""
        if not self._current_bdt or not self._current_bdt.file_path:
            return
        file_path = self._current_bdt.file_path
        if not os.path.isfile(file_path):
            file_name = os.path.basename(file_path)
            fallback_dirs: list[str] = []
            viewer_dir = getattr(self._viewer, "_uploaded_folder_path", "") or ""
            if viewer_dir:
                fallback_dirs.append(viewer_dir)
            edit_dir = getattr(getattr(self._viewer, "_edit_dir", None), "text", lambda: "")().strip()
            if edit_dir:
                fallback_dirs.append(edit_dir)
            site_path = getattr(self._viewer, "_uploaded_site_path", "") or ""
            if site_path:
                fallback_dirs.append(os.path.dirname(site_path))
            try:
                saved = state.load_state() or {}
                saved_dir = str(saved.get("uploaded_folder_path") or saved.get("directory") or "").strip()
                if saved_dir:
                    fallback_dirs.append(saved_dir)
            except Exception:
                pass

            for base in fallback_dirs:
                candidate = os.path.join(base, file_name)
                if os.path.isfile(candidate):
                    file_path = candidate
                    break

        url = QUrl.fromLocalFile(file_path)
        QDesktopServices.openUrl(url)

    # ------------------------------------------------------------------
    # Photo fullsize viewer
    # ------------------------------------------------------------------
    @staticmethod
    def _slot_has_image(slot) -> bool:
        return bool(getattr(slot, "image_data", None) or getattr(slot, "image_path", ""))

    @staticmethod
    def _slot_pixmap(slot) -> QPixmap:
        pix = QPixmap()
        image_data = getattr(slot, "image_data", None)
        if image_data:
            pix.loadFromData(image_data)
        else:
            image_path = str(getattr(slot, "image_path", "") or "")
            if image_path:
                pix.load(image_path)
        return pix

    @staticmethod
    def _slot_fullsize_source(slot):
        image_data = getattr(slot, "image_data", None)
        if image_data:
            return image_data
        return str(getattr(slot, "image_path", "") or "")

    def _show_photo_fullsize(self, image_source, label: str):
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
        if isinstance(image_source, (bytes, bytearray)):
            original_pix.loadFromData(bytes(image_source))
        else:
            original_pix.load(str(image_source or ""))

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

    # ------------------------------------------------------------------
    # Photo layout helpers
    # ------------------------------------------------------------------
    def _relayout_bdt_photos_if_needed(self):
        """Re-run _populate_bdt_photos if the photo scroll viewport width
        has changed materially since the last layout."""
        if not hasattr(self, "_bdt_photo_scroll"):
            return
        try:
            new_w = self._bdt_photo_scroll.viewport().width()
        except Exception:
            return
        last = getattr(self, "_bdt_photo_last_viewport_w", 0)
        # Only re-layout if the width change would shift the thumbnail size.
        if abs(new_w - last) < 24:
            return
        self._bdt_photo_last_viewport_w = new_w
        bdt = getattr(self, "_current_bdt_photos", None)
        if bdt is not None:
            self._populate_bdt_photos(bdt)

    def _compute_photo_thumb_width(self, cols: int) -> int:
        """Return the thumbnail width that fits the widest band in the
        current photo scroll viewport (safely clamped)."""
        try:
            viewport = self._bdt_photo_scroll.viewport().width()
        except Exception:
            viewport = 0
        if viewport <= 0:
            viewport = max(560, self._bdt_photo_scroll.width()
                           if hasattr(self, "_bdt_photo_scroll") else 560)
        cols = max(1, min(4, int(cols)))
        # Grid spacing (8) × (cols - 1) + container padding (8) +
        # card padding (8) × cols.
        chrome = 8 * (cols - 1) + 8 + 8 * cols
        available = viewport - chrome
        width = available // cols
        return max(self._PHOTO_THUMB_MIN,
                   min(self._PHOTO_THUMB_MAX, int(width)))

    def _group_photo_slots(self, bdt: BDTData | None) -> list[tuple[str, list]]:
        if not bdt or not bdt.photo_slots:
            return []
        grouped: dict[str, list] = {}
        for slot in bdt.photo_slots:
            # Skip empty placeholders so the gallery has no blank gaps.
            if not self._slot_has_image(slot):
                continue
            category = self._slot_category(slot)
            grouped.setdefault(category, []).append(slot)

        bands: list[tuple[str, list]] = []
        for category in self._PHOTO_CATEGORY_ORDER:
            slots = grouped.pop(category, [])
            if slots:
                bands.append((self._PHOTO_CATEGORY_TITLE.get(category, category.title()), slots))
        for category in sorted(grouped.keys()):
            slots = grouped[category]
            if slots:
                bands.append((self._PHOTO_CATEGORY_TITLE.get(category, category.title()), slots))
        return bands

    def _render_bdt_photo_bands(
        self,
        bands: list[tuple[str, list]],
        thumb_w: int,
        start_row: int,
        max_cols: int,
    ) -> int:
        """Render one BDT's photo bands into _bdt_photo_grid starting at
        start_row. Returns the next free grid_row after rendering."""
        grid_row = start_row
        for band_name, slots in bands:
            if not slots:
                continue
            heading = QLabel(band_name.upper())
            heading.setObjectName("bdt_section_title")
            heading.setAlignment(Qt.AlignLeft)
            self._bdt_photo_grid.addWidget(heading, grid_row, 0, 1, max_cols)
            grid_row += 1

            for idx, slot in enumerate(slots):
                row_offset = idx // max_cols
                col = idx % max_cols

                card = QFrame()
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(4, 4, 4, 4)
                card_lay.setSpacing(2)

                if self._slot_has_image(slot):
                    card.setObjectName("bdt_photo_card")
                    card.setCursor(Qt.PointingHandCursor)
                    pix = self._slot_pixmap(slot)
                    if pix.isNull():
                        card.setObjectName("bdt_photo_missing")
                        card.setMinimumHeight(int(thumb_w * 0.66))
                        na_lbl = QLabel("Not Available")
                        na_lbl.setObjectName("bdt_photo_missing_label")
                        na_lbl.setAlignment(Qt.AlignCenter)
                        card_lay.addWidget(na_lbl, 1)
                    else:
                        thumb = pix.scaledToWidth(
                            thumb_w, Qt.SmoothTransformation)
                        img_lbl = QLabel()
                        img_lbl.setPixmap(thumb)
                        img_lbl.setAlignment(Qt.AlignCenter)
                        card_lay.addWidget(img_lbl)
                        _source = self._slot_fullsize_source(slot)
                        _label = slot.label
                        card.mousePressEvent = lambda _, s=_source, l=_label: self._show_photo_fullsize(s, l)
                else:
                    card.setObjectName("bdt_photo_missing")
                    card.setMinimumHeight(int(thumb_w * 0.66))
                    na_lbl = QLabel("Not Available")
                    na_lbl.setObjectName("bdt_photo_missing_label")
                    na_lbl.setAlignment(Qt.AlignCenter)
                    card_lay.addWidget(na_lbl, 1)

                name_lbl = QLabel(slot.label)
                name_lbl.setObjectName("bdt_photo_label")
                name_lbl.setAlignment(Qt.AlignCenter)
                name_lbl.setWordWrap(True)
                card_lay.addWidget(name_lbl)

                auth_text = self._photo_verification_text(slot)
                if auth_text:
                    auth_lbl = QLabel(auth_text)
                    auth_lbl.setObjectName("bdt_photo_meta")
                    auth_lbl.setAlignment(Qt.AlignCenter)
                    auth_lbl.setWordWrap(True)
                    card_lay.addWidget(auth_lbl)

                self._bdt_photo_grid.addWidget(card, grid_row + row_offset, col)

            grid_row += (len(slots) - 1) // max_cols + 1

        return grid_row

    def _populate_bdt_photos(self, bdt: BDTData | None):
        """Fill the photo gallery grid with the current BDT's photos, then
        append every older sibling test for the same site beneath it,
        newest-first, each under its own 'PREVIOUS TEST — yyyy-MM-dd'
        separator. Siblings come from the currently loaded validation
        batch via _sibling_bdt_for_site."""
        # Clear existing widgets
        while self._bdt_photo_grid.count():
            item = self._bdt_photo_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Remember the current BDT so splitter/window resizes can re-layout.
        self._current_bdt_photos = bdt
        try:
            self._bdt_photo_last_viewport_w = (
                self._bdt_photo_scroll.viewport().width())
        except Exception:
            pass

        if not bdt or not bdt.photo_slots:
            lbl = QLabel("No photo data")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_photo_grid.addWidget(lbl, 0, 0)
            return

        try:
            verify_photo_slots(bdt.photo_slots)
        except Exception:
            pass

        bands = self._group_photo_slots(bdt)
        if not bands:
            lbl = QLabel("No photo data")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_photo_grid.addWidget(lbl, 0, 0)
            return
        max_slots_in_band = max((len(slots) for _, slots in bands), default=1)
        max_cols = max(1, min(4, max_slots_in_band))
        thumb_w = self._compute_photo_thumb_width(max_cols)

        # ── Current test ──────────────────────────────────────
        grid_row = self._render_bdt_photo_bands(
            bands, thumb_w, start_row=0, max_cols=max_cols)

        # ── Older sibling tests for the same site, newest-first ─
        # _sibling_bdt_for_site already sorts desc by test_date and excludes
        # the current BDT.
        try:
            siblings = self._sibling_bdt_for_site(bdt)
        except Exception:
            siblings = []

        current_ts = bdt.test_date
        older = [
            s for s in siblings
            if s.test_date and current_ts and s.test_date < current_ts
        ]

        for sibling in older:
            # Lazy-load photos from the sibling .xlsx (no-op if already loaded)
            try:
                load_bdt_photos(sibling)
            except Exception:
                continue
            if not sibling.photo_slots:
                continue
            try:
                verify_photo_slots(sibling.photo_slots)
            except Exception:
                pass

            # Separator heading — full width, distinct style
            sep_date = (sibling.test_date.strftime("%Y-%m-%d")
                        if sibling.test_date else "unknown date")
            summary = self._photo_category_summary(sibling.photo_slots)
            sep_text = (
                f"◂  PREVIOUS TEST    "
                f"{self._category_summary_text(sep_date, summary)}"
            )
            sep = QLabel(sep_text)
            sep.setObjectName("bdt_history_separator")
            sep.setAlignment(Qt.AlignLeft)
            self._bdt_photo_grid.addWidget(sep, grid_row, 0, 1, max_cols)
            grid_row += 1

            sibling_bands = self._group_photo_slots(sibling)
            sibling_cols = max(1, min(4, max((len(slots) for _, slots in sibling_bands), default=1)))
            sibling_thumb = self._compute_photo_thumb_width(sibling_cols)
            grid_row = self._render_bdt_photo_bands(
                sibling_bands, sibling_thumb, start_row=grid_row, max_cols=sibling_cols)

    # ------------------------------------------------------------------
    # Previous-test photo helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _slot_category(slot) -> str:
        category = getattr(slot, "category", "")
        if category:
            return str(category).lower()
        return "other"

    def _photo_category_summary(self, slots) -> dict[str, int]:
        summary = dict.fromkeys(sorted(self._PHOTO_SUMMARY_CATEGORIES), 0)
        for slot in slots:
            cat = self._slot_category(slot)
            if cat in summary and self._slot_has_image(slot):
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

    def _sibling_bdt_for_site(self, bdt: BDTData) -> list[BDTData]:
        """Collect other BDT files for the same site from map + filename fallback."""
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
        for candidate in self._viewer._bdt_by_site.get(key, []):
            _add_candidate(candidate)

        # Fallback source: filename contains current site code token.
        for res in self._viewer._bdt_results:
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
