"""
LeftPanel — sidebar with directory browser and file list.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QListWidget, QAbstractItemView,
)
from PyQt5.QtCore import Qt


class LeftPanel(QWidget):
    """Sidebar containing directory selector, file list, and load button."""

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
        self.btn_load.setEnabled(False)
        self.btn_load.clicked.connect(viewer._load)
        lay.addWidget(self.btn_load)

        self.lbl_loaded = QLabel("")
        self.lbl_loaded.setAlignment(Qt.AlignCenter)
        self.lbl_loaded.setStyleSheet(
            "color:#45475a; font-size:11px; background:transparent;")
        lay.addWidget(self.lbl_loaded)
