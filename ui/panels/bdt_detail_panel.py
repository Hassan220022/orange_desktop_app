"""
BdtDetailPanel — BDT detail/photo gallery panel extracted from AlarmViewer.
"""

import os
import re
from datetime import datetime

import pandas as pd

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy,
    QDialog, QScrollArea, QGridLayout, QComboBox,
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QColor, QPixmap, QDesktopServices

try:
    from ...bdt.parser import BDTData, load_bdt_photos
    from ...bdt.validator import ValidationResult
    from ...data.alarm_store import load_alarm_slice_for_bdt
    from ...data import state
except ImportError:
    try:
        from alarm_app.bdt.parser import BDTData, load_bdt_photos
        from alarm_app.bdt.validator import ValidationResult
        from alarm_app.data.alarm_store import load_alarm_slice_for_bdt
        from alarm_app.data import state
    except ImportError:
        from bdt.parser import BDTData, load_bdt_photos
        from bdt.validator import ValidationResult
        from data.alarm_store import load_alarm_slice_for_bdt
        from data import state


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

    _COMPARE_KEY_CATEGORIES = {"rectifier", "batteries", "modules"}

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._current_bdt = None
        self._current_bdt_photos = None
        self._bdt_photo_last_viewport_w = 0
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        """Build BDT detail panel: info+discharge (left) | rules (center) | photos (right)."""
        self.setObjectName("bdt_detail_panel")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(0)

        # Horizontal splitter for resizable sections
        self._bdt_detail_splitter = QSplitter(Qt.Horizontal)
        self._bdt_detail_splitter.setHandleWidth(3)

        # ═══ LEFT — info grid + discharge table ═══
        left = QWidget()
        left.setMinimumWidth(260)
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
        info_scroll.setMinimumHeight(140)
        left_lay.addWidget(info_scroll, 1)

        btn_open_bdt = QPushButton("Open BDT File")
        btn_open_bdt.setObjectName("btn_search")
        btn_open_bdt.setFixedHeight(28)
        btn_open_bdt.setMinimumWidth(0)
        btn_open_bdt.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn_open_bdt.clicked.connect(self._open_current_bdt_file)
        left_lay.addWidget(btn_open_bdt)
        self._btn_open_bdt = btn_open_bdt

        lbl_dis = QLabel("DISCHARGE READINGS")
        lbl_dis.setObjectName("bdt_section_title")
        left_lay.addWidget(lbl_dis)

        # Discharge table — shares vertical space equally with the
        # File Info scroll area (both added with stretch=1 above/below).
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
        self._bdt_discharge_table.setMinimumHeight(140)
        dis_hdr = self._bdt_discharge_table.horizontalHeader()
        dis_hdr.resizeSection(0, 110)
        dis_hdr.resizeSection(1, 100)
        dis_hdr.setStretchLastSection(True)
        left_lay.addWidget(self._bdt_discharge_table, 1)

        self._bdt_detail_splitter.addWidget(left)

        # ═══ CENTER — validation rules ═══
        center = QWidget()
        center.setMinimumWidth(320)
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(6)

        lbl_rules = QLabel("VALIDATION RULES")
        lbl_rules.setObjectName("bdt_section_title")
        center_lay.addWidget(lbl_rules)

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
        self._bdt_rules_table.setMinimumHeight(200)
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

        # ── Door Alarm History ─────────────────────────────────────
        # Kept visually minimal when empty — section cap + single-line
        # placeholder. Only expands to a real table when door alarms
        # actually exist, so the Validation Rules section above keeps
        # the vertical real estate.
        self._bdt_door_section_label = QLabel("DOOR ALARM HISTORY")
        self._bdt_door_section_label.setObjectName("bdt_section_title")
        center_lay.addWidget(self._bdt_door_section_label)

        self._bdt_door_table = QTableWidget(0, 4)
        self._bdt_door_table.setHorizontalHeaderLabels(
            ["Site", "Occurred", "Cleared", "Alarm Name"])
        self._bdt_door_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._bdt_door_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._bdt_door_table.setAlternatingRowColors(True)
        self._bdt_door_table.verticalHeader().setVisible(False)
        self._bdt_door_table.verticalHeader().setDefaultSectionSize(24)
        self._bdt_door_table.setColumnWidth(0, 90)
        self._bdt_door_table.setColumnWidth(1, 150)
        self._bdt_door_table.setColumnWidth(2, 150)
        self._bdt_door_table.horizontalHeader().setStretchLastSection(True)
        self._bdt_door_table.setMaximumHeight(160)
        self._bdt_door_table.setVisible(False)
        center_lay.addWidget(self._bdt_door_table)

        self._bdt_door_empty = QLabel("—  no door alarms for this test date")
        self._bdt_door_empty.setObjectName("bdt_empty_hint")
        center_lay.addWidget(self._bdt_door_empty)

        # ── Test History Comparison ────────────────────────────────
        self._bdt_hist_section_label = QLabel("TEST HISTORY COMPARISON")
        self._bdt_hist_section_label.setObjectName("bdt_section_title")
        center_lay.addWidget(self._bdt_hist_section_label)

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
        center_lay.addWidget(self._bdt_history_table)

        self._bdt_history_label = QLabel(
            "—  no previous test history found")
        self._bdt_history_label.setObjectName("bdt_empty_hint")
        self._bdt_history_label.setWordWrap(True)
        center_lay.addWidget(self._bdt_history_label)

        self._bdt_detail_splitter.addWidget(center)

        # ═══ RIGHT — photo gallery ═══
        right = QWidget()
        right.setMinimumWidth(560)
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

        # Initial proportions favor photos (left:center:right ≈ 1:1.4:2.8)
        self._bdt_detail_splitter.setSizes([260, 360, 720])
        # On window resize, give photos most of the new space.
        self._bdt_detail_splitter.setStretchFactor(0, 0)  # file info
        self._bdt_detail_splitter.setStretchFactor(1, 1)  # rules
        self._bdt_detail_splitter.setStretchFactor(2, 3)  # photos
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

    # ------------------------------------------------------------------
    # Data population
    # ------------------------------------------------------------------
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
        if bdt and bdt.test_date:
            try:
                try:
                    from ...bdt.validator import _find_door_alarms
                except ImportError:
                    try:
                        from alarm_app.bdt.validator import _find_door_alarms
                    except ImportError:
                        from bdt.validator import _find_door_alarms
                test_date_ts = pd.Timestamp(bdt.test_date).normalize()
                alarm_df = self._load_door_alarm_subset(bdt.site_code, test_date_ts)
                doors = _find_door_alarms(alarm_df, bdt.site_code, test_date_ts)
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

        # Collapse the door section to its empty-hint when there's no data,
        # so Validation Rules above doesn't get squished by an empty table.
        has_doors = self._bdt_door_table.rowCount() > 0
        self._bdt_door_table.setVisible(has_doors)
        self._bdt_door_empty.setVisible(not has_doors)

        # ── Populate test history comparison ──────────────────
        self._bdt_history_table.setRowCount(0)
        self._bdt_history_label.setText("—  no previous test history found")
        if bdt and bdt.site_code:
            try:
                try:
                    from ...bdt.history import (
                        load_previous_test, compare_tests,
                        load_second_most_recent_test,
                    )
                except ImportError:
                    try:
                        from alarm_app.bdt.history import (
                            load_previous_test, compare_tests,
                            load_second_most_recent_test,
                        )
                    except ImportError:
                        from bdt.history import (
                            load_previous_test, compare_tests,
                            load_second_most_recent_test,
                        )
                from datetime import date as date_type, datetime as datetime_type
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

                    if comp.has_critical_change:
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

        # Collapse the history section to its empty-hint when there's no
        # previous record — keeps the Validation Rules table tall.
        has_history = self._bdt_history_table.rowCount() > 0
        self._bdt_history_table.setVisible(has_history)

        # ── Photos (lazy-load if skipped during batch validation) ──
        if bdt:
            load_bdt_photos(bdt)
        self._populate_bdt_photos(bdt)

        # ── Photo comparison setup ──
        self._current_bdt = bdt
        self._setup_photo_comparison(bdt)

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
            if not getattr(slot, "image_data", None):
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

                if slot.image_data:
                    card.setObjectName("bdt_photo_card")
                    card.setCursor(Qt.PointingHandCursor)
                    pix = QPixmap()
                    pix.loadFromData(slot.image_data)
                    thumb = pix.scaledToWidth(
                        thumb_w, Qt.SmoothTransformation)
                    img_lbl = QLabel()
                    img_lbl.setPixmap(thumb)
                    img_lbl.setAlignment(Qt.AlignCenter)
                    card_lay.addWidget(img_lbl)
                    _data = slot.image_data
                    _label = slot.label
                    card.mousePressEvent = lambda _, d=_data, l=_label: self._show_photo_fullsize(d, l)
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

                self._bdt_photo_grid.addWidget(card, grid_row + row_offset, col)

            grid_row += (len(slots) - 1) // max_cols + 1

        return grid_row

    def _populate_bdt_photos(self, bdt: BDTData | None):
        """Fill the photo gallery grid with the current BDT's photos, then
        append every older sibling test for the same site beneath it,
        newest-first, each under its own 'PREVIOUS TEST — yyyy-MM-dd'
        separator. Siblings come from the currently loaded validation
        batch via _comparison_candidates_for_site."""
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
        # _comparison_candidates_for_site already sorts desc by test_date
        # and excludes the current BDT.
        try:
            siblings = self._comparison_candidates_for_site(bdt)
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

            # Separator heading — full width, distinct style
            sep_date = (sibling.test_date.strftime("%Y-%m-%d")
                        if sibling.test_date else "unknown date")
            sep = QLabel(f"◂  PREVIOUS TEST    {sep_date}")
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
    # Photo comparison utilities
    # ------------------------------------------------------------------
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

    @staticmethod
    def _slot_match_key(slot) -> str:
        label = re.sub(r"\s+", " ", str(getattr(slot, "label", "")).strip().lower())
        category = str(getattr(slot, "category", "")).strip().lower() or "other"
        return f"{category}|{label}"

    def _comparison_slot_pairs(self, bdt: BDTData, other: BDTData,
                               all_slots: bool) -> list[tuple]:
        cur_map = {self._slot_match_key(slot): slot for slot in bdt.photo_slots}
        oth_map = {self._slot_match_key(slot): slot for slot in other.photo_slots}

        keys = sorted(set(cur_map.keys()) | set(oth_map.keys()))
        pairs: list[tuple] = []
        for key in keys:
            cur_slot = cur_map.get(key)
            oth_slot = oth_map.get(key)
            # Skip empty placeholders in comparison view (both sides must
            # have real images to avoid N/A gaps).
            if not (cur_slot and getattr(cur_slot, "image_data", None)):
                continue
            if not (oth_slot and getattr(oth_slot, "image_data", None)):
                continue
            if not all_slots:
                cur_cat = self._slot_category(cur_slot) if cur_slot else "other"
                oth_cat = self._slot_category(oth_slot) if oth_slot else "other"
                if (cur_cat not in self._COMPARE_KEY_CATEGORIES
                        and oth_cat not in self._COMPARE_KEY_CATEGORIES):
                    continue
            display = (getattr(cur_slot, "label", "") or getattr(oth_slot, "label", "") or key)
            pairs.append((display, cur_slot, oth_slot))
        return pairs

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

        slot_pairs = self._comparison_slot_pairs(bdt, other, all_slots)

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
                [cur for _, cur, _ in slot_pairs if cur is not None])
            oth_summary = self._build_compare_category_summary(
                [oth for _, _, oth in slot_pairs if oth is not None])
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

        if not slot_pairs:
            lbl = QLabel("No matching slots for this comparison mode")
            lbl.setObjectName("bdt_photo_label")
            lbl.setAlignment(Qt.AlignCenter)
            self._bdt_compare_grid.addWidget(lbl, grid_row, 0, 1, 3)
            return

        for display, cur_slot, oth_slot in slot_pairs:
            # Slot label
            name_lbl = QLabel(display)
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

        if slot and slot.image_data:
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
