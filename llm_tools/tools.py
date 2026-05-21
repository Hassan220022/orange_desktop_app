"""Tool registry shared by MCP and OpenRouter entrypoints."""

from __future__ import annotations

import math
from typing import Any

from .service import LocalDataService


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
        "outputSchema": _output_schema({
            "path": {"type": "string"},
            "graph_type": {"type": "string"},
            "site_code": {"type": "string"},
            "points": {"type": "integer"},
            "labels": _STRING_LIST,
            "values": _NUMBER_LIST,
            "error": {"type": "string"},
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
}

_WRITE_TOOL_NAMES = {"export_report", "generate_graph", "get_site_dossier"}


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

    for field, value in args.items():
        field_schema = properties.get(field, {})
        expected_type = field_schema.get("type")
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
