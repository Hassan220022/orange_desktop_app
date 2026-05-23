# Read-only MCP Site Data Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every structured site-related record and existing computed app report reachable through read-only MCP tools with pagination, path redaction, and no UI-state coupling.

**Architecture:** Keep MCP dispatch centralized in `llm_tools/tools.py` and guarded data access in `llm_tools/service.py`. Add direct tools for core entities and one computed-report dispatcher for app-derived outputs, reusing existing app functions rather than duplicating report logic.

**Tech Stack:** Python, pandas, DuckDB-backed `data.alarm_store`/`data.catalog_store`, SQLAlchemy app DB models, existing MCP JSON-RPC server, pytest, ruff, mypy.

---

## Decisions locked by grilling

- MCP is read-only for app data.
- “Everything” means every structured site-related row and field is reachable through paginated calls.
- Default page size is 500; hard cap is 1000 rows per call.
- Paginated responses always include `returned`, `limit`, `offset`, and `has_more`; include `total` when cheap.
- `site_id` and `site_code` are equal aliases for the same normalized Site ID.
- “All sites” is the union of Site Metadata, alarms, BDT Summary Catalog, and BDT validation DB identities.
- MCP excludes desktop UI state/settings and raw local filesystem paths.
- Broad/context/report tools return photo metadata, not image bytes.
- Site-related engineer/reviewer/comment fields are in scope.
- Site-related review events are in scope with path redaction.
- Raw JSON payload strings are hidden by default and exposed only with `include_raw_json=true`.
- Date/period-sensitive computed tools return a missing-period error instead of guessing.
- Source-file-dependent reports use verified app-known uploads or MCP upload allowlists only.

## File map

- Modify `llm_tools/service.py`
  - Add pagination/path-redaction/raw-JSON helpers.
  - Add core entity tools: `list_sites`, `query_network_summary`, `query_alarm_events`, `query_bdt_full`, `get_site_full_context`, `get_sites_context_report`, `get_computed_report`.
  - Keep all data access behind `LocalDataService`.
- Modify `llm_tools/tools.py`
  - Add MCP/OpenRouter schemas for new tools.
  - Mark all new tools read-only.
  - Raise new tool limit maximums to 1000.
- Modify `data/catalog_store.py` only if service-level filtering becomes too slow or awkward.
  - Prefer service-level filtering first to keep change small.
- Modify `tests/test_llm_tools.py`
  - Unit tests for schemas, helpers, redaction, pagination, core tools, and computed report dispatcher.
- Modify `tests/test_e2e_backend.py`
  - HTTP MCP `tools/list` includes new read-only tools.
- Keep docs current:
  - `CONTEXT.md`
  - `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`

---

### Task 1: Pagination, redaction, and raw JSON helpers

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing pagination helper tests**

Add tests near `test_limit_clamps_to_safe_maximum`:

```python
def test_mcp_page_limit_defaults_to_500_and_caps_at_1000():
    assert service_mod._mcp_limit(None) == 500
    assert service_mod._mcp_limit("bad") == 500
    assert service_mod._mcp_limit(25) == 25
    assert service_mod._mcp_limit(5000) == 1000


def test_page_records_reports_has_more_without_total():
    rows = [{"id": i} for i in range(5)]

    result = service_mod._page_records(rows, limit=2, offset=2)

    assert result == {
        "rows": [{"id": 2}, {"id": 3}],
        "returned": 2,
        "limit": 2,
        "offset": 2,
        "has_more": True,
    }


def test_page_records_includes_total_when_supplied():
    result = service_mod._page_records([{"id": 1}], limit=500, offset=0, total=9)

    assert result["total"] == 9
    assert result["has_more"] is True
```

- [ ] **Step 2: Add failing path-redaction/raw-json tests**

Add:

```python
def test_sanitize_mcp_record_removes_local_paths_and_expands_json():
    record = {
        "site_id": "0A63DE",
        "local_path": "/Users/me/.alarm_viewer/blobs/photo.png",
        "original_path": "C:\\Users\\me\\source.xlsx",
        "original_name": "source.xlsx",
        "raw_data_json": json.dumps({"Area": "Cairo", "Comment": "Needs visit"}),
    }

    sanitized = service_mod._sanitize_mcp_record(record)

    assert "local_path" not in sanitized
    assert "original_path" not in sanitized
    assert sanitized["original_name"] == "source.xlsx"
    assert sanitized["Area"] == "Cairo"
    assert sanitized["Comment"] == "Needs visit"
    assert "raw_data_json" not in sanitized


def test_sanitize_mcp_record_keeps_raw_json_when_requested():
    record = {"payload_json": json.dumps({"verdict": "Accepted"})}

    sanitized = service_mod._sanitize_mcp_record(record, include_raw_json=True)

    assert sanitized["verdict"] == "Accepted"
    assert sanitized["payload_json"] == json.dumps({"verdict": "Accepted"})
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_mcp_page_limit_defaults_to_500_and_caps_at_1000 tests/test_llm_tools.py::test_page_records_reports_has_more_without_total tests/test_llm_tools.py::test_page_records_includes_total_when_supplied tests/test_llm_tools.py::test_sanitize_mcp_record_removes_local_paths_and_expands_json tests/test_llm_tools.py::test_sanitize_mcp_record_keeps_raw_json_when_requested -q
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 4: Implement helpers in `llm_tools/service.py`**

Add near `_limit`:

```python
MCP_DEFAULT_PAGE_LIMIT = 500
MCP_MAX_PAGE_LIMIT = 1000
_RAW_JSON_FIELDS = {"raw_data_json", "original_headers_json", "evidence_json", "payload_json"}
_PATH_FIELD_NAMES = {"path", "local_path", "original_path", "source_path", "file_path"}


def _mcp_limit(value: Any, default: int = MCP_DEFAULT_PAGE_LIMIT) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MCP_MAX_PAGE_LIMIT))


def _mcp_offset(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return max(parsed, 0)


def _expand_json_payload_fields(record: dict[str, Any], *, include_raw_json: bool = False) -> dict[str, Any]:
    expanded = dict(record)
    for field in list(_RAW_JSON_FIELDS):
        raw = expanded.get(field)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                parsed = None
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    expanded.setdefault(str(key), value)
        if field in expanded and not include_raw_json:
            expanded.pop(field, None)
    return expanded


def _sanitize_mcp_record(record: dict[str, Any], *, include_raw_json: bool = False) -> dict[str, Any]:
    expanded = _expand_json_payload_fields(record, include_raw_json=include_raw_json)
    sanitized: dict[str, Any] = {}
    for key, value in expanded.items():
        key_text = str(key)
        if key_text.lower() in _PATH_FIELD_NAMES:
            continue
        sanitized[key_text] = _jsonable(value)
    return sanitized


def _sanitize_mcp_records(records: list[dict[str, Any]], *, include_raw_json: bool = False) -> list[dict[str, Any]]:
    return [_sanitize_mcp_record(row, include_raw_json=include_raw_json) for row in records]


def _page_records(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    total: int | None = None,
) -> dict[str, Any]:
    page = rows[offset:offset + limit] if limit else rows[offset:]
    payload: dict[str, Any] = {
        "rows": page,
        "returned": len(page),
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(page)) < (total if total is not None else len(rows)),
    }
    if total is not None:
        payload["total"] = total
    return payload
```

- [ ] **Step 5: Run helper tests to verify pass**

Run the same pytest command from Step 3.

Expected: PASS.

- [ ] **Step 6: Run lint for helper changes**

Run:

```bash
.venv/bin/python -m ruff check llm_tools/service.py tests/test_llm_tools.py
```

Expected: `All checks passed!`

---

### Task 2: Add read-only tool schemas

**Files:**
- Modify: `llm_tools/tools.py`
- Test: `tests/test_llm_tools.py`, `tests/test_e2e_backend.py`

- [ ] **Step 1: Add failing schema tests**

Add near `test_tool_definitions_are_available_for_mcp_and_openrouter`:

```python
def test_read_only_mcp_parity_tools_are_registered():
    tools = {tool["name"]: tool for tool in tool_definitions_for_mcp()}
    expected = {
        "list_sites",
        "query_network_summary",
        "query_alarm_events",
        "query_bdt_full",
        "get_site_full_context",
        "get_sites_context_report",
        "get_computed_report",
    }

    assert expected.issubset(tools)
    for name in expected:
        assert tools[name]["annotations"] == {"readOnlyHint": True}


def test_new_broad_tools_allow_limit_up_to_1000():
    tools = {tool["name"]: tool for tool in tool_definitions_for_mcp()}

    for name in ("list_sites", "query_network_summary", "query_alarm_events", "query_bdt_full"):
        assert tools[name]["inputSchema"]["properties"]["limit"]["maximum"] == 1000
```

Update `tests/test_e2e_backend.py::test_mcp_tools_list_includes_chatgpt_safety_annotations` to assert:

```python
assert tools["list_sites"]["annotations"] == {"readOnlyHint": True}
assert tools["get_computed_report"]["annotations"] == {"readOnlyHint": True}
```

- [ ] **Step 2: Run schema tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_read_only_mcp_parity_tools_are_registered tests/test_llm_tools.py::test_new_broad_tools_allow_limit_up_to_1000 tests/test_e2e_backend.py::TestMcpConnectorE2E::test_mcp_tools_list_includes_chatgpt_safety_annotations -q
```

Expected: FAIL because schemas are missing.

- [ ] **Step 3: Add shared schema fragments in `llm_tools/tools.py`**

Add near existing constants:

```python
_PAGING_PROPERTIES = {
    "limit": {"type": "integer", "minimum": 0, "maximum": 1000},
    "offset": {"type": "integer", "minimum": 0},
}
_PAGING_OUTPUT = {
    "rows": _OBJECT_ROWS,
    "returned": {"type": "integer"},
    "limit": {"type": "integer"},
    "offset": {"type": "integer"},
    "has_more": {"type": "boolean"},
    "total": {"type": "integer"},
    "error": {"type": "string"},
}
_SITE_ALIAS_PROPERTIES = {
    "site_id": {"type": "string", "description": "Normalized or raw site id."},
    "site_code": {"type": "string", "description": "Alias for site_id."},
    "site_text": {"type": "string", "description": "Site id/text filter."},
}
```

- [ ] **Step 4: Add tool schema entries**

Add these keys to `TOOL_SCHEMAS`:

```python
"list_sites": {
    "description": "List all known sites across Site Metadata, alarms, BDT Summary, and BDT validation data with source flags and counts.",
    "inputSchema": _schema({
        **_SITE_ALIAS_PROPERTIES,
        "area": {"type": "string"},
        "subcontractor": {"type": "string"},
        "contractor": {"type": "string"},
        "backup_status": {"type": "string"},
        "battery_status": {"type": "string"},
        "has_alarms": {"type": "boolean"},
        "has_bdt": {"type": "boolean"},
        "has_bdt_summary": {"type": "boolean"},
        "has_bdt_validation": {"type": "boolean"},
        "has_metadata": {"type": "boolean"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_PAGING_OUTPUT),
},
"query_network_summary": {
    "description": "Read full imported Network Summary/Site Metadata rows with normalized and original workbook-header fields.",
    "inputSchema": _schema({
        **_SITE_ALIAS_PROPERTIES,
        "area": {"type": "string"},
        "subcontractor": {"type": "string"},
        "contractor": {"type": "string"},
        "backup_status": {"type": "string"},
        "battery_status": {"type": "string"},
        "include_raw_json": {"type": "boolean"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_PAGING_OUTPUT),
},
"query_alarm_events": {
    "description": "Read all stored alarm event fields with filters, sorting, and pagination.",
    "inputSchema": _schema({
        **_SITE_ALIAS_PROPERTIES,
        "category": {"type": "string"},
        "vendor": {"type": "string"},
        "network_type": {"type": "string"},
        "date_from": {"type": "string"},
        "date_to": {"type": "string"},
        "sort_by": {"type": "string"},
        "sort_desc": {"type": "boolean"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_PAGING_OUTPUT),
},
"query_bdt_full": {
    "description": "Read BDT Summary catalog rows, validation runs, rule results, photo metadata, and review events for site/date filters.",
    "inputSchema": _schema({
        **_SITE_ALIAS_PROPERTIES,
        "reporting_period": {"type": "string"},
        "period": {"type": "string"},
        "week": {"type": "string"},
        "date_from": {"type": "string"},
        "date_to": {"type": "string"},
        "overall": {"type": "string"},
        "rule_id": {"type": "string"},
        "rule_verdict": {"type": "string"},
        "include_raw_json": {"type": "boolean"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema({
        "summary": _OBJECT_OUTPUT,
        "validation_runs": _OBJECT_OUTPUT,
        "rule_results": _OBJECT_OUTPUT,
        "photo_metadata": _OBJECT_OUTPUT,
        "review_events": _OBJECT_OUTPUT,
        "error": {"type": "string"},
    }),
},
"get_site_full_context": {
    "description": "Return full read-only context for one site: metadata, alarms, BDT data, photo metadata, review events, and counts.",
    "inputSchema": _schema({
        "site_id": {"type": "string"},
        "site_code": {"type": "string"},
        "date_from": {"type": "string"},
        "date_to": {"type": "string"},
        "include_raw_json": {"type": "boolean"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_OBJECT_OUTPUT),
},
"get_sites_context_report": {
    "description": "Return workbook-like report sections for one/all sites. Without sheet, returns manifest; with sheet, returns paginated rows.",
    "inputSchema": _schema({
        **_SITE_ALIAS_PROPERTIES,
        "sheet": {"type": "string"},
        "date_from": {"type": "string"},
        "date_to": {"type": "string"},
        "include_raw_json": {"type": "boolean"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_OBJECT_OUTPUT),
},
"get_computed_report": {
    "description": "Run existing app read-only computed report logic and return structured paginated sections.",
    "inputSchema": _schema({
        "report_type": {
            "type": "string",
            "enum": [
                "backup_times",
                "ht_meet_rows",
                "ht_weekly_summary",
                "ht_consolidated_history",
                "bdt_export_sections",
                "accepted_pm_report",
                "alarm_category_counts",
                "alarm_daily_counts",
                "alarm_duration_by_category",
                "bdt_verdict_counts",
                "bdt_duration_trend",
            ],
        },
        **_SITE_ALIAS_PROPERTIES,
        "export_week": {"type": "string"},
        "start_week": {"type": "string"},
        "date_from": {"type": "string"},
        "date_to": {"type": "string"},
        "source_file_id": {"type": "string"},
        "health_pct": {"type": "number"},
        "sheet": {"type": "string"},
        **_PAGING_PROPERTIES,
    }, required=["report_type"]),
    "outputSchema": _output_schema(_OBJECT_OUTPUT),
},
```

- [ ] **Step 5: Run schema tests to verify pass**

Run the pytest command from Step 2.

Expected: PASS.

---

### Task 3: Network Summary and all-site inventory tools

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing `query_network_summary` test**

Add:

```python
def test_query_network_summary_returns_normalized_and_original_fields(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service_mod.catalog_store, "read_site_metadata", lambda: pd.DataFrame([
        {
            "site_id": "0A63DE",
            "site_name": "SUNBAT2",
            "area": "Cairo",
            "raw_data_json": json.dumps({"Code": "0A63DE", "Original Area": "Cairo", "Engineer": "Ali"}),
        }
    ]))

    result = service.query_network_summary(site_id="0A63DE")

    assert result["returned"] == 1
    assert result["rows"][0]["site_id"] == "0A63DE"
    assert result["rows"][0]["site_name"] == "SUNBAT2"
    assert result["rows"][0]["Code"] == "0A63DE"
    assert result["rows"][0]["Engineer"] == "Ali"
    assert "raw_data_json" not in result["rows"][0]
```

- [ ] **Step 2: Add failing `list_sites` union test**

Add:

```python
def test_list_sites_returns_union_with_source_flags(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service_mod.catalog_store, "read_site_metadata", lambda: pd.DataFrame([
        {"site_id": "META1", "site_name": "Meta Site", "area": "A"},
    ]))
    monkeypatch.setattr(service_mod.catalog_store, "read_bdt_summary", lambda: pd.DataFrame([
        {"site_id": "BDT1", "reporting_period": "2026"},
    ]))
    monkeypatch.setattr(service_mod.alarm_store, "distinct_values", lambda column, q=None: ["ALARM1"] if column == "site_id" else [])
    monkeypatch.setattr(service_mod.db_engine, "get_session", lambda: SimpleNamespace(close=lambda: None, query=lambda *args: _SiteQuery(["VALID1"])))

    result = service.list_sites(limit=10)

    by_site = {row["site_id"]: row for row in result["rows"]}
    assert {"META1", "BDT1", "ALARM1", "VALID1"}.issubset(by_site)
    assert by_site["META1"]["has_metadata"] is True
    assert by_site["ALARM1"]["has_alarms"] is True
    assert by_site["BDT1"]["has_bdt_summary"] is True
    assert by_site["VALID1"]["has_bdt_validation"] is True
```

Add small test helper near other fake query classes:

```python
class _SiteQuery:
    def __init__(self, site_codes):
        self.site_codes = site_codes

    def join(self, *args, **kwargs):
        return self

    def all(self):
        return [(code,) for code in self.site_codes]
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_network_summary_returns_normalized_and_original_fields tests/test_llm_tools.py::test_list_sites_returns_union_with_source_flags -q
```

Expected: FAIL because methods do not exist.

- [ ] **Step 4: Implement `query_network_summary`**

Add to `LocalDataService`:

```python
    def query_network_summary(self, **kwargs) -> dict[str, Any]:
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        include_raw_json = bool(kwargs.get("include_raw_json", False))
        df = catalog_store.read_site_metadata()
        if df.empty:
            return _page_records([], limit=limit, offset=offset, total=0)

        filtered = df.copy()
        site_text = str(kwargs.get("site_text") or kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        if site_text:
            needle = site_text.upper()
            normalized = catalog_store._normalize_site_id(site_text)
            mask = filtered.get("site_id", pd.Series("", index=filtered.index)).fillna("").astype(str).str.upper().str.contains(normalized, regex=False, na=False)
            if "site_name" in filtered.columns:
                mask |= filtered["site_name"].fillna("").astype(str).str.upper().str.contains(needle, regex=False, na=False)
            filtered = filtered[mask]
        for columns, value in (
            (("area", "orange_area"), kwargs.get("area")),
            (("subcontractor", "contractor"), kwargs.get("subcontractor") or kwargs.get("contractor")),
            (("backup_status", "battery_status"), kwargs.get("backup_status") or kwargs.get("battery_status")),
        ):
            if value:
                mask = pd.Series(False, index=filtered.index)
                for column in columns:
                    if column in filtered.columns:
                        mask |= filtered[column].fillna("").astype(str).str.contains(str(value), case=False, regex=False, na=False)
                filtered = filtered[mask]

        records = _sanitize_mcp_records(_df_records(filtered), include_raw_json=include_raw_json)
        return _page_records(records, limit=limit, offset=offset, total=len(records))
```

- [ ] **Step 5: Implement `list_sites` with union source flags**

Add to `LocalDataService`:

```python
    def list_sites(self, **kwargs) -> dict[str, Any]:
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        sites: dict[str, dict[str, Any]] = {}

        metadata = self.query_network_summary(limit=1000, offset=0, include_raw_json=kwargs.get("include_raw_json", False))
        for row in metadata.get("rows", []):
            site_id = catalog_store._normalize_site_id(row.get("site_id") or row.get("site_code") or "")
            if not site_id:
                continue
            sites.setdefault(site_id, {"site_id": site_id})
            sites[site_id].update(row)
            sites[site_id]["has_metadata"] = True

        try:
            alarm_ids = self._with_alarm_source(lambda: alarm_store.distinct_values("site_id")) or []
        except Exception:
            alarm_ids = []
        for raw_site in alarm_ids:
            site_id = catalog_store._normalize_site_id(raw_site)
            if site_id:
                sites.setdefault(site_id, {"site_id": site_id})["has_alarms"] = True

        bdt_summary = catalog_store.read_bdt_summary()
        if not bdt_summary.empty and "site_id" in bdt_summary.columns:
            for raw_site in bdt_summary["site_id"].dropna().unique().tolist():
                site_id = catalog_store._normalize_site_id(raw_site)
                if site_id:
                    sites.setdefault(site_id, {"site_id": site_id})["has_bdt_summary"] = True

        session = db_engine.get_session()
        try:
            for (raw_site,) in session.query(BDTTest.site_code).distinct().all():
                site_id = catalog_store._normalize_site_id(raw_site)
                if site_id:
                    sites.setdefault(site_id, {"site_id": site_id})["has_bdt_validation"] = True
        finally:
            session.close()

        rows = []
        for site_id, row in sites.items():
            row.setdefault("site_code", site_id)
            row.setdefault("has_metadata", False)
            row.setdefault("has_alarms", False)
            row.setdefault("has_bdt_summary", False)
            row.setdefault("has_bdt_validation", False)
            row["has_bdt"] = bool(row["has_bdt_summary"] or row["has_bdt_validation"])
            rows.append(_sanitize_mcp_record(row, include_raw_json=bool(kwargs.get("include_raw_json", False))))

        for flag in ("has_alarms", "has_bdt", "has_bdt_summary", "has_bdt_validation", "has_metadata"):
            if flag in kwargs and kwargs[flag] is not None:
                rows = [row for row in rows if bool(row.get(flag)) is bool(kwargs[flag])]
        rows = sorted(rows, key=lambda row: str(row.get("site_id") or ""))
        return _page_records(rows, limit=limit, offset=offset, total=len(rows))
```

- [ ] **Step 6: Run tests to verify pass**

Run the pytest command from Step 3.

Expected: PASS.

---

### Task 4: Alarm event query tool

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing `query_alarm_events` test**

Add:

```python
def test_query_alarm_events_returns_all_stored_fields_and_pagination(monkeypatch):
    service = LocalDataService()
    captured = {}

    def fake_query(q):
        captured["query"] = q
        return pd.DataFrame([
            {"site_id": "0A63DE", "alarm_name": "Power", "occurred_on": pd.Timestamp("2026-05-01"), "extra_stored": "kept"},
            {"site_id": "0A63DE", "alarm_name": "Temp", "occurred_on": pd.Timestamp("2026-05-02"), "extra_stored": "kept2"},
        ])

    monkeypatch.setattr(service_mod.alarm_store, "query_alarms", fake_query)
    monkeypatch.setattr(service_mod.alarm_store, "count_alarms", lambda q: 2)

    result = service.query_alarm_events(site_id="0A63DE", limit=1, offset=1)

    assert result["returned"] == 1
    assert result["total"] == 2
    assert result["has_more"] is False
    assert result["rows"][0]["extra_stored"] == "kept2"
    assert captured["query"].site_text == "0A63DE"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_alarm_events_returns_all_stored_fields_and_pagination -q
```

Expected: FAIL because method is missing.

- [ ] **Step 3: Implement `query_alarm_events`**

Add to `LocalDataService`:

```python
    def query_alarm_events(self, **kwargs) -> dict[str, Any]:
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_code") or kwargs.get("site_id") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
            sort_by=str(kwargs.get("sort_by") or "occurred_on"),
            sort_desc=bool(kwargs.get("sort_desc", False)),
            limit=limit,
            offset=offset,
        )
        df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
        try:
            total = int(self._with_alarm_source(lambda: alarm_store.count_alarms(q)) or len(df))
        except Exception:
            total = None
        rows = _sanitize_mcp_records(_df_records(df))
        return {
            "rows": rows,
            "returned": len(rows),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(rows)) < total if total is not None else len(rows) == limit,
            **({"total": total} if total is not None else {}),
        }
```

- [ ] **Step 4: Run test to verify pass**

Run the pytest command from Step 2.

Expected: PASS.

---

### Task 5: BDT full query and review events

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing BDT full test**

Add:

```python
def test_query_bdt_full_returns_sections_and_redacts_paths(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service_mod.catalog_store, "query_bdt_summary", lambda **kwargs: pd.DataFrame([
        {"site_id": "0A63DE", "reporting_period": "2026", "raw_data_json": json.dumps({"Engineer": "Mona"})}
    ]))
    monkeypatch.setattr(service, "query_bdt_results", lambda **kwargs: {"rows": [{"validation_run_id": 7, "site_code": "0A63DE"}], "total": 1})
    monkeypatch.setattr(service, "get_photo_metadata", lambda **kwargs: {"rows": [{"sha256": "abc", "local_path": "/Users/me/blob.png"}], "row_count": 1})
    monkeypatch.setattr(service, "_query_rule_results", lambda **kwargs: [{"rule_code": "R1", "verdict": "Accepted"}])
    monkeypatch.setattr(service, "_query_review_events", lambda **kwargs: [{"site_code": "0A63DE", "reviewer": "Nora", "filename": "report.xlsx", "payload_json": json.dumps({"path": "/tmp/report.xlsx", "note": "ok"})}])

    result = service.query_bdt_full(site_id="0A63DE", limit=10)

    assert result["summary"]["rows"][0]["Engineer"] == "Mona"
    assert result["validation_runs"]["rows"][0]["validation_run_id"] == 7
    assert "local_path" not in result["photo_metadata"]["rows"][0]
    assert result["rule_results"]["rows"][0]["rule_code"] == "R1"
    assert result["review_events"]["rows"][0]["reviewer"] == "Nora"
    assert "path" not in result["review_events"]["rows"][0]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_bdt_full_returns_sections_and_redacts_paths -q
```

Expected: FAIL because method/helpers are missing.

- [ ] **Step 3: Implement BDT helper methods**

Add to `LocalDataService`:

```python
    def _query_rule_results(self, **kwargs) -> list[dict[str, Any]]:
        site_code = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip().upper()
        session = db_engine.get_session()
        try:
            query = (
                session.query(PMRuleResult, PMRuleCatalog, PMValidationRun, BDTTest)
                .join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                .join(PMValidationRun, PMRuleResult.validation_run_id == PMValidationRun.id)
                .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
            )
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            rows = []
            for result, catalog, run, bdt in query.all():
                rows.append({
                    "validation_run_id": run.id,
                    "bdt_test_id": bdt.id,
                    "site_id": bdt.site_code,
                    "site_code": bdt.site_code,
                    "test_date": bdt.test_date,
                    "rule_code": catalog.rule_code,
                    "rule_name": catalog.name,
                    "verdict": result.verdict,
                    "evidence_json": result.evidence_json,
                })
            return rows
        finally:
            session.close()

    def _query_review_events(self, **kwargs) -> list[dict[str, Any]]:
        site_code = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip().upper()
        session = db_engine.get_session()
        try:
            query = session.query(ReviewEvent)
            if site_code:
                query = query.filter(ReviewEvent.site_code == site_code)
            return [
                {
                    "site_id": event.site_code,
                    "site_code": event.site_code,
                    "test_date": event.test_date,
                    "event_type": event.event_type,
                    "reviewer": event.reviewer,
                    "filename": Path(str(event.filename or "")).name if event.filename else None,
                    "verdict": event.verdict,
                    "payload_json": event.payload_json,
                    "reviewed_at": event.reviewed_at,
                }
                for event in query.all()
            ]
        finally:
            session.close()
```

Update imports in `llm_tools/service.py` to include `ReviewEvent` in both import branches.

- [ ] **Step 4: Implement `query_bdt_full`**

Add:

```python
    def query_bdt_full(self, **kwargs) -> dict[str, Any]:
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        include_raw_json = bool(kwargs.get("include_raw_json", False))
        site_id = str(kwargs.get("site_id") or kwargs.get("site_code") or "").strip() or None
        summary_df = catalog_store.query_bdt_summary(
            site_id=site_id,
            reporting_period=str(kwargs.get("reporting_period") or kwargs.get("period") or "").strip() or None,
            week=str(kwargs.get("week") or "").strip() or None,
            test_date_from=str(kwargs.get("date_from") or "").strip() or None,
            test_date_to=str(kwargs.get("date_to") or "").strip() or None,
        )
        summary_rows = _sanitize_mcp_records(_df_records(summary_df), include_raw_json=include_raw_json)
        runs_payload = self.query_bdt_results(
            site_code=site_id or "",
            overall=kwargs.get("overall") or "",
            rule_id=kwargs.get("rule_id") or "",
            rule_verdict=kwargs.get("rule_verdict") or "",
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            limit=limit,
            offset=offset,
        )
        rule_rows = _sanitize_mcp_records(self._query_rule_results(**kwargs), include_raw_json=include_raw_json)
        photo_payload = self.get_photo_metadata(site_code=site_id or "", limit=limit)
        photo_rows = _sanitize_mcp_records(photo_payload.get("rows", []), include_raw_json=include_raw_json)
        review_rows = _sanitize_mcp_records(self._query_review_events(**kwargs), include_raw_json=include_raw_json)
        return {
            "summary": _page_records(summary_rows, limit=limit, offset=offset, total=len(summary_rows)),
            "validation_runs": _page_records(_sanitize_mcp_records(runs_payload.get("rows", [])), limit=limit, offset=0, total=int(runs_payload.get("total") or len(runs_payload.get("rows", [])))),
            "rule_results": _page_records(rule_rows, limit=limit, offset=offset, total=len(rule_rows)),
            "photo_metadata": _page_records(photo_rows, limit=limit, offset=offset, total=len(photo_rows)),
            "review_events": _page_records(review_rows, limit=limit, offset=offset, total=len(review_rows)),
        }
```

- [ ] **Step 5: Run BDT full test to verify pass**

Run the pytest command from Step 2.

Expected: PASS.

---

### Task 6: Full site context tool

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing test**

Add:

```python
def test_get_site_full_context_composes_sections(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service, "query_network_summary", lambda **kwargs: {"rows": [{"site_id": "0A63DE"}], "returned": 1})
    monkeypatch.setattr(service, "alarm_stats", lambda **kwargs: {"total": 3})
    monkeypatch.setattr(service, "query_alarm_events", lambda **kwargs: {"rows": [{"alarm_name": "Power"}], "returned": 1})
    monkeypatch.setattr(service, "query_bdt_full", lambda **kwargs: {"summary": {"rows": [{"site_id": "0A63DE"}]}, "validation_runs": {"rows": []}, "rule_results": {"rows": []}, "photo_metadata": {"rows": []}, "review_events": {"rows": []}})

    result = service.get_site_full_context(site_id="0A63DE")

    assert result["site_id"] == "0A63DE"
    assert result["metadata"]["rows"][0]["site_id"] == "0A63DE"
    assert result["alarm_stats"]["total"] == 3
    assert result["alarms"]["rows"][0]["alarm_name"] == "Power"
    assert "summary" in result["bdt"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_get_site_full_context_composes_sections -q
```

Expected: FAIL because method is missing.

- [ ] **Step 3: Implement `get_site_full_context`**

Add:

```python
    def get_site_full_context(self, **kwargs) -> dict[str, Any]:
        site_id = catalog_store._normalize_site_id(kwargs.get("site_id") or kwargs.get("site_code") or "")
        if not site_id:
            return {"error": "site_id or site_code is required"}
        date_from = kwargs.get("date_from")
        date_to = kwargs.get("date_to")
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        return {
            "site_id": site_id,
            "site_code": site_id,
            "metadata": self.query_network_summary(site_id=site_id, include_raw_json=kwargs.get("include_raw_json", False), limit=limit, offset=offset),
            "alarm_stats": self.alarm_stats(site_text=site_id, date_from=date_from, date_to=date_to),
            "alarms": self.query_alarm_events(site_id=site_id, date_from=date_from, date_to=date_to, limit=limit, offset=offset),
            "bdt": self.query_bdt_full(site_id=site_id, date_from=date_from, date_to=date_to, include_raw_json=kwargs.get("include_raw_json", False), limit=limit, offset=offset),
        }
```

- [ ] **Step 4: Run test to verify pass**

Run the pytest command from Step 2.

Expected: PASS.

---

### Task 7: Workbook-like context report tool

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing manifest/page tests**

Add:

```python
def test_get_sites_context_report_returns_manifest(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service, "list_sites", lambda **kwargs: {"rows": [{"site_id": "S1"}], "total": 1, "returned": 1})
    monkeypatch.setattr(service, "query_network_summary", lambda **kwargs: {"rows": [{"site_id": "S1"}], "total": 1, "returned": 1})
    monkeypatch.setattr(service, "query_alarm_events", lambda **kwargs: {"rows": [], "total": 0, "returned": 0})
    monkeypatch.setattr(service, "query_bdt_full", lambda **kwargs: {"summary": {"rows": [], "total": 0}, "validation_runs": {"rows": [], "total": 0}, "rule_results": {"rows": [], "total": 0}, "photo_metadata": {"rows": [], "total": 0}, "review_events": {"rows": [], "total": 0}})

    result = service.get_sites_context_report()

    assert result["sheets"]["Sites"]["total"] == 1
    assert result["sheets"]["Network Summary"]["total"] == 1


def test_get_sites_context_report_returns_sheet_page(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service, "list_sites", lambda **kwargs: {"rows": [{"site_id": "S1"}], "total": 1, "returned": 1, "limit": 500, "offset": 0, "has_more": False})

    result = service.get_sites_context_report(sheet="Sites")

    assert result["sheet"] == "Sites"
    assert result["rows"] == [{"site_id": "S1"}]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_get_sites_context_report_returns_manifest tests/test_llm_tools.py::test_get_sites_context_report_returns_sheet_page -q
```

Expected: FAIL because method is missing.

- [ ] **Step 3: Implement report section builder**

Add:

```python
    def _site_context_report_sections(self, **kwargs) -> dict[str, dict[str, Any]]:
        bdt = self.query_bdt_full(**kwargs)
        return {
            "Sites": self.list_sites(**kwargs),
            "Network Summary": self.query_network_summary(**kwargs),
            "Alarms": self.query_alarm_events(**kwargs),
            "BDT Summary": bdt.get("summary", {}),
            "BDT Runs": bdt.get("validation_runs", {}),
            "BDT Rules": bdt.get("rule_results", {}),
            "Photo Metadata": bdt.get("photo_metadata", {}),
            "Review Events": bdt.get("review_events", {}),
        }

    def get_sites_context_report(self, **kwargs) -> dict[str, Any]:
        requested_sheet = str(kwargs.get("sheet") or "").strip()
        sections = self._site_context_report_sections(**kwargs)
        if not requested_sheet:
            return {
                "sheets": {
                    name: {
                        "returned": int(section.get("returned") or len(section.get("rows", []))),
                        "total": section.get("total"),
                        "has_more": bool(section.get("has_more", False)),
                    }
                    for name, section in sections.items()
                }
            }
        if requested_sheet not in sections:
            return {"error": f"unknown sheet: {requested_sheet}", "sheets": list(sections)}
        return {"sheet": requested_sheet, **sections[requested_sheet]}
```

- [ ] **Step 4: Run report tests to verify pass**

Run the pytest command from Step 2.

Expected: PASS.

---

### Task 8: Computed report dispatcher

**Files:**
- Modify: `llm_tools/service.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing missing-period test**

Add:

```python
def test_get_computed_report_requires_export_week_for_ht_reports():
    result = LocalDataService().get_computed_report(report_type="ht_meet_rows")

    assert result == {"error": "export_week is required; ask the user which HT Workbook Week Label to use"}
```

- [ ] **Step 2: Add failing backup/chart dispatcher tests**

Add:

```python
def test_get_computed_report_dispatches_backup_times(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service, "query_backup_times", lambda **kwargs: {"rows": [{"site_id": "S1"}], "returned": 1})

    result = service.get_computed_report(report_type="backup_times", date_from="2026-05-01", date_to="2026-05-02")

    assert result["rows"][0]["site_id"] == "S1"


def test_get_computed_report_dispatches_chart_data(monkeypatch):
    service = LocalDataService()
    monkeypatch.setattr(service, "generate_graph", lambda **kwargs: {"graph_type": kwargs["graph_type"], "labels": ["Power"], "values": [3]})

    result = service.get_computed_report(report_type="alarm_category_counts")

    assert result == {"graph_type": "alarm_category_counts", "labels": ["Power"], "values": [3]}
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_get_computed_report_requires_export_week_for_ht_reports tests/test_llm_tools.py::test_get_computed_report_dispatches_backup_times tests/test_llm_tools.py::test_get_computed_report_dispatches_chart_data -q
```

Expected: FAIL because method is missing.

- [ ] **Step 4: Implement dispatcher shell**

Add imports in `llm_tools/service.py` for HT functions in both import branches:

```python
from alarm_app.core.temp_alarm import compute_ht_meet_rows, build_temp_alarm_summary
```

Fallback branch:

```python
from core.temp_alarm import compute_ht_meet_rows, build_temp_alarm_summary
```

Add method:

```python
    def get_computed_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "").strip()
        if report_type == "backup_times":
            return self.query_backup_times(**kwargs)
        if report_type in {"alarm_category_counts", "alarm_daily_counts", "alarm_duration_by_category", "bdt_verdict_counts", "bdt_duration_trend"}:
            return self.generate_graph(graph_type=report_type, **{k: v for k, v in kwargs.items() if k != "report_type"})
        if report_type in {"ht_meet_rows", "ht_weekly_summary", "ht_consolidated_history"}:
            export_week = str(kwargs.get("export_week") or "").strip()
            if not export_week:
                return {"error": "export_week is required; ask the user which HT Workbook Week Label to use"}
            return self._computed_ht_report(report_type=report_type, export_week=export_week, **kwargs)
        if report_type == "bdt_export_sections":
            results = self._load_validation_results()
            sheets = build_bdt_export_sheets(results, health_pct=float(kwargs.get("health_pct") or 80.0))
            return self._computed_dataframe_sections(sheets, sheet=str(kwargs.get("sheet") or ""), limit=_mcp_limit(kwargs.get("limit")), offset=_mcp_offset(kwargs.get("offset")))
        if report_type == "accepted_pm_report":
            source_file_id = str(kwargs.get("source_file_id") or "").strip()
            if not source_file_id:
                return {"error": "source_file_id is required; ask the user which accepted PM upload to use"}
            return self._computed_accepted_pm_rows(**kwargs)
        return {"error": f"unsupported report_type: {report_type}"}
```

- [ ] **Step 5: Implement minimal dataframe section helper**

Add:

```python
    def _computed_dataframe_sections(self, sheets: dict[str, pd.DataFrame], *, sheet: str, limit: int, offset: int) -> dict[str, Any]:
        if not sheet:
            return {"sheets": {name: {"total": len(df)} for name, df in sheets.items()}}
        if sheet not in sheets:
            return {"error": f"unknown sheet: {sheet}", "sheets": list(sheets)}
        rows = _sanitize_mcp_records(_df_records(sheets[sheet]))
        return {"sheet": sheet, **_page_records(rows, limit=limit, offset=offset, total=len(rows))}
```

- [ ] **Step 6: Implement HT computed report adapter**

Add:

```python
    def _computed_ht_report(self, *, report_type: str, export_week: str, **kwargs) -> dict[str, Any]:
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        source_df = self._with_alarm_source(lambda: alarm_store.query_alarms(alarm_store.AlarmQuery(limit=None, offset=0)))
        meet, missing = compute_ht_meet_rows(source_df, week_label=export_week)
        if report_type == "ht_meet_rows":
            rows = _sanitize_mcp_records(_df_records(meet))
            return _page_records(rows, limit=limit, offset=offset, total=len(rows))
        summary = build_temp_alarm_summary(meet, export_week)
        rows = _sanitize_mcp_records(_df_records(summary))
        return _page_records(rows, limit=limit, offset=offset, total=len(rows))
```

If `build_temp_alarm_summary` signature differs, inspect `core/temp_alarm.py` and adapt the call to its actual parameters before running tests.

- [ ] **Step 7: Implement accepted PM rows adapter using verified uploads**

Add:

```python
    def _computed_accepted_pm_rows(self, **kwargs) -> dict[str, Any]:
        fmt = "xlsx"
        name = "accepted_pm_mcp"
        exported = self._export_accepted_pm_report(fmt=fmt, name=name, **kwargs)
        if "error" in exported:
            return exported
        return {
            "report_type": "accepted_pm_report",
            "source_file_id": exported.get("source_file_id"),
            "rows": exported.get("rows", 0),
            "sheet_name": exported.get("sheet_name"),
            "site_column": exported.get("site_column"),
            "date_column": exported.get("date_column"),
            "status_column": exported.get("status_column"),
        }
```

This adapter uses existing verified source-file handling and does not expose the generated local path.

- [ ] **Step 8: Run dispatcher tests to verify pass**

Run the pytest command from Step 3.

Expected: PASS.

---

### Task 9: Full verification and cleanup

**Files:**
- Modify if needed: `llm_tools/service.py`, `llm_tools/tools.py`, `tests/test_llm_tools.py`, `tests/test_e2e_backend.py`, `CONTEXT.md`, spec file.

- [ ] **Step 1: Run focused MCP tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_tools.py tests/test_e2e_backend.py::TestMcpConnectorE2E -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run style/type checks**

Run:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy --ignore-missing-imports --explicit-package-bases --follow-imports=silent core/ data/ db/ web/ bdt/
```

Expected: ruff all checks pass; mypy no issues.

- [ ] **Step 3: Run full suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: full suite passes or known skips only.

- [ ] **Step 4: Run GitNexus change detection**

Run:

```bash
/opt/homebrew/bin/gitnexus detect-changes -r orange_desktop_app --scope all
```

Expected: affected flows are limited to MCP/local data service/tool schema/test/docs paths.

- [ ] **Step 5: Inspect git state**

Run:

```bash
git status -sb
git diff --stat
```

Expected: only intended files changed. Existing unrelated untracked `.superpowers/`, temp session, and old docs files remain uncommitted unless the user explicitly asks to include them.

- [ ] **Step 6: Commit only if user explicitly requests commit**

If the user requests a commit, run:

```bash
git add CONTEXT.md docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md llm_tools/service.py llm_tools/tools.py tests/test_llm_tools.py tests/test_e2e_backend.py
git commit -m "feat(mcp): expose read-only site data parity"
```

Do not push unless the user explicitly requests push.

---

## Self-review

- Spec coverage: covers read-only scope, pagination, all-site union, path redaction, UI-state exclusion, Network/BDT original fields, review events, computed report reuse, missing period errors, and source-file restrictions.
- Placeholder scan: no unfinished-work placeholders are present in this plan.
- Type consistency: new public `LocalDataService` method names match tool schema names.
- Scope check: this is broad but cohesive around one MCP parity surface; tasks are split into independently testable vertical slices.
