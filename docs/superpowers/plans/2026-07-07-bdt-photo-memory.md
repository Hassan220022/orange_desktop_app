# BDT Photo Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist BDT photos per validated workbook during the validation run, then release raw image bytes from RAM without changing photo validation behavior.

**Architecture:** Keep the existing BDT parser and validator path. Move photo persistence from the end-of-batch backlog to the per-result path inside `BDTValidationThread.run()`, then clear each persisted slot's `image_data` while keeping slot metadata and stored photo references available through existing DB-backed detail loading.

**Tech Stack:** Python 3.14, PyQt5 `QThread`, SQLAlchemy repositories, pytest.

## Global Constraints

- Do not skip photo extraction by default.
- R1 photo validation must still inspect the photos for each BDT before bytes get cleared.
- Raw `PhotoSlot.image_data` must not remain in memory for every BDT until the full validation batch ends.
- Use existing storage/persistence functions; do not add a new storage system.
- Keep changes in the BDT validation/persistence path only.

---

### Task 1: Persist and release BDT photos per validation result

**Files:**

- Modify: `ui/threads.py:530-791`
- Modify: `bdt/history.py:583-772`
- Test: `tests/test_bdt_history.py`
- Test: `tests/test_parsers.py`

**Interfaces:**

- Consumes: `bdt.history.save_validation_batch(items, alarm_df, params) -> (run_payloads, photo_jobs, failed_items)`
- Consumes: `bdt.history.persist_photo_jobs(photo_jobs) -> int`
- Produces: no new public API. Existing `finished(results, by_site)` signal keeps returning validation results and BDT data.

- [ ] **Step 1: Write failing tests for photo byte release**

Add tests that prove:

```python
from types import SimpleNamespace

from alarm_app.bdt.parser import PhotoSlot
from alarm_app.bdt.history import save_validation_batch


def test_save_validation_batch_clears_photo_bytes_after_queue(monkeypatch):
    slot = PhotoSlot(label="Rectifier", image_data=b"photo-bytes", image_ext="jpg", category="rectifier")
    bdt_data = SimpleNamespace(
        site_code="A-01",
        test_date="2026-01-05",
        file_path="/tmp/BDT_A01.xlsx",
        photo_slots=[slot],
    )
    validation_result = SimpleNamespace(overall="Accepted", rules=[], battery_backup_insight={})

    monkeypatch.setattr("alarm_app.bdt.history._get_session", lambda: fake_session)
    monkeypatch.setattr("alarm_app.bdt.history._register_bdt_uploaded_file", lambda *_: None)
    monkeypatch.setattr("alarm_app.db.repos.bdt_repo.save_bdt_test", lambda *_args, **_kwargs: SimpleNamespace(id=123))
    monkeypatch.setattr("alarm_app.db.repos.pm_repo.get_or_create_parameter_set", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("alarm_app.db.repos.pm_repo.get_or_create_rule_catalog", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("alarm_app.db.repos.pm_repo.save_validation_run", lambda *_args, **_kwargs: SimpleNamespace(id=456))
    monkeypatch.setattr("alarm_app.bdt.history._build_rule_results", lambda *_: [SimpleNamespace(rule_id="R1")])
    monkeypatch.setattr("alarm_app.bdt.history.compute_alarm_input_sha256", lambda *_: "alarmhash")

    _run_payloads, photo_jobs, _failed = save_validation_batch(
        items=[{"bdt_data": bdt_data, "validation_result": validation_result}],
        alarm_df=None,
        params={},
    )

    assert photo_jobs[0]["photo_slots"][0].image_data == b"photo-bytes"
    assert slot.image_data is None
```

If the existing test helpers already provide a fake session for `save_validation_batch`, reuse them instead of writing a new fake session.

- [ ] **Step 2: Run the new failing test**

Run:

```bash
source .venv/bin/activate
pytest tests/test_bdt_history.py::test_save_validation_batch_clears_photo_bytes_after_queue -q
```

Expected before fix: FAIL because `slot.image_data` still equals `b"photo-bytes"`.

- [ ] **Step 3: Implement minimal release after queue copy**

In `bdt/history.py`, after creating the `photo_jobs` copy, clear the original slots:

```python
photo_slots = list(getattr(bdt_data, "photo_slots", []) or [])
if photo_slots:
    photo_jobs.append({
        "bdt_test_id": int(bdt_db.id),
        "photo_slots": photo_slots,
    })
    for slot in photo_slots:
        if getattr(slot, "image_data", None):
            slot.image_data = None
```

If this clears bytes before `photo_jobs` persists them because the job shares the same slot objects, copy the slot objects first with `copy.copy(slot)` and queue the copies. Use stdlib `copy.copy`; do not add a dependency.

- [ ] **Step 4: Persist queued photos more often**

In `ui/threads.py`, stop building one giant photo backlog. After each successful `save_validation_batch()` call or after small chunks, call `persist_photo_jobs(photo_jobs)` and clear the queued list.

Use the smallest safe change:

```python
run_payloads, photo_jobs, failed_items = save_validation_batch(...)
if photo_jobs:
    self.progress.emit(96, "Saving validation photos …")
    stored = persist_photo_jobs(photo_jobs)
    self.photo_persistence_finished.emit(stored)
```

If keeping one `save_validation_batch()` at the very end makes photos persist only after every validation finishes, split `persist_items` into chunks of 1 inside the `for future in as_completed(futures)` loop. Prefer chunk size 1 because memory is the bug.

- [ ] **Step 5: Cap validation workers**

Change `workers = min(total, (os.cpu_count() or 1) * 4, 32)` to:

```python
workers = min(total, max(1, min(os.cpu_count() or 1, 4)))
```

This keeps photo-rich validation from loading too many workbooks at once.

- [ ] **Step 6: Run focused tests**

Run:

```bash
source .venv/bin/activate
pytest tests/test_bdt_history.py tests/test_parsers.py::TestBDTValidationThreadFiltering tests/test_non_table_alarm_migration.py::test_bdt_validation_thread_queries_targeted_alarm_subset -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ui/threads.py bdt/history.py tests/test_bdt_history.py tests/test_parsers.py
git commit -m "fix(bdt): release photo bytes during validation"
```
