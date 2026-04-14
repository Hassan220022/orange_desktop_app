"""
BdtValidationPanel — BDT validation results tab extracted from AlarmViewer.
"""

import os
import re
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QFrame, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy, QMessageBox,
    QFileDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

try:
    from ...constants import BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS
    from ..threads import ExportThread, BDTValidationThread
    from ...bdt.parser import BDTData
    from ...bdt.validator import ValidationResult
    from ...bdt.export import build_bdt_export_sheets
    from ..dialogs import DailyReviewReportDialog
    from ...data import state
except ImportError:
    from alarm_app.constants import BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS
    from alarm_app.ui.threads import ExportThread, BDTValidationThread
    from alarm_app.bdt.parser import BDTData
    from alarm_app.bdt.validator import ValidationResult
    from alarm_app.bdt.export import build_bdt_export_sheets
    from alarm_app.ui.dialogs import DailyReviewReportDialog
    from alarm_app.data import state


class BdtValidationPanel(QWidget):
    """BDT validation results table with controls, search, and export."""

    row_selected = pyqtSignal(object)  # emits ValidationResult

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._build(viewer)

    # ------------------------------------------------------------------
    def _build(self, viewer):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

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

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        # ACTION group
        action_group, action_row = _make_group("ACTION")
        btn_validate = QPushButton("Validate")
        btn_validate.setObjectName("btn_search")
        btn_validate.setCursor(Qt.PointingHandCursor)
        btn_validate.setMinimumWidth(0)
        btn_validate.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn_validate.clicked.connect(self._run_validation)
        action_row.addWidget(btn_validate)
        header_row.addWidget(action_group)

        # PARAMETERS group
        params_group, params_row = _make_group("PARAMETERS")

        params_row.addWidget(_inline_label("Tolerance"))
        self.spn_tolerance = QSpinBox()
        self.spn_tolerance.setObjectName("filter_spin")
        self.spn_tolerance.setRange(10, 20)
        self.spn_tolerance.setValue(15)
        self.spn_tolerance.setSuffix(" %")
        self.spn_tolerance.setFixedWidth(82)
        params_row.addWidget(self.spn_tolerance)

        params_row.addWidget(_inline_label("Health"))
        self.spn_health = QSpinBox()
        self.spn_health.setObjectName("filter_spin")
        self.spn_health.setRange(50, 100)
        self.spn_health.setValue(80)
        self.spn_health.setSuffix(" %")
        self.spn_health.setFixedWidth(82)
        params_row.addWidget(self.spn_health)

        header_row.addWidget(params_group)

        # SEARCH group
        search_group, search_row_inner = _make_group("SEARCH")
        self.bdt_search = QLineEdit()
        self.bdt_search.setObjectName("filter_input")
        self.bdt_search.setPlaceholderText(
            "Search by site ID or date  \u2014  e.g.  ABC123, 2025-01-12, 2025")
        self.bdt_search.setClearButtonEnabled(True)
        self.bdt_search.setMinimumWidth(220)
        self.bdt_search.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.bdt_search.textChanged.connect(self._filter_bdt_table)
        search_row_inner.addWidget(self.bdt_search)
        header_row.addWidget(search_group, 1)

        lay.addLayout(header_row)

        # Vertical splitter: results table + detail panel placeholder
        self.bdt_splitter = QSplitter(Qt.Vertical)
        self.bdt_splitter.setHandleWidth(1)

        # Results table
        cols = BDT_RESULT_HEADERS
        self.bdt_table = QTableWidget(0, len(cols))
        self.bdt_table.setHorizontalHeaderLabels(cols)
        self.bdt_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bdt_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bdt_table.setAlternatingRowColors(True)
        self.bdt_table.verticalHeader().setVisible(False)
        self.bdt_table.verticalHeader().setDefaultSectionSize(28)
        hdr = self.bdt_table.horizontalHeader()
        rule_cols = {c for c in cols if c.startswith("R") and c[1:].isdigit()}
        for i, col in enumerate(cols):
            if col in rule_cols:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                hdr.resizeSection(i, BDT_RESULT_WIDTHS.get(col, 80))
        hdr.setStretchLastSection(True)
        self.bdt_table.clicked.connect(self._on_bdt_row_clicked)
        self.bdt_splitter.addWidget(self.bdt_table)

        # Detail panel slot (will be filled by viewer via set_detail_panel)
        self._detail_panel_placeholder = None

        lay.addWidget(self.bdt_splitter, 1)

        # Bottom bar
        bot = QHBoxLayout()
        self.bdt_summary = QLabel("")
        self.bdt_summary.setStyleSheet(
            "color:#6c7086; font-size:12px; background:transparent;")
        bot.addWidget(self.bdt_summary)
        bot.addStretch()

        self.btn_bdt_export = QPushButton("Export Results XLSX")
        self.btn_bdt_export.setObjectName("btn_export")
        self.btn_bdt_export.setMinimumWidth(0)
        self.btn_bdt_export.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_bdt_export.clicked.connect(self._export_bdt_results)
        bot.addWidget(self.btn_bdt_export)

        self.btn_bdt_report = QPushButton("Daily Report")
        self.btn_bdt_report.setObjectName("btn_dir")
        self.btn_bdt_report.setMinimumWidth(0)
        self.btn_bdt_report.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.btn_bdt_report.clicked.connect(self._show_daily_review_report)
        bot.addWidget(self.btn_bdt_report)

        lay.addLayout(bot)

    def set_detail_panel(self, panel: QWidget):
        """Attach the BDT detail panel to the splitter."""
        self._detail_panel_placeholder = panel
        panel.setVisible(False)
        self.bdt_splitter.addWidget(panel)
        self.bdt_splitter.setSizes([250, 550])
        self.bdt_splitter.setStretchFactor(0, 0)
        self.bdt_splitter.setStretchFactor(1, 1)

    # ------------------------------------------------------------------
    # Validation logic
    # ------------------------------------------------------------------
    def _run_validation(self):
        viewer = self._viewer
        directory = viewer._edit_dir.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(
                self, "No Directory",
                "Set a directory in the sidebar first.")
            return

        bdt_files = []
        for root, _dirs, files in os.walk(directory):
            for f in files:
                fl = f.lower()
                if (fl.endswith(".xlsx") and "bdt" in fl
                        and not f.startswith("~$") and not f.startswith("._")):
                    bdt_files.append(os.path.join(root, f))

        if not bdt_files:
            QMessageBox.information(
                self, "No BDT Files",
                "No BDT .xlsx files found in directory.\n"
                "BDT filenames must contain 'BDT'.")
            return

        alarm_df = viewer._full_df if not viewer._full_df.empty else None
        tolerance = self.spn_tolerance.value() / 100.0
        health_pct = self.spn_health.value() / 100.0
        self._viewer._last_bdt_health_pct = health_pct

        viewer._sbar.showMessage(
            f"Validating {len(bdt_files)} BDT file(s)\u2026")
        self._viewer._bdt_results = []
        self._viewer._bdt_by_site = {}
        if self._detail_panel_placeholder:
            self._detail_panel_placeholder.setVisible(False)
        viewer._prog.setVisible(True)
        viewer._prog.setValue(0)

        self._bdt_thread = BDTValidationThread(
            bdt_files, alarm_df, tolerance, health_pct, skip_photos=viewer._skip_photos)
        self._bdt_thread.progress.connect(
            lambda v, m: (viewer._prog.setValue(v),
                          viewer._sbar.showMessage(m)))
        self._bdt_thread.finished.connect(self._on_validation_done)
        self._bdt_thread.error.connect(self._on_validation_error)
        self._bdt_thread.start()

    def _on_validation_done(self, results, by_site):
        viewer = self._viewer
        self._viewer._bdt_results = results
        self._viewer._bdt_by_site = by_site
        viewer._prog.setVisible(False)
        self._viewer._reviewed_bdt_keys.clear()
        self._populate_bdt_table()
        viewer._sbar.showMessage(
            f"Validated {len(self._viewer._bdt_results)} BDT file(s)")

    def _on_validation_error(self, msg):
        self._viewer._prog.setVisible(False)
        QMessageBox.critical(self, "Validation Error", msg)
        self._viewer._sbar.showMessage("Validation failed")

    def set_results(self, results: list):
        """Load validation results (e.g. restored from DB) and populate the table."""
        self._viewer._bdt_results = results
        self._populate_bdt_table()

    def _populate_bdt_table(self):
        results = self._viewer._bdt_results
        self.bdt_table.setRowCount(len(results))

        colors = {
            "Accepted":      QColor("#a6e3a1"),
            "Rejected":      QColor("#f38ba8"),
            "Revise":        QColor("#fab387"),
            "N/A":           QColor("#45475a"),
            "No alarm data": QColor("#45475a"),
        }

        for r, res in enumerate(results):
            row_map = {
                "File": res.filename,
                "Site Code": res.site_code or "--",
                "Test Date": res.test_date,
                "Verdict": res.overall,
                "End Rectifier Voltage (V)": self._format_end_rectifier_voltage(
                    res.bdt_data),
                "Lead-acid SOH (%)": self._format_lead_acid_soh(res.bdt_data),
            }
            for rule in res.rules:
                row_map[rule.rule_id] = self._rule_cell_text(rule)

            for c, col_name in enumerate(BDT_RESULT_HEADERS):
                val = row_map.get(col_name, "--")
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col_name == "Verdict" or col_name.startswith("R"):
                    item.setForeground(colors.get(val, QColor("#cdd6f4")))
                self.bdt_table.setItem(r, c, item)

        all_rules = [rule for r in results for rule in r.rules]
        n_acc = sum(1 for r in all_rules if r.verdict == "Accepted")
        n_rej = sum(1 for r in all_rules if r.verdict == "Rejected")
        n_rev = sum(1 for r in all_rules if r.verdict == "Revise")
        self.bdt_summary.setText(
            f"<span style='color:#a6e3a1;'>{n_acc} Accepted</span>"
            f" &middot; <span style='color:#f38ba8;'>{n_rej} Rejected</span>"
            f" &middot; <span style='color:#fab387;'>{n_rev} Revise</span>"
            f" &middot; <span style='color:#6c7086;'>"
            f"{len(results)} files</span>")

        self._filter_bdt_table(self.bdt_search.text())

    @staticmethod
    def _rule_cell_text(rule) -> str:
        if (rule.verdict == "N/A"
                and "no alarm data" in str(rule.detail).lower()):
            return "No alarm data"
        return rule.verdict

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

    def _filter_bdt_table(self, text: str):
        text = text.strip()
        if not text:
            for r in range(self.bdt_table.rowCount()):
                self.bdt_table.setRowHidden(r, False)
            return

        text_lower = text.lower()
        is_year = re.fullmatch(r"\d{4}", text)
        is_date = re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)

        for r in range(self.bdt_table.rowCount()):
            if r >= len(self._viewer._bdt_results):
                break
            res = self._viewer._bdt_results[r]
            show = False

            if is_year:
                show = res.test_date.startswith(text)
            elif is_date:
                show = res.test_date == text
            else:
                show = (text_lower in (res.site_code or "").lower()
                        or text_lower in (res.filename or "").lower())

            self.bdt_table.setRowHidden(r, not show)

    def _on_bdt_row_clicked(self, index):
        row = index.row()
        if row >= len(self._viewer._bdt_results):
            return
        res = self._viewer._bdt_results[row]
        self._record_review_event(res)

        if self._detail_panel_placeholder and not self._detail_panel_placeholder.isVisible():
            self._detail_panel_placeholder.setVisible(True)
            row_count = self.bdt_table.rowCount()
            header_h = self.bdt_table.horizontalHeader().height()
            row_h = self.bdt_table.verticalHeader().defaultSectionSize()
            table_h = header_h + (row_count * row_h) + 6
            table_h = min(table_h, 250)
            total = self.bdt_splitter.height() or 800
            self.bdt_splitter.setSizes([table_h, total - table_h])

        self.row_selected.emit(res)

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
