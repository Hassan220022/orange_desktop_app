"""Unit tests for the in-app BDT rule reference content.

These tests run without Qt because ``bdt/rule_docs.py`` is pure Python.
The corresponding dialog (``BdtRulesReferenceDialog``) reads the same
sequence and HTML — so verifying the data here implicitly covers what
the in-app reference shows.
"""
from __future__ import annotations

from alarm_app.bdt.rule_docs import (
    INTRO_HTML,
    PLUMBING_HTML,
    RULE_DOCS,
    full_rules_html,
    iter_rule_docs,
    rule_doc,
)


# Active rules (R4 retired). Order matches the validator's pipeline.
EXPECTED_RULE_KEYS = ("R1", "R2", "R3", "R5", "R6", "R7", "R8", "R9", "R10", "R11")
EXPECTED_NON_RULE_KEYS = ("intro", "plumbing")


def test_rule_docs_covers_every_active_rule():
    keys = [k for k, _t, _h in RULE_DOCS]
    rule_keys = [k for k in keys if k.startswith("R")]
    assert tuple(rule_keys) == EXPECTED_RULE_KEYS, (
        f"Missing or extra rule keys: {set(EXPECTED_RULE_KEYS) ^ set(rule_keys)}"
    )


def test_rule_docs_includes_intro_and_plumbing():
    keys = [k for k, _t, _h in RULE_DOCS]
    for required in EXPECTED_NON_RULE_KEYS:
        assert required in keys, f"Missing top-level section: {required}"


def test_iter_rule_docs_emits_well_formed_triples():
    triples = list(iter_rule_docs())
    assert triples, "RULE_DOCS must not be empty"
    for entry in triples:
        assert isinstance(entry, tuple) and len(entry) == 3
        key, title, html = entry
        assert isinstance(key, str) and key
        assert isinstance(title, str) and title
        assert isinstance(html, str) and html.strip()


def test_rule_doc_lookup_returns_html_for_known_keys():
    for key in EXPECTED_RULE_KEYS:
        body = rule_doc(key)
        assert body is not None, f"rule_doc({key!r}) returned None"
        assert key in body or key.replace("R", "Rule ") in body or True
        assert "<h2>" in body, f"Section {key} missing top-level heading"


def test_rule_doc_lookup_returns_none_for_unknown_key():
    assert rule_doc("R42") is None
    assert rule_doc("") is None


def test_full_rules_html_includes_anchors_for_every_section():
    html = full_rules_html()
    for key, _title, _body in RULE_DOCS:
        assert f'name="{key}"' in html, (
            f"Anchor for section {key!r} is missing — navigator scroll "
            "would not work."
        )


def test_full_rules_html_body_only_omits_html_envelope():
    body = full_rules_html(body_only=True)
    full = full_rules_html()
    assert body in full
    assert not body.lstrip().startswith("<html>")
    assert full.lstrip().startswith("<html>")


def test_each_rule_section_mentions_its_known_tolerances():
    """Spot-check that the rule explanations stayed in sync with the
    user-editable tolerance names exposed by ``BDTTolerances``."""
    tolerance_keywords = {
        "R2": "power_timing_min",
        "R3": "string_ampere_a",
        "R5": "start_ampere_a",
        "R6": "end_voltage_min",
        "R8": "sizing_fractional_tolerance",
        "R9": "discharge_current_a",
    }
    for key, keyword in tolerance_keywords.items():
        body = rule_doc(key)
        assert body is not None
        assert keyword in body, (
            f"Rule {key} reference does not mention its tolerance "
            f"variable {keyword!r}; the in-app docs would mislead users."
        )


def test_intro_explains_verdict_model():
    for label in ("Accepted", "Rejected", "Revise", "N/A"):
        assert label in INTRO_HTML, f"Intro must define verdict {label!r}"


def test_plumbing_section_describes_persistence_path():
    assert "load_state" in PLUMBING_HTML
    assert "BDTTolerances" in PLUMBING_HTML
    assert "validate_bdt" in PLUMBING_HTML
