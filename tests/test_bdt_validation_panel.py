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
