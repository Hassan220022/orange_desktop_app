from types import SimpleNamespace

from alarm_app.ui.dialogs import BdtRulesReferenceDialog, _resolved_parent_theme_mode


def test_resolved_parent_theme_mode_uses_auto_detector():
    parent = SimpleNamespace(
        _theme_mode="auto",
        _detect_os_theme=lambda: "light",
        parent=lambda: None,
    )

    assert _resolved_parent_theme_mode(parent) == "light"


def test_bdt_rules_reference_dialog_label_style_changes_with_theme():
    light_stub = SimpleNamespace(_theme_mode="light")
    dark_stub = SimpleNamespace(_theme_mode="dark")

    assert "#4c4f69" in BdtRulesReferenceDialog._label_style(light_stub, "intro")
    assert "#5c5f77" in BdtRulesReferenceDialog._label_style(light_stub, "body")

    assert "#cdd6f4" in BdtRulesReferenceDialog._label_style(dark_stub, "intro")
    assert "#6c7086" in BdtRulesReferenceDialog._label_style(dark_stub, "summary")
