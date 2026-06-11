"""
LeftPanel — sidebar with directory browser and file list.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ALARM_SOURCE_TOOLTIPS = {
    "directory": (
        "Directory mode: reads selected CSV/XLSX alarm files from the folder, "
        "rebuilds derived alarm fields, and saves/replaces the alarm DuckDB cache "
        "after a successful load."
    ),
    "db": (
        "DB mode: reads only the saved DuckDB alarm cache. It is fast and does not write "
        "or rescan directory files. Use Clear cached data or Directory mode when rules changed."
    ),
    "both": (
        "Both mode: reads saved DuckDB first, parses selected directory files, merges and "
        "deduplicates the rows, then saves the merged/re-derived alarm cache."
    ),
}


class LeftPanel(QWidget):
    """Sidebar containing the directory browser, file list, and stats."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._build(viewer)

    def _build(self, viewer):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(12)

        # App brand in sidebar
        brand_row = QHBoxLayout()
        icon_lbl = QLabel("\U0001f4e1")
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

        self.edit_dir = QLineEdit()
        self.edit_dir.setPlaceholderText("Select or paste path\u2026")
        lay.addWidget(self.edit_dir)

        dir_row = QHBoxLayout(); dir_row.setSpacing(6)
        b_br = QPushButton("Browse")
        b_br.setObjectName("btn_dir")
        b_br.clicked.connect(viewer._browse)
        b_sc = QPushButton("\u27f3  Scan")
        b_sc.setObjectName("btn_dir")
        b_sc.clicked.connect(viewer._scan)
        dir_row.addWidget(b_br); dir_row.addWidget(b_sc)
        lay.addLayout(dir_row)

        # Files sub-section
        sec2 = QLabel("FILES")
        sec2.setObjectName("lbl_section")
        lay.addWidget(sec2)

        self.lbl_file_count = QLabel("No directory scanned")
        self.lbl_file_count.setStyleSheet(
            "color:#45475a; font-size:11px; background:transparent;")
        lay.addWidget(self.lbl_file_count)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(
            QAbstractItemView.MultiSelection)
        self.file_list.setMinimumHeight(180)
        lay.addWidget(self.file_list, 1)

        sel_row = QHBoxLayout(); sel_row.setSpacing(5)
        b_all = QPushButton("All")
        b_all.setObjectName("btn_small")
        b_none = QPushButton("None")
        b_none.setObjectName("btn_small")
        b_all.setFixedWidth(44); b_none.setFixedWidth(44)
        b_all.clicked.connect(self.file_list.selectAll)
        b_none.clicked.connect(self.file_list.clearSelection)
        sel_row.addWidget(b_all)
        sel_row.addWidget(b_none)
        sel_row.addStretch()
        lay.addLayout(sel_row)

        self.btn_load = QPushButton("Load Selected Files")
        self.btn_load.setObjectName("btn_load")
        self.btn_load.setProperty("compact", True)
        self.btn_load.setEnabled(False)
        self.btn_load.clicked.connect(viewer._load)

        self.cmb_alarm_source = QComboBox()
        self.cmb_alarm_source.addItem("Directory", "directory")
        self.cmb_alarm_source.addItem("DB", "db")
        self.cmb_alarm_source.addItem("Both (Verify)", "both")
        self.cmb_alarm_source.setToolTip(
            "Choose where alarm rows come from and whether this load updates the local cache."
        )
        for i in range(self.cmb_alarm_source.count()):
            mode = str(self.cmb_alarm_source.itemData(i) or "")
            self.cmb_alarm_source.setItemData(i, ALARM_SOURCE_TOOLTIPS.get(mode, ""), Qt.ToolTipRole)
        self.cmb_alarm_source.currentIndexChanged.connect(viewer._on_alarm_source_changed)
        lay.addWidget(self.cmb_alarm_source)

        lay.addWidget(self.btn_load)

        self.btn_cancel_load = QPushButton("Cancel Load")
        self.btn_cancel_load.setObjectName("btn_clear")
        self.btn_cancel_load.setProperty("compact", True)
        self.btn_cancel_load.setEnabled(False)
        self.btn_cancel_load.setVisible(False)
        if hasattr(viewer, "_cancel_alarm_load"):
            self.btn_cancel_load.clicked.connect(viewer._cancel_alarm_load)
        lay.addWidget(self.btn_cancel_load)

        self.btn_clear_alarm_caches = QPushButton("Clear alarm cache")
        self.btn_clear_alarm_caches.setObjectName("btn_clear")
        self.btn_clear_alarm_caches.setProperty("compact", True)
        self.btn_clear_alarm_caches.setToolTip(
            "Wipe only the alarm cache (DuckDB files and SQLite alarm_records). "
            "BDT validation results, BDT history, and source files are preserved."
        )
        if hasattr(viewer, "_clear_alarm_caches"):
            self.btn_clear_alarm_caches.clicked.connect(viewer._clear_alarm_caches)
        else:  # pragma: no cover - viewer is always supplied in production
            self.btn_clear_alarm_caches.setEnabled(False)
        lay.addWidget(self.btn_clear_alarm_caches)

        self.lbl_loaded = QLabel("")
        self.lbl_loaded.setAlignment(Qt.AlignCenter)
        self.lbl_loaded.setStyleSheet(
            "color:#45475a; font-size:11px; background:transparent;")
        lay.addWidget(self.lbl_loaded)

        stats_frame = QFrame()
        stats_frame.setObjectName("stats_frame")
        sf = QVBoxLayout(stats_frame)
        sf.setContentsMargins(12, 10, 12, 10)
        sf.setSpacing(7)

        sec_lbl = QLabel("STATISTICS")
        sec_lbl.setObjectName("stats_section_label")
        sf.addWidget(sec_lbl)

        self.stats: dict[str, QLabel] = {}
        stat_obj_names = {
            "total": "stat_total", "power": "stat_power",
            "down": "stat_down", "door": "stat_door", "temp": "stat_temp",
            "sites": "stat_sites", "avg_dur": "stat_avg_dur",
        }
        for key, label in (
            ("total",    "Total Records"),
            ("power",    "Power Alarms"),
            ("down",     "Down Alarms"),
            ("door",     "Door Alarms"),
            ("temp",     "Temp Alarms"),
            ("sites",    "Unique Sites"),
            ("avg_dur",  "Avg Duration"),
        ):
            row_h = QHBoxLayout(); row_h.setSpacing(4)
            lt = QLabel(label)
            lt.setObjectName("stats_label")
            lv = QLabel("—")
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

        lay.addWidget(stats_frame)
