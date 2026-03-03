"""
Backup-time computation and dialog.
"""

import traceback
from datetime import datetime

import pandas as pd

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QAbstractItemView, QHeaderView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from .constants import BT_HEADERS, BT_WIDTHS


# ─────────────────────────────────────────────────────────────────
# Computation
# ─────────────────────────────────────────────────────────────────
def compute_backup_times(df: pd.DataFrame):
    """
    For each site, find Down alarms that fall **inside** a Power alarm's
    time window (power_occurred_on → power_cleared_on).  The backup time
    is how long the battery held: down_occurred_on − power_occurred_on.

    When multiple techs (2G/3G/4G/5G) go down within the same power
    outage, only the **longest** backup time is kept (last tech to die).

    Returns ``(result_df, error_msg)``.  *error_msg* is ``''`` on success.
    """
    if df.empty or "alarm_category" not in df.columns:
        return pd.DataFrame(), "No data loaded."

    need = ["site_id", "occurred_on", "cleared_on", "alarm_category",
            "network_type", "vendor"]
    sub = df[[c for c in need if c in df.columns]].copy()
    sub = sub.dropna(subset=["site_id", "occurred_on"])
    sub["site_id"] = sub["site_id"].astype(str).str.strip()

    pwr = sub[sub["alarm_category"] == "Power"].copy()
    dwn = sub[sub["alarm_category"] == "Down"].copy()

    if pwr.empty:
        return pd.DataFrame(), "No Power alarms found in loaded data."
    if dwn.empty:
        return pd.DataFrame(), "No Down alarms found in loaded data."

    # Build power-event table with the outage window
    p_cols = ["site_id", "occurred_on"]
    if "cleared_on" in pwr.columns:
        p_cols.append("cleared_on")
    p_extra = [c for c in ("network_type", "vendor") if c in pwr.columns]
    p_cols += p_extra
    pwr = pwr[p_cols].rename(columns={
        "occurred_on": "power_time",
        "cleared_on":  "power_cleared",
    })
    # Drop power alarms with no cleared time (still active — no window)
    pwr = pwr.dropna(subset=["power_cleared"])

    dwn = (dwn[["site_id", "occurred_on"]]
           .rename(columns={"occurred_on": "down_time"}))

    # Inner-join on site_id, then filter: down_time inside [power_time, power_cleared]
    merged = pwr.merge(dwn, on="site_id", how="inner")
    merged = merged[
        (merged["down_time"] >= merged["power_time"])
        & (merged["down_time"] <= merged["power_cleared"])
    ].copy()

    if merged.empty:
        return pd.DataFrame(), (
            "No Down alarms found inside any Power alarm window.")

    merged["backup_td"] = merged["down_time"] - merged["power_time"]

    # Per incident (site + power_time), keep only the LONGEST backup
    # (= the last technology to go down).
    idx = merged.groupby(["site_id", "power_time"])["backup_td"].idxmax()
    merged = merged.loc[idx].copy()

    merged["backup_time"]    = merged["backup_td"].apply(_fmt_td)
    merged["power_time"]     = merged["power_time"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    merged["power_cleared"]  = merged["power_cleared"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    merged["down_time"]      = merged["down_time"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    merged = merged.sort_values("backup_td", ascending=False).reset_index(drop=True)

    out = [c for c in ["site_id", "network_type", "vendor",
                        "power_time", "power_cleared",
                        "down_time", "backup_time"]
           if c in merged.columns]
    return merged[out], ""


def _fmt_td(td):
    total = int(td.total_seconds())
    h, r  = divmod(total, 3600)
    m, s  = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────
# Dialog
# ─────────────────────────────────────────────────────────────────
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

        # ── summary strip ────────────────────────────────────────
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

        # ── note ─────────────────────────────────────────────────
        note = QLabel(
            "Backup Time = time between the Power alarm (mains failure) "
            "and the Down alarm (site offline) for the same site.  "
            "Only pairs within a 72-hour window are shown.")
        note.setStyleSheet("color:#6c7086; font-size:11px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        # ── table ────────────────────────────────────────────────
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

    # ── export ───────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────
# Background thread
# ─────────────────────────────────────────────────────────────────
class BackupTimeThread(QThread):
    """Compute backup times in a background thread.

    Signals:
        progress(int, str)            — percentage + status message
        finished(DataFrame, str)      — result df + error string ('' on success)
        error(str)                    — traceback on unexpected failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, str)
    error    = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def run(self):
        try:
            self.progress.emit(30, "Computing backup times …")
            result, err = compute_backup_times(self._df)
            self.progress.emit(100, "Done")
            self.finished.emit(result, err)
        except Exception:
            self.error.emit(traceback.format_exc())
