"""
BdtValidationPanel — BDT validation results tab extracted from AlarmViewer.
"""

import os
import re
from datetime import datetime

import pandas as pd
from PyQt5.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from alarm_app.bdt.export import build_bdt_export_sheets
from alarm_app.bdt.parser import BDTData
from alarm_app.bdt.validator import BDTTolerances, ValidationResult, bdt_battery_status
from alarm_app.constants import (
    BDT_RESULT_HEADERS,
    BDT_RESULT_WIDTHS,
    format_bdt_rule_label,
)
from alarm_app.data import state
from alarm_app.data.alarm_store import AlarmQuery, distinct_values, query_alarms
from alarm_app.data.site_report import build_pm_accept_report, read_pm_accept_sheet
from alarm_app.ui.dialogs import (
    AcceptedPmReportDialog,
    BdtParametersDialog,
    BdtRulesReferenceDialog,
    BdtValidationIntroDialog,
    ColumnFilterPopup,
    DailyReviewReportDialog,
)
from alarm_app.ui.threads import BDTValidationThread, ExportThread


class BdtValidationPanel(QWidget):
    """BDT validation results table with controls, search, and export."""

    row_selected = pyqtSignal(object)  # emits ValidationResult

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._bdt_col_filters: dict[str, set[str] | None] = {}
        self._bdt_page_size = 100
        self._bdt_page_offset = 0
        self._bdt_filtered_results: list = []
        self._bdt_filter_signature: tuple | None = None
        self._bdt_row_map_cache: dict[int, dict[str, str]] = {}
        self._bdt_distinct_cache: dict[str, list[str]] = {}
        self._bdt_summary_cache: tuple[int, int, int] | None = None
        self._build(viewer)

    @staticmethod
    def _mark_compact(button: QPushButton):
        button.setProperty("compact", True)
        button.setMinimumWidth(0)
        button.setMinimumHeight(max(28, button.fontMetrics().height() + 10))
        button.setMaximumHeight(16777215)
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    # ------------------------------------------------------------------
    def _build(self, viewer):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        self.spn_health = QSpinBox()
        self.spn_health.setObjectName("filter_spin")
        self.spn_health.setRange(50, 100)
        self.spn_health.setValue(80)
        self.spn_health.setSuffix(" %")
        self.spn_health.setFixedWidth(82)
        self.spn_health.setVisible(False)

        self.cmb_bdt_source = QComboBox()
        self.cmb_bdt_source.setObjectName("filter_combo")
        self.cmb_bdt_source.addItem("Directory", "directory")
        self.cmb_bdt_source.addItem("DB", "db")
        self.cmb_bdt_source.addItem("Both (Verify)", "both")
        self.cmb_bdt_source.setVisible(False)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        # PARAMETERS group: compact toolbar instead of a tall card.
        params_group = QFrame()
        params_group.setObjectName("filter_group")
        params_group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        params_lay = QVBoxLayout(params_group)
        params_lay.setContentsMargins(10, 6, 10, 7)
        params_lay.setSpacing(4)

        params_cap = QLabel("PARAMETERS")
        params_cap.setObjectName("filter_section")
        params_lay.addWidget(params_cap)

        params_row = QHBoxLayout()
        params_row.setSpacing(8)
        self.btn_parameters = QPushButton("Open Parameters")
        self.btn_parameters.setObjectName("btn_dir")
        self._mark_compact(self.btn_parameters)
        self.btn_parameters.clicked.connect(self._show_parameters_dialog)
        params_row.addWidget(self.btn_parameters)

        self.btn_rule_guide = QPushButton("Explain Rules")
        self.btn_rule_guide.setObjectName("btn_dir")
        self._mark_compact(self.btn_rule_guide)
        self.btn_rule_guide.clicked.connect(self._show_rules_reference_dialog)
        params_row.addWidget(self.btn_rule_guide)
        params_lay.addLayout(params_row)

        self._lbl_param_summary = QLabel("")
        self._lbl_param_summary.setWordWrap(False)
        self._lbl_param_summary.setObjectName("lbl_dim")
        self._lbl_param_summary.setStyleSheet("color:#6c7086; font-size:11px; background:transparent;")
        self._lbl_param_summary.setMaximumHeight(18)
        params_lay.addWidget(self._lbl_param_summary)
        self._refresh_parameter_summary()

        header_row.addWidget(params_group)

        # SEARCH group: label + field in one row to keep the table high.
        search_group = QFrame()
        search_group.setObjectName("filter_group")
        search_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        search_row_inner = QHBoxLayout(search_group)
        search_row_inner.setContentsMargins(10, 6, 10, 7)
        search_row_inner.setSpacing(10)
        search_cap = QLabel("SEARCH")
        search_cap.setObjectName("filter_section")
        search_row_inner.addWidget(search_cap)
        self.bdt_search = QLineEdit()
        self.bdt_search.setObjectName("filter_input")
        self.bdt_search.setPlaceholderText(
            "Search by site ID or date  \u2014  e.g.  ABC123, 2025-01-12, 2025")
        self.bdt_search.setClearButtonEnabled(True)
        self.bdt_search.setMinimumWidth(220)
        self.bdt_search.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.bdt_search.textChanged.connect(self._filter_bdt_table)
        search_row_inner.addWidget(self.bdt_search, 1)
        header_row.addWidget(search_group, 1)

        lay.addLayout(header_row)

        # Vertical splitter: results table + detail panel placeholder
        self.bdt_splitter = QSplitter(Qt.Vertical)
        self.bdt_splitter.setHandleWidth(1)
        self.bdt_splitter.setChildrenCollapsible(False)

        # Results table
        cols = BDT_RESULT_HEADERS
        self.bdt_table = QTableWidget(0, len(cols))
        self.bdt_table.setHorizontalHeaderLabels([self._display_header_name(col) for col in cols])
        self.bdt_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bdt_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bdt_table.setAlternatingRowColors(True)
        self.bdt_table.verticalHeader().setVisible(False)
        self.bdt_table.verticalHeader().setDefaultSectionSize(28)
        self.bdt_table.setMinimumHeight(112)
        hdr = self.bdt_table.horizontalHeader()
        rule_cols = {c for c in cols if c.startswith("R") and c[1:].isdigit()}
        for i, col in enumerate(cols):
            if col in rule_cols:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                hdr.resizeSection(i, BDT_RESULT_WIDTHS.get(col, 80))
        hdr.setStretchLastSection(True)
        hdr.sectionClicked.connect(self._on_bdt_header_clicked)
        self.bdt_table.clicked.connect(self._on_bdt_row_clicked)
        self.bdt_table.doubleClicked.connect(self._copy_bdt_cell)
        self.bdt_splitter.addWidget(self.bdt_table)

        # Detail panel slot (will be filled by viewer via set_detail_panel)
        self._detail_panel_placeholder = None

        lay.addWidget(self.bdt_splitter, 1)

        # Bottom bar
        bot = QHBoxLayout()
        bot.setContentsMargins(0, 0, 0, 0)
        bot.setSpacing(6)
        self._btn_bdt_prev_page = QPushButton("Prev")
        self._mark_compact(self._btn_bdt_prev_page)
        self._btn_bdt_prev_page.clicked.connect(self._load_previous_bdt_page)
        bot.addWidget(self._btn_bdt_prev_page)

        self._btn_bdt_next_page = QPushButton("Next")
        self._mark_compact(self._btn_bdt_next_page)
        self._btn_bdt_next_page.clicked.connect(self._load_next_bdt_page)
        bot.addWidget(self._btn_bdt_next_page)

        self._lbl_bdt_page = QLabel("Page 0/0")
        self._lbl_bdt_page.setObjectName("lbl_dim")
        bot.addWidget(self._lbl_bdt_page)

        self._lbl_bdt_page_range = QLabel("Rows 0-0 of 0")
        self._lbl_bdt_page_range.setObjectName("lbl_dim")
        bot.addWidget(self._lbl_bdt_page_range)

        self.bdt_summary = QLabel("")
        self.bdt_summary.setStyleSheet(
            "color:#6c7086; font-size:12px; background:transparent;")
        bot.addWidget(self.bdt_summary)
        bot.addStretch()
        lay.addLayout(bot)

        self.btn_pm_accept_report = QPushButton("Accepted PM Report")
        self.btn_pm_accept_report.setVisible(False)
        self.btn_bdt_export = QPushButton("Export Results XLSX")
        self.btn_bdt_export.setVisible(False)
        self.btn_bdt_report = QPushButton("Daily Report")
        self.btn_bdt_report.setVisible(False)

    @staticmethod
    def _reference_alarm_sites_df() -> pd.DataFrame:
        site_ids = [site_id for site_id in distinct_values("site_id") if str(site_id).strip()]
        return pd.DataFrame({"site_id": site_ids})

    @staticmethod
    def _pm_accept_alarm_subset_query(
        pm_df: pd.DataFrame,
        site_id_column: str,
        date_column: str,
    ) -> AlarmQuery:
        site_keys = [
            str(value).strip()
            for value in pm_df.get(site_id_column, pd.Series(dtype=object)).tolist()
            if str(value).strip()
        ]
        parsed_dates = pd.to_datetime(pm_df.get(date_column, pd.Series(dtype=object)), errors="coerce", format="mixed")
        valid_dates = [pd.Timestamp(value) for value in parsed_dates.tolist() if not pd.isna(value)]
        date_from = (min(valid_dates) - pd.Timedelta(days=1)).to_pydatetime() if valid_dates else None
        date_to = (max(valid_dates) + pd.Timedelta(days=1)).to_pydatetime() if valid_dates else None
        return AlarmQuery(
            site_scope_keys=site_keys or None,
            date_from=date_from,
            date_to=date_to,
            sort_by="occurred_on",
            sort_desc=False,
        )

    @classmethod
    def _load_pm_accept_alarm_subset(
        cls,
        pm_df: pd.DataFrame,
        site_id_column: str,
        date_column: str,
    ) -> pd.DataFrame:
        return query_alarms(cls._pm_accept_alarm_subset_query(pm_df, site_id_column, date_column))

    def set_detail_panel(self, panel: QWidget):
        """Attach the BDT detail panel to the splitter."""
        self._detail_panel_placeholder = panel
        panel.setVisible(False)
        self.bdt_splitter.addWidget(panel)
        self.bdt_splitter.setStretchFactor(0, 0)
        self.bdt_splitter.setStretchFactor(1, 1)
        self.bdt_splitter.setCollapsible(0, False)
        self.bdt_splitter.setCollapsible(1, False)
        self._apply_bdt_splitter_ratio()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_bdt_splitter_ratio()

    def _apply_bdt_splitter_ratio(self):
        if not hasattr(self, "bdt_splitter"):
            return
        sizes = self.bdt_splitter.sizes()
        if len(sizes) != 2:
            return
        total = self.bdt_splitter.height() or sum(sizes) or 1
        if self._detail_panel_placeholder and self._detail_panel_placeholder.isVisible():
            table_h = max(96, int(total * 0.28))
            self.bdt_splitter.setSizes([table_h, max(1, total - table_h)])
        else:
            self.bdt_splitter.setSizes([total, 0])

    @staticmethod
    def _validation_source_label(source_mode: str) -> str:
        return {
            "directory": "Directory",
            "db": "DB",
            "both": "Both (Verify)",
        }.get(str(source_mode or "").strip().lower(), "Directory")

    # ------------------------------------------------------------------
    # Validation logic
    # ------------------------------------------------------------------
    def _run_validation(self):
        viewer = self._viewer
        source_mode = self._current_source_mode()
        viewer._sbar.showMessage("Opening BDT validation overview…")
        health_pct_value = self.spn_health.value()
        intro_dialog = BdtValidationIntroDialog(
            source_label=self._validation_source_label(source_mode),
            health_pct=health_pct_value,
            skip_photos=bool(viewer._skip_photos),
            parent=self,
        )
        if intro_dialog.exec_() != QDialog.Accepted:
            viewer._sbar.showMessage("BDT validation cancelled")
            return

        viewer._prog.setVisible(True)
        viewer._prog.setValue(5)
        viewer._sbar.showMessage("Preparing BDT validation…")
        QApplication.processEvents()

        if source_mode == "db":
            viewer._prog.setValue(35)
            viewer._sbar.showMessage("Loading saved BDT validation results from DB…")
            results = viewer._load_bdt_results_from_db()
            if not results:
                viewer._prog.setVisible(False)
                QMessageBox.information(self, "No BDT Results", "No saved BDT validation results found in the DB.")
                return
            viewer._apply_bdt_results(
                results,
                status_message=f"Loaded {len(results)} BDT validation result(s) from DB",
            )
            viewer._reviewed_bdt_keys.clear()
            viewer._prog.setVisible(False)
            return

        bdt_files = [
            viewer._bdt_file_list.item(i).data(Qt.UserRole)["path"]
            for i in range(viewer._bdt_file_list.count())
            if viewer._bdt_file_list.item(i).isSelected()
        ] if hasattr(viewer, "_bdt_file_list") else []

        directory = viewer._edit_bdt_dir.text().strip() if hasattr(viewer, "_edit_bdt_dir") else ""
        if not directory:
            directory = str(getattr(viewer, "_bdt_uploaded_folder_path", "") or "").strip()
        if not directory:
            directory = viewer._edit_dir.text().strip()
        if not directory:
            directory = str(getattr(viewer, "_uploaded_folder_path", "") or "").strip()

        if directory and hasattr(viewer, "_edit_bdt_dir") and not viewer._edit_bdt_dir.text().strip():
            viewer._edit_bdt_dir.setText(directory)
        if directory and not viewer._edit_dir.text().strip():
            viewer._edit_dir.setText(directory)
        if not bdt_files and hasattr(viewer, "_bdt_file_infos") and viewer._bdt_file_infos:
            bdt_files = [str(info.get("path", "")) for info in viewer._bdt_file_infos if info.get("path")]

        try:
            saved = state.load_state() or {}
            saved["bdt_directory"] = directory
            state.save_state(saved)
        except Exception:
            pass

        if not bdt_files and directory and os.path.isdir(directory):
            for root, _dirs, files in os.walk(directory):
                for f in files:
                    fl = f.lower()
                    if (fl.endswith(".xlsx") and "bdt" in fl
                            and not f.startswith("~$") and not f.startswith("._")):
                        bdt_files.append(os.path.join(root, f))

        if not bdt_files:
            viewer._prog.setVisible(False)
            QMessageBox.information(
                self, "No BDT Files",
                "No BDT .xlsx files found in the selected BDT workspace.\n"
                "BDT filenames must contain 'BDT'.")
            return

        health_pct = health_pct_value / 100.0
        self._viewer._last_bdt_health_pct = health_pct

        try:
            saved_state = state.load_state() or {}
        except Exception:
            saved_state = {}
        tolerances = BDTTolerances.from_dict(saved_state.get("bdt_tolerances"))
        self._viewer._last_bdt_tolerances = tolerances

        viewer._sbar.showMessage(
            f"Validating {len(bdt_files)} BDT file(s)\u2026")
        self._viewer._bdt_results = []
        self._viewer._bdt_by_site = {}
        if self._detail_panel_placeholder:
            self._detail_panel_placeholder.setVisible(False)
        viewer._prog.setValue(10)
        self._pending_bdt_source_mode = source_mode
        self._db_seed_results = viewer._load_bdt_results_from_db() if source_mode == "both" else []

        self._bdt_thread = BDTValidationThread(
            bdt_files, None,
            tolerances.sizing_fractional_tolerance,
            health_pct,
            skip_photos=viewer._skip_photos,
            tolerances=tolerances,
        )
        self._bdt_thread.progress.connect(
            lambda v, m: (viewer._prog.setValue(v),
                          viewer._sbar.showMessage(m)))
        self._bdt_thread.finished.connect(self._on_validation_done)
        self._bdt_thread.error.connect(self._on_validation_error)
        self._bdt_thread.start()

    def _on_validation_done(self, results, by_site):
        viewer = self._viewer
        if getattr(self, "_pending_bdt_source_mode", "directory") == "both":
            results = self._merge_results(self._db_seed_results, results)
            by_site = self._build_site_map(results)
        self._viewer._bdt_results = results
        self._viewer._bdt_by_site = by_site
        self._invalidate_bdt_filter_cache()
        viewer._prog.setVisible(False)
        self._viewer._reviewed_bdt_keys.clear()
        self._populate_bdt_table()
        viewer._sbar.showMessage(
            f"Validated {len(self._viewer._bdt_results)} BDT file(s)")

    def _on_validation_error(self, msg):
        self._viewer._prog.setVisible(False)
        QMessageBox.critical(self, "Validation Error", msg)
        self._viewer._sbar.showMessage("Validation failed")

    def _generate_pm_accept_report(self):
        viewer = self._viewer
        if not viewer._bdt_results:
            QMessageBox.information(self, "No BDT Results", "Run validation first.")
            return

        viewer._sbar.showMessage("Opening Accepted PM report overview…")

        health_pct = (
            viewer._last_bdt_health_pct
            if viewer._last_bdt_health_pct is not None
            else self.spn_health.value() / 100.0
        )
        intro_dialog = AcceptedPmReportDialog(
            health_pct=round(float(health_pct) * 100),
            parent=self,
        )
        if intro_dialog.exec_() != QDialog.Accepted:
            viewer._sbar.showMessage("Accepted PM report cancelled")
            return

        viewer._prog.setVisible(True)
        viewer._prog.setValue(5)
        viewer._sbar.showMessage("Preparing Accepted PM report…")
        QApplication.processEvents()

        start_dir = (
            getattr(viewer, "_uploaded_folder_path", "")
            or viewer._edit_dir.text().strip()
            or str(os.path.expanduser("~"))
        )
        in_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Accepted PM List",
            start_dir,
            "Spreadsheet Files (*.xlsx *.xls *.csv)",
        )
        if not in_path:
            viewer._prog.setVisible(False)
            viewer._prog.setValue(0)
            viewer._sbar.showMessage("Accepted PM report cancelled")
            return

        try:
            viewer._prog.setValue(20)
            viewer._sbar.showMessage("Reading Accepted PM list …")
            site_reference_df = self._reference_alarm_sites_df()
            pm_df, sheet_name, site_col, date_col, status_col = read_pm_accept_sheet(
                in_path, site_reference_df
            )
            viewer._prog.setValue(45)
            viewer._sbar.showMessage("Loading matching alarm history …")
            alarm_df = self._load_pm_accept_alarm_subset(pm_df, site_col, date_col)
            if alarm_df.empty:
                viewer._prog.setVisible(False)
                QMessageBox.information(self, "No Alarm Data", "No matching alarm records were found in the local alarm store.")
                viewer._sbar.showMessage("Accepted PM report has no matching alarm data")
                return
            viewer._prog.setValue(70)
            viewer._sbar.showMessage("Building Accepted PM correlation report …")
            report_df = build_pm_accept_report(
                pm_df=pm_df,
                site_id_column=site_col,
                date_column=date_col,
                bdt_results=viewer._bdt_results,
                alarm_df=alarm_df,
                health_pct=health_pct,
                status_column=status_col,
            )
        except Exception as exc:
            viewer._prog.setVisible(False)
            QMessageBox.critical(self, "Accepted PM Report Error", str(exc))
            viewer._sbar.showMessage("Accepted PM report failed")
            return

        default_name = f"accepted_pm_backup_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        viewer._prog.setValue(85)
        viewer._sbar.showMessage("Choose where to save the Accepted PM report …")
        QApplication.processEvents()
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Accepted PM Backup Report",
            os.path.join(os.path.dirname(in_path), default_name),
            "Excel Files (*.xlsx)",
        )
        if not out_path:
            viewer._prog.setVisible(False)
            viewer._prog.setValue(0)
            viewer._sbar.showMessage("Accepted PM report export cancelled")
            return

        export_sheet_name = (sheet_name or "Accepted PM Report")[:31]
        self.btn_pm_accept_report.setEnabled(False)
        viewer._sbar.showMessage("Exporting Accepted PM backup report …")
        self._pm_accept_export_thread = ExportThread({export_sheet_name: report_df}, out_path)
        self._pm_accept_export_thread.progress.connect(
            lambda v, m: (
                viewer._prog.setVisible(True),
                viewer._prog.setValue(v),
                viewer._sbar.showMessage(m),
            )
        )
        self._pm_accept_export_thread.finished.connect(self._on_pm_accept_export_done)
        self._pm_accept_export_thread.error.connect(self._on_pm_accept_export_error)
        self._pm_accept_export_thread.start()

    def _on_pm_accept_export_done(self, fp: str):
        self.btn_pm_accept_report.setEnabled(True)
        self._viewer._prog.setVisible(False)
        QMessageBox.information(self, "Export OK", f"Saved to:\n{fp}")
        self._viewer._sbar.showMessage(f"Accepted PM backup report → {fp}")

    def _on_pm_accept_export_error(self, msg: str):
        self.btn_pm_accept_report.setEnabled(True)
        self._viewer._prog.setVisible(False)
        QMessageBox.critical(self, "Export Failed", msg)
        self._viewer._sbar.showMessage("Accepted PM report export failed")

    def set_results(self, results: list):
        """Load validation results (e.g. restored from DB) and populate the table."""
        self._viewer._bdt_results = results
        self._invalidate_bdt_filter_cache()
        self._bdt_page_offset = 0
        self._populate_bdt_table()

    def _invalidate_bdt_filter_cache(self):
        self._bdt_row_map_cache.clear()
        self._bdt_distinct_cache.clear()
        self._bdt_summary_cache = None
        self._bdt_filter_signature = None

    def _current_bdt_filter_signature(self) -> tuple:
        filters = tuple(
            sorted(
                (col_name, tuple(sorted(values or ())))
                for col_name, values in self._bdt_col_filters.items()
            )
        )
        return (
            id(self._viewer._bdt_results),
            len(self._viewer._bdt_results),
            self.bdt_search.text(),
            filters,
        )

    def _populate_bdt_table(self, *, refresh_filter: bool = True):
        results = self._viewer._bdt_results
        signature = self._current_bdt_filter_signature()
        if refresh_filter or signature != self._bdt_filter_signature:
            filtered_results = self._filtered_bdt_results_for_text(self.bdt_search.text())
            self._bdt_filtered_results = filtered_results
            self._bdt_filter_signature = signature
        else:
            filtered_results = self._bdt_filtered_results
        total = len(filtered_results)
        page_size = max(int(self._bdt_page_size), 1)
        max_offset = ((total - 1) // page_size) * page_size if total > 0 else 0
        self._bdt_page_offset = min(max(int(self._bdt_page_offset), 0), max_offset)
        page_results = filtered_results[self._bdt_page_offset:self._bdt_page_offset + page_size]
        blocker = QSignalBlocker(self.bdt_table) if hasattr(self.bdt_table, "blockSignals") else None
        if hasattr(self.bdt_table, "setUpdatesEnabled"):
            self.bdt_table.setUpdatesEnabled(False)
        if hasattr(self.bdt_table, "clearSelection"):
            self.bdt_table.clearSelection()
        if hasattr(self.bdt_table, "clearContents"):
            self.bdt_table.clearContents()
        self.bdt_table.setRowCount(len(page_results))

        colors = {
            "Accepted":      QColor("#a6e3a1"),
            "Rejected":      QColor("#f38ba8"),
            "Revise":        QColor("#fab387"),
            "No data":       QColor("#45475a"),
        }

        for r, res in enumerate(page_results):
            row_map = self._row_map_for_result(res)

            for c, col_name in enumerate(BDT_RESULT_HEADERS):
                val = row_map.get(col_name, "--")
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col_name == "Verdict" or col_name.startswith("R"):
                    item.setForeground(colors.get(val, QColor("#cdd6f4")))
                self.bdt_table.setItem(r, c, item)
        if blocker is not None:
            del blocker
        if hasattr(self.bdt_table, "setUpdatesEnabled"):
            self.bdt_table.setUpdatesEnabled(True)

        if self._bdt_summary_cache is None:
            n_acc = n_rej = n_rev = 0
            for result in results:
                for rule in getattr(result, "rules", []) or []:
                    verdict = getattr(rule, "verdict", "")
                    if verdict == "Accepted":
                        n_acc += 1
                    elif verdict == "Rejected":
                        n_rej += 1
                    elif verdict == "Revise":
                        n_rev += 1
            self._bdt_summary_cache = (n_acc, n_rej, n_rev)
        else:
            n_acc, n_rej, n_rev = self._bdt_summary_cache
        self.bdt_summary.setText(
            f"<span style='color:#a6e3a1;'>{n_acc} Accepted</span>"
            f" &middot; <span style='color:#f38ba8;'>{n_rej} Rejected</span>"
            f" &middot; <span style='color:#fab387;'>{n_rev} Revise</span>"
            f" &middot; <span style='color:#6c7086;'>"
            f"{len(results)} files</span>")
        self._update_bdt_pagination_controls()

    def _row_map_for_result(self, res) -> dict[str, str]:
        cache_key = id(res)
        cached = self._bdt_row_map_cache.get(cache_key)
        if cached is not None:
            return cached
        row_map = {
            "File": getattr(res, "filename", "") or "--",
            "Site Code": getattr(res, "site_code", "") or "--",
            "Test Date": getattr(res, "test_date", "") or "--",
            "Verdict": getattr(res, "overall", "") or "--",
            "Battery Status": bdt_battery_status(getattr(res, "bdt_data", None)),
            "End Rectifier Voltage (V)": self._format_end_rectifier_voltage(
                getattr(res, "bdt_data", None)),
            "Lead-acid SOH (%)": self._format_lead_acid_soh(getattr(res, "bdt_data", None)),
        }
        for rule in getattr(res, "rules", []) or []:
            row_map[getattr(rule, "rule_id", "")] = self._rule_cell_text(rule)
        self._bdt_row_map_cache[cache_key] = row_map
        return row_map

    def _distinct_bdt_values(self, col_name: str) -> list[str]:
        cached = self._bdt_distinct_cache.get(col_name)
        if cached is not None:
            return cached
        values = sorted(
            {
                str(self._row_map_for_result(res).get(col_name, "--"))
                for res in self._viewer._bdt_results
            },
            key=lambda value: value.lower() if value else "",
        )
        self._bdt_distinct_cache[col_name] = values
        return values

    @staticmethod
    def _display_header_name(col_name: str) -> str:
        if col_name.startswith("R") and col_name[1:].isdigit():
            return format_bdt_rule_label(col_name)
        return col_name

    @staticmethod
    def _rule_cell_text(rule) -> str:
        verdict = str(getattr(rule, "verdict", "") or "").strip()
        if verdict in {"Accepted", "Rejected", "Revise"}:
            return verdict
        return "No data"

    def _current_source_mode(self) -> str:
        return str(self.cmb_bdt_source.currentData() or "directory")

    def _refresh_parameter_summary(self):
        self._lbl_param_summary.setText(
            f"Health {self.spn_health.value()}% for Rule R8 battery sizing."
        )

    def _show_parameters_dialog(self):
        try:
            saved_state = state.load_state() or {}
        except Exception:
            saved_state = {}
        saved_tolerances = saved_state.get("bdt_tolerances") or {}
        dlg = BdtParametersDialog(
            health_pct=self.spn_health.value(),
            tolerances=saved_tolerances,
            parent=self,
        )
        if dlg.exec_() == QDialog.Accepted:
            health_pct = dlg.get_values()
            self.spn_health.setValue(health_pct)
            tolerance_values = dlg.get_tolerances()
            try:
                saved_state = state.load_state() or {}
                saved_state["bdt_tolerances"] = tolerance_values
                state.save_state(saved_state)
            except Exception:
                import logging
                _log = logging.getLogger(__name__)
                _log.warning("Failed to persist BDT tolerances", exc_info=True)
            self._viewer._last_bdt_tolerances = BDTTolerances.from_dict(tolerance_values)
            self._refresh_parameter_summary()

    def _show_rules_reference_dialog(self):
        try:
            saved_state = state.load_state() or {}
        except Exception:
            saved_state = {}
        tolerances = BDTTolerances.from_dict(saved_state.get("bdt_tolerances"))
        dialog = BdtRulesReferenceDialog(
            tolerances=tolerances,
            health_pct=int(self.spn_health.value()),
            parent=self,
        )
        dialog.exec_()

    @staticmethod
    def _result_identity(res) -> tuple[str, str, str]:
        file_token = ""
        bdt = getattr(res, "bdt_data", None)
        if bdt and getattr(bdt, "file_path", ""):
            file_token = os.path.basename(str(getattr(bdt, "file_path", ""))).strip().lower()
        elif getattr(res, "filename", ""):
            file_token = os.path.basename(str(getattr(res, "filename", ""))).strip().lower()
        return (
            str(getattr(res, "site_code", "") or "").strip().upper(),
            str(getattr(res, "test_date", "") or "").strip(),
            file_token,
        )

    def _merge_results(self, db_results: list, new_results: list) -> list:
        ordered: dict[tuple[str, str, str], object] = {}
        for res in list(db_results or []) + list(new_results or []):
            ordered[self._result_identity(res)] = res
        return list(ordered.values())

    @staticmethod
    def _build_site_map(results: list) -> dict[str, list]:
        def _sort_test_date(bdt) -> datetime:
            test_date = getattr(bdt, "test_date", None)
            if test_date is None:
                return datetime.min
            try:
                return pd.Timestamp(test_date).to_pydatetime()
            except Exception:
                return datetime.min

        by_site: dict[str, list] = {}
        for res in results:
            bdt = getattr(res, "bdt_data", None)
            site_code = str(getattr(res, "site_code", "") or "").strip().upper()
            if site_code and bdt is not None:
                by_site.setdefault(site_code, []).append(bdt)
        for items in by_site.values():
            items.sort(key=_sort_test_date, reverse=True)
        return by_site

    @staticmethod
    def _is_lithium_brand(brand: str | None) -> bool:
        return "lith" in (brand or "").lower()

    def _lead_acid_soh_percent(self, bdt: BDTData | None) -> float | None:
        if not bdt or self._is_lithium_brand(bdt.battery_brand):
            return None
        if self._viewer._last_bdt_health_pct is None:
            return None
        return self._viewer._last_bdt_health_pct * 100.0

    @staticmethod
    def _format_end_rectifier_voltage(bdt: BDTData | None) -> str:
        if not bdt or bdt.end_voltage is None:
            return "--"
        return f"{bdt.end_voltage:.2f}"

    def _format_lead_acid_soh(self, bdt: BDTData | None) -> str:
        soh = self._lead_acid_soh_percent(bdt)
        if soh is None:
            return "--"
        return f"{soh:.0f}"

    def _filtered_bdt_results_for_text(self, text: str) -> list:
        text = text.strip()

        text_lower = text.lower()
        is_year = re.fullmatch(r"\d{4}", text)
        is_date = re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)
        filtered: list = []

        for res in self._viewer._bdt_results:
            row_map = self._row_map_for_result(res)
            show = True

            if text:
                if is_year:
                    show = str(getattr(res, "test_date", "") or "").startswith(text)
                elif is_date:
                    show = str(getattr(res, "test_date", "") or "") == text
                else:
                    show = (
                        text_lower in str(row_map.get("Site Code", "")).lower()
                        or text_lower in str(row_map.get("File", "")).lower()
                    )

            if show and self._bdt_col_filters:
                for col_name, allowed in self._bdt_col_filters.items():
                    if allowed is None:
                        continue
                    if str(row_map.get(col_name, "--")) not in allowed:
                        show = False
                        break
            if show:
                filtered.append(res)
        return filtered

    def _filter_bdt_table(self, text: str):
        self._bdt_page_offset = 0
        self._populate_bdt_table()

    def _on_bdt_header_clicked(self, logical_index: int):
        if logical_index >= len(BDT_RESULT_HEADERS) or not self._viewer._bdt_results:
            return
        col_name = BDT_RESULT_HEADERS[logical_index]
        unique = self._distinct_bdt_values(col_name)
        popup = ColumnFilterPopup(
            col_name,
            self._display_header_name(col_name),
            unique,
            self._bdt_col_filters.get(col_name),
            self._sort_bdt_column,
            parent=self,
        )
        popup.applied.connect(self._on_bdt_col_filter_applied)
        hdr = self.bdt_table.horizontalHeader()
        x = hdr.sectionViewportPosition(logical_index)
        header_pos = hdr.mapToGlobal(hdr.rect().bottomLeft())
        popup.move(header_pos.x() + x, header_pos.y())
        popup.show()

    def _sort_bdt_column(self, col_name: str, order):
        if col_name not in BDT_RESULT_HEADERS:
            return
        reverse = order == Qt.DescendingOrder
        self._viewer._bdt_results.sort(
            key=lambda res: str(self._row_map_for_result(res).get(col_name, "--")).lower(),
            reverse=reverse,
        )
        self._bdt_page_offset = 0
        self._populate_bdt_table()

    def _on_bdt_col_filter_applied(self, col_name: str, selected):
        if selected is None:
            self._bdt_col_filters.pop(col_name, None)
        else:
            self._bdt_col_filters[col_name] = {str(value) for value in selected}
        self._bdt_page_offset = 0
        self._filter_bdt_table(self.bdt_search.text())

    def _on_bdt_row_clicked(self, index):
        row = index.row()
        absolute_row = self._bdt_page_offset + row
        if absolute_row >= len(self._bdt_filtered_results):
            return
        res = self._bdt_filtered_results[absolute_row]
        self._record_review_event(res)

        if self._detail_panel_placeholder and not self._detail_panel_placeholder.isVisible():
            self._detail_panel_placeholder.setVisible(True)
            self._apply_bdt_splitter_ratio()

        self.row_selected.emit(res)

    def _update_bdt_pagination_controls(self):
        total = len(self._bdt_filtered_results)
        page_size = max(int(self._bdt_page_size), 1)
        offset = max(int(self._bdt_page_offset), 0)
        if total <= 0:
            start = 0
            end = 0
            page_no = 0
            total_pages = 0
        else:
            start = offset + 1
            end = min(offset + self.bdt_table.rowCount(), total)
            page_no = (offset // page_size) + 1
            total_pages = ((total - 1) // page_size) + 1
        self._lbl_bdt_page.setText(f"Page {page_no}/{total_pages}")
        self._lbl_bdt_page_range.setText(f"Rows {start:,}-{end:,} of {total:,}")
        self._btn_bdt_prev_page.setEnabled(offset > 0)
        self._btn_bdt_next_page.setEnabled(total > 0 and offset + self.bdt_table.rowCount() < total)

    def _load_previous_bdt_page(self):
        self._bdt_page_offset = max(self._bdt_page_offset - self._bdt_page_size, 0)
        self._populate_bdt_table(refresh_filter=False)

    def _load_next_bdt_page(self):
        total = len(self._bdt_filtered_results)
        if total <= 0:
            return
        max_offset = ((total - 1) // self._bdt_page_size) * self._bdt_page_size
        self._bdt_page_offset = min(self._bdt_page_offset + self._bdt_page_size, max_offset)
        self._populate_bdt_table(refresh_filter=False)

    def _copy_bdt_cell(self, index):
        if not index.isValid():
            return
        item = self.bdt_table.item(index.row(), index.column())
        if item is None:
            return
        value = (item.text() or "").strip()
        if not value:
            return
        QApplication.clipboard().setText(value)
        self._viewer._sbar.showMessage(f"Copied: {value[:80]}", 2000)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_bdt_results(self):
        if not self._viewer._bdt_results:
            QMessageBox.information(
                self, "Nothing to Export", "Run validation first.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Validation Results",
            f"bdt_validation_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            "Excel Files (*.xlsx)")
        if not fp:
            return
        sheets = build_bdt_export_sheets(
            self._viewer._bdt_results,
            health_pct=self._viewer._last_bdt_health_pct,
        )
        self.btn_bdt_export.setEnabled(False)
        self._viewer._sbar.showMessage("Exporting BDT results \u2026")
        self._bdt_export_thread = ExportThread(sheets, fp)
        self._bdt_export_thread.progress.connect(
            lambda v, m: self._viewer._sbar.showMessage(m))
        self._bdt_export_thread.finished.connect(self._on_bdt_export_done)
        self._bdt_export_thread.error.connect(self._on_bdt_export_error)
        self._bdt_export_thread.start()

    def _on_bdt_export_done(self, fp: str):
        self.btn_bdt_export.setEnabled(True)
        QMessageBox.information(
            self, "Export OK", f"Saved to:\n{fp}")
        self._viewer._sbar.showMessage(f"BDT export \u2192 {fp}")

    def _on_bdt_export_error(self, msg: str):
        self.btn_bdt_export.setEnabled(True)
        QMessageBox.critical(self, "Export Failed", msg)
        self._viewer._sbar.showMessage("BDT export failed")

    # ------------------------------------------------------------------
    # Review tracking
    # ------------------------------------------------------------------
    def _record_review_event(self, res: ValidationResult):
        key = (
            self._viewer._current_user,
            str(res.filename or ""),
            str(res.test_date or ""),
        )
        if key in self._viewer._reviewed_bdt_keys:
            return
        try:
            state.append_review_event(
                username=self._viewer._current_user,
                filename=res.filename,
                site_code=res.site_code,
                test_date=res.test_date,
                verdict=res.overall,
            )
            self._viewer._reviewed_bdt_keys.add(key)
        except Exception:
            pass

    def _show_daily_review_report(self):
        dlg = DailyReviewReportDialog(self)
        dlg.exec_()
