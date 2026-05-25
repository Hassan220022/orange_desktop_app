# MCP Federated Site Query and Admin SQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe all-sites full context and flexible expert SQL access for AI/MCP across Site Metadata, alarms, BDT Summary, and BDT validation data.

**Architecture:** Add a federated query layer that stitches approved app data sources by canonical Site ID with whitelisted fields/filters, then expose `get_all_sites_full_context` as a preset wrapper. Add an expert SQL layer backed by approved read-only views materialized from app/DuckDB sources into an isolated in-memory query engine; never expose raw physical tables or raw local file paths.

**Tech Stack:** Python, pandas, DuckDB in-memory registration, SQLAlchemy ORM read queries, existing MCP/OpenRouter tool registry, pytest, ruff, mypy, GitNexus.

---

## Current decisions captured in docs

- `CONTEXT.md` now defines **All-Sites Full Context Report**, **Federated Site Query**, and **Admin Read-Only SQL Query**.
- `docs/adr/0003-mcp-federated-site-query-and-admin-sql-views.md` records the architecture decision.
- Global MCP row cap is now a domain rule: **500 rows/request**.

## File map

- Modify `CONTEXT.md`: already updated with glossary decisions.
- Create/modify `docs/adr/0003-mcp-federated-site-query-and-admin-sql-views.md`: decision record.
- Create `llm_tools/federated_site.py`: field catalog, filter operators, federated row assembly, admin SQL view catalog, SQL validation/execution helpers.
- Modify `llm_tools/service.py`: use 500 global cap, add service methods for `describe_federated_site_data`, `query_federated_site_data`, `get_all_sites_full_context`, `describe_admin_sql_views`, `query_admin_readonly_sql`; add VIP/office metadata aliases to site rows.
- Modify `llm_tools/tools.py`: add MCP/OpenRouter schemas for new tools and update paging cap from 1000 to 500.
- Modify `tests/test_llm_tools.py`: regression tests for descriptors, safe query object, full context wrapper, SQL view joins, blocked SQL, row caps, and path redaction.
- Optional modify `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`: append a short follow-up section for Federated Site Query/Admin SQL if desired after code lands.

---

### Task 1: Enforce global MCP row cap of 500

**Files:**
- Modify: `llm_tools/service.py:85-92`
- Modify: `llm_tools/tools.py:33-35`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Run GitNexus impact before editing symbols**

Run:
```bash
/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream _mcp_limit
/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream dispatch_tool
```

Expected: record risk output before edits. If HIGH/CRITICAL, pause and report.

- [ ] **Step 2: Add failing cap tests**

Append to `tests/test_llm_tools.py`:

```python
def test_mcp_paging_schema_caps_at_500():
    from llm_tools.tools import TOOL_SCHEMAS

    paging = TOOL_SCHEMAS["query_network_summary"]["inputSchema"]["properties"]["limit"]
    assert paging["maximum"] == 500
    assert paging["xClampMaximum"] is True


def test_dispatch_clamps_broad_mcp_limits_to_500(monkeypatch):
    from llm_tools.service import LocalDataService
    from llm_tools.tools import dispatch_tool

    service = LocalDataService()
    seen = {}

    def _query_network_summary(**kwargs):
        seen.update(kwargs)
        return {"rows": [], "returned": 0, "limit": kwargs["limit"], "offset": 0, "has_more": False, "total": 0}

    monkeypatch.setattr(service, "query_network_summary", _query_network_summary)

    result = dispatch_tool(service, "query_network_summary", {"limit": 5000})

    assert seen["limit"] == 500
    assert result["limit"] == 500
```

- [ ] **Step 3: Run tests to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_mcp_paging_schema_caps_at_500 tests/test_llm_tools.py::test_dispatch_clamps_broad_mcp_limits_to_500 -q
```

Expected: first test fails because `_PAGING_PROPERTIES.maximum` is still 1000.

- [ ] **Step 4: Implement cap change**

Change in `llm_tools/service.py`:

```python
MCP_DEFAULT_PAGE_LIMIT = 500
MCP_MAX_PAGE_LIMIT = 500
```

Change in `llm_tools/tools.py`:

```python
_PAGING_PROPERTIES = {
    "limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
    "offset": {"type": "integer", "minimum": 0},
}
```

- [ ] **Step 5: Verify tests pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_mcp_paging_schema_caps_at_500 tests/test_llm_tools.py::test_dispatch_clamps_broad_mcp_limits_to_500 -q
```

Expected: both pass.

---

### Task 2: Add VIP/office metadata into site-level rows

**Files:**
- Modify: `llm_tools/service.py:92-99`, `llm_tools/service.py:2578-2595`, `llm_tools/service.py:2625-2628`, `llm_tools/service.py:2940-2942`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Run GitNexus impact before editing symbols**

Run:
```bash
/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream _metadata_site_rows_by_id
/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream list_sites
```

- [ ] **Step 2: Add failing test for VIP/office in `list_sites`**

Append to `tests/test_llm_tools.py`:

```python
def test_list_sites_includes_vip_and_office_from_metadata_aliases(monkeypatch):
    import json
    import pandas as pd

    from llm_tools.service import LocalDataService
    from llm_tools import service as service_module

    raw = {"vip": "VIP", "office": "Maadi", "site_name": "Alpha"}
    monkeypatch.setattr(
        service_module.catalog_store,
        "read_site_metadata",
        lambda: pd.DataFrame([
            {
                "site_id": "0900DE",
                "raw_data_json": json.dumps(raw),
                "site_name": "Alpha",
            }
        ]),
    )
    monkeypatch.setattr(LocalDataService, "_alarm_site_ids", lambda self: (set(), []))
    monkeypatch.setattr(LocalDataService, "_alarm_site_stats", lambda self: ({}, []))
    monkeypatch.setattr(LocalDataService, "_bdt_summary_site_ids", lambda self: (set(), []))
    monkeypatch.setattr(LocalDataService, "_bdt_summary_site_stats", lambda self: ({}, []))
    monkeypatch.setattr(LocalDataService, "_bdt_validation_site_ids", lambda self: (set(), []))
    monkeypatch.setattr(LocalDataService, "_bdt_validation_site_stats", lambda self: ({}, []))

    result = LocalDataService().list_sites(site_id="0900DE")

    row = result["rows"][0]
    assert row["vip"] == "VIP"
    assert row["office"] == "Maadi"
```

- [ ] **Step 3: Run test to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_list_sites_includes_vip_and_office_from_metadata_aliases -q
```

Expected: fails because `vip` and `office` are not copied into site rows.

- [ ] **Step 4: Implement metadata aliases**

Update `_FIELD_ALIASES` in `llm_tools/service.py`:

```python
_FIELD_ALIASES = {
    "site_name": ("site_name", "sitename", "name"),
    "area": ("area", "orange_area", "orangearea"),
    "office": ("office", "fm_office", "orange_office", "office_name"),
    "vip": ("vip", "is_vip", "vip_status"),
    "contractor": ("contractor",),
    "subcontractor": ("subcontractor", "sub_contractor", "subcontractor_name", "contractor"),
    "backup_status": ("backup_status", "backupstatus"),
    "battery_status": ("battery_status", "batterystatus"),
}
```

Add `office` and `vip` to the `needed_columns` set and to both field-copy loops:

```python
for field in ("site_name", "area", "office", "vip", "contractor", "subcontractor", "backup_status", "battery_status"):
    value = _metadata_value_for_field(row, raw_rows, field)
    if value is not None:
        existing[field] = value
```

```python
for field in ("site_name", "area", "office", "vip", "contractor", "subcontractor", "backup_status", "battery_status"):
    if field in metadata:
        row[field] = metadata.get(field)
```

- [ ] **Step 5: Verify test passes**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_list_sites_includes_vip_and_office_from_metadata_aliases -q
```

Expected: pass.

---

### Task 3: Add federated data descriptor and schema

**Files:**
- Create: `llm_tools/federated_site.py`
- Modify: `llm_tools/service.py`
- Modify: `llm_tools/tools.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing descriptor tests**

Append to `tests/test_llm_tools.py`:

```python
def test_describe_federated_site_data_lists_fields_sources_and_examples():
    from llm_tools.service import LocalDataService

    result = LocalDataService().describe_federated_site_data()

    assert result["join_key"] == "site_id"
    assert "site_metadata" in result["sources"]
    assert "alarms" in result["sources"]
    assert "bdt_summary" in result["sources"]
    assert "bdt_validation" in result["sources"]
    assert "vip" in result["fields"]
    assert "network_summary_rows" in result["nested_sections"]
    assert "contains" in result["operators"]
    assert result["row_cap"] == 500


def test_describe_federated_site_data_tool_schema_is_available():
    from llm_tools.tools import TOOL_SCHEMAS

    assert "describe_federated_site_data" in TOOL_SCHEMAS
    assert TOOL_SCHEMAS["describe_federated_site_data"]["inputSchema"]["additionalProperties"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_describe_federated_site_data_lists_fields_sources_and_examples tests/test_llm_tools.py::test_describe_federated_site_data_tool_schema_is_available -q
```

Expected: fail because tool/method does not exist.

- [ ] **Step 3: Create `llm_tools/federated_site.py` descriptor constants**

Create file:

```python
"""Federated site query descriptors and helpers for MCP tools."""

from __future__ import annotations

from typing import Any

ROW_CAP = 500

SITE_FIELDS = [
    "site_id",
    "site_code",
    "site_name",
    "area",
    "office",
    "vip",
    "contractor",
    "subcontractor",
    "backup_status",
    "battery_status",
    "has_metadata",
    "has_alarms",
    "alarm_count",
    "latest_alarm_at",
    "has_bdt_summary",
    "bdt_summary_count",
    "has_bdt_validation",
    "bdt_validation_count",
    "has_bdt",
    "latest_bdt_at",
]

SOURCES = {
    "site_metadata": "Network Summary / Site Metadata rows keyed by Site ID.",
    "alarms": "Stored alarm rows and alarm aggregates keyed by Site ID.",
    "bdt_summary": "BDT Summary Catalog rows keyed by Site ID.",
    "bdt_validation": "BDT validation runs, rule results, photo metadata, and review events keyed by Site ID.",
}

NESTED_SECTIONS = [
    "network_summary_rows",
    "alarm_rows",
    "bdt_summary_rows",
    "bdt_validation_runs",
    "bdt_rule_results",
    "photo_metadata",
    "review_events",
]

OPERATORS = ["eq", "neq", "contains", "not_contains", "in", "not_in", "is_blank", "is_not_blank", "gte", "lte"]


def describe_federated_site_data() -> dict[str, Any]:
    return {
        "join_key": "site_id",
        "row_cap": ROW_CAP,
        "sources": SOURCES,
        "fields": SITE_FIELDS,
        "nested_sections": NESTED_SECTIONS,
        "operators": OPERATORS,
        "section_match_modes": ["filter_nested_only", "require_matching_sites"],
        "examples": [
            {
                "question": "List VIP sites with backup status.",
                "select": ["site_id", "site_name", "vip", "office", "area", "subcontractor", "backup_status"],
                "site_filters": {"vip": {"not_in": ["_", "", None]}},
            },
            {
                "question": "Show VIP sites with Power alarms last week.",
                "select": ["site_id", "site_name", "vip", "alarm_count", "latest_alarm_at", "alarm_rows"],
                "site_filters": {"vip": {"not_in": ["_", "", None]}},
                "section_filters": {"alarms": {"category": "Power"}},
                "section_match_mode": "require_matching_sites",
            },
        ],
    }
```

- [ ] **Step 4: Add service method**

Add imports in `llm_tools/service.py` for both import branches:

```python
from alarm_app.llm_tools import federated_site
```

and fallback:

```python
from llm_tools import federated_site
```

Add method on `LocalDataService`:

```python
def describe_federated_site_data(self, **kwargs) -> dict[str, Any]:
    return federated_site.describe_federated_site_data()
```

- [ ] **Step 5: Add tool schema**

Add to `TOOL_SCHEMAS` in `llm_tools/tools.py`:

```python
"describe_federated_site_data": {
    "description": "Describe the curated fields, sources, filters, operators, and examples for federated site data queries.",
    "inputSchema": _schema({}),
    "outputSchema": _output_schema(_OBJECT_OUTPUT),
},
```

- [ ] **Step 6: Verify descriptor tests pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_describe_federated_site_data_lists_fields_sources_and_examples tests/test_llm_tools.py::test_describe_federated_site_data_tool_schema_is_available -q
```

Expected: pass.

---

### Task 4: Implement `query_federated_site_data`

**Files:**
- Modify: `llm_tools/federated_site.py`
- Modify: `llm_tools/service.py`
- Modify: `llm_tools/tools.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Run GitNexus impact before editing service symbols**

Run:
```bash
/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream list_sites
/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream get_site_full_context
```

- [ ] **Step 2: Add failing federated query tests**

Append to `tests/test_llm_tools.py`:

```python
def test_query_federated_site_data_selects_and_filters_site_fields(monkeypatch):
    from llm_tools.service import LocalDataService

    service = LocalDataService()
    monkeypatch.setattr(
        service,
        "list_sites",
        lambda **kwargs: {
            "rows": [
                {"site_id": "S1", "site_code": "S1", "site_name": "Alpha", "vip": "VIP", "office": "Cairo", "alarm_count": 3},
                {"site_id": "S2", "site_code": "S2", "site_name": "Beta", "vip": "_", "office": "Giza", "alarm_count": 0},
            ],
            "returned": 2,
            "limit": 500,
            "offset": 0,
            "has_more": False,
            "total": 2,
        },
    )

    result = service.query_federated_site_data(
        select=["site_id", "site_name", "vip", "office"],
        site_filters={"vip": {"not_in": ["_", "", None]}},
        limit=500,
    )

    assert result["rows"] == [{"site_id": "S1", "site_name": "Alpha", "vip": "VIP", "office": "Cairo"}]
    assert result["total"] == 1


def test_query_federated_site_data_rejects_unknown_fields():
    from llm_tools.service import LocalDataService

    result = LocalDataService().query_federated_site_data(select=["site_id", "password_hash"])

    assert "error" in result
    assert "unsupported field" in result["error"]
```

- [ ] **Step 3: Run tests to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_federated_site_data_selects_and_filters_site_fields tests/test_llm_tools.py::test_query_federated_site_data_rejects_unknown_fields -q
```

Expected: fail because method/tool does not exist.

- [ ] **Step 4: Add filter/select helpers in `llm_tools/federated_site.py`**

Append:

```python
def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _matches_filter(value: Any, spec: Any) -> bool:
    if not isinstance(spec, dict):
        return str(value or "").casefold() == str(spec or "").casefold()
    for op, expected in spec.items():
        text = "" if value is None else str(value)
        expected_values = expected if isinstance(expected, list) else [expected]
        expected_texts = ["" if item is None else str(item) for item in expected_values]
        if op == "eq" and text.casefold() != str(expected or "").casefold():
            return False
        if op == "neq" and text.casefold() == str(expected or "").casefold():
            return False
        if op == "contains" and str(expected or "").casefold() not in text.casefold():
            return False
        if op == "not_contains" and str(expected or "").casefold() in text.casefold():
            return False
        if op == "in" and text not in expected_texts:
            return False
        if op == "not_in" and text in expected_texts:
            return False
        if op == "is_blank" and not _is_blank(value):
            return False
        if op == "is_not_blank" and _is_blank(value):
            return False
        if op == "gte" and text < str(expected or ""):
            return False
        if op == "lte" and text > str(expected or ""):
            return False
        if op not in OPERATORS:
            return False
    return True


def apply_site_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not filters:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if all(_matches_filter(row.get(field), spec) for field, spec in filters.items()):
            filtered.append(row)
    return filtered


def project_site_fields(row: dict[str, Any], select: list[str] | None) -> dict[str, Any]:
    fields = select or SITE_FIELDS
    return {field: row.get(field) for field in fields if field in row}
```

- [ ] **Step 5: Add service method**

Add to `LocalDataService`:

```python
def query_federated_site_data(self, **kwargs) -> dict[str, Any]:
    select = kwargs.get("select") or federated_site.SITE_FIELDS
    if not isinstance(select, list):
        return {"error": "select must be an array of field names"}
    unsupported = [field for field in select if field not in federated_site.SITE_FIELDS and field not in federated_site.NESTED_SECTIONS]
    if unsupported:
        return {"error": f"unsupported field(s): {', '.join(map(str, unsupported))}"}

    limit = _mcp_limit(kwargs.get("limit"))
    offset = _mcp_offset(kwargs.get("offset"))
    site_payload = self.list_sites(limit=500, offset=0)
    rows = site_payload.get("rows", []) if isinstance(site_payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    rows = federated_site.apply_site_filters(rows, kwargs.get("site_filters") if isinstance(kwargs.get("site_filters"), dict) else {})

    total = len(rows)
    page = rows[offset:offset + limit] if limit > 0 else []
    projected = [federated_site.project_site_fields(row, select) for row in page]
    return {
        "rows": _sanitize_mcp_records(projected),
        "returned": len(projected),
        "limit": limit,
        "offset": offset,
        "has_more": limit > 0 and offset + len(projected) < total,
        "total": total,
    }
```

- [ ] **Step 6: Add tool schema**

Add to `TOOL_SCHEMAS`:

```python
"query_federated_site_data": {
    "description": "Query selected fields from federated site data with whitelisted filters, joined by Site ID.",
    "inputSchema": _schema({
        "select": _STRING_LIST,
        "sources": _STRING_LIST,
        "site_filters": _OBJECT_OUTPUT,
        "section_filters": _OBJECT_OUTPUT,
        "section_match_mode": {"type": "string", "enum": ["filter_nested_only", "require_matching_sites"]},
        "include_sections": _STRING_LIST,
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_PAGING_OUTPUT),
},
```

- [ ] **Step 7: Verify tests pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_federated_site_data_selects_and_filters_site_fields tests/test_llm_tools.py::test_query_federated_site_data_rejects_unknown_fields -q
```

Expected: pass.

---

### Task 5: Add `get_all_sites_full_context` preset wrapper

**Files:**
- Modify: `llm_tools/service.py`
- Modify: `llm_tools/tools.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing full-context tests**

Append to `tests/test_llm_tools.py`:

```python
def test_get_all_sites_full_context_batches_one_site_context_per_site(monkeypatch):
    from llm_tools.service import LocalDataService

    service = LocalDataService()
    monkeypatch.setattr(
        service,
        "query_federated_site_data",
        lambda **kwargs: {
            "rows": [{"site_id": "S1", "site_code": "S1", "site_name": "Alpha", "vip": "VIP"}],
            "returned": 1,
            "limit": kwargs.get("limit", 500),
            "offset": kwargs.get("offset", 0),
            "has_more": False,
            "total": 1,
        },
    )
    monkeypatch.setattr(
        service,
        "get_site_full_context",
        lambda **kwargs: {"site_id": kwargs["site_id"], "alarm_rows": {"rows": [{"alarm_name": "Power"}], "returned": 1}},
    )

    result = service.get_all_sites_full_context(site_filters={"vip": {"not_in": ["_", "", None]}}, limit=10, alarm_limit=5)

    assert result["rows"][0]["site_id"] == "S1"
    assert result["rows"][0]["context"]["alarm_rows"]["returned"] == 1
    assert result["returned"] == 1
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_get_all_sites_full_context_batches_one_site_context_per_site -q
```

Expected: fail because method/tool does not exist.

- [ ] **Step 3: Implement service wrapper**

Add to `LocalDataService`:

```python
def get_all_sites_full_context(self, **kwargs) -> dict[str, Any]:
    limit = _mcp_limit(kwargs.get("limit"), default=50)
    offset = _mcp_offset(kwargs.get("offset"))
    base_payload = self.query_federated_site_data(
        select=[
            "site_id", "site_code", "site_name", "area", "office", "vip", "contractor", "subcontractor",
            "backup_status", "battery_status", "has_metadata", "has_alarms", "alarm_count", "latest_alarm_at",
            "has_bdt_summary", "bdt_summary_count", "has_bdt_validation", "bdt_validation_count", "has_bdt", "latest_bdt_at",
        ],
        site_filters=kwargs.get("site_filters") if isinstance(kwargs.get("site_filters"), dict) else {},
        limit=limit,
        offset=offset,
    )
    rows = base_payload.get("rows", []) if isinstance(base_payload, dict) else []
    result_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        site_id = str(row.get("site_id") or row.get("site_code") or "").strip()
        context = self.get_site_full_context(
            site_id=site_id,
            site_code=site_id,
            metadata_limit=min(_mcp_limit(kwargs.get("metadata_limit"), default=3), 500),
            alarm_limit=min(_mcp_limit(kwargs.get("alarm_limit"), default=5), 500),
            bdt_limit=min(_mcp_limit(kwargs.get("bdt_limit"), default=5), 500),
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            category=kwargs.get("category"),
            vendor=kwargs.get("vendor"),
            network_type=kwargs.get("network_type"),
            reporting_period=kwargs.get("reporting_period") or kwargs.get("period"),
            week=kwargs.get("week"),
            overall=kwargs.get("overall"),
            rule_id=kwargs.get("rule_id"),
            rule_verdict=kwargs.get("rule_verdict"),
        )
        result_rows.append({**row, "context": _jsonable(context)})
    return {
        "rows": _sanitize_mcp_records(result_rows),
        "returned": len(result_rows),
        "limit": limit,
        "offset": offset,
        "has_more": bool(base_payload.get("has_more")) if isinstance(base_payload, dict) else False,
        "total": int(base_payload.get("total", len(result_rows))) if isinstance(base_payload, dict) else len(result_rows),
    }
```

- [ ] **Step 4: Add tool schema**

Add to `TOOL_SCHEMAS`:

```python
"get_all_sites_full_context": {
    "description": "Return a page of sites with operational base fields and limited nested per-site context sections.",
    "inputSchema": _schema({
        "site_filters": _OBJECT_OUTPUT,
        "section_filters": _OBJECT_OUTPUT,
        "section_match_mode": {"type": "string", "enum": ["filter_nested_only", "require_matching_sites"]},
        "metadata_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
        "alarm_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
        "bdt_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
        "date_from": {"type": "string"},
        "date_to": {"type": "string"},
        "category": {"type": "string"},
        "vendor": {"type": "string"},
        "network_type": {"type": "string"},
        "reporting_period": {"type": "string"},
        "period": {"type": "string"},
        "week": {"type": "string"},
        "overall": {"type": "string"},
        "rule_id": {"type": "string"},
        "rule_verdict": {"type": "string"},
        **_PAGING_PROPERTIES,
    }),
    "outputSchema": _output_schema(_PAGING_OUTPUT),
},
```

- [ ] **Step 5: Verify test passes**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_get_all_sites_full_context_batches_one_site_context_per_site -q
```

Expected: pass.

---

### Task 6: Add approved admin SQL view descriptor

**Files:**
- Modify: `llm_tools/federated_site.py`
- Modify: `llm_tools/service.py`
- Modify: `llm_tools/tools.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing descriptor test**

Append to `tests/test_llm_tools.py`:

```python
def test_describe_admin_sql_views_lists_approved_views_only():
    from llm_tools.service import LocalDataService

    result = LocalDataService().describe_admin_sql_views()

    assert result["row_cap"] == 500
    assert "site_metadata_view" in result["views"]
    assert "alarm_events_view" in result["views"]
    assert "bdt_validation_runs_view" in result["views"]
    assert "uploaded_files" not in result["views"]
    assert "SELECT" in result["allowed_sql"]
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_describe_admin_sql_views_lists_approved_views_only -q
```

Expected: fail because method does not exist.

- [ ] **Step 3: Add view catalog in `llm_tools/federated_site.py`**

Append:

```python
ADMIN_SQL_VIEWS = {
    "site_metadata_view": ["site_id", "site_code", "site_name", "area", "office", "vip", "contractor", "subcontractor", "backup_status", "battery_status"],
    "site_index_view": SITE_FIELDS,
    "alarm_events_view": ["site_id", "alarm_name", "alarm_id", "occurred_on", "cleared_on", "duration", "duration_secs", "category", "vendor", "network_type", "severity", "alarm_category", "clearance_status", "site_down"],
    "alarm_summary_view": ["site_id", "alarm_count", "latest_alarm_at"],
    "bdt_summary_view": ["site_id", "reporting_period", "week", "test_date", "overall_verdict", "site_name"],
    "bdt_validation_runs_view": ["site_id", "validation_run_id", "bdt_test_id", "test_date", "overall_verdict", "run_at"],
    "bdt_rule_results_view": ["site_id", "validation_run_id", "rule_id", "rule_name", "verdict", "test_date", "created_at"],
    "photo_metadata_view": ["site_id", "bdt_test_id", "slot_index", "slot_category", "sha256", "mime_type", "file_size", "width", "height", "created_at"],
    "review_events_view": ["site_id", "event_type", "test_date", "reviewer", "filename", "verdict", "reviewed_at", "created_at"],
}


def describe_admin_sql_views() -> dict[str, Any]:
    return {
        "row_cap": ROW_CAP,
        "join_key": "site_id",
        "views": ADMIN_SQL_VIEWS,
        "allowed_sql": ["SELECT", "WITH", "JOIN", "WHERE", "GROUP BY", "ORDER BY", "CASE", "subqueries", "COUNT", "SUM", "MIN", "MAX", "AVG"],
        "blocked_sql": ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "ATTACH", "DETACH", "PRAGMA", "COPY", "INSTALL", "LOAD", "read_csv", "read_parquet"],
        "examples": [
            "SELECT s.site_id, s.site_name, s.vip, s.office FROM site_metadata_view s WHERE s.vip NOT IN ('_', '') LIMIT 500",
            "SELECT s.site_id, s.vip, a.alarm_count FROM site_metadata_view s LEFT JOIN alarm_summary_view a ON a.site_id = s.site_id WHERE s.vip NOT IN ('_', '') LIMIT 500",
        ],
    }
```

- [ ] **Step 4: Add service method and tool schema**

Add to `LocalDataService`:

```python
def describe_admin_sql_views(self, **kwargs) -> dict[str, Any]:
    return federated_site.describe_admin_sql_views()
```

Add to `TOOL_SCHEMAS`:

```python
"describe_admin_sql_views": {
    "description": "Describe approved read-only SQL views available to trusted admin SQL queries.",
    "inputSchema": _schema({}),
    "outputSchema": _output_schema(_OBJECT_OUTPUT),
},
```

- [ ] **Step 5: Verify descriptor test passes**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_describe_admin_sql_views_lists_approved_views_only -q
```

Expected: pass.

---

### Task 7: Implement approved-view admin SQL execution

**Files:**
- Modify: `llm_tools/federated_site.py`
- Modify: `llm_tools/service.py`
- Modify: `llm_tools/tools.py`
- Test: `tests/test_llm_tools.py`

- [ ] **Step 1: Add failing SQL tests**

Append to `tests/test_llm_tools.py`:

```python
def test_query_admin_readonly_sql_can_join_approved_views(monkeypatch):
    from llm_tools.service import LocalDataService

    service = LocalDataService()
    monkeypatch.setattr(
        service,
        "_admin_sql_view_frames",
        lambda: {
            "site_metadata_view": __import__("pandas").DataFrame([
                {"site_id": "S1", "site_name": "Alpha", "vip": "VIP"},
                {"site_id": "S2", "site_name": "Beta", "vip": "_"},
            ]),
            "alarm_summary_view": __import__("pandas").DataFrame([
                {"site_id": "S1", "alarm_count": 4},
            ]),
        },
    )

    result = service.query_admin_readonly_sql(
        sql="""
        SELECT s.site_id, s.site_name, s.vip, a.alarm_count
        FROM site_metadata_view s
        LEFT JOIN alarm_summary_view a ON a.site_id = s.site_id
        WHERE s.vip NOT IN ('_', '')
        ORDER BY s.site_id
        """
    )

    assert result["rows"] == [{"site_id": "S1", "site_name": "Alpha", "vip": "VIP", "alarm_count": 4}]
    assert result["returned"] == 1


def test_query_admin_readonly_sql_blocks_mutation_and_raw_tables(monkeypatch):
    from llm_tools.service import LocalDataService

    service = LocalDataService()
    monkeypatch.setattr(service, "_admin_sql_view_frames", lambda: {})

    assert "error" in service.query_admin_readonly_sql(sql="DELETE FROM site_metadata_view")
    assert "error" in service.query_admin_readonly_sql(sql="PRAGMA table_info(site_metadata_view)")
    assert "error" in service.query_admin_readonly_sql(sql="SELECT * FROM uploaded_files")
```

- [ ] **Step 2: Run tests to verify failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_admin_readonly_sql_can_join_approved_views tests/test_llm_tools.py::test_query_admin_readonly_sql_blocks_mutation_and_raw_tables -q
```

Expected: fail because method does not exist.

- [ ] **Step 3: Add SQL validator/executor helpers in `llm_tools/federated_site.py`**

Append:

```python
import re
import pandas as pd

BLOCKED_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|ATTACH|DETACH|PRAGMA|COPY|INSTALL|LOAD|CALL|SET|VACUUM|EXPORT|IMPORT)\b|read_csv|read_parquet|sqlite_master|information_schema|duckdb_",
    re.IGNORECASE,
)


def validate_admin_sql(sql: str) -> str | None:
    text = str(sql or "").strip()
    if not text:
        return "sql is required"
    stripped = text.rstrip(";").strip()
    if ";" in stripped:
        return "multiple SQL statements are not allowed"
    if not re.match(r"^(SELECT|WITH)\b", stripped, flags=re.IGNORECASE):
        return "only SELECT/WITH read-only queries are allowed"
    if BLOCKED_SQL_PATTERN.search(stripped):
        return "query contains blocked SQL syntax or internal schema access"
    lower = stripped.casefold()
    approved = {name.casefold() for name in ADMIN_SQL_VIEWS}
    candidate_identifiers = set(re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped, flags=re.IGNORECASE))
    unknown = [name for name in candidate_identifiers if name.casefold() not in approved]
    if unknown:
        return f"query references unsupported view(s): {', '.join(sorted(unknown))}"
    return None


def run_admin_sql(sql: str, frames: dict[str, pd.DataFrame], *, offset: int = 0, limit: int = ROW_CAP) -> dict[str, Any]:
    error = validate_admin_sql(sql)
    if error:
        return {"rows": [], "returned": 0, "limit": min(limit, ROW_CAP), "offset": offset, "has_more": False, "total": 0, "error": error}
    import duckdb

    capped_limit = max(0, min(int(limit), ROW_CAP))
    capped_offset = max(0, int(offset))
    con = duckdb.connect(database=":memory:")
    try:
        for name in ADMIN_SQL_VIEWS:
            frame = frames.get(name)
            if frame is None:
                frame = pd.DataFrame(columns=ADMIN_SQL_VIEWS[name])
            con.register(name, frame)
        wrapped = f"SELECT * FROM ({str(sql).rstrip(';')}) AS admin_query LIMIT {capped_limit + 1} OFFSET {capped_offset}"
        result = con.execute(wrapped).fetchdf()
    finally:
        con.close()
    has_more = len(result) > capped_limit
    if has_more:
        result = result.iloc[:capped_limit]
    rows = result.to_dict(orient="records")
    return {"rows": rows, "returned": len(rows), "limit": capped_limit, "offset": capped_offset, "has_more": has_more, "total": capped_offset + len(rows) + (1 if has_more else 0)}
```

- [ ] **Step 4: Add view frame builder and SQL method in `LocalDataService`**

Add to `LocalDataService`:

```python
def _admin_sql_view_frames(self) -> dict[str, pd.DataFrame]:
    site_index = self.list_sites(limit=500, offset=0).get("rows", [])
    network = self.query_network_summary(limit=500, offset=0).get("rows", [])
    alarms = self.query_alarm_events(limit=500, offset=0).get("rows", [])
    bdt = self.query_bdt_full(limit=500, offset=0)
    bdt_summary = bdt.get("bdt_summary", {}).get("rows", []) if isinstance(bdt, dict) else []
    bdt_runs = bdt.get("validation_runs", {}).get("rows", []) if isinstance(bdt, dict) else []
    bdt_rules = bdt.get("rule_results", {}).get("rows", []) if isinstance(bdt, dict) else []
    photos = bdt.get("photos", {}).get("rows", []) if isinstance(bdt, dict) else []
    reviews = bdt.get("review_events", {}).get("rows", []) if isinstance(bdt, dict) else []
    return {
        "site_index_view": pd.DataFrame(site_index),
        "site_metadata_view": pd.DataFrame(network),
        "alarm_events_view": pd.DataFrame(alarms),
        "alarm_summary_view": pd.DataFrame([
            {"site_id": row.get("site_id"), "alarm_count": row.get("alarm_count"), "latest_alarm_at": row.get("latest_alarm_at")}
            for row in site_index if isinstance(row, dict)
        ]),
        "bdt_summary_view": pd.DataFrame(bdt_summary),
        "bdt_validation_runs_view": pd.DataFrame(bdt_runs),
        "bdt_rule_results_view": pd.DataFrame(bdt_rules),
        "photo_metadata_view": pd.DataFrame(photos),
        "review_events_view": pd.DataFrame(reviews),
    }


def query_admin_readonly_sql(self, **kwargs) -> dict[str, Any]:
    sql = str(kwargs.get("sql") or "")
    limit = _mcp_limit(kwargs.get("limit"))
    offset = _mcp_offset(kwargs.get("offset"))
    payload = federated_site.run_admin_sql(sql, self._admin_sql_view_frames(), limit=limit, offset=offset)
    if isinstance(payload.get("rows"), list):
        payload["rows"] = _sanitize_mcp_records(payload["rows"])
    if payload.get("error") is not None:
        payload["error"] = _sanitize_mcp_value(payload["error"])
    return _jsonable(payload)
```

Note for implementer: this minimal view-frame builder uses existing capped service methods first. If follow-up tests require SQL filtering over more than the first 500 source rows, add internal uncapped-but-bounded view loaders per source while still preserving 500 returned rows.

- [ ] **Step 5: Add tool schema**

Add to `TOOL_SCHEMAS`:

```python
"query_admin_readonly_sql": {
    "description": "Run trusted read-only SQL against approved MCP views only. Results are capped at 500 rows and sanitized.",
    "inputSchema": _schema({
        "sql": {"type": "string", "description": "SELECT/WITH query against approved views from describe_admin_sql_views."},
        **_PAGING_PROPERTIES,
    }, required=["sql"]),
    "outputSchema": _output_schema(_PAGING_OUTPUT),
},
```

- [ ] **Step 6: Verify SQL tests pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py::test_query_admin_readonly_sql_can_join_approved_views tests/test_llm_tools.py::test_query_admin_readonly_sql_blocks_mutation_and_raw_tables -q
```

Expected: pass.

---

### Task 8: Verify MCP/OpenRouter safety and full regression suite

**Files:**
- Modify as needed from prior tasks.

- [ ] **Step 1: Run targeted MCP tests**

Run:
```bash
.venv/bin/python -m pytest tests/test_llm_tools.py -q
```

Expected: all `tests/test_llm_tools.py` tests pass.

- [ ] **Step 2: Run full suite and static checks**

Run:
```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy --ignore-missing-imports --explicit-package-bases --follow-imports=silent core/ data/ db/ web/ bdt/
git diff --check
```

Expected:
- pytest passes
- ruff: `All checks passed!`
- mypy: `Success: no issues found`
- `git diff --check` returns no output

- [ ] **Step 3: Run GitNexus change detection before commit**

Run:
```bash
/opt/homebrew/bin/gitnexus detect-changes -r orange_desktop_app --scope all
```

Expected: affected symbols align with MCP/federated query/admin SQL work. If risk is HIGH/CRITICAL, report before commit.

---

## Self-review checklist

- Spec coverage: covers global 500 cap, curated descriptor, federated query object, all-sites full context preset, approved-view admin SQL, cross-view joins, blocked mutation/raw table access, path redaction through existing sanitizers.
- Placeholder scan: each task includes concrete test/implementation snippets and avoids deferred-work placeholders.
- Type consistency: tool names are `describe_federated_site_data`, `query_federated_site_data`, `get_all_sites_full_context`, `describe_admin_sql_views`, and `query_admin_readonly_sql` throughout.
