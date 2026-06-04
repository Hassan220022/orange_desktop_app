"""Tool registry shared by MCP and OpenRouter entrypoints."""

from __future__ import annotations

import math
from typing import Any

from .charts import chart_type_description, chart_type_ids
from .service import CHART_DATA_MAX_POINTS, CHART_WIDGET_URI, LocalDataService


def _schema(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _output_schema(properties: dict[str, Any] | None = None, *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": True,
    }


_OBJECT_OUTPUT = {"type": "object", "additionalProperties": True}
_OBJECT_ROWS = {"type": "array", "items": _OBJECT_OUTPUT}
_STRING_LIST = {"type": "array", "items": {"type": "string"}}
_NUMBER_LIST = {"type": "array", "items": {"type": "number"}}
_PAGING_PROPERTIES = {
    "limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
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


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_data_sources": {
        "description": "List local Alarm Viewer storage sources, table row counts, DuckDB alarm stores, blob storage, and export path.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema({
            "sqlite": _OBJECT_OUTPUT,
            "duckdb": _OBJECT_ROWS,
            "blob_storage": _OBJECT_OUTPUT,
            "exports": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "get_current_time": {
        "description": "Return the current local machine time and timezone for date-aware answers.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema({
            "local_time": {"type": "string"},
            "utc_time": {"type": "string"},
            "timezone": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "query_alarms": {
        "description": "Read alarm rows from the local DuckDB alarm store using safe filters and pagination.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "sort_by": {"type": "string"},
            "sort_desc": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_alarm_events": {
        "description": "Read all stored alarm rows from the local DuckDB alarm store with safe filters, sorting, and pagination.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Fuzzy site id/name filter."},
            "site_code": {"type": "string", "description": "Alias for normalized Site ID."},
            "site_id": {"type": "string", "description": "Alias for normalized Site ID."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "sort_by": {"type": "string", "description": "Sortable column name."},
            "sort_direction": {"type": "string", "enum": ["asc", "desc"], "description": "Sort direction."},
            "sort_desc": {"type": "boolean", "description": "Deprecated explicit sort direction flag (overridden by sort_direction when provided)."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "query_backup_times": {
        "description": "Compute backup-time site results from local alarms and return sites whose hold-up exceeds a threshold.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "min_minutes": {"type": "number", "minimum": 0},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "total_count": {"type": "integer"},
            "site_count": {"type": "integer"},
            "site_ids": _STRING_LIST,
            "min_minutes": {"type": "number"},
            "threshold_minutes": {"type": "number"},
            "error": {"type": "string"},
        }),
    },
    "alarm_stats": {
        "description": "Return aggregate alarm statistics for safe filters without loading all rows.",
        "inputSchema": _schema({
            "site_text": {"type": "string"},
            "category": {"type": "string"},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
        }),
        "outputSchema": _output_schema({
            "total": {"type": "integer"},
            "power": {"type": "integer"},
            "down": {"type": "integer"},
            "door": {"type": "integer"},
            "temp": {"type": "integer"},
            "sites": {"type": "integer"},
            "avg_duration_secs": {"type": "number"},
            "error": {"type": "string"},
        }),
    },
    "query_bdt_results": {
        "description": "Read BDT validation run summaries from the local app DB.",
        "inputSchema": _schema({
            "site_code": {"type": "string"},
            "overall": {"type": "string", "description": "Overall BDT verdict."},
            "rule_id": {"type": "string", "description": "Rule code such as R3 or R10."},
            "rule_verdict": {"type": "string", "description": "Rule verdict such as Accepted, Rejected, Revise, No data."},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "total": {"type": "integer"},
            "rows": _OBJECT_ROWS,
            "error": {"type": "string"},
        }),
    },
    "get_bdt_detail": {
        "description": "Read one BDT validation detail with rules, discharge readings, and photo metadata.",
        "inputSchema": _schema({
            "validation_run_id": {"type": "integer"},
            "site_code": {"type": "string"},
            "test_date": {"type": "string"},
        }),
        "outputSchema": _output_schema({
            "validation_run_id": {"type": "integer"},
            "overall_verdict": {"type": "string"},
            "run_at": {},
            "bdt": _OBJECT_OUTPUT,
            "rules": _OBJECT_ROWS,
            "photos": _OBJECT_ROWS,
            "error": {"type": "string"},
        }),
    },
    "get_photo_metadata": {
        "description": "Read BDT photo metadata from the local app DB without returning image bytes.",
        "inputSchema": _schema({
            "site_code": {"type": "string"},
            "bdt_test_id": {"type": "integer"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "get_site_dossier": {
        "description": (
            "Build a complete site dossier from local DuckDB alarms and BDT DB data. "
            "Returns alarm previews, BDT summaries/details, and exports a full XLSX with alarms, BDT rules, photos, and discharge content."
        ),
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Required normalized or raw site code."},
            "site_text": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "alarm_preview_limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "bdt_preview_limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "bdt_detail_limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "site_code": {"type": "string"},
            "alarm_total": {"type": "integer"},
            "alarm_stats": _OBJECT_OUTPUT,
            "alarm_rows": _OBJECT_ROWS,
            "bdt_total": {"type": "integer"},
            "bdt_rows": _OBJECT_ROWS,
            "bdt_details": _OBJECT_ROWS,
            "export_path": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "describe_federated_site_data": {
        "description": "Describe the curated fields, sources, filters, operators, and examples for federated site data queries.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema(),
    },
    "describe_admin_sql_views": {
        "description": "Describe approved read-only SQL views available to trusted admin SQL queries.",
        "inputSchema": _schema({}),
        "outputSchema": _output_schema(),
    },
    "query_admin_readonly_sql": {
        "description": "Run trusted read-only SQL against approved MCP views only. Results are capped at 500 rows and sanitized.",
        "inputSchema": _schema({
            "sql": {"type": "string", "description": "SELECT/WITH query against approved views from describe_admin_sql_views."},
            **_PAGING_PROPERTIES,
        }, required=["sql"]),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
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
    "list_chart_types": {
        "description": "List supported chart types. For ChatGPT charts, call list_chart_types, then get_chart_data, then render_chart_widget.",
        "inputSchema": _schema({
            "family": {"type": "string", "description": "Optional chart family filter, such as alarm, backup, bdt, pm, or metadata."},
            "chart_kind": {"type": "string", "description": "Optional chart kind filter, such as bar, donut, line, heatmap, or scatter."},
            "renderable_only": {"type": "boolean", "description": "When true, return only charts that can be rendered as images."},
        }),
        "outputSchema": _output_schema({
            "charts": _OBJECT_ROWS,
            "count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "get_chart_data": {
        "description": (
            "Return validated structured chart data without creating an image. "
            "Preferred ChatGPT chart flow: list_chart_types -> get_chart_data -> render_chart_widget."
        ),
        "inputSchema": _schema({
            "chart_id": {
                "type": "string",
                "enum": chart_type_ids(renderable_only=True),
                "description": "Chart id from list_chart_types.",
            },
            "filters": {
                "type": "object",
                "description": "Optional safe chart filters such as site_code, site_text, date_from, date_to, category, vendor, network_type, and min_minutes.",
                "additionalProperties": True,
            },
            "max_points": {"type": "integer", "minimum": 0, "maximum": CHART_DATA_MAX_POINTS, "xClampMaximum": True},
            "group_by": {"type": "string", "description": "Reserved grouping hint when supported by a chart."},
            "sort_by": {"type": "string", "description": "Reserved sort hint when supported by a chart."},
            "sort_direction": {"type": "string", "enum": ["asc", "desc"], "description": "Reserved sort direction hint."},
        }, required=["chart_id"]),
        "outputSchema": _output_schema({
            "chart_id": {"type": "string"},
            "chart_kind": {"type": "string"},
            "title": {"type": "string"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": _OBJECT_ROWS,
            "x_axis": _OBJECT_OUTPUT,
            "y_axis": _OBJECT_OUTPUT,
            "warnings": _STRING_LIST,
            "data_quality": _OBJECT_OUTPUT,
            "query_context": _OBJECT_OUTPUT,
            "empty_state": _OBJECT_OUTPUT,
            "error": {"type": "string"},
        }),
    },
    "render_chart_widget": {
        "description": (
            "Render the Apps SDK chart widget from a validated get_chart_data payload. "
            "Call get_chart_data first, then pass its structured payload here."
        ),
        "inputSchema": _schema({
            "chart_id": {"type": "string"},
            "chart_kind": {"type": "string"},
            "title": {"type": "string"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": _OBJECT_ROWS,
            "x_axis": _OBJECT_OUTPUT,
            "y_axis": _OBJECT_OUTPUT,
            "warnings": _STRING_LIST,
            "data_quality": _OBJECT_OUTPUT,
            "query_context": _OBJECT_OUTPUT,
            "empty_state": _OBJECT_OUTPUT,
        }, required=["chart_id", "chart_kind", "title", "labels", "values", "series"]),
        "outputSchema": _output_schema({
            "chart_id": {"type": "string"},
            "chart_kind": {"type": "string"},
            "title": {"type": "string"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": _OBJECT_ROWS,
            "x_axis": _OBJECT_OUTPUT,
            "y_axis": _OBJECT_OUTPUT,
            "warnings": _STRING_LIST,
            "data_quality": _OBJECT_OUTPUT,
            "query_context": _OBJECT_OUTPUT,
            "empty_state": _OBJECT_OUTPUT,
            "_meta": _OBJECT_OUTPUT,
            "error": {"type": "string"},
        }),
        "_meta": {
            "openai/outputTemplate": CHART_WIDGET_URI,
            "ui": {"resourceUri": CHART_WIDGET_URI},
            "openai/toolInvocation/invoking": "Rendering chart...",
            "openai/toolInvocation/invoked": "Chart ready.",
        },
    },
    "get_computed_report": {
        "description": "Read computed chart-like or report-like rows for backups and charts without creating files.",
        "inputSchema": _schema({
            "report_type": {
                "type": "string",
                "description": f"Supported values: backup_times, {chart_type_description()}, ht_meet, ht_weekly_summary, ht_consolidated_history, bdt_export, accepted_pm_report, or chart:* aliases.",
            },
            "site_code": {"type": "string"},
            "site_id": {"type": "string"},
            "site_text": {"type": "string", "description": "Site fuzzy text filter for alarm-derived report types."},
            "export_week": {"type": "string", "description": "Required HT/summary period input (e.g. W01-26)."},
            "week_label": {"type": "string", "description": "Alias for export_week."},
            "source_file_id": {"type": "string", "description": "Allowlisted uploaded file id for source-file report types."},
            "section": {"type": "string", "description": "Section selector for bdt_export."},
            "health_pct": {"type": "number", "minimum": 0},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "min_minutes": {"type": "number", "minimum": 0},
            "include_raw_json": {"type": "boolean", "description": "Include flattened raw JSON fields in row results."},
            **_PAGING_PROPERTIES,
        }, required=["report_type"]),
        "outputSchema": _output_schema({
            "report_type": {"type": "string"},
            "rows": _OBJECT_ROWS,
            "returned": {"type": "integer"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
            "has_more": {"type": "boolean"},
            "total": {"type": "integer"},
            "row_count": {"type": "integer"},
            "site_count": {"type": "integer"},
            "site_ids": _STRING_LIST,
            "min_minutes": {"type": "number"},
            "threshold_minutes": {"type": "number"},
            "points": {"type": "integer"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "series": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "number"},
                    },
                    "additionalProperties": True,
                },
            },
            "error": {"type": "string"},
            "required": {
                "type": "array",
                "items": {"type": "string"},
            },
            "action": {"type": "string"},
            "section": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {"type": "string"},
            },
            "export_week": {"type": "string"},
            "week_label": {"type": "string"},
            "sheet_name": {"type": "string"},
            "site_column": {"type": "string"},
            "date_column": {"type": "string"},
            "status_column": {"type": "string"},
            "health_pct": {"type": "number"},
            "source_file_id": {"type": "string"},
        }),
    },
    "read_photo_blob": {
        "description": "Read one stored photo blob by SHA-256 as base64. Use only when the user explicitly asks to inspect an image.",
        "inputSchema": _schema({
            "sha256": {"type": "string"},
        }, required=["sha256"]),
        "outputSchema": _output_schema({
            "sha256": {"type": "string"},
            "mime_type": {"type": "string"},
            "base64": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "export_report": {
        "description": (
            "Create a CSV/XLSX export under the controlled local exports directory. "
            "Use site_alarm_report with an uploaded VIP/site-list CSV/XLSX, "
            "accepted_pm_report with an uploaded Accepted PM CSV/XLSX, and "
            "bdt_export for full BDT validation exports."
        ),
        "inputSchema": _schema({
            "report_type": {
                "type": "string",
                "enum": [
                    "alarms",
                    "bdt_results",
                    "photo_manifest",
                    "site_alarm_report",
                    "accepted_pm_report",
                    "bdt_export",
                ],
            },
            "format": {"type": "string", "enum": ["csv", "xlsx"]},
            "name": {"type": "string"},
            "source_file_id": {
                "type": "string",
                "description": (
                    "Opaque upload ID from the chat context. Required for site_alarm_report "
                    "and accepted_pm_report when the file was uploaded through chat; optional "
                    "for bdt_export to restrict the export to uploaded site codes."
                ),
            },
            "health_pct": {
                "type": "number",
                "description": "BDT health percentage threshold used by accepted PM and BDT exports.",
            },
            "site_text": {"type": "string"},
            "site_code": {"type": "string"},
            "category": {"type": "string"},
            "overall": {"type": "string"},
            "rule_id": {"type": "string"},
            "rule_verdict": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }, required=["report_type"]),
        "outputSchema": _output_schema({
            "path": {"type": "string"},
            "rows": {"type": "integer"},
            "format": {"type": "string"},
            "report_type": {"type": "string"},
            "source_file_id": {"type": "string"},
            "sheet_name": {"type": "string"},
            "site_column": {"type": "string"},
            "date_column": {"type": "string"},
            "status_column": {"type": "string"},
            "site_count": {"type": "integer"},
            "alarm_rows": {"type": "integer"},
            "bdt_results": {"type": "integer"},
            "sheets": _STRING_LIST,
            "error": {"type": "string"},
        }),
    },
    "search_site_metadata": {
        "description": "Search imported Site Metadata Catalog rows by site text, area, subcontractor/contractor, or backup/battery status.",
        "inputSchema": _schema({
            "site_text": {"type": "string"},
            "site_code": {"type": "string"},
            "site_id": {"type": "string"},
            "area": {"type": "string"},
            "subcontractor": {"type": "string"},
            "contractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_site_metadata": {
        "description": "Read normalized site metadata from the local DuckDB catalog for a given site code.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
        }),
        "outputSchema": _output_schema({
            "site_id": {"type": "string"},
            "rows": _OBJECT_ROWS,
            "row_count": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_bdt_summary": {
        "description": "Read BDT summary catalog rows from the local DuckDB catalog with optional filters.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "reporting_period": {"type": "string"},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
            "offset": {"type": "integer", "minimum": 0},
        }),
        "outputSchema": _output_schema({
            "rows": _OBJECT_ROWS,
            "total": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "query_bdt_full": {
        "description": "Read BDT summary, validation runs, rules, photos, and review events for one site period with shared pagination.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "reporting_period": {"type": "string"},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "overall": {"type": "string", "description": "Overall BDT verdict."},
            "rule_id": {"type": "string", "description": "Rule code such as R3 or R10."},
            "rule_verdict": {"type": "string", "description": "Rule verdict such as Accepted, Rejected, Revise, No data."},
            "include_raw_json": {"type": "boolean", "description": "Include raw JSON payload fields."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema({
            "bdt_summary": _output_schema(_PAGING_OUTPUT),
            "validation_runs": _output_schema(_PAGING_OUTPUT),
            "bdt_tests": _output_schema(_PAGING_OUTPUT),
            "rule_results": _output_schema(_PAGING_OUTPUT),
            "photos": _output_schema(_PAGING_OUTPUT),
            "review_events": _output_schema(_PAGING_OUTPUT),
            "error": {"type": "string"},
        }),
    },
    "list_sites": {
        "description": (
            "Read-only inventory index across all known sites, with optional filters for metadata, statuses, and data source presence."
        ),
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Match normalized site id or site_name."},
            "site_code": {"type": "string", "description": "Alias for site_text."},
            "site_id": {"type": "string", "description": "Alias for site_text."},
            "area": {"type": "string"},
            "contractor": {"type": "string"},
            "subcontractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "has_metadata": {"type": "boolean"},
            "has_alarms": {"type": "boolean"},
            "has_bdt_summary": {"type": "boolean"},
            "has_bdt_validation": {"type": "boolean"},
            "has_bdt": {"type": "boolean"},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT),
    },
    "query_network_summary": {
        "description": "Read full imported Network Summary/Site Metadata rows with normalized and original workbook-header fields.",
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "site_code": {"type": "string", "description": "Alias for site_id."},
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
    "get_site_alarm_context": {
        "description": "Return combined alarm statistics and recent alarm rows for a given site.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
        }),
        "outputSchema": _output_schema({
            "site_code": {"type": "string"},
            "alarm_stats": _OBJECT_OUTPUT,
            "alarm_rows": _OBJECT_ROWS,
            "alarm_total": {"type": "integer"},
            "error": {"type": "string"},
        }),
    },
    "get_site_full_context": {
        "description": "Return one-site full context including network summary, alarm statistics, alarm rows, and BDT sections.",
        "inputSchema": _schema({
            "site_code": {"type": "string", "description": "Normalized or raw site code."},
            "site_id": {"type": "string", "description": "Alias for site_code."},
            "metadata_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "metadata_offset": {"type": "integer", "minimum": 0},
            "alarm_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "alarm_offset": {"type": "integer", "minimum": 0},
            "bdt_limit": {"type": "integer", "minimum": 0, "maximum": 500, "xClampMaximum": True},
            "bdt_offset": {"type": "integer", "minimum": 0},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "reporting_period": {"type": "string", "description": "BDT reporting period alias."},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "overall": {"type": "string", "description": "Filter BDT runs by overall verdict."},
            "rule_id": {"type": "string", "description": "Filter BDT rule results by rule code."},
            "rule_verdict": {"type": "string", "description": "Filter BDT rule results by verdict."},
            "include_raw_json": {"type": "boolean", "description": "Include raw JSON payload fields."},
        }),
        "outputSchema": _output_schema({
            "site_id": {"type": "string"},
            "site_code": {"type": "string"},
            "network_summary": _output_schema(_PAGING_OUTPUT),
            "alarm_stats": _OBJECT_OUTPUT,
            "alarm_rows": _output_schema(_PAGING_OUTPUT),
            "bdt_summary": _output_schema(_PAGING_OUTPUT),
            "validation_runs": _output_schema(_PAGING_OUTPUT),
            "bdt_tests": _output_schema(_PAGING_OUTPUT),
            "rule_results": _output_schema(_PAGING_OUTPUT),
            "photos": _output_schema(_PAGING_OUTPUT),
            "review_events": _output_schema(_PAGING_OUTPUT),
            "bdt_error": {"type": "string"},
            "error": {"type": "string"},
        }),
    },
    "get_sites_context_report": {
        "description": "Return workbook-like all-sites context by sheet, with manifest and pagination metadata.",
        "inputSchema": _schema({
            "sheet": {"type": "string", "description": "Optional sheet name (case-insensitive). If omitted, returns manifest."},
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "site_code": {"type": "string", "description": "Alias for site_text."},
            "site_id": {"type": "string", "description": "Alias for site_text."},
            "area": {"type": "string"},
            "contractor": {"type": "string"},
            "subcontractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "has_metadata": {"type": "boolean"},
            "has_alarms": {"type": "boolean"},
            "has_bdt_summary": {"type": "boolean"},
            "has_bdt_validation": {"type": "boolean"},
            "has_bdt": {"type": "boolean"},
            "category": {"type": "string", "description": "Alarm category such as Power, Down, Door, or All."},
            "vendor": {"type": "string"},
            "network_type": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive date, YYYY-MM-DD."},
            "reporting_period": {"type": "string", "description": "BDT reporting period."},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "overall": {"type": "string", "description": "Filter BDT validation runs by overall verdict."},
            "rule_id": {"type": "string", "description": "Filter BDT rule results by rule code."},
            "rule_verdict": {"type": "string", "description": "Filter BDT rule results by verdict."},
            "include_raw_json": {"type": "boolean", "description": "Include raw JSON payload fields."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema({
            "sheets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "total": {"type": "integer"},
                        "available": {"type": "boolean"},
                    },
                    "additionalProperties": True,
                },
            },
            "sheet": {"type": "string"},
            "rows": _OBJECT_ROWS,
            "returned": {"type": "integer"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
            "has_more": {"type": "boolean"},
            "total": {"type": "integer"},
            "error": {"type": "string"},
            "error_sheet": {"type": "string"},
        }),
    },
    "query_battery_backup_insights": {
        "description": (
            "Read-only operational battery/backup insights by linking Network Summary metadata with BDT summary, "
            "BDT tests, validation runs, rules, and photo evidence."
        ),
        "inputSchema": _schema({
            "site_text": {"type": "string", "description": "Site id/text filter."},
            "site_code": {"type": "string", "description": "Alias for site_text."},
            "site_id": {"type": "string", "description": "Alias for site_text."},
            "area": {"type": "string"},
            "contractor": {"type": "string"},
            "subcontractor": {"type": "string"},
            "backup_status": {"type": "string"},
            "battery_status": {"type": "string"},
            "has_bdt": {"type": "boolean"},
            "has_bdt_summary": {"type": "boolean"},
            "has_bdt_validation": {"type": "boolean"},
            "date_from": {"type": "string", "description": "Inclusive BDT test date, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive BDT test date, YYYY-MM-DD."},
            "reporting_period": {"type": "string", "description": "BDT reporting period."},
            "period": {"type": "string", "description": "Alias for reporting_period."},
            "week": {"type": "string"},
            "overall": {"type": "string", "description": "Filter BDT validation runs by overall verdict."},
            "min_backup_minutes": {"type": "number", "description": "Minimum measured BDT discharge minutes considered dependable."},
            "backup_minutes_tolerance": {"type": "number", "description": "Allowed absolute minute difference between Network Summary and BDT measured backup."},
            **_PAGING_PROPERTIES,
        }),
        "outputSchema": _output_schema(_PAGING_OUTPUT | {
            "source_errors": _OBJECT_OUTPUT,
        }),
    },
}

_WRITE_TOOL_NAMES = {"export_report", "get_site_dossier"}
_OPENROUTER_EXCLUDED_TOOL_NAMES = {"render_chart_widget"}


def _mcp_annotations(name: str) -> dict[str, Any]:
    if name in _WRITE_TOOL_NAMES:
        return {
            "readOnlyHint": False,
            "openWorldHint": False,
            "destructiveHint": False,
        }
    return {"readOnlyHint": True}


def tool_definitions_for_mcp() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": schema["description"],
            "inputSchema": schema["inputSchema"],
            "outputSchema": schema["outputSchema"],
            "annotations": _mcp_annotations(name),
            **({"_meta": schema["_meta"]} if "_meta" in schema else {}),
        }
        for name, schema in TOOL_SCHEMAS.items()
    ]


def tool_definitions_for_openrouter() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": schema["description"],
                "parameters": schema["inputSchema"],
            },
        }
        for name, schema in TOOL_SCHEMAS.items()
        if name not in _OPENROUTER_EXCLUDED_TOOL_NAMES
    ]


def _type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        return isinstance(value, float) and value.is_integer()
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def _validate_tool_arguments(arguments: Any, input_schema: dict[str, Any]) -> dict[str, Any] | str:
    if arguments is None:
        args: dict[str, Any] = {}
    elif isinstance(arguments, dict):
        args = dict(arguments)
    else:
        return "arguments must be an object"

    if input_schema.get("type") == "object" and not isinstance(args, dict):
        return "arguments must be an object"

    properties = input_schema.get("properties", {})
    for field in input_schema.get("required", []):
        if field not in args:
            return f"missing required property: {field}"

    if input_schema.get("additionalProperties") is False:
        for field in args:
            if field not in properties:
                return f"unexpected property: {field}"

    required_fields = set(input_schema.get("required", []))

    for field, value in args.items():
        field_schema = properties.get(field, {})
        expected_type = field_schema.get("type")
        if value is None and field not in required_fields:
            continue
        if expected_type == "number" and isinstance(value, float) and not math.isfinite(value):
            return f"{field} must be finite"
        if expected_type == "integer" and isinstance(value, float) and math.isinf(value):
            return f"{field} must be finite"
        if expected_type and not _type_matches(value, expected_type):
            return f"{field} must be {expected_type}"
        if expected_type == "integer" and isinstance(value, float):
            value = int(value)
            args[field] = value

        enum_values = field_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            return f"{field} must be one of: {', '.join(str(item) for item in enum_values)}"

        if expected_type in {"integer", "number"}:
            minimum = field_schema.get("minimum")
            if minimum is not None and value < minimum:
                return f"{field} must be >= {minimum}"
            maximum = field_schema.get("maximum")
            if maximum is not None and value > maximum:
                if field_schema.get("xClampMaximum"):
                    args[field] = maximum
                else:
                    return f"{field} must be <= {maximum}"

    return args


def dispatch_tool(service: LocalDataService, name: str, arguments: Any = None) -> Any:
    if name not in TOOL_SCHEMAS:
        return {"error": f"unknown tool: {name}"}

    validated_args = _validate_tool_arguments(arguments, TOOL_SCHEMAS[name]["inputSchema"])
    if isinstance(validated_args, str):
        return {"error": f"invalid arguments for {name}: {validated_args}"}

    method = getattr(service, name, None)
    if method is None or not callable(method):
        return {"error": f"tool unavailable: {name}"}
    try:
        return method(**validated_args)
    except Exception as exc:
        return {"error": f"{name} failed: {exc}"}
