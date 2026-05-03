"""Tool registry shared by MCP and OpenRouter entrypoints."""

from __future__ import annotations

from typing import Any, Callable

from .service import LocalDataService


def _schema(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_data_sources": {
        "description": "List local Alarm Viewer storage sources, table row counts, DuckDB alarm stores, blob storage, and export path.",
        "inputSchema": _schema({}),
    },
    "get_current_time": {
        "description": "Return the current local machine time and timezone for date-aware answers.",
        "inputSchema": _schema({}),
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
    },
    "get_bdt_detail": {
        "description": "Read one BDT validation detail with rules, discharge readings, and photo metadata.",
        "inputSchema": _schema({
            "validation_run_id": {"type": "integer"},
            "site_code": {"type": "string"},
            "test_date": {"type": "string"},
        }),
    },
    "get_photo_metadata": {
        "description": "Read BDT photo metadata from the local app DB without returning image bytes.",
        "inputSchema": _schema({
            "site_code": {"type": "string"},
            "bdt_test_id": {"type": "integer"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 500},
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
    },
    "generate_graph": {
        "description": (
            "Generate a PNG chart from local alarm or BDT data and return the image path plus chart data."
        ),
        "inputSchema": _schema({
            "graph_type": {
                "type": "string",
                "enum": [
                    "alarm_category_counts",
                    "alarm_daily_counts",
                    "alarm_duration_by_category",
                    "bdt_verdict_counts",
                    "bdt_duration_trend",
                ],
            },
            "site_code": {"type": "string"},
            "site_text": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "title": {"type": "string"},
        }, required=["graph_type"]),
    },
    "read_photo_blob": {
        "description": "Read one stored photo blob by SHA-256 as base64. Use only when the user explicitly asks to inspect an image.",
        "inputSchema": _schema({
            "sha256": {"type": "string"},
        }, required=["sha256"]),
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
            "source_file_path": {
                "type": "string",
                "description": (
                    "Local path to a user-uploaded CSV/XLSX list. Required for "
                    "site_alarm_report and accepted_pm_report; optional for bdt_export "
                    "to restrict the export to uploaded site codes."
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
    },
}


def tool_definitions_for_mcp() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": schema["description"],
            "inputSchema": schema["inputSchema"],
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
    ]


def dispatch_tool(service: LocalDataService, name: str, arguments: dict[str, Any] | None = None) -> Any:
    args = dict(arguments or {})
    if name not in TOOL_SCHEMAS:
        return {"error": f"unknown tool: {name}"}
    method = getattr(service, name, None)
    if method is None or not callable(method):
        return {"error": f"tool unavailable: {name}"}
    try:
        return method(**args)
    except Exception as exc:
        return {"error": f"{name} failed: {exc}"}
