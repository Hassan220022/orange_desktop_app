from types import SimpleNamespace

from alarm_app.ui.panels.bdt_validation_panel import BdtValidationPanel


class _FakeTable:
    def __init__(self, row_count):
        self._row_count = row_count
        self._items = {}

    def rowCount(self):
        return self._row_count

    def setRowCount(self, row_count):
        self._row_count = row_count

    def item(self, row, column):
        return self._items.get((row, column))

    def setItem(self, row, column, item):
        self._items[(row, column)] = item


class _FakeItem:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _Button:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, enabled):
        self.enabled = enabled


def _result(site_code, test_date, verdict, filename):
    return SimpleNamespace(
        site_code=site_code,
        test_date=test_date,
        overall=verdict,
        filename=filename,
        rules=[],
        bdt_data=None,
    )


def _panel_for(results):
    panel = SimpleNamespace()
    panel._viewer = SimpleNamespace(_bdt_results=list(results))
    panel._bdt_col_filters = {}
    panel._bdt_page_size = 2
    panel._bdt_page_offset = 0
    panel._bdt_filtered_results = []
    panel.bdt_table = _FakeTable(len(results))
    panel.bdt_search = SimpleNamespace(text=lambda: "")
    panel.bdt_summary = _Label()
    panel._lbl_bdt_page = _Label()
    panel._lbl_bdt_page_range = _Label()
    panel._btn_bdt_prev_page = _Button()
    panel._btn_bdt_next_page = _Button()
    panel._format_end_rectifier_voltage = lambda bdt: "--"
    panel._format_lead_acid_soh = lambda bdt: "--"
    panel._row_map_for_result = lambda res: BdtValidationPanel._row_map_for_result(panel, res)
    panel._filtered_bdt_results_for_text = lambda text: BdtValidationPanel._filtered_bdt_results_for_text(panel, text)
    panel._update_bdt_pagination_controls = lambda: BdtValidationPanel._update_bdt_pagination_controls(panel)
    panel._populate_bdt_table = lambda: BdtValidationPanel._populate_bdt_table(panel)
    return panel


def test_filter_bdt_table_combines_search_and_column_filters():
    results = [
        _result("AAA001", "2026-04-19", "Accepted", "alpha.xlsx"),
        _result("BBB002", "2026-04-20", "Rejected", "beta.xlsx"),
        _result("AAA003", "2026-04-20", "Rejected", "gamma.xlsx"),
    ]
    panel = _panel_for(results)
    panel._bdt_col_filters = {"Verdict": {"Rejected"}}

    panel.bdt_search = SimpleNamespace(text=lambda: "AAA")
    BdtValidationPanel._populate_bdt_table(panel)

    assert [result.site_code for result in panel._bdt_filtered_results] == ["AAA003"]
    assert panel.bdt_table.rowCount() == 1
    assert panel._lbl_bdt_page.text == "Page 1/1"
    assert panel._lbl_bdt_page_range.text == "Rows 1-1 of 1"


def test_sort_bdt_column_reorders_backing_results():
    results = [
        _result("CCC003", "2026-04-21", "Accepted", "c.xlsx"),
        _result("AAA001", "2026-04-19", "Accepted", "a.xlsx"),
        _result("BBB002", "2026-04-20", "Rejected", "b.xlsx"),
    ]
    panel = _panel_for(results)
    populate_calls = []
    panel._populate_bdt_table = lambda: populate_calls.append(
        [result.site_code for result in panel._viewer._bdt_results]
    )

    BdtValidationPanel._sort_bdt_column(panel, "Site Code", 0)

    assert [result.site_code for result in panel._viewer._bdt_results] == [
        "AAA001",
        "BBB002",
        "CCC003",
    ]
    assert populate_calls == [["AAA001", "BBB002", "CCC003"]]


def test_bdt_pagination_tracks_page_and_range_labels():
    results = [
        _result("AAA001", "2026-04-19", "Accepted", "a.xlsx"),
        _result("BBB002", "2026-04-20", "Rejected", "b.xlsx"),
        _result("CCC003", "2026-04-21", "Accepted", "c.xlsx"),
    ]
    panel = _panel_for(results)

    BdtValidationPanel._populate_bdt_table(panel)
    assert panel._lbl_bdt_page.text == "Page 1/2"
    assert panel._lbl_bdt_page_range.text == "Rows 1-2 of 3"
    assert panel._btn_bdt_prev_page.enabled is False
    assert panel._btn_bdt_next_page.enabled is True

    BdtValidationPanel._load_next_bdt_page(panel)
    assert panel._lbl_bdt_page.text == "Page 2/2"
    assert panel._lbl_bdt_page_range.text == "Rows 3-3 of 3"
    assert panel._btn_bdt_prev_page.enabled is True
    assert panel._btn_bdt_next_page.enabled is False


def test_display_header_name_expands_rule_codes():
    assert BdtValidationPanel._display_header_name("R1") == "R1 - Photos"
    assert BdtValidationPanel._display_header_name("R10") == "R10 - Door Alarm Condition"
    assert BdtValidationPanel._display_header_name("Verdict") == "Verdict"


def test_copy_bdt_cell_copies_value_and_updates_status(monkeypatch):
    copied = {}
    panel = _panel_for([])
    panel.bdt_table._items[(1, 2)] = _FakeItem("Rejected")
    panel._viewer._sbar = SimpleNamespace(messages=[], showMessage=lambda msg, timeout=0: panel._viewer._sbar.messages.append((msg, timeout)))

    class _Clipboard:
        def setText(self, text):
            copied["text"] = text

    monkeypatch.setattr(
        "alarm_app.ui.panels.bdt_validation_panel.QApplication",
        SimpleNamespace(clipboard=lambda: _Clipboard()),
    )

    index = SimpleNamespace(isValid=lambda: True, row=lambda: 1, column=lambda: 2)
    BdtValidationPanel._copy_bdt_cell(panel, index)

    assert copied["text"] == "Rejected"
    assert panel._viewer._sbar.messages[-1] == ("Copied: Rejected", 2000)


def test_generate_pm_accept_report_shows_intro_dialog_before_file_picker(monkeypatch):
    calls = {}
    viewer = SimpleNamespace(
        _bdt_results=[_result("AAA001", "2026-04-19", "Accepted", "a.xlsx")],
        _last_bdt_health_pct=0.8,
        _uploaded_folder_path="",
        _edit_dir=SimpleNamespace(text=lambda: "/tmp"),
        _sbar=SimpleNamespace(messages=[], showMessage=lambda msg, timeout=0: viewer._sbar.messages.append((msg, timeout))),
    )
    panel = SimpleNamespace(
        _viewer=viewer,
        spn_health=SimpleNamespace(value=lambda: 80),
    )

    class _Dialog:
        def __init__(self, *, health_pct, parent=None):
            calls["health_pct"] = health_pct
            calls["parent"] = parent

        def exec_(self):
            return 0

    monkeypatch.setattr(
        "alarm_app.ui.panels.bdt_validation_panel.AcceptedPmReportDialog",
        _Dialog,
    )
    monkeypatch.setattr(
        "alarm_app.ui.panels.bdt_validation_panel.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("file picker should not open when intro is cancelled")),
    )

    BdtValidationPanel._generate_pm_accept_report(panel)

    assert calls["health_pct"] == 80
    assert calls["parent"] is panel
    assert viewer._sbar.messages[-1] == ("Accepted PM report cancelled", 0)


def test_run_validation_shows_intro_dialog_before_starting(monkeypatch):
    calls = {}
    viewer = SimpleNamespace(
        _skip_photos=True,
        _sbar=SimpleNamespace(messages=[], showMessage=lambda msg, timeout=0: viewer._sbar.messages.append((msg, timeout))),
    )
    panel = SimpleNamespace(
        _viewer=viewer,
        spn_tolerance=SimpleNamespace(value=lambda: 15),
        spn_health=SimpleNamespace(value=lambda: 80),
        _current_source_mode=lambda: "both",
        _validation_source_label=lambda source_mode: BdtValidationPanel._validation_source_label(source_mode),
    )

    class _Dialog:
        def __init__(self, *, source_label, tolerance_pct, health_pct, skip_photos, parent=None):
            calls["source_label"] = source_label
            calls["tolerance_pct"] = tolerance_pct
            calls["health_pct"] = health_pct
            calls["skip_photos"] = skip_photos
            calls["parent"] = parent

        def exec_(self):
            return 0

    monkeypatch.setattr(
        "alarm_app.ui.panels.bdt_validation_panel.BdtValidationIntroDialog",
        _Dialog,
    )

    BdtValidationPanel._run_validation(panel)

    assert calls == {
        "source_label": "Both (Verify)",
        "tolerance_pct": 15,
        "health_pct": 80,
        "skip_photos": True,
        "parent": panel,
    }
    assert viewer._sbar.messages[-1] == ("BDT validation cancelled", 0)
