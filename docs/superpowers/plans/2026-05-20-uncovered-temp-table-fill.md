# Uncovered Temp Table Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill every Uncovered Temp Alarms table column with available source data instead of leaving prior-Power fields blank.

**Architecture:** Keep table rendering unchanged. Enrich `compute_temp_alarm_matches()` output rows with nearest same-site prior Power metadata when available, while preserving blank Power fields only when no prior same-site Power exists.

**Tech Stack:** Python, pandas, PyQt5, pytest.

---

## File Structure

- Modify: `core/temp_alarm.py`
  - Track nearest prior same-site Power for every uncovered Temp row.
  - Fill Power Alarm, Power Cleared, X Duration, Temp After Power, Temp After Clearance, and Coverage Status from available data.
- Modify: `tests/test_temp_alarm.py`
  - Add a regression test for uncovered Temp after prior Power outside Y margin.

## Task 1: Prior Power Details for Uncovered Temps

**Files:**
- Modify: `tests/test_temp_alarm.py`
- Modify: `core/temp_alarm.py:117-214`

- [ ] **Step 1: Write failing test**

Add a test that asserts an uncovered Temp alarm after a prior same-site Power alarm fills all prior-Power columns.

- [ ] **Step 2: Run focused test**

Run: `./.venv/bin/python -m pytest tests/test_temp_alarm.py::test_uncovered_temp_after_prior_power_includes_power_context -q`

Expected before implementation: FAIL because power context fields are blank.

- [ ] **Step 3: Implement enrichment**

Update `compute_temp_alarm_matches()` to collect uncovered records as `(temp_row, prior_power_row, coverage_end)`. For each uncovered Temp:

- If a prior Power exists, fill Power columns and delay columns.
- If no prior Power exists, keep Power columns blank and set coverage status to `No same-site Power alarm before Temp`.

- [ ] **Step 4: Run focused and full tests**

Run focused test, then `./.venv/bin/python -m pytest tests/test_temp_alarm.py -q`.

## Self-Review

- Spec coverage: approved fill strategy is covered.
- Placeholder scan: no placeholders remain.
- Scope: limited to table output data, not table rendering.
