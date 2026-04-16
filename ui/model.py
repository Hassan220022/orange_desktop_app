"""
AlarmTableModel — High-performance QAbstractTableModel backed by pandas.

Optimisations vs naive approach:
 • Pre-builds a 2-D Python list (_cache) on load so data() never touches
   pandas per-cell → 5-10× faster scrolling on large datasets.
 • Column colour maps are built once, not re-evaluated per cell.
 • Sort converts only the target column once (not the whole DF stringified).
"""

import pandas as pd
import numpy as np

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor, QBrush

try:
    from ..constants import DISPLAY_COLUMNS
except ImportError:
    try:
        from alarm_app.constants import DISPLAY_COLUMNS
    except ImportError:
        from constants import DISPLAY_COLUMNS

# ── Pre-computed colour objects (created once, reused for every cell) ──
_CLR_PWR_BG   = QBrush(QColor("#2d1a1a"))
_CLR_DWN_BG   = QBrush(QColor("#1a2d1a"))
_CLR_DOR_BG   = QBrush(QColor("#132236"))
_CLR_CLEARED  = QBrush(QColor("#a6e3a1"))
_CLR_PWR_FG   = QBrush(QColor("#f38ba8"))
_CLR_DWN_FG   = QBrush(QColor("#fab387"))
_CLR_DOR_FG   = QBrush(QColor("#89dceb"))
_CLR_SITE     = QBrush(QColor("#cba6f7"))
_CLR_VENDOR   = QBrush(QColor("#89dceb"))
_CLR_NET = {
    "2G": QBrush(QColor("#2a2418")),
    "3G": QBrush(QColor("#1e2a1e")),
    "4G": QBrush(QColor("#1a1e2a")),
    "5G": QBrush(QColor("#2a1a2a")),
}
_CLR_NET_DEF  = QBrush(QColor("#181825"))

_CENTER = int(Qt.AlignCenter)
_ALIGN_COLS = frozenset(("occurred_on", "cleared_on", "duration", "alarm_id"))


class AlarmTableModel(QAbstractTableModel):
    """Fast pandas-backed table model with pre-stringified display cache."""

    __slots__ = ("_df", "_cols", "_cache", "_row_count", "_col_count")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: pd.DataFrame = pd.DataFrame()
        self._cols: list[str] = []
        self._cache: list[list[str]] = []
        self._row_count = 0
        self._col_count = 0

    # ── data loading ─────────────────────────────────────────────
    def load(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self._cols = list(df.columns)
        self._row_count = len(self._df)
        self._col_count = len(self._cols)
        self._rebuild_cache()
        self.endResetModel()

    def _rebuild_cache(self):
        """Convert every cell to its display string once (vectorized)."""
        df = self._df
        parts: list[np.ndarray] = []
        for c in self._cols:
            s = df[c]
            if s.dtype.kind == "M":  # datetime64
                parts.append(
                    s.dt.strftime("%Y-%m-%d  %H:%M:%S").fillna("").values)
            else:
                parts.append(s.fillna("").astype(str).values)
        if parts:
            self._cache = np.column_stack(parts).tolist()
        else:
            self._cache = []

    # ── Qt interface ─────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()):
        return self._row_count

    def columnCount(self, parent=QModelIndex()):
        return self._col_count

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        if r >= self._row_count or c >= self._col_count:
            return None

        cname = self._cols[c]

        if role == Qt.DisplayRole:
            return self._cache[r][c]

        sval = self._cache[r][c]

        if role == Qt.BackgroundRole:
            if cname == "alarm_category":
                if "Power" in sval:
                    return _CLR_PWR_BG
                if "Down" in sval:
                    return _CLR_DWN_BG
                if "Door" in sval:
                    return _CLR_DOR_BG
                return None
            if cname == "network_type":
                return _CLR_NET.get(sval, _CLR_NET_DEF)
            return None

        if role == Qt.ForegroundRole:
            if cname == "clearance_status" and sval == "Cleared":
                return _CLR_CLEARED
            if cname == "alarm_category":
                if "Power" in sval:
                    return _CLR_PWR_FG
                if "Down" in sval:
                    return _CLR_DWN_FG
                if "Door" in sval:
                    return _CLR_DOR_FG
                return None
            if cname == "site_id":
                return _CLR_SITE
            if cname == "vendor":
                return _CLR_VENDOR
            return None

        if role == Qt.TextAlignmentRole:
            if cname in _ALIGN_COLS:
                return _CENTER
            return None

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and section < self._col_count:
            col_map = dict(DISPLAY_COLUMNS)
            return col_map.get(
                self._cols[section],
                self._cols[section].replace("_", " ").title(),
            )
        return str(section + 1)

    # ── sorting ──────────────────────────────────────────────────
    def sort(self, column, order=Qt.AscendingOrder):
        if column >= self._col_count:
            return
        self.beginResetModel()
        col = self._cols[column]
        asc = order == Qt.AscendingOrder

        # Use native dtype for datetime columns, stringify only when needed
        if self._df[col].dtype.kind == "M":
            self._df = self._df.sort_values(
                by=col, ascending=asc, na_position="last"
            ).reset_index(drop=True)
        else:
            self._df = self._df.sort_values(
                by=col, ascending=asc, na_position="last",
                key=lambda s: s.astype(str).str.lower(),
            ).reset_index(drop=True)
        self._rebuild_cache()
        self.endResetModel()

    # ── public helpers ───────────────────────────────────────────
    def get_df(self):
        return self._df.copy()
