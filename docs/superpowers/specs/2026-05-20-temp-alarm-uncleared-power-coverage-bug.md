# PRD: Uncleared Power Alarms Excluded from Temp Coverage

**Status:** `ready-for-agent`
**Created:** 2026-05-20
**Author:** Orchestrator (code review of Uncovered Temp Alarms)

---

## Problem Statement

An operations engineer opens the **Uncovered Temp Alarms** dialog to find temperature alarms that occurred *without* a corresponding power outage — these represent anomalous equipment failures that need investigation, not expected heat rise during a known power cut.

When a power alarm is *ongoing* (has no cleared-on timestamp), the tool silently drops it. The engineer sees temp alarms during live power outages listed as "uncovered," even though they're a normal consequence of the outage. The engineer wastes time chasing false leads on alarms that are already explained.

**Root cause:** `compute_temp_alarm_matches` filters to `valid_power = pwr.dropna(subset=["occurred_on", "cleared_on"])` — this discards every power alarm that has not been cleared. Ongoing outages contribute zero coverage, so every temp alarm during an active outage is falsely reported as uncovered.

**Precedent in the codebase:** Two sibling modules handle uncleared power alarms correctly:
- `core/classify.py` (site-down detection): fills NaT `cleared_on` with `pd.Timestamp.max` (infinite coverage)
- `core/backup_time.py` (backup-time computation): fills NaT `cleared_on` with end-of-occurrence-day

---

## Solution

Treat an uncleared power alarm as having infinite coverage — it started, it hasn't ended, so it covers every temp alarm at the same site after its occurrence time.

**Concrete change:** In `compute_temp_alarm_matches`, replace the `dropna` call with `fillna(pd.Timestamp.max)`, matching the pattern already proven in `classify.py`.

---

## User Stories

1. As an alarm analyst, I want temp alarms during an active power outage to be **excluded** from the Uncovered list, so that I focus only on unexplained temperature events.
2. As an alarm analyst, I want the Uncovered Temp Alarms count to reflect only genuine anomalies, so that I can trust the number and not mentally subtract alarms I know are during outages.
3. As an alarm analyst, I want Uncleared power alarms to contribute to coverage exactly like cleared ones — from occurrence onward — so that the dialog's behavior matches the note: "Power coverage runs from occurrence through clearance plus Y."
4. As an alarm analyst, I want the Uncovered Temp Alarms dialog to behave consistently with other features in the app (e.g., site-down detection and backup-time computation) so that I don't have to learn different rules for each feature.
5. As an alarm analyst viewing a site with a long-duration power outage, I want all temp alarms during that outage hidden from the Uncovered list, regardless of how long the outage has lasted.
6. As an alarm analyst exporting the Uncovered list to XLSX, I want the export to reflect the same corrected coverage logic, so that management reports don't contain false positives.
7. As a developer, I want the coverage algorithm to have test coverage for uncleared power alarms, so that this bug doesn't regress in future changes.

---

## Implementation Decisions

### Core fix

**Function:** `compute_temp_alarm_matches` in the temp-alarm core module
**Change:** Replace the line that drops NaT `cleared_on` with a fill operation, then filter as before.

**Before (buggy):**
```
valid_power = pwr.dropna(subset=["occurred_on", "cleared_on"])
valid_power = valid_power[valid_power["cleared_on"] >= valid_power["occurred_on"]]
```

**After (fixed):**
```
valid_power = pwr.dropna(subset=["occurred_on"]).copy()
valid_power["cleared_on"] = valid_power["cleared_on"].fillna(pd.Timestamp.max)
valid_power = valid_power[valid_power["cleared_on"] >= valid_power["occurred_on"]]
```

### Rationale for `Timestamp.max` over end-of-day

- `classify.py` uses `pd.Timestamp.max` for the same problem (site-down detection with uncleared power alarms). Consistency with existing conventions.
- End-of-day (`normalize + 1 day`, used in `backup_time.py`) is arbitrary — a power outage can span multiple days. `Timestamp.max` correctly models "ongoing = covers everything."
- The timestamp `pd.Timestamp.max` is ~year 2262, which is safely beyond any alarm data range.

### No interface changes

- `compute_temp_alarm_matches` signature is unchanged.
- `compute_temp_alarm_matches_for_query` inherits the fix automatically since it delegates.
- UI layer (`TempAlarmDialog`, `_recompute`, export) needs no changes.

### No schema changes

No database migrations required. The fix is pure DataFrame logic.

---

## Testing Decisions

### Test philosophy (from repo conventions)

Tests must verify behavior through the public interface (`compute_temp_alarm_matches`), not through internal data structures. A good test survives refactoring of the coverage algorithm — it asserts that specific temp alarms are covered or uncovered, not that particular columns have particular values.

### Tests to add (in existing test file)

| # | Test name | What it verifies |
|---|-----------|-----------------|
| 1 | `test_temp_during_active_power_outage_is_covered` | A temp alarm occurring *after* an uncleared power alarm is excluded from uncovered |
| 2 | `test_multiple_temps_during_active_outage_all_covered` | Multiple temp alarms during the same ongoing outage are all excluded |
| 3 | `test_temp_before_active_power_outage_is_uncovered` | A temp alarm occurring *before* the power outage started is still listed as uncovered |
| 4 | `test_mix_of_cleared_and_uncleared_power_coverage` | When a site has both cleared and uncleared power alarms, coverage windows work correctly for both |

### Prior art

The existing test `test_power_with_no_cleared_on` in the parsers test suite (site-down detection) is the closest analog. Use the same `_make_df` helper and `pd.NaT` pattern. The new tests live alongside the existing 15+ temp-alarm coverage tests.

### What NOT to test

- Internal data structures (column order, internal Series objects)
- The exact value of `pd.Timestamp.max` — treat it as opaque
- Rendering or UI behavior (that's an integration test concern)

---

## Out of Scope

- Refactoring the coverage algorithm beyond the NaT fix
- UI changes to the Uncovered Temp Alarms dialog
- Performance optimization of the power-alarm query (`date_from=None` issue)
- Deduplication of temp alarms
- Total-clear-duration formatting (day vs raw hours display)
- Adding end-to-end integration tests that require a running Qt app
- Tests for `compute_temp_alarm_matches_for_query` (DuckDB path) — covered by the pure function tests

---

## Further Notes

- The bug was discovered during a code review comparing the implementation against a running UI screenshot showing 52,726 uncovered temp alarms across 1,508 sites.
- The `filter_temp_matches_to_query` and `filter_temp_matches_to_selected_temps` post-filters are unaffected — they only limit which temp alarms appear in results, not which are considered covered.
- The XLSX export path (`export_temp_alarm_workbook`) receives pre-computed matches and needs no changes.
