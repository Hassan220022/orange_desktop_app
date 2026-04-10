"""
SearchPanel — command-console-style filter panel extracted from AlarmViewer.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QDateEdit, QComboBox, QFrame, QCheckBox, QSpinBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont, QTextCharFormat


class SearchPanel(QWidget):
    """Filter panel with site, classification, duration, date, action buttons
    and statistics sidebar."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._build(viewer)

    # ------------------------------------------------------------------
    @staticmethod
    def _style_calendar(date_edit: QDateEdit):
        """Fix weekend/holiday text colours on the calendar popup."""
        cal = date_edit.calendarWidget()
        if cal is None:
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#cdd6f4"))
        cal.setWeekdayTextFormat(Qt.Saturday, fmt)
        cal.setWeekdayTextFormat(Qt.Sunday, fmt)

    # ------------------------------------------------------------------
    def _build(self, viewer):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # ──────────────────────────────────────────────────────────
        # Filter panel — "Command Console" design
        # ──────────────────────────────────────────────────────────
        grp = QFrame()
        grp.setObjectName("filter_panel")
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(14, 12, 14, 12)
        gl.setSpacing(10)

        def _make_group(title: str, object_name: str = "filter_group"):
            frame = QFrame()
            frame.setObjectName(object_name)
            v = QVBoxLayout(frame)
            v.setContentsMargins(12, 8, 12, 10)
            v.setSpacing(5)
            cap = QLabel(title)
            cap.setObjectName("filter_section")
            v.addWidget(cap)
            inner = QHBoxLayout()
            inner.setSpacing(8)
            v.addLayout(inner)
            return frame, inner

        def _inline_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("filter_inline")
            return lbl

        # ── Row 1: Site / Classification / Duration ────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # — SITE group (flex)
        site_group, site_row = _make_group("SITE ID")
        self.edit_site = QLineEdit()
        self.edit_site.setObjectName("filter_input")
        self.edit_site.setPlaceholderText(
            "Comma-separated  —  e.g.  3420, 0813, KONA")
        self.edit_site.setMinimumWidth(200)
        self.edit_site.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.edit_site.returnPressed.connect(viewer._search)
        site_row.addWidget(self.edit_site)
        row1.addWidget(site_group, 1)

        # — CLASSIFICATION group (fixed)
        class_group, class_row = _make_group("CLASSIFICATION")

        self.cb_cat = QComboBox()
        self.cb_cat.setObjectName("filter_combo")
        self.cb_cat.addItems(["All", "Power", "Down", "Door"])
        self.cb_cat.setFixedWidth(100)
        self.cb_cat.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        class_row.addWidget(_inline_label("Category"))
        class_row.addWidget(self.cb_cat)

        self.cb_net = QComboBox()
        self.cb_net.setObjectName("filter_combo")
        self.cb_net.addItems(["All", "2G", "3G", "4G", "5G"])
        self.cb_net.setFixedWidth(78)
        self.cb_net.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        class_row.addWidget(_inline_label("Network"))
        class_row.addWidget(self.cb_net)

        self.cb_vnd = QComboBox()
        self.cb_vnd.setObjectName("filter_combo")
        self.cb_vnd.addItems(["All", "HUAWEI", "Nokia"])
        self.cb_vnd.setFixedWidth(100)
        self.cb_vnd.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        class_row.addWidget(_inline_label("Vendor"))
        class_row.addWidget(self.cb_vnd)

        row1.addWidget(class_group)

        # — DURATION group (fixed)
        dur_group, dur_row = _make_group("MIN DURATION")

        self.chk_mindur = QCheckBox("Active")
        self.chk_mindur.setObjectName("filter_toggle")
        self.chk_mindur.setChecked(True)
        self.chk_mindur.setToolTip(
            "Hide alarms shorter than the specified duration")
        dur_row.addWidget(self.chk_mindur)

        self.spn_mindur = QSpinBox()
        self.spn_mindur.setObjectName("filter_spin")
        self.spn_mindur.setRange(0, 1440)
        self.spn_mindur.setValue(15)
        self.spn_mindur.setSuffix(" min")
        self.spn_mindur.setToolTip("Minimum duration in minutes")
        self.spn_mindur.setFixedWidth(92)
        dur_row.addWidget(self.spn_mindur)

        row1.addWidget(dur_group)

        gl.addLayout(row1)

        # ── Row 2: DATE FILTER group (spans full width) ────────────
        date_frame = QFrame()
        date_frame.setObjectName("filter_group_date")
        date_v = QVBoxLayout(date_frame)
        date_v.setContentsMargins(12, 8, 12, 10)
        date_v.setSpacing(7)

        # Header row: cap label + master Date toggle
        date_head = QHBoxLayout()
        date_head.setSpacing(10)
        date_cap = QLabel("DATE FILTER")
        date_cap.setObjectName("filter_section")
        date_head.addWidget(date_cap)

        self.chk_date = QCheckBox("Enabled")
        self.chk_date.setObjectName("filter_toggle")
        self.chk_date.setChecked(True)
        self.chk_date.setToolTip("Enable / disable date filtering")
        self.chk_date.toggled.connect(viewer._toggle_date_filter)
        date_head.addWidget(self.chk_date)
        date_head.addStretch(1)
        date_v.addLayout(date_head)

        # Range sub-row
        range_row = QHBoxLayout()
        range_row.setSpacing(8)

        self.chk_date_range = QCheckBox("Range")
        self.chk_date_range.setObjectName("filter_toggle")
        self.chk_date_range.setChecked(True)
        self.chk_date_range.setToolTip(
            "Include the From-To range in date search")
        self.chk_date_range.toggled.connect(viewer._toggle_date_mode_controls)
        range_row.addWidget(self.chk_date_range)

        self.lbl_from = _inline_label("From")
        range_row.addWidget(self.lbl_from)
        self.d_from = QDateEdit(calendarPopup=True)
        self.d_from.setObjectName("filter_date")
        self.d_from.setDate(QDate(2025, 12, 1))
        self.d_from.setDisplayFormat("yyyy-MM-dd")
        self.d_from.setFixedWidth(128)
        self._style_calendar(self.d_from)
        range_row.addWidget(self.d_from)

        self.lbl_to = _inline_label("To")
        range_row.addWidget(self.lbl_to)
        self.d_to = QDateEdit(calendarPopup=True)
        self.d_to.setObjectName("filter_date")
        self.d_to.setDate(QDate.currentDate())
        self.d_to.setDisplayFormat("yyyy-MM-dd")
        self.d_to.setFixedWidth(128)
        self._style_calendar(self.d_to)
        range_row.addWidget(self.d_to)

        range_row.addStretch(1)

        # Quick-pick pills
        self.date_quick_widgets = []
        for label, days in (("TODAY", 0), ("7D", 7),
                            ("30D", 30), ("ALL", -1)):
            btn = QPushButton(label)
            btn.setObjectName("btn_pill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.clicked.connect(
                lambda _checked, d=days: viewer._quick_date(d))
            range_row.addWidget(btn)
            self.date_quick_widgets.append(btn)

        date_v.addLayout(range_row)

        # Specific days sub-row
        days_row = QHBoxLayout()
        days_row.setSpacing(8)

        self.chk_date_days = QCheckBox("Specific days")
        self.chk_date_days.setObjectName("filter_toggle")
        self.chk_date_days.setChecked(False)
        self.chk_date_days.setToolTip(
            "Include one or more exact days in date search")
        self.chk_date_days.toggled.connect(viewer._toggle_date_mode_controls)
        days_row.addWidget(self.chk_date_days)

        self.lbl_day = _inline_label("Day")
        days_row.addWidget(self.lbl_day)
        self.d_day = QDateEdit(calendarPopup=True)
        self.d_day.setObjectName("filter_date")
        self.d_day.setDate(QDate.currentDate())
        self.d_day.setDisplayFormat("yyyy-MM-dd")
        self.d_day.setFixedWidth(128)
        self._style_calendar(self.d_day)
        days_row.addWidget(self.d_day)

        self.btn_add_day = QPushButton("+ Add")
        self.btn_add_day.setObjectName("btn_pill_accent")
        self.btn_add_day.setCursor(Qt.PointingHandCursor)
        self.btn_add_day.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_add_day.clicked.connect(viewer._add_selected_day)
        days_row.addWidget(self.btn_add_day)

        self.edit_days = QLineEdit()
        self.edit_days.setObjectName("filter_input")
        self.edit_days.setPlaceholderText(
            "yyyy-mm-dd, yyyy-mm-dd, ...")
        self.edit_days.setToolTip(
            "Comma/space separated list of exact days")
        self.edit_days.setMinimumWidth(200)
        self.edit_days.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.edit_days.returnPressed.connect(viewer._search)
        days_row.addWidget(self.edit_days, 1)

        self.btn_clear_days = QPushButton("\u00d7 Clear")
        self.btn_clear_days.setObjectName("btn_ghost")
        self.btn_clear_days.setCursor(Qt.PointingHandCursor)
        self.btn_clear_days.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_clear_days.clicked.connect(viewer._clear_selected_days)
        days_row.addWidget(self.btn_clear_days)

        date_v.addLayout(days_row)

        gl.addWidget(date_frame)

        # NOTE: viewer._toggle_date_filter() is called by AlarmViewer._build_ui()
        # after bridge refs are assigned — do NOT call it here during construction.

        # ── Row 3: Action buttons ─────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        row3.addStretch(1)

        btn_search = QPushButton("Search")
        btn_search.setObjectName("btn_search")
        btn_search.setCursor(Qt.PointingHandCursor)
        btn_search.setMinimumWidth(0)
        btn_search.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn_search.clicked.connect(viewer._search)
        row3.addWidget(btn_search)

        btn_cl = QPushButton("Clear")
        btn_cl.setObjectName("btn_clear")
        btn_cl.setCursor(Qt.PointingHandCursor)
        btn_cl.setMinimumWidth(0)
        btn_cl.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn_cl.clicked.connect(viewer._clear_filters)
        row3.addWidget(btn_cl)

        self.btn_export = QPushButton("Export XLSX")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setMinimumWidth(0)
        self.btn_export.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_export.clicked.connect(viewer._export)
        row3.addWidget(self.btn_export)

        self.btn_backup = QPushButton("Backup Time")
        self.btn_backup.setObjectName("btn_backup")
        self.btn_backup.setCursor(Qt.PointingHandCursor)
        self.btn_backup.setMinimumWidth(0)
        self.btn_backup.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_backup.clicked.connect(viewer._show_backup_times)
        row3.addWidget(self.btn_backup)

        self.btn_site_sheet = QPushButton("Upload Site Sheet")
        self.btn_site_sheet.setObjectName("btn_dir")
        self.btn_site_sheet.setCursor(Qt.PointingHandCursor)
        self.btn_site_sheet.setMinimumWidth(0)
        self.btn_site_sheet.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_site_sheet.clicked.connect(viewer._upload_site_sheet)
        row3.addWidget(self.btn_site_sheet)

        self.btn_site_report = QPushButton("Generate Site Report")
        self.btn_site_report.setObjectName("btn_export")
        self.btn_site_report.setCursor(Qt.PointingHandCursor)
        self.btn_site_report.setMinimumWidth(0)
        self.btn_site_report.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_site_report.clicked.connect(viewer._export_site_sheet_report)
        row3.addWidget(self.btn_site_report)

        self.btn_both = QPushButton("Both P+D")
        self.btn_both.setObjectName("btn_both")
        self.btn_both.setCursor(Qt.PointingHandCursor)
        self.btn_both.setMinimumWidth(0)
        self.btn_both.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_both.setToolTip(
            "Show only sites that have both Power and Down alarms")
        self.btn_both.clicked.connect(viewer._activate_both_pd)
        row3.addWidget(self.btn_both)

        gl.addLayout(row3)
        outer.addWidget(grp, 1)

        # ── Stats panel (right of search) ─────────────────
        stats_frame = QFrame()
        stats_frame.setObjectName("stats_frame")
        stats_frame.setFixedWidth(220)
        sf = QVBoxLayout(stats_frame)
        sf.setContentsMargins(12, 10, 12, 10)
        sf.setSpacing(7)

        sec_lbl = QLabel("STATISTICS")
        sec_lbl.setObjectName("stats_section_label")
        sf.addWidget(sec_lbl)

        self.stats: dict[str, QLabel] = {}
        stat_obj_names = {
            "total": "stat_total", "power": "stat_power",
            "down": "stat_down", "door": "stat_door",
            "sites": "stat_sites", "avg_dur": "stat_avg_dur",
        }
        for key, label in (
            ("total",    "Total Records"),
            ("power",    "Power Alarms"),
            ("down",     "Down Alarms"),
            ("door",     "Door Alarms"),
            ("sites",    "Unique Sites"),
            ("avg_dur",  "Avg Duration"),
        ):
            row_h = QHBoxLayout(); row_h.setSpacing(4)
            lt = QLabel(label)
            lt.setObjectName("stats_label")
            lv = QLabel("\u2014")
            lv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lv.setObjectName(stat_obj_names[key])
            self.stats[key] = lv
            row_h.addWidget(lt); row_h.addWidget(lv)
            sf.addLayout(row_h)

            if key != "avg_dur":
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setObjectName("stats_sep")
                sf.addWidget(sep)

        outer.addWidget(stats_frame)
