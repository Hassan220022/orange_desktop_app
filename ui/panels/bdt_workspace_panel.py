"""
BdtWorkspacePanel — VS Code-style sidebar for the test validation workspace.
"""

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from alarm_app.ui.panels.bdt_validation_panel import BDT_SOURCE_TOOLTIPS
except ImportError:
    from ui.panels.bdt_validation_panel import BDT_SOURCE_TOOLTIPS


class BdtWorkspacePanel(QWidget):
    """Sidebar for the BDT/Test Validation workspace."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._build()

    @staticmethod
    def _mark_compact(button: QPushButton):
        button.setProperty("compact", True)
        button.setMinimumWidth(0)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 12, 10, 10)
        lay.setSpacing(8)
        self._scroll = scroll
        self._content = content

        brand = QLabel("Orange Workspace")
        brand.setObjectName("sidebar_brand")
        lay.addWidget(brand)

        sec = QLabel("TEST VALIDATION")
        sec.setObjectName("lbl_section")
        lay.addWidget(sec)

        title = QLabel("Battery discharge validation")
        title.setObjectName("sidebar_title")
        title.setWordWrap(True)
        lay.addWidget(title)

        summary = QLabel("Browse BDT folders, inspect candidate files, then validate.")
        summary.setWordWrap(True)
        summary.setObjectName("sidebar_body")
        lay.addWidget(summary)

        dir_section = QLabel("DIRECTORY")
        dir_section.setObjectName("lbl_section")
        lay.addWidget(dir_section)

        self.edit_dir = QLineEdit()
        self.edit_dir.setPlaceholderText("Select or paste BDT path...")
        lay.addWidget(self.edit_dir)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        btn_browse = QPushButton("Browse")
        btn_browse.setObjectName("btn_dir")
        self._mark_compact(btn_browse)
        btn_browse.clicked.connect(self._viewer._browse_bdt)
        dir_row.addWidget(btn_browse)

        btn_scan = QPushButton("Scan")
        btn_scan.setObjectName("btn_dir")
        self._mark_compact(btn_scan)
        btn_scan.clicked.connect(self._viewer._scan_bdt)
        dir_row.addWidget(btn_scan)
        lay.addLayout(dir_row)

        files_section = QLabel("FILES")
        files_section.setObjectName("lbl_section")
        lay.addWidget(files_section)

        self.lbl_file_count = QLabel("No directory scanned")
        self.lbl_file_count.setObjectName("sidebar_body")
        lay.addWidget(self.lbl_file_count)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.file_list.setMinimumHeight(120)
        lay.addWidget(self.file_list, 1)

        file_actions = QHBoxLayout()
        file_actions.setSpacing(5)
        btn_all = QPushButton("All")
        btn_all.setObjectName("btn_small")
        btn_all.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_all.clicked.connect(self.file_list.selectAll)
        file_actions.addWidget(btn_all)

        btn_none = QPushButton("None")
        btn_none.setObjectName("btn_small")
        btn_none.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_none.clicked.connect(self.file_list.clearSelection)
        file_actions.addWidget(btn_none)
        file_actions.addStretch()
        lay.addLayout(file_actions)

        source_card = QFrame()
        source_card.setObjectName("workspace_card")
        source_lay = QVBoxLayout(source_card)
        source_lay.setContentsMargins(10, 8, 10, 10)
        source_lay.setSpacing(6)

        source_label = QLabel("Validation Source")
        source_label.setObjectName("workspace_card_title")
        source_lay.addWidget(source_label)

        self.cmb_bdt_source = QComboBox()
        self.cmb_bdt_source.addItem("Directory", "directory")
        self.cmb_bdt_source.addItem("DB", "db")
        self.cmb_bdt_source.addItem("Both (Verify)", "both")
        self.cmb_bdt_source.setToolTip(
            "Choose where BDT validation results come from and whether validation updates SQLite."
        )
        source_card.setToolTip(self.cmb_bdt_source.toolTip())
        source_label.setToolTip(self.cmb_bdt_source.toolTip())
        for i in range(self.cmb_bdt_source.count()):
            mode = str(self.cmb_bdt_source.itemData(i) or "")
            self.cmb_bdt_source.setItemData(i, BDT_SOURCE_TOOLTIPS.get(mode, ""), Qt.ToolTipRole)
        self.cmb_bdt_source.currentIndexChanged.connect(self._sync_to_main_panel)
        source_lay.addWidget(self.cmb_bdt_source)
        lay.addWidget(source_card)

        actions_card = QFrame()
        actions_card.setObjectName("workspace_card")
        actions_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        actions_lay = QVBoxLayout(actions_card)
        actions_lay.setContentsMargins(10, 8, 10, 10)
        actions_lay.setSpacing(5)
        self._actions_card = actions_card
        self._actions_layout = actions_lay

        actions_title = QLabel("Workflow")
        actions_title.setObjectName("workspace_card_title")
        actions_lay.addWidget(actions_title)
        self._actions_title = actions_title

        btn_validate = QPushButton("Validate BDT Files")
        btn_validate.setObjectName("btn_search")
        self._mark_compact(btn_validate)
        btn_validate.clicked.connect(self._viewer._bdt_validation_panel._run_validation)
        actions_lay.addWidget(btn_validate)

        btn_report = QPushButton("Accepted PM Report")
        btn_report.setObjectName("btn_export")
        self._mark_compact(btn_report)
        btn_report.clicked.connect(
            self._viewer._bdt_validation_panel._generate_pm_accept_report
        )
        actions_lay.addWidget(btn_report)

        btn_daily = QPushButton("Daily Review")
        btn_daily.setObjectName("btn_dir")
        self._mark_compact(btn_daily)
        btn_daily.clicked.connect(
            self._viewer._bdt_validation_panel._show_daily_review_report
        )
        actions_lay.addWidget(btn_daily)

        self.btn_bdt_summary = QPushButton("Import BDT Summary")
        self.btn_bdt_summary.setObjectName("btn_dir")
        self._mark_compact(self.btn_bdt_summary)
        self.btn_bdt_summary.setToolTip("Import BDT Summary workbook sheets into the BDT Summary Catalog")
        self.btn_bdt_summary.clicked.connect(self._viewer._import_bdt_summary_catalog)
        actions_lay.addWidget(self.btn_bdt_summary)

        btn_export = QPushButton("Export Results")
        btn_export.setObjectName("btn_load")
        self._mark_compact(btn_export)
        btn_export.clicked.connect(self._viewer._bdt_validation_panel._export_bdt_results)
        actions_lay.addWidget(btn_export)

        self.btn_clear_bdt_caches = QPushButton("Clear BDT cache")
        self.btn_clear_bdt_caches.setObjectName("btn_clear")
        self._mark_compact(self.btn_clear_bdt_caches)
        self.btn_clear_bdt_caches.setToolTip(
            "Wipe only BDT validation cache, imported BDT summary rows, and BDT history. "
            "Alarm cache, source files, and photo files are preserved."
        )
        if hasattr(self._viewer, "_clear_bdt_caches"):
            self.btn_clear_bdt_caches.clicked.connect(self._viewer._clear_bdt_caches)
        else:  # pragma: no cover - viewer is always supplied in production
            self.btn_clear_bdt_caches.setEnabled(False)
        actions_lay.addWidget(self.btn_clear_bdt_caches)

        lay.addWidget(actions_card)

        status_card = QFrame()
        status_card.setObjectName("workspace_card")
        status_lay = QVBoxLayout(status_card)
        status_lay.setContentsMargins(10, 8, 10, 10)
        status_lay.setSpacing(5)

        status_title = QLabel("Context")
        status_title.setObjectName("workspace_card_title")
        status_lay.addWidget(status_title)

        self.lbl_context = QLabel(
            "This workspace validates the selected BDT files against the current alarm cache."
        )
        self.lbl_context.setWordWrap(True)
        self.lbl_context.setObjectName("sidebar_body")
        status_lay.addWidget(self.lbl_context)

        lay.addWidget(status_card)
        lay.addStretch()

        self._adaptive_primary_buttons = [
            btn_browse,
            btn_scan,
            btn_validate,
            btn_report,
            btn_daily,
            self.btn_bdt_summary,
            btn_export,
            self.btn_clear_bdt_caches,
        ]
        self._adaptive_small_buttons = [btn_all, btn_none]
        self._workflow_buttons = [
            btn_validate,
            btn_report,
            btn_daily,
            self.btn_bdt_summary,
            btn_export,
            self.btn_clear_bdt_caches,
        ]

        self._viewer._bdt_validation_panel.cmb_bdt_source.currentIndexChanged.connect(
            self._sync_from_main_panel
        )
        self._sync_from_main_panel()
        self._sync_skip_photos_from_viewer()
        self._refresh_responsive_metrics()

    def _refresh_responsive_metrics(self):
        primary_height = 0
        content_width = 0
        for btn in getattr(self, "_adaptive_primary_buttons", []):
            fm = btn.fontMetrics()
            primary_height = max(primary_height, fm.height() + 10)
            content_width = max(content_width, fm.horizontalAdvance(btn.text()) + 34)
        primary_height = max(primary_height, 30)
        for btn in getattr(self, "_adaptive_primary_buttons", []):
            btn.setMinimumHeight(primary_height)
            btn.setMaximumHeight(16777215)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        small_height = 0
        for btn in getattr(self, "_adaptive_small_buttons", []):
            small_height = max(small_height, int(btn.fontMetrics().height() * 1.8))
        small_height = max(small_height, 30)
        for btn in getattr(self, "_adaptive_small_buttons", []):
            btn.setMinimumHeight(small_height)

        combo_width = self.cmb_bdt_source.fontMetrics().horizontalAdvance("Both (Verify)") + 72
        sidebar_min = max(280, content_width + 20, combo_width + 32)
        self._recommended_min_width = sidebar_min
        self.setMinimumWidth(sidebar_min)

        actions_card = getattr(self, "_actions_card", None)
        actions_title = getattr(self, "_actions_title", None)
        workflow_buttons = list(getattr(self, "_workflow_buttons", []) or [])
        if actions_card is not None and actions_title is not None and workflow_buttons:
            margins = actions_card.layout().contentsMargins()
            spacing = actions_card.layout().spacing()
            title_h = actions_title.sizeHint().height()
            card_h = (
                margins.top()
                + margins.bottom()
                + title_h
                + (primary_height * len(workflow_buttons))
                + (spacing * len(workflow_buttons))
            )
            actions_card.setMinimumHeight(card_h)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {QEvent.FontChange, QEvent.StyleChange, QEvent.PaletteChange}:
            self._refresh_responsive_metrics()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_responsive_metrics()

    def _sync_to_main_panel(self, index: int):
        main_combo = self._viewer._bdt_validation_panel.cmb_bdt_source
        if main_combo.currentIndex() != index:
            main_combo.setCurrentIndex(index)

    def _sync_from_main_panel(self, _index=None):
        main_combo = self._viewer._bdt_validation_panel.cmb_bdt_source
        index = main_combo.currentIndex()
        if self.cmb_bdt_source.currentIndex() != index:
            self.cmb_bdt_source.setCurrentIndex(index)

    def _sync_skip_photos_to_viewer(self, checked: bool):
        viewer_chk = getattr(self._viewer, "_chk_skip_photos", None)
        if viewer_chk is not None and viewer_chk.isChecked() != checked:
            viewer_chk.setChecked(checked)
        else:
            self._viewer._toggle_skip_photos(checked)

    def _sync_skip_photos_from_viewer(self):
        if not hasattr(self, "chk_skip_photos"):
            return
        checked = bool(getattr(self._viewer, "_skip_photos", False))
        self.chk_skip_photos.blockSignals(True)
        self.chk_skip_photos.setChecked(checked)
        self.chk_skip_photos.blockSignals(False)
