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
