# BDT Multi-Layout Parser — Bolt-Proof Plan

## State of Reality (as of 2026-04-14)

The original plan was written before implementation. This revision reflects
what actually exists in the codebase and what still needs work.

### Already shipped in this session

| Component                                                                     | File                    | Status |
| ----------------------------------------------------------------------------- | ----------------------- | ------ |
| `_LAYOUT_A` + `_LAYOUT_B` cell-position dicts                                 | `bdt/parser.py`         | Done   |
| `_detect_layout()` — L4 site-code + T3 date signals                           | `bdt/parser.py`         | Done   |
| Core field extraction routed through detected layout                          | `bdt/parser.py`         | Done   |
| `_PHOTO_LAYOUTS` — 6/15/16 photo variants with band_ranges + col_groups       | `bdt/parser.py`         | Done   |
| `_select_photo_layout()` — anchor-count-based version selection               | `bdt/parser.py`         | Done   |
| `_extract_photo_slots()` — anchor-first extraction, 4→N column remap          | `bdt/parser.py`         | Done   |
| `BDTData.photo_layout_id` + `required_photo_count` fields                     | `bdt/parser.py`         | Done   |
| R1 reads `bdt.required_photo_count` — live BDT_REQUIRED_PHOTO_COUNT bug fixed | `bdt/validator.py`      | Done   |
| `save_validation_batch()` with savepoint isolation per file                   | `bdt/history.py`        | Done   |
| Parallel parse+validate (up to 32 workers)                                    | `ui/threads.py`         | Done   |
| Deferred photo persistence — daemon thread post-UI-signal                     | `ui/threads.py`         | Done   |
| `append_outbox_events()` batch function                                       | `db/repos/sync_repo.py` | Done   |
| `pm_run is not None` guard for ghost outbox events                            | `bdt/history.py`        | Done   |

**The multi-layout parser core is working. The six-photo template photo
validation bug is fixed. What remains is test coverage, known edge-case
gaps, and Layout B real-world verification.**

---

## Phase 1: Lock in Working Code with Tests (Priority: High)

### Why first

No regression detection exists. `tests/fixtures/golden/` is empty.
Any future edit to `parser.py` can silently break the current correct
behavior and nobody will know until a user file fails.

### Work items

**1.1 Create minimal real-file fixtures**

Pull one representative file from each known template variant:

- `tests/fixtures/bdt_layout_a_16photo.xlsx` — Layout A, 16-photo (confirmed on 11 production files)
- `tests/fixtures/bdt_layout_a_6photo.xlsx` — Layout A, 6-photo (older template)
- `tests/fixtures/bdt_layout_b.xlsx` — Layout B (if any exist; skip if no files found)

Strip personal data: replace site codes and names with synthetic values
using openpyxl before committing.

**1.2 Core-field golden tests** (`tests/test_bdt_parser_core.py`)

For each fixture:

- `site_code` parses to expected value
- `test_date` parses and is not None
- `battery_ah`, `battery_voltage`, `num_batteries` parse to valid floats/ints
- `rectifier_brand` is non-empty

Failure = regression in `_detect_layout` or layout cell positions.

**1.3 Photo layout golden tests** (`tests/test_bdt_photo_layouts.py`)

For each fixture:

- `photo_layout_id` matches expected string
- `required_photo_count` matches expected int
- `len(photo_slots)` matches expected count
- Filled slots (`slot.image_data is not None`) count matches expected
- At least one slot has `category == "rectifier"` and one has `category == "batteries"`

Failure = regression in `_extract_photo_slots`, `_select_photo_layout`, or slot remapping.

**1.4 R1 validation test** (`tests/test_bdt_validator_r1.py`)

- 6-photo file: R1 passes when 6 photos present, fails with correct detail when 0 present
- 16-photo file: R1 passes at 16, fails at 15 with correct missing count

### Acceptance criteria

All tests pass on CI. Adding a new file fixture and running the suite
catches any regression within that fixture's scope.

---

## Phase 2: Fix Known Gaps (Priority: Medium)

### Gap 1 — Photo anchor count dead zone (8–12 anchors)

`_select_photo_layout` treats 8–12 anchors as "ambiguous" and falls
back to `max_anchor_col` heuristic. Real files in this range have not
been observed, but a corrupt 15-photo file with 3 missing photos would
land here and be misidentified.

**Fix:** add an explicit rule — 8–12 anchors with `max_anchor_col >= 22`
maps to `LAYOUT_PHOTO_15`, else `LAYOUT_PHOTO_6`. Document the heuristic
in a comment. No behavior change on observed files.

File: `bdt/parser.py` — `_select_photo_layout()`.

### Gap 2 — `_detect_layout` false-negative on blank L4 + blank T3

If both L4 and T3 are empty (e.g. a Layout A file with the site code
missing), `_detect_layout` falls through to Layout B and reads from the
wrong columns. This causes every subsequent field to be blank or wrong.

**Fix:** add a third signal — check L13 (rectifier brand at Layout A
row 13, col 12). A non-empty string there is strong evidence for Layout A
even if the header cells are blank.

```python
# In _detect_layout(), after the T3 check:
if max_col >= 12:
    rectifier_a = _safe_str(cell_fn(13, 12))
    if rectifier_a:
        return _LAYOUT_A
```

File: `bdt/parser.py` — `_detect_layout()`.

### Gap 3 — Layout B not tested on real files

`_LAYOUT_B` cell positions were inferred from the original code's
column-9 reads and adjusted. They have not been confirmed against a
real Layout B file. If no Layout B files exist in production, remove
the layout and simplify to "Layout A or log a warning."

**Fix:** run the parser on any file that `_detect_layout` classifies as
Layout B. Check that `site_code` and `test_date` parse correctly.
If no Layout B files exist after scanning the full archive, demote
`_LAYOUT_B` to a comment and make `_detect_layout` always return
`_LAYOUT_A` with a warning for unrecognized files.

File: `bdt/parser.py` — `_detect_layout()`, `_LAYOUT_B`.

---

## Phase 3: Robustness for New Templates (Priority: Low)

Only do this when a real new template variant is found in production.
Do not speculate ahead of actual data.

### When a new template arrives

1. Open the file in Excel. Record which cells hold site code, test date,
   battery brand, and photo count.
2. Add a new `_LAYOUT_C` dict with the confirmed positions.
3. Add a detection signal to `_detect_layout` that uniquely identifies it.
4. Add a fixture + golden test.
5. If photo geometry differs: add a `LAYOUT_PHOTO_N` entry to `_PHOTO_LAYOUTS`.

**No adapter classes. No scoring engine. No configuration flags.**
The dict + detect function pattern handles 3+ layouts with ~30 lines of code.
Complexity should grow only when a real variant demands it.

---

## Known Non-Issues (Do Not Reopen)

| Item                                         | Why it is not a problem                                                                                                                                             |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BDT_REQUIRED_PHOTO_COUNT` in `constants.py` | R1 now reads `bdt.required_photo_count`, which is set by `_extract_photo_slots`. The constant is now only the fallback default and does not control validation.     |
| Thread safety of layout dicts                | `_LAYOUT_A`, `_LAYOUT_B`, `_PHOTO_LAYOUTS` are module-level constants — read-only, no locks needed.                                                                 |
| Dashboards / metrics                         | This is a local desktop app with no network backend. There is nothing to dashboard. Log lines at `DEBUG` level are the observability layer.                         |
| Adapter class hierarchy                      | Two layout dicts + one detect function cover all current needs. Do not add classes until there are at least 4 layouts with genuinely different parsing logic paths. |
| Score-based detection                        | Image anchor counts are deterministic (6, 15, 16 are disjoint ranges). Score-based detection adds complexity without accuracy gain for this use case.               |
| Alembic migrations (task T6)                 | Separate concern from BDT parser. Track on its own task.                                                                                                            |

---

## File Change Map

| File                              | Change                                                           |
| --------------------------------- | ---------------------------------------------------------------- |
| `bdt/parser.py`                   | Gap 1 fix (`_select_photo_layout`), Gap 2 fix (`_detect_layout`) |
| `tests/test_bdt_parser_core.py`   | New — core field golden tests                                    |
| `tests/test_bdt_photo_layouts.py` | New — photo layout golden tests                                  |
| `tests/test_bdt_validator_r1.py`  | New — R1 rule unit tests                                         |
| `tests/fixtures/bdt_*.xlsx`       | New — anonymised fixture files                                   |

No other files need changes for the multi-layout work.

---

## Realistic Timeline

| Phase                      | Effort                                                            |
| -------------------------- | ----------------------------------------------------------------- |
| Phase 1 (fixtures + tests) | 1–2 days, gated on finding real Layout B files                    |
| Phase 2 (gap fixes)        | 2–3 hours each — all are small targeted changes                   |
| Phase 3 (new template)     | Per-template: 1 hour to confirm cells + 1 hour to add dict + test |

Total for Phases 1–2: under 2 days.

---

## Definition of Done

- Golden tests exist and pass for every template variant found in production.
- `_detect_layout` logs which layout it chose for every file processed.
- R1 passes on a 6-photo file with 6 photos present.
- R1 fails on a 16-photo file with only 6 photos and the detail string says "6/16 (missing 10)".
- No test in `tests/` imports `BDT_REQUIRED_PHOTO_COUNT` as the source of truth for required count.
