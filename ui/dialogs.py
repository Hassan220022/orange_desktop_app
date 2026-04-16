"""Standalone dialog windows."""

from datetime import datetime

import pandas as pd

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QCheckBox, QScrollArea, QWidget,
    QTableWidget, QTableWidgetItem,
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

    def __init__(self, flags: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feature Flags")
        self.setFixedWidth(300)
        if parent:
            self.setStyleSheet(parent.styleSheet())

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
