from datetime import datetime
from types import SimpleNamespace

from alarm_app.ui.panels.bdt_detail_panel import BdtDetailPanel


class _Widget:
    def __init__(self):
        self.visible = None

    def setVisible(self, visible):
        self.visible = visible


def test_sync_optional_sections_hides_empty_sections():
    panel = SimpleNamespace(
        _bdt_door_section_label=_Widget(),
        _bdt_door_table=_Widget(),
        _bdt_door_empty=_Widget(),
        _bdt_hist_section_label=_Widget(),
        _bdt_history_table=_Widget(),
        _bdt_history_label=_Widget(),
    )

    BdtDetailPanel._sync_optional_sections(panel, has_doors=False, has_history=False)

    assert panel._bdt_door_section_label.visible is False
    assert panel._bdt_door_table.visible is False
    assert panel._bdt_door_empty.visible is False
    assert panel._bdt_hist_section_label.visible is False
    assert panel._bdt_history_table.visible is False
    assert panel._bdt_history_label.visible is False


def test_sync_optional_sections_shows_only_sections_with_content():
    panel = SimpleNamespace(
        _bdt_door_section_label=_Widget(),
        _bdt_door_table=_Widget(),
        _bdt_door_empty=_Widget(),
        _bdt_hist_section_label=_Widget(),
        _bdt_history_table=_Widget(),
        _bdt_history_label=_Widget(),
    )

    BdtDetailPanel._sync_optional_sections(panel, has_doors=True, has_history=False)

    assert panel._bdt_door_section_label.visible is True
    assert panel._bdt_door_table.visible is True
    assert panel._bdt_door_empty.visible is False
    assert panel._bdt_hist_section_label.visible is False
    assert panel._bdt_history_table.visible is False
    assert panel._bdt_history_label.visible is False


def test_display_rule_verdict_normalizes_non_primary_statuses():
    assert BdtDetailPanel._display_rule_verdict(SimpleNamespace(verdict="N/A")) == "No data"
    assert BdtDetailPanel._display_rule_verdict(SimpleNamespace(verdict="")) == "No data"
    assert BdtDetailPanel._display_rule_verdict(SimpleNamespace(verdict="Accepted")) == "Accepted"


def test_photo_verification_text_summarizes_c2pa_and_synthid_states():
    slot = SimpleNamespace(
        verification={
            "synthid": {"status": "detected", "confidence": 0.91},
        }
    )

    text = BdtDetailPanel._photo_verification_text(slot)

    assert "AI flag: SynthID detected (0.91)" in text


def test_photo_verification_text_hides_non_flagged_results():
    slot = SimpleNamespace(
        verification={
            "c2pa": {"status": "verified"},
            "synthid": {"status": "not_detected", "confidence": 0.12},
        }
    )

    assert BdtDetailPanel._photo_verification_text(slot) == ""


class _Combo:
    def __init__(self):
        self.items = []
        self.blocked = []

    def blockSignals(self, blocked):
        self.blocked.append(blocked)

    def clear(self):
        self.items.clear()

    def addItem(self, label, data):
        self.items.append((label, data))


def test_setup_photo_comparison_aggregates_all_previous_tests():
    current = SimpleNamespace(site_code="AAA001", test_date=datetime(2026, 4, 22))
    older1 = SimpleNamespace(site_code="AAA001", test_date=datetime(2026, 4, 21))
    older2 = SimpleNamespace(site_code="AAA001", test_date=datetime(2026, 4, 20))
    panel = SimpleNamespace(
        _bdt_compare_grid=SimpleNamespace(count=lambda: 0),
        _bdt_compare_section=_Widget(),
        _cmb_compare_year=_Combo(),
        _comparison_candidates_for_site=lambda bdt: [older1, older2],
        _show_photo_comparison=lambda all_slots=False: None,
    )

    BdtDetailPanel._setup_photo_comparison(panel, current)

    assert panel._bdt_compare_section.visible is True
    assert len(panel._cmb_compare_year.items) == 1
    label, data = panel._cmb_compare_year.items[0]
    assert label == "2 previous test(s)"
    assert data == [older1, older2]


def test_build_discharge_detail_rows_includes_bus_sum_and_delta():
    bdt = SimpleNamespace(
        start_voltage=53.42,
        start_ampere=69.0,
        after_reconnect_voltage=52.28,
        after_reconnect_ampere=70.1,
        discharge_readings=[
            ("10 Mins", 48.90, 64.90),
            ("30 Mins", 48.80, 66.00),
        ],
        string_discharge_readings=[
            [(53.42, 0.17), (53.42, 0.59), (53.42, 0.90)],
            [(48.90, 21.40), (48.90, 23.40), (48.90, 20.00)],
            [(48.80, 21.70), (48.80, 23.70), (48.80, 20.50)],
        ],
    )

    rows = BdtDetailPanel._build_discharge_detail_rows(bdt)

    assert [row["label"] for row in rows] == [
        "Before disconnecting Rectifier",
        "10 Mins",
        "30 Mins",
        "After Connecting power",
    ]
    assert rows[0]["sum_string_a"] is None
    assert rows[0]["delta_sum_minus_bus"] is None
    assert rows[1]["sum_string_a"] == 64.8
    assert round(rows[1]["delta_sum_minus_bus"], 2) == -0.10
    assert rows[1]["strings"][:3] == [
        (48.90, 21.40),
        (48.90, 23.40),
        (48.90, 20.00),
    ]
    assert len(rows[1]["strings"]) == 3
    assert rows[-1]["sum_string_a"] is None
    assert rows[-1]["delta_sum_minus_bus"] is None


def test_detect_active_discharge_strings_ignores_empty_trailing_strings():
    string_rows = [
        [(53.42, 0.17), (53.42, 0.59), (None, None), (None, None)],
        [(48.90, 21.40), (48.90, 23.40), (None, None), (None, None)],
    ]

    assert BdtDetailPanel._detect_active_discharge_strings(string_rows) == 2


def test_discharge_display_headers_expand_group_labels():
    headers = BdtDetailPanel._discharge_display_headers(2)

    assert headers[:5] == [
        "TIME: MIN (H)",
        "REC BUS\nV",
        "REC BUS\nA",
        "Σ STRING\nA",
        "Δ Σ-BUS",
    ]
    assert headers[5:] == ["STRING 1\nV", "STRING 1\nA", "STRING 2\nV", "STRING 2\nA"]


def test_discharge_section_index_groups_string_pairs_together():
    assert BdtDetailPanel._discharge_section_index_for_column(0) == 0
    assert BdtDetailPanel._discharge_section_index_for_column(4) == 4
    assert BdtDetailPanel._discharge_section_index_for_column(5) == 5
    assert BdtDetailPanel._discharge_section_index_for_column(6) == 5
    assert BdtDetailPanel._discharge_section_index_for_column(7) == 6
    assert BdtDetailPanel._discharge_section_index_for_column(8) == 6


def test_discharge_section_palette_keeps_sections_visually_distinct():
    rec_bus_header, rec_bus_body = BdtDetailPanel._discharge_section_palette(1, "dark")
    string_one_header, string_one_body = BdtDetailPanel._discharge_section_palette(5, "dark")

    assert rec_bus_header != string_one_header
    assert rec_bus_body != string_one_body


def test_discharge_section_palette_supports_light_and_dark_modes():
    light_header, light_body = BdtDetailPanel._discharge_section_palette(1, "light")
    dark_header, dark_body = BdtDetailPanel._discharge_section_palette(1, "dark")

    assert light_header != dark_header
    assert light_body != dark_body


class _FakeTable:
    def __init__(self):
        self.hidden = {}

    def setColumnHidden(self, idx, hidden):
        self.hidden[idx] = hidden


class _FakeButton:
    def __init__(self):
        self.text = None
        self.visible = None

    def setText(self, text):
        self.text = text

    def setVisible(self, visible):
        self.visible = visible


def test_apply_discharge_column_visibility_collapses_and_expands_string_columns():
    panel = SimpleNamespace(
        _bdt_discharge_expanded=False,
        _bdt_active_discharge_strings=2,
        _bdt_discharge_table=_FakeTable(),
        _btn_discharge_expand=_FakeButton(),
        _DISCHARGE_FIXED_HEADERS=BdtDetailPanel._DISCHARGE_FIXED_HEADERS,
        _DISCHARGE_MAX_STRINGS=BdtDetailPanel._DISCHARGE_MAX_STRINGS,
    )

    panel._bdt_discharge_table.columnCount = lambda: len(BdtDetailPanel._DISCHARGE_FIXED_HEADERS) + 4
    BdtDetailPanel._apply_discharge_column_visibility(panel)
    first_string_col = len(BdtDetailPanel._DISCHARGE_FIXED_HEADERS)
    assert panel._bdt_discharge_table.hidden[first_string_col] is True
    assert panel._btn_discharge_expand.text == "EXPAND STRINGS ⇲"
    assert panel._btn_discharge_expand.visible is True

    panel._bdt_discharge_expanded = True
    BdtDetailPanel._apply_discharge_column_visibility(panel)
    assert panel._bdt_discharge_table.hidden[first_string_col] is False
    assert panel._btn_discharge_expand.text == "COLLAPSE ⇱"


def test_apply_discharge_column_visibility_hides_button_when_no_strings():
    panel = SimpleNamespace(
        _bdt_discharge_expanded=False,
        _bdt_active_discharge_strings=0,
        _bdt_discharge_table=_FakeTable(),
        _btn_discharge_expand=_FakeButton(),
        _DISCHARGE_FIXED_HEADERS=BdtDetailPanel._DISCHARGE_FIXED_HEADERS,
        _DISCHARGE_MAX_STRINGS=BdtDetailPanel._DISCHARGE_MAX_STRINGS,
    )

    panel._bdt_discharge_table.columnCount = lambda: len(BdtDetailPanel._DISCHARGE_FIXED_HEADERS)
    BdtDetailPanel._apply_discharge_column_visibility(panel)
    assert panel._btn_discharge_expand.visible is False
