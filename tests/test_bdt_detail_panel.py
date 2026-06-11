from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from alarm_app.ui.panels.bdt_detail_panel import BdtDetailPanel


class _Widget:
    def __init__(self):
        self.visible = None

    def setVisible(self, visible):
        self.visible = visible


class _Hint:
    def __init__(self, text=""):
        self._text = text
        self.visible = None

    def text(self):
        return self._text

    def setVisible(self, visible):
        self.visible = visible


def _alarm_review_panel(*, door_hint_text=""):
    return SimpleNamespace(
        _bdt_door_section_label=_Widget(),
        _bdt_door_window_hint=_Hint(door_hint_text),
        _bdt_door_table=_Widget(),
        _bdt_door_empty=_Widget(),
        _bdt_power_section_label=_Widget(),
        _bdt_power_window_hint=_Hint(),
        _bdt_power_table=_Widget(),
        _bdt_power_empty=_Widget(),
        _bdt_hist_section_label=_Widget(),
        _bdt_history_table=_Widget(),
        _bdt_history_label=_Widget(),
    )


def test_sync_optional_sections_hides_alarm_review_when_no_bdt():
    panel = _alarm_review_panel()

    BdtDetailPanel._sync_optional_sections(
        panel,
        show_alarm_review=False,
        has_doors=False,
        has_power=False,
        has_history=False,
    )

    assert panel._bdt_door_section_label.visible is False
    assert panel._bdt_door_table.visible is False
    assert panel._bdt_door_empty.visible is False
    assert panel._bdt_power_section_label.visible is False
    assert panel._bdt_power_table.visible is False
    assert panel._bdt_power_empty.visible is False
    assert panel._bdt_hist_section_label.visible is False
    assert panel._bdt_history_table.visible is False
    assert panel._bdt_history_label.visible is False


def test_sync_optional_sections_always_shows_alarm_tables_for_open_bdt():
    panel = _alarm_review_panel(door_hint_text="Onsite window: 11:05 → 13:42")

    BdtDetailPanel._sync_optional_sections(
        panel,
        show_alarm_review=True,
        has_doors=False,
        has_power=False,
        has_history=False,
    )

    assert panel._bdt_door_section_label.visible is True
    assert panel._bdt_door_table.visible is True
    assert panel._bdt_door_empty.visible is True
    assert panel._bdt_door_window_hint.visible is True
    assert panel._bdt_power_section_label.visible is True
    assert panel._bdt_power_table.visible is True
    assert panel._bdt_power_empty.visible is True
    assert panel._bdt_hist_section_label.visible is False


def test_sync_optional_sections_hides_empty_hints_when_rows_exist():
    panel = _alarm_review_panel()

    BdtDetailPanel._sync_optional_sections(
        panel,
        show_alarm_review=True,
        has_doors=True,
        has_power=True,
        has_history=True,
    )

    assert panel._bdt_door_empty.visible is False
    assert panel._bdt_power_empty.visible is False
    assert panel._bdt_hist_section_label.visible is True
    assert panel._bdt_history_table.visible is True
    assert panel._bdt_history_label.visible is True


def test_power_alarms_for_test_date_filters_same_day_rows():
    alarm_df = pd.DataFrame(
        {
            "site_id": ["4528CA", "4528CA", "4528CA"],
            "occurred_on": pd.to_datetime(
                ["2026-04-02 10:00", "2026-04-01 09:00", "2026-04-02 11:05"]
            ),
            "cleared_on": pd.to_datetime(
                ["2026-04-02 12:00", "2026-04-01 10:00", "2026-04-02 13:00"]
            ),
            "alarm_category": ["Power", "Power", "Power"],
            "alarm_name": ["Mains Fail", "Mains Fail", "Mains Fail"],
            "duration": ["02:00:00", "01:00:00", "01:55:00"],
        }
    )

    def _find_power(df, site):
        return df[df["alarm_category"].str.lower() == "power"]

    rows = BdtDetailPanel._power_alarms_for_test_date(
        alarm_df,
        "4528CA",
        pd.Timestamp("2026-04-02"),
        _find_power,
    )

    assert len(rows) == 2
    assert rows.iloc[0]["occurred_on"].strftime("%Y-%m-%d %H:%M") == "2026-04-02 10:00"


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


def test_category_summary_text_formats_previous_test_heading():
    summary = {"batteries": 6, "modules": 0, "rectifier": 4}
    text = BdtDetailPanel._category_summary_text("2024-05-26", summary)

    assert text == "2024-05-26: Rectifier 4 · Batteries 6 · Modules 0"


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
        "REC BUS V",
        "REC BUS A",
        "Σ STR A",
        "Δ Σ-BUS",
    ]
    assert headers[5:] == ["S1 V", "S1 A", "S2 V", "S2 A"]


def test_discharge_section_index_groups_related_column_pairs():
    assert BdtDetailPanel._discharge_section_index_for_column(0) == 0
    assert BdtDetailPanel._discharge_section_index_for_column(1) == 1
    assert BdtDetailPanel._discharge_section_index_for_column(2) == 1
    assert BdtDetailPanel._discharge_section_index_for_column(3) == 2
    assert BdtDetailPanel._discharge_section_index_for_column(4) == 2
    assert BdtDetailPanel._discharge_section_index_for_column(5) == 3
    assert BdtDetailPanel._discharge_section_index_for_column(6) == 3
    assert BdtDetailPanel._discharge_section_index_for_column(7) == 4
    assert BdtDetailPanel._discharge_section_index_for_column(8) == 4


def test_discharge_section_palette_keeps_sections_visually_distinct():
    rect_header, rect_body = BdtDetailPanel._discharge_section_palette(1, "dark")
    string_one_header, string_one_body = BdtDetailPanel._discharge_section_palette(3, "dark")

    assert rect_header != string_one_header
    assert rect_body != string_one_body
    rect_bus_v, _ = BdtDetailPanel._discharge_section_palette(
        BdtDetailPanel._discharge_section_index_for_column(1),
        "dark",
    )
    rect_bus_a, _ = BdtDetailPanel._discharge_section_palette(
        BdtDetailPanel._discharge_section_index_for_column(2),
        "dark",
    )
    assert rect_bus_v == rect_bus_a


def test_discharge_section_palette_supports_light_and_dark_modes():
    light_header, light_body = BdtDetailPanel._discharge_section_palette(1, "light")
    dark_header, dark_body = BdtDetailPanel._discharge_section_palette(1, "dark")

    assert light_body != dark_body
    assert light_header.name() == dark_header.name()


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


def test_discharge_chart_points_uses_rec_bus_voltage_series():
    rows = [
        {"bus_v": 53.5, "bus_a": 44.0},
        {"bus_v": 47.7, "bus_a": 48.6},
        {"bus_v": None, "bus_a": 12.0},
        {"bus_v": 51.1, "bus_a": 44.0},
    ]

    assert BdtDetailPanel._discharge_chart_points(rows) == [53.5, 47.7, 51.1]


def test_discharge_col_minimum_width_uses_fixed_and_string_defaults():
    assert BdtDetailPanel._discharge_col_minimum_width(0) == BdtDetailPanel._DISCHARGE_COL_TIME
    assert BdtDetailPanel._discharge_col_minimum_width(3) == BdtDetailPanel._DISCHARGE_COL_NUMERIC
    assert BdtDetailPanel._discharge_col_minimum_width(5) == BdtDetailPanel._DISCHARGE_COL_STRING


def test_apply_discharge_column_visibility_always_shows_all_columns():
    panel = SimpleNamespace(
        _bdt_discharge_table=_FakeTable(),
    )

    panel._bdt_discharge_table.columnCount = lambda: len(BdtDetailPanel._DISCHARGE_FIXED_HEADERS) + 4
    BdtDetailPanel._apply_discharge_column_visibility(panel)

    for col in range(len(BdtDetailPanel._DISCHARGE_FIXED_HEADERS) + 4):
        assert panel._bdt_discharge_table.hidden[col] is False


def test_bdt_fullscreen_window_title_uses_site_and_date():
    bdt = SimpleNamespace(site_code="3406CA", test_date=datetime(2026, 4, 1))
    panel = SimpleNamespace(_current_bdt=bdt)

    title = BdtDetailPanel._bdt_fullscreen_window_title(panel)

    assert title == "BDT Test — 3406CA — 2026-04-01"


def test_compact_discharge_label_shortens_long_boundary_rows():
    assert BdtDetailPanel._compact_discharge_label("Before disconnecting Rectifier") == "Before …"
    assert BdtDetailPanel._compact_discharge_label("After Connecting power") == "After …"
    assert BdtDetailPanel._compact_discharge_label("30 Mins") == "30 Mins"
