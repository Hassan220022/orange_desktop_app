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
