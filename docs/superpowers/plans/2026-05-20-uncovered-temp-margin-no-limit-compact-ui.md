# Uncovered Temp Margin No-Limit Compact UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the 60-minute Y-margin cap and shrink the Uncovered Temp Alarms header into a compact toolbar.

**Architecture:** Update both core margin normalization and UI controls so Y margin is any non-negative integer minute value. Keep the explicit Apply flow for responsive typing, and replace the oversized card header with compact inline controls and metric pills.

**Tech Stack:** Python, pandas, PyQt5, pytest.

---

## File Structure

- Modify: `core/temp_alarm.py`
  - Remove upper clamp in `compute_temp_alarm_matches` and `_covered_temp_rows`.
  - Add safe margin handling so extremely large margins do not overflow pandas timestamps.
- Modify: `ui/dialogs.py`
  - Remove 60 cap in `TempAlarmDialog` initialization and spinbox range.
  - Replace large filter/export dashboard cards with a compact toolbar layout.
  - Update explanatory note text.
- Modify: `tests/test_temp_alarm.py`
  - Add a regression test proving margins greater than 60 affect matching.

## Task 1: Core No-Limit Margin

**Files:**
- Modify: `core/temp_alarm.py:100-145`
- Modify: `core/temp_alarm.py:792-814`
- Test: `tests/test_temp_alarm.py`

- [ ] **Step 1: Add a failing regression test**

Add a test to `tests/test_temp_alarm.py` after `test_includes_temp_after_y_margin`:

```python
def test_margin_can_exceed_sixty_minutes():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 13:30:00",
            "cleared_on": "2026-02-01 14:00:00",
            "duration": "00:30:00",
        },
    ])

    result, err = compute_temp_alarm_matches(df, margin_minutes=120)

    assert result.empty
    assert "No uncovered Temp alarms" in err
```

- [ ] **Step 2: Run the new test to verify it fails before the fix**

Run: `./.venv/bin/python -m pytest tests/test_temp_alarm.py::test_margin_can_exceed_sixty_minutes -q`

Expected before implementation: FAIL because margin is clamped to 60 and the 13:30 Temp alarm remains uncovered.

- [ ] **Step 3: Implement non-negative margin normalization**

Add helpers near the top of `core/temp_alarm.py`:

```python
def _normalize_margin_minutes(margin_minutes: int | None) -> int:
    try:
        value = int(margin_minutes or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, value)


def _safe_margin_delta(margin_minutes: int) -> pd.Timedelta | None:
    if margin_minutes <= 0:
        return pd.Timedelta(0)
    try:
        return pd.Timedelta(minutes=margin_minutes)
    except (OverflowError, ValueError):
        return None
```

- [ ] **Step 4: Use helpers in coverage calculations**

Replace `max(0, min(int(margin_minutes or 0), 60))` with `_normalize_margin_minutes(margin_minutes)` in both core functions. For margin addition, if `_safe_margin_delta` returns `None`, set finite coverage ends to `pd.Timestamp.max`; otherwise use the existing safe-add logic.

- [ ] **Step 5: Run focused tests**

Run: `./.venv/bin/python -m pytest tests/test_temp_alarm.py::test_margin_can_exceed_sixty_minutes tests/test_temp_alarm.py::test_includes_temp_after_y_margin tests/test_temp_alarm.py::test_excludes_temp_after_power_clearance_within_y_margin -q`

Expected: all selected tests pass.

## Task 2: Compact Toolbar UI

**Files:**
- Modify: `ui/dialogs.py:1734-1904`

- [ ] **Step 1: Run GitNexus impact analysis**

Run: `/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream 'Method:ui/dialogs.py:TempAlarmDialog._build#0'`

Expected: LOW risk, limited to `TempAlarmDialog.__init__`.

- [ ] **Step 2: Remove UI 60 cap**

Change dialog initialization to clamp only to zero:

```python
self._margin_minutes = max(0, int(margin_minutes or 0))
```

Set the spinbox range to:

```python
self._spn_margin.setRange(0, 2_147_483_647)
```

- [ ] **Step 3: Compact the header**

Replace the large filter card and export card with a single compact `QHBoxLayout` toolbar:

```python
margin_label = QLabel("Y margin")
margin_label.setStyleSheet("color:#a6adc8; font-size:12px; font-weight:700;")
tl.addWidget(margin_label)
tl.addWidget(self._spn_margin)

margin_unit = QLabel("min")
margin_unit.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
tl.addWidget(margin_unit)

self._btn_apply_margin = QPushButton("Apply")
self._btn_apply_margin.setFixedSize(62, 30)
self._btn_apply_margin.clicked.connect(self._recompute_margin_now)
tl.addWidget(self._btn_apply_margin)
```

- [ ] **Step 4: Shrink metric cards**

Set metric card minimum width to about `112`, reduce padding to `8, 6, 8, 6`, and keep the same four values.

- [ ] **Step 5: Update note text**

Change the note to:

```python
"Temp alarms are shown only when no same-site Power alarm covers them. "
"Power coverage runs from occurrence through clearance plus Y. "
"Y is a non-negative margin in minutes."
```

## Task 3: Verification

**Files:**
- Test: `tests/test_temp_alarm.py`
- Test: `ui/dialogs.py`

- [ ] **Step 1: Compile UI**

Run: `./.venv/bin/python -m py_compile ui/dialogs.py`

Expected: exits with no output.

- [ ] **Step 2: Run Temp alarm tests**

Run: `./.venv/bin/python -m pytest tests/test_temp_alarm.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run PyQt margin harness**

Run the existing offscreen harness pattern with a value above 60, such as `120`, and assert `spin.value() == 120` and `_margin_minutes == 120` after Apply.

Expected: value above 60 is accepted and applied.

## Self-Review

- Spec coverage: plan removes 60 cap in core and UI, updates note text, and compacts header.
- Placeholder scan: no placeholders remain.
- Type consistency: helper names and `TempAlarmDialog` attributes are consistent.
