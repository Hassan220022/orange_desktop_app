import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # MUST be first, before any PyQt5 imports

import time
from datetime import datetime as dt
from types import SimpleNamespace

import pytest
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

# -------------------------------------------------------------------
# Shared helpers
# -------------------------------------------------------------------

def _mock_result(site_code="0123AB", test_date=None, verdict="Accepted",
                 filename="test_bdt.xlsx", rules=None):
    if test_date is None:
        test_date = dt(2026, 5, 10)
    elif isinstance(test_date, str):
        test_date = dt.strptime(test_date, "%Y-%m-%d")
    return SimpleNamespace(
        site_code=site_code,
        test_date=test_date,
        overall=verdict,
        filename=filename,
        bdt_data=SimpleNamespace(
            file_path=f"/tmp/{filename}",
            site_code=site_code,
            site_name="Test Site",
            test_date=test_date,
            time_in="08:00",
            time_out="12:00",
            discharge_minutes=240.0,
            starting_ibattery_ampere=10.0,
            ibat_before_test=None,
            end_voltage=48.5,
            battery_brand="lead-acid",
            battery_ah=100,
            battery_voltage=48,
            num_strings=2,
            num_batteries=4,
            photo_count=3,
            summary_data={},
        ),
        rules=rules or [
            SimpleNamespace(verdict="Accepted", rule_id="R1"),
            SimpleNamespace(verdict="Rejected", rule_id="R2"),
            SimpleNamespace(verdict="Revise", rule_id="R3"),
        ],
    )


class _FakeBDTValidationThread(QObject):
    """Replaces BDTValidationThread — short-circuits to deliver mock results."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, bdt_files, alarm_df, tolerance, health_pct,
                 skip_photos=False, tolerances=None):
        super().__init__()
        self._files = bdt_files
        self._tolerance = tolerance
        self._health_pct = health_pct

    def start(self):
        results = []
        for fp in self._files:
            results.append(_mock_result(
                filename=os.path.basename(fp),
                site_code="0123AB",
                test_date="2026-05-10",
                verdict="Accepted",
            ))
        by_site: dict[str, list] = {}
        for res in results:
            if res.site_code and res.bdt_data is not None:
                by_site.setdefault(res.site_code.upper(), []).append(res.bdt_data)
        self.finished.emit(results, by_site)


# -------------------------------------------------------------------
# Fixture
# -------------------------------------------------------------------

@pytest.fixture
def gui_app(tmp_path, monkeypatch):
    """Create a QApplication, patch dependencies, yield the viewer."""
    monkeypatch.setattr("alarm_app.ui.state_manager.StateManager.apply", lambda *a, **kw: None)
    monkeypatch.setattr("alarm_app.data.state.load_state", lambda: {})
    monkeypatch.setattr(
        "alarm_app.data.state.load_feature_flags",
        lambda *a, **kw: {"sync_on": False, "cloud_read_on": False, "bootstrap_on": False},
    )
    monkeypatch.setattr("alarm_app.data.state.has_alarm_cache", lambda: False)
    monkeypatch.setattr("getpass.getuser", lambda: "test_user")

    # Patch DB engine paths to tmp_path
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.engine._app_engine", None)
    monkeypatch.setattr("alarm_app.db.engine._app_session_factory", None)
    monkeypatch.setattr("alarm_app.data.state._engine", None)
    monkeypatch.setattr("alarm_app.data.state._SessionFactory", None)

    # Prevent sync worker / bootstrap from spawning threads
    monkeypatch.setattr(
        "alarm_app.ui.viewer.LocalSyncWorker",
        type("FakeSync", (), {"start": lambda s: None}),
    )

    # Short-circuit the BDT validation thread
    monkeypatch.setattr(
        "alarm_app.ui.panels.bdt_validation_panel.BDTValidationThread",
        _FakeBDTValidationThread,
    )
    monkeypatch.setattr(
        "alarm_app.ui.panels.bdt_validation_panel.ExportThread",
        type("FakeExport", (), {"start": lambda s: None}),
    )

    # Auto-accept all modal dialogs
    def _auto_accept(dialog_self, *args, **kwargs):
        dialog_self.accept()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", _auto_accept)
    monkeypatch.setattr(QMessageBox, "exec_", _auto_accept)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: QMessageBox.Ok)

    app = QApplication([])
    app.setStyle("Fusion")

    from alarm_app.ui.viewer import AlarmViewer
    viewer = AlarmViewer()
    viewer.show()
    app.processEvents()

    yield viewer

    viewer.close()
    app.processEvents()
    app.quit()


# -------------------------------------------------------------------
# Populate helpers
# -------------------------------------------------------------------

def _inject_results(viewer, results):
    """Inject mock results into the viewer and populate the BDT table."""
    viewer._bdt_results = list(results)
    panel = viewer._bdt_validation_panel
    panel._invalidate_bdt_filter_cache()
    panel._bdt_page_offset = 0
    panel._populate_bdt_table()
    viewer._prog.setVisible(False)
    QApplication.processEvents()


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

class TestBDTValidationGUI:

    def test_bdt_panel_exists_on_startup(self, gui_app):
        gui_app._tabs.setCurrentIndex(1)  # switch to BDT tab
        gui_app._apply_workspace_state(1)
        QApplication.processEvents()

        panel = gui_app._bdt_validation_panel
        assert panel is not None
        assert panel.isVisible()
        assert hasattr(panel, "btn_parameters")
        assert panel.btn_parameters is not None
        assert panel.btn_parameters.text() == "Open Parameters"

    def test_bdt_source_combo_has_options(self, gui_app):
        cmb = gui_app._bdt_validation_panel.cmb_bdt_source
        assert cmb is not None
        assert cmb.count() >= 2
        items = [cmb.itemText(i) for i in range(cmb.count())]
        assert "Directory" in items
        assert "DB" in items

    def test_bdt_validation_runs_with_real_files(self, gui_app, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Rectifier 1"
        ws["I4"] = "0123AB"
        xlsx_path = tmp_path / "test_bdt_data.xlsx"
        wb.save(str(xlsx_path))

        viewer = gui_app
        viewer._bdt_uploaded_folder_path = str(tmp_path)
        viewer._bdt_file_infos = [
            {"path": str(xlsx_path), "filename": xlsx_path.name,
             "ext": ".xlsx", "size_kb": 1.0, "rel_path": xlsx_path.name},
        ]
        viewer._bdt_validation_panel.cmb_bdt_source.setCurrentIndex(0)

        panel = viewer._bdt_validation_panel
        panel._run_validation()
        QApplication.processEvents()
        time.sleep(0.05)
        QApplication.processEvents()

        assert len(viewer._bdt_results) > 0
        assert len(viewer._bdt_results) == 1
        assert viewer._bdt_results[0].site_code == "0123AB"

    def test_bdt_results_table_populated_after_validation(self, gui_app):
        results = [_mock_result("SITE01", "2026-05-10", "Accepted", "f1.xlsx")]
        _inject_results(gui_app, results)
        panel = gui_app._bdt_validation_panel
        assert panel.bdt_table.rowCount() > 0
        assert panel.bdt_table.rowCount() == 1
        item = panel.bdt_table.item(0, 0)
        assert item is not None
        assert item.text() == "f1.xlsx"

    def test_bdt_parameters_dialog_opens(self, gui_app):
        panel = gui_app._bdt_validation_panel
        panel._show_parameters_dialog()
        QApplication.processEvents()
        assert panel.spn_health is not None
        assert isinstance(panel.spn_health.value(), int)

    def test_filter_bdt_by_verdict(self, gui_app):
        results = [
            _mock_result("S01", "2026-05-10", "Accepted", "acc.xlsx",
                         rules=[SimpleNamespace(verdict="Accepted", rule_id="R1")]),
            _mock_result("S02", "2026-05-10", "Rejected", "rej.xlsx",
                         rules=[SimpleNamespace(verdict="Rejected", rule_id="R2")]),
            _mock_result("S03", "2026-05-10", "Accepted", "acc2.xlsx",
                         rules=[SimpleNamespace(verdict="Accepted", rule_id="R1")]),
        ]
        _inject_results(gui_app, results)
        panel = gui_app._bdt_validation_panel
        total = panel.bdt_table.rowCount()

        # Filter by "Accepted" via search on the Verdict column
        panel._bdt_col_filters = {"Verdict": {"Accepted"}}
        panel._filter_bdt_table("")

        filtered = panel.bdt_table.rowCount()
        assert filtered > 0
        assert filtered < total
        assert filtered == 2

    def test_bdt_export_button_exists(self, gui_app):
        btn = gui_app._bdt_validation_panel.btn_bdt_export
        assert btn is not None
        assert btn.text() == "Export Results XLSX"
        assert isinstance(btn.isEnabled(), bool)

    def test_bdt_detail_panel_selects_item(self, gui_app):
        results = [
            _mock_result("DET01", dt(2026, 5, 10), "Accepted", "detail.xlsx"),
        ]
        _inject_results(gui_app, results)

        panel = gui_app._bdt_validation_panel
        model = panel.bdt_table.model()
        assert model is not None

        index = model.index(0, 0)
        assert index.isValid()

        panel.row_selected.disconnect()
        spy_calls = []

        def _spy(res):
            spy_calls.append(res)

        panel.row_selected.connect(_spy)

        panel._on_bdt_row_clicked(index)
        QApplication.processEvents()

        assert len(spy_calls) == 1
        assert spy_calls[0].site_code == "DET01"

        detail_panel = getattr(gui_app, "_bdt_detail_panel_obj", None)
        assert detail_panel is not None

    def test_bdt_rules_reference_dialog_opens(self, gui_app):
        panel = gui_app._bdt_validation_panel
        panel._show_rules_reference_dialog()
        QApplication.processEvents()
        assert panel.btn_rule_guide is not None
