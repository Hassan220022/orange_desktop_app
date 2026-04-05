## Plan: Full BDT Validation Recovery

Deliver a desktop-only, production-ready validation flow in alarm_app by preserving stable rules, adding typed comparison data extraction, surfacing auditable outputs in UI/export, and shipping with strict test gates. Scope excludes web parity and image-AI/CV inference. R1 stays count-only by decision: 16 photos Accepted, partial Revise, 0 Rejected.

**Steps**
1. Phase 0: Baseline lock and guardrails
1.1. Run the full desktop baseline test suite and record the pass count.
1.2. Freeze unchanged behavior for rules R2, R4, R5, R6, R7, R8, R9, R10 and existing summary columns.
1.3. Publish a do-not-change list for core symbols to execution agents.
1.4. Dependency: none.
1.5. Parallelism: can run with Step 2.1 documentation inventory.

2. Phase 1: Parser data model extension for typed comparison
2.1. Extend BDT parsed metadata to capture comparison-ready fields sourced from parsed sheet/slot labels: battery type signal, module type signal, rectifier type signal, optional counts when present.
2.2. Keep all existing parse paths and fallback behavior unchanged for current required fields.
2.3. Add normalization helpers so type tokens and counts are deterministic across years/files.
2.4. Dependency: Step 1 complete baseline lock.
2.5. Parallelism: test scaffolding for parser can run in parallel with Step 2.2.

3. Phase 2: Validation criteria hardening without behavior regressions
3.1. Preserve R1 final logic per decision: count-only policy (16 Accepted, partial Revise, 0 Rejected).
3.2. Add auditable comparison criteria utilities (not new blocking validation rule) to compute old vs new typed deltas from parser output.
3.3. Ensure criteria outputs are stable and machine-readable for UI and export use.
3.4. Dependency: Step 2 parser fields available.
3.5. Parallelism: UI wire-up prep can run in parallel once utility interfaces are finalized.

4. Phase 3: UI and export auditability upgrade
4.1. Upgrade comparison section to show old vs new for battery/module/rectifier typed signals plus optional counts.
4.2. Keep existing output labels stable: Starting I-Battery ampere, End Rectifier Voltage (V), Lead-acid SOH (%).
4.3. Improve rule-detail readability in the detail panel so operator can audit verdict reasons quickly.
4.4. Keep export schema backward compatible while appending any new comparison fields at the end only.
4.5. Dependency: Step 3 utilities complete.
4.6. Parallelism: styling polish can run in parallel with export mapping.

5. Phase 4: Test implementation and quality gates
5.1. Add parser tests for typed signal extraction and optional-count parsing under both fixed-cell and fallback scan paths.
5.2. Add validator utility tests for typed comparison outputs.
5.3. Add UI-helper tests for comparison summary generation and stable label formatting.
5.4. Re-run full suite and enforce zero regressions for stable rules and existing exports.
5.5. Dependency: Steps 2-4 complete.
5.6. Parallelism: parser tests and UI-helper tests can run in parallel.

6. Phase 5: Documentation and release handoff
6.1. Update requirements/design docs to reflect final implemented behavior and decisions.
6.2. Update README usage notes for validation criteria and comparison interpretation.
6.3. Publish a handoff packet with changed symbols, test evidence, and manual QA results.
6.4. Dependency: Step 5 test pass.

7. Execution orchestration with Explore subagents
7.1. Explore Agent A (Parser/Validator Track)
Deliverables: parser field additions, normalization helpers, comparison utility outputs, backward compatibility notes, parser+validator tests.
Scope files: /Users/mikawi/Developer/orange/alarm_app/bdt_parser.py, /Users/mikawi/Developer/orange/alarm_app/bdt_validator.py, /Users/mikawi/Developer/orange/alarm_app/constants.py, /Users/mikawi/Developer/orange/alarm_app/tests/test_bdt_parser.py, /Users/mikawi/Developer/orange/alarm_app/tests/test_bdt_validator.py.

7.2. Explore Agent B (UI/Export Track)
Deliverables: comparison UI mapping, detail-panel readability updates, export column append-only integration, UI-helper tests.
Scope files: /Users/mikawi/Developer/orange/alarm_app/viewer.py, /Users/mikawi/Developer/orange/alarm_app/styles.py, /Users/mikawi/Developer/orange/alarm_app/constants.py, /Users/mikawi/Developer/orange/alarm_app/tests (UI helper tests).

7.3. Explore Agent C (QA/Docs Track)
Deliverables: execution gate scripts, failure triage, manual QA checklist, docs updates.
Scope files: /Users/mikawi/Developer/orange/alarm_app/README.md, /Users/mikawi/Developer/orange/alarm_app/docs/requirements-specification.md, /Users/mikawi/Developer/orange/alarm_app/docs/plans/2026-03-02-alarm-id-and-bdt-validation-plan.md, /Users/mikawi/Developer/orange/alarm_app/docs/plans/2026-03-02-alarm-id-classification-and-bdt-validation-design.md.

7.4. Parallel policy
Run A+B+C in parallel for discovery and implementation bursts where file ownership does not conflict. Serialize only at merge points: constants schema agreement, final export mapping, and final full-suite run.

**Relevant files**
- /Users/mikawi/Developer/orange/alarm_app/bdt_parser.py — add typed comparison signals and optional count parsing while preserving current extraction behavior.
- /Users/mikawi/Developer/orange/alarm_app/bdt_validator.py — preserve existing rule outcomes, add comparison utility outputs for old/new typed deltas.
- /Users/mikawi/Developer/orange/alarm_app/constants.py — keep stable rule/summary constants; append-only additions for new comparison fields.
- /Users/mikawi/Developer/orange/alarm_app/viewer.py — comparison rendering, detail readability, export append-only mapping.
- /Users/mikawi/Developer/orange/alarm_app/styles.py — minimal styling updates for readability and comparison emphasis.
- /Users/mikawi/Developer/orange/alarm_app/tests/test_bdt_parser.py — parser coverage for new typed/count extraction.
- /Users/mikawi/Developer/orange/alarm_app/tests/test_bdt_validator.py — stability regression checks + comparison utility tests.
- /Users/mikawi/Developer/orange/alarm_app/README.md — user-facing behavior update.
- /Users/mikawi/Developer/orange/alarm_app/docs/requirements-specification.md — formal requirement alignment.
- /Users/mikawi/Developer/orange/alarm_app/docs/plans/2026-03-02-alarm-id-and-bdt-validation-plan.md — implementation-plan alignment.
- /Users/mikawi/Developer/orange/alarm_app/docs/plans/2026-03-02-alarm-id-classification-and-bdt-validation-design.md — design truth update.

**Verification**
1. Baseline before changes: run ./test_venv/bin/python -m pytest -q and record pass count.
2. Phase gates:
2.1. After parser changes: run parser tests then targeted validator tests.
2.2. After utility changes: run targeted comparison tests and unchanged-rule regression tests.
2.3. After UI/export changes: run UI-helper tests and export-shape checks.
3. Final gate: run full suite ./test_venv/bin/python -m pytest -q; require all pass.
4. Manual QA checklist:
4.1. Validate BDT folder run and verify row verdict/detail consistency.
4.2. Open compare-by-year view and confirm old/new typed deltas render correctly.
4.3. Export results and confirm stable existing columns plus append-only new fields.

**Decisions**
- Included scope: desktop app only under alarm_app.
- Excluded scope: web parity and image-similarity AI/CV inference.
- R1 final policy: count-only (16 Accepted, partial Revise, 0 Rejected).
- Type comparison source: parsed data under image labels and related parsed sheet metadata.

**Further Considerations**
1. Typed comparison granularity recommendation:
Option A: label-token based only.
Option B: label-token + sheet metadata merge.
Recommendation: Option B for stronger cross-year matching with low complexity.
2. Export field strategy recommendation:
Option A: replace current columns.
Option B: append-only new columns.
Recommendation: Option B to protect downstream consumers.
3. Future enhancement recommendation:
Add a non-blocking advisory rule for typed mismatch once current plan is stable and fully tested.