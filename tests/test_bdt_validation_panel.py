from types import SimpleNamespace

from alarm_app.ui.panels.bdt_validation_panel import BdtValidationPanel


class _FakeTable:
    def __init__(self, row_count):
        self._row_count = row_count
        self.hidden = {}

    def rowCount(self):
        return self._row_count

    def setRowHidden(self, row, hidden):
        self.hidden[row] = hidden


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
    panel.bdt_table = _FakeTable(len(results))
    panel._format_end_rectifier_voltage = lambda bdt: "--"
    panel._format_lead_acid_soh = lambda bdt: "--"
    panel._row_map_for_result = lambda res: BdtValidationPanel._row_map_for_result(panel, res)
    return panel


def test_filter_bdt_table_combines_search_and_column_filters():
    results = [
        _result("AAA001", "2026-04-19", "Accepted", "alpha.xlsx"),
        _result("BBB002", "2026-04-20", "Rejected", "beta.xlsx"),
        _result("AAA003", "2026-04-20", "Rejected", "gamma.xlsx"),
    ]
    panel = _panel_for(results)
    panel._bdt_col_filters = {"Verdict": {"Rejected"}}

    BdtValidationPanel._filter_bdt_table(panel, "AAA")

    assert panel.bdt_table.hidden == {
        0: True,
        1: True,
        2: False,
    }


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
