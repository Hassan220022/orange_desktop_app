# PRD: Robust Multi-Layout BDT Parsing and Photo Validation (Production-Grade)

## 1. Document Info
- Product: Alarm App BDT Pipeline
- Repo: `/Users/mikawi/Developer/orange/alarm_app`
- Spec Source: `/Users/mikawi/Developer/orange/BDT_LAYOUT_ANALYSIS.md`
- Priority: P0
- Owner: Engineering
- Audience: AI Coding Agent implementing end-to-end
- Status: Ready for implementation

## 2. Problem Statement
Current BDT parsing and photo validation are brittle because they assume partially fixed sheet geometry and infer photo layout from anchor counts. Production files have multiple sheet families and uncontrolled image layout/count. This causes false rejects, inconsistent behavior, and hard-to-debug outcomes.

The system must parse all production BDT families reliably, validate photos by semantic categories instead of rigid slot counts, and preserve high throughput for large batches.

## 3. Goals
1. Parse BDT files across known production families with deterministic primary detection and robust fallbacks.
2. Replace rigid photo-count validation with category-based validation that tolerates layout variability.
3. Keep per-file parsing complexity effectively O(N) and maintain batch throughput.
4. Preserve or improve current persistence safety guarantees (no ghost outbox events, no batch-wide rollback on single duplicate).
5. Ship with comprehensive automated tests and real-fixture coverage.

## 4. Non-Goals
1. No UI redesign.
2. No schema-breaking DB migration unless strictly required.
3. No remote telemetry platform integration.
4. No OCR/computer-vision model introduction.

## 5. Success Metrics
- Parsing success rate on production corpus: `>= 99%` for non-corrupt BDT files.
- False reject rate for photo rule R1: `< 1%` on manually spot-checked sample.
- Throughput: no regression vs current baseline; target `>= current files/sec`.
- Test suite: all relevant parser/validator/history/thread tests passing.
- Deterministic behavior: ambiguous cases explicitly flagged, not silently misclassified.

## 6. Scope
### In Scope
1. `bdt/parser.py` core layout-family detection and extraction flow.
2. Photo extraction and category mapping logic.
3. `bdt/validator.py` R1 rule redesign to category-based validation.
4. Batch persistence path correctness in `bdt/history.py`, `ui/threads.py`, and related repos.
5. Tests and fixtures in `tests/`.

### Out of Scope
1. Rewriting whole architecture into plugin framework.
2. Replacing pandas/SQLAlchemy stack.
3. Full historical backfill of old DB records.

## 7. Functional Requirements

### FR-001: Deterministic Sheet Family Detection
The parser must detect family using workbook/sheet structure first, in this precedence:
1. Layout A family: canonical `BDT`.
2. Layout B1 family: `Rectifier 1` singleton.
3. Layout B2 family: paired rectifier names (`Rec1/Rec2`, `Rec 1/Rec 2`, `Rect.1/Rect.2`).
4. Layout C family: test_pms multi-sheet (`BDT sheet`, `Power Alarm`, `Config`, `Summary `).
5. Summary-only/aggregate workbooks must be identified and excluded from individual BDT validation flow.

### FR-002: Coordinate Strategy by Family
1. Layout A and B2 use Layout A coordinate baseline.
2. Layout B1 uses Layout B coordinate baseline.
3. Layout C coordinates are non-canonical and must rely on fallback scanning for key fields.
4. Parser output must include detection metadata:
- `core_layout_family` (A/B1/B2/C/UNKNOWN)
- `detection_confidence` (high/medium/low)
- `detection_reasons` (short machine-readable reasons)

### FR-003: Dynamic Photo Validation Contract
1. Photo validation must not depend on fixed slot count (6/15/16) as primary rule.
2. Required pass criteria for R1 must be category-based:
- At least one `rectifier` photo.
- At least one `batteries` photo.
3. Optional categories (`modules`, `rack`, `load`, `charging`, etc.) may improve completeness score but must not hard-fail unless configured.
4. If category mapping confidence is low, result must be `N/A` or `Revise` with explicit reason, never silent pass/fail ambiguity.

### FR-004: O(N) Photo Mapping
1. Parse drawing anchors once.
2. Build label index once per sheet.
3. Map anchors to nearest semantic label region without repeated full-sheet scans.
4. Avoid per-image decode for validation decision path.
5. Complexity target per file: `O(A + L + I)` where `A` anchors, `L` scanned labels, `I` mapped images.

### FR-005: Persistence Safety
1. No outbox event may be emitted unless PM run persisted.
2. Duplicate PM run must not roll back whole batch.
3. Deferred photo persistence failures must be item-scoped and logged with identifiers.
4. Batch API must return structured failure details for post-run diagnostics.

### FR-006: Backward Compatibility
1. Existing valid Layout A behavior must remain stable.
2. Existing tested photo extraction paths must not regress.
3. Existing APIs consumed by UI threads/state modules must remain compatible or be updated atomically.

## 8. Technical Approach

### 8.1 Detection Pipeline
1. Workbook open and sheet inventory.
2. Family detection by sheet names/patterns.
3. Family baseline extraction.
4. Fallback keyword scans for missing fields.
5. Normalize outputs to canonical `BDTData`.

### 8.2 Photo Pipeline
1. Resolve BDT sheet drawing relations.
2. Extract anchor positions and image references.
3. Build semantic label map from localized text patterns (EN/AR).
4. Assign images to categories by proximity and band heuristics.
5. Produce:
- `photo_categories_found`
- `photo_mapping_confidence`
- `photo_detection_mode` (`normal` or `fallback`)

### 8.3 Validation Rule R1
1. Evaluate required categories from parser output.
2. If missing required category, fail with explicit detail.
3. If mapping uncertain, mark non-terminal status and reason.
4. Preserve strict mode toggle via config if needed later.

## 9. Data Contract Updates

### BDTData required fields
- `core_layout_family: str`
- `detection_confidence: str`
- `detection_reasons: list[str]`
- `photo_categories_found: set[str] | list[str]`
- `photo_mapping_confidence: str`
- `photo_detection_mode: str`
- `required_photo_categories: list[str]`

### Logging fields
- `file_path`
- `layout_family`
- `photo_detection_mode`
- `photo_mapping_confidence`
- `r1_verdict`
- `failure_reason_code`

## 10. Performance Requirements
1. No repeated workbook open/close inside same parse flow.
2. No image byte decode on R1 fast path.
3. DB writes remain batched.
4. Thread pool remains for parse/validate; DB commits remain controlled and safe.
5. Must provide before/after benchmark on representative sample.

## 11. Test Plan

### Unit Tests
1. Sheet family detection matrix.
2. Coordinate extraction by family.
3. Fallback extraction for Layout C missing fields.
4. Photo category mapping with synthetic anchor/label grids.
5. R1 decision table for category combinations and ambiguity states.

### Integration Tests
1. Real fixture files for A/B1/B2/C families.
2. Batch persistence duplicate handling.
3. Outbox emission only on persisted PM run.
4. Deferred photo persistence partial-failure isolation.

### Regression Tests
1. Existing parser and validator suites must pass.
2. Historical known edge cases (missing drawings, shifted anchors, malformed dates).

## 12. Acceptance Criteria
1. All tests pass in CI/local for touched modules.
2. Real-fixture validation confirms correct family detection and key field extraction.
3. R1 uses category-based pass criteria and no hardcoded 16-photo assumption.
4. No ghost outbox events.
5. Batch duplicate handling is item-scoped.
6. Performance report shows no regression.

## 13. Rollout Plan
1. Phase 1: Implement parser detection + metadata, keep old R1 behind compatibility switch.
2. Phase 2: Enable new category-based R1 by default after test pass.
3. Phase 3: Clean obsolete layout-count assumptions and dead code.
4. Phase 4: Monitor logs for ambiguity/fallback rates and tune patterns.

## 14. Risks and Mitigations
1. Risk: Label text drift.
- Mitigation: configurable pattern dictionary with tests.
2. Risk: Corrupt drawing relationships.
- Mitigation: explicit fallback mode and non-terminal verdict.
3. Risk: Hidden behavior dependencies in UI/state.
- Mitigation: end-to-end thread + persistence integration tests.
4. Risk: Overfitting to current corpus.
- Mitigation: keep UNKNOWN path explicit and observable.

## 15. AI Agent Execution Instructions
1. Use multiple subagents in parallel with disjoint ownership:
- Subagent A: parser detection/fallback/photo mapping.
- Subagent B: validator R1 redesign.
- Subagent C: history/thread/persistence safety.
- Subagent D: tests/fixtures/benchmark script.
2. Verify workbook assumptions with Excel MCP when uncertain.
3. Do not stop at plan; implement, run tests, and produce verification report.
4. Final deliverables must include:
- changed files
- test results
- benchmark summary
- residual risks list
- explicit note of any unresolved ambiguity paths.
