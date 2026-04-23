"""Standalone dialog windows."""

from datetime import datetime

import pandas as pd

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QCheckBox, QScrollArea, QWidget,
    QTableWidget, QTableWidgetItem, QSpinBox,
    QFileDialog, QMessageBox, QAbstractItemView, QHeaderView,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

try:
    from ..constants import BT_HEADERS, BT_WIDTHS
    from ..core.backup_time import fmt_td as _fmt_td
    from ..data import state
except ImportError:
    try:
        from alarm_app.constants import BT_HEADERS, BT_WIDTHS
        from alarm_app.core.backup_time import fmt_td as _fmt_td
        from alarm_app.data import state
    except ImportError:
        from constants import BT_HEADERS, BT_WIDTHS
        from core.backup_time import fmt_td as _fmt_td
        from data import state


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


class BdtParametersDialog(QDialog):
    """Edit active BDT validation parameters with inline explanations."""

    def __init__(self, *, health_pct: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BDT Validation Parameters")
        self.setMinimumWidth(460)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build(health_pct)

    def _build(self, health_pct: int):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        intro = QLabel(
            "These parameters affect the active BDT validation rules and their calculations."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#6c7086; font-size:12px; background:transparent;")
        lay.addWidget(intro)

        health_card = QFrame()
        health_card.setObjectName("workspace_card")
        health_lay = QVBoxLayout(health_card)
        health_lay.setContentsMargins(12, 12, 12, 12)
        health_lay.setSpacing(8)
        health_title = QLabel("Health")
        health_title.setObjectName("workspace_card_title")
        health_lay.addWidget(health_title)
        self._spn_health = QSpinBox()
        self._spn_health.setRange(50, 100)
        self._spn_health.setValue(int(health_pct))
        self._spn_health.setSuffix(" %")
        self._spn_health.setObjectName("filter_spin")
        health_lay.addWidget(self._spn_health)
        health_help = QLabel(
            "Assumed usable battery efficiency for lead-acid sizing checks. This is used when "
            "estimating theoretical backup time for Rule R8. Example: 80% means the app treats "
            "the battery as delivering 80% of nominal capacity. Lithium batteries are handled "
            "differently and do not use the same reduction."
        )
        health_help.setWordWrap(True)
        health_help.setStyleSheet("color:#6c7086; font-size:11px; background:transparent;")
        health_lay.addWidget(health_help)
        lay.addWidget(health_card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setObjectName("btn_search")
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

    def get_values(self) -> int:
        return self._spn_health.value()


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
    """Reference dialog that explains each BDT validation rule."""

    def __init__(self, *, rule_rows: list[tuple[str, str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("BDT Validation Rules")
        self.setMinimumWidth(760)
        self.setMinimumHeight(640)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build(rule_rows)

    def _build(self, rule_rows: list[tuple[str, str, str]]):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        intro = QLabel(
            "This reference explains what each BDT validation rule checks, so reviewers can read a verdict and understand the reason behind it."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#cdd6f4; font-size:13px; background:transparent;")
        lay.addWidget(intro)

        summary = QLabel(
            "Use it when you need a plain-language explanation of the rule intent, not just the short rule label shown in the table."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color:#6c7086; font-size:12px; background:transparent;")
        lay.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        rows_lay = QVBoxLayout(container)
        rows_lay.setContentsMargins(0, 0, 0, 0)
        rows_lay.setSpacing(10)

        for rule_code, rule_name, description in rule_rows:
            card = QFrame()
            card.setObjectName("workspace_card")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(12, 12, 12, 12)
            card_lay.setSpacing(6)

            title = QLabel(f"{rule_code} - {rule_name}")
            title.setObjectName("workspace_card_title")
            card_lay.addWidget(title)

            body = QLabel(description)
            body.setWordWrap(True)
            body.setStyleSheet("color:#cdd6f4; font-size:12px; background:transparent;")
            card_lay.addWidget(body)

            rows_lay.addWidget(card)

        rows_lay.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

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
            "and the Down alarm (site offline) for the same site.  "
            "Only pairs within a 72-hour window are shown.")
        note.setStyleSheet("color:#6c7086; font-size:11px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        # ── table ─────��──────────────────────────────────────────
        cols = [c for c in BT_HEADERS if c in df.columns]
        self._tbl = QTableWidget(len(df), len(cols))
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

        for r, row in df.iterrows():
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
