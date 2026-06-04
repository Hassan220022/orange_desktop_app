"""Minimal stdio MCP server for local Alarm Viewer data."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .openrouter_agent import _model_safe_tool_result
from .service import CHART_WIDGET_MIME_TYPE, CHART_WIDGET_URI, LocalDataService
from .tools import dispatch_tool, tool_definitions_for_mcp

SERVER_INFO = {"name": "alarm-viewer-local-data", "version": "0.1.0"}

_WIDGET_NAME = "chart-widget"
_WIDGET_TITLE = "Alarm Chart Widget"
_WIDGET_HTML_PATH = Path(__file__).resolve().parents[1] / "mcp_app" / "chart_widget" / "dist" / "chart.html"


def chart_widget_resource() -> dict[str, Any]:
    return {
        "uri": CHART_WIDGET_URI,
        "name": _WIDGET_NAME,
        "title": _WIDGET_TITLE,
        "mimeType": CHART_WIDGET_MIME_TYPE,
    }


def chart_widget_html() -> str:
    if not _WIDGET_HTML_PATH.exists():
        raise FileNotFoundError(f"chart widget build artifact missing: {_WIDGET_HTML_PATH}")
    return _WIDGET_HTML_PATH.read_text(encoding="utf-8")


def read_chart_widget_resource(uri: str) -> dict[str, Any] | None:
    if uri != CHART_WIDGET_URI:
        return None
    return {
        "uri": CHART_WIDGET_URI,
        "mimeType": CHART_WIDGET_MIME_TYPE,
        "text": chart_widget_html(),
        "_meta": {"ui": {"prefersBorder": True}},
    }



def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class AlarmViewerMcpServer:
    def __init__(self, service: LocalDataService | None = None):
        self.service = service or LocalDataService()

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        raw_params = request.get("params")
        params = raw_params if isinstance(raw_params, dict) else ({} if raw_params is None else None)

        if method == "initialize":
            return _response(request_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}, "resources": {}},
            })

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return _response(request_id, {"tools": tool_definitions_for_mcp()})

        if method == "resources/list":
            return _response(request_id, {"resources": [chart_widget_resource()]})

        if method == "resources/read":
            if params is None:
                return _error(request_id, -32602, "resources/read params must be an object")
            uri = str(params.get("uri") or "")
            try:
                resource = read_chart_widget_resource(uri)
            except FileNotFoundError as exc:
                return _error(request_id, -32002, str(exc))
            if resource is None:
                return _error(request_id, -32002, f"resource not found: {uri}")
            return _response(request_id, {"contents": [resource]})

        if method == "tools/call":
            if params is None:
                return _error(request_id, -32602, "tools/call params must be an object")
            name = str(params.get("name") or "")
            arguments = params.get("arguments") if "arguments" in params else {}
            result = dispatch_tool(self.service, name, arguments)
            safe_result = _model_safe_tool_result(result)
            content = [
                {
                    "type": "text",
                    "text": json.dumps(safe_result, default=str, ensure_ascii=False),
                }
            ]
            response_payload = {
                "content": content,
                "structuredContent": safe_result,
                "isError": isinstance(result, dict) and "error" in result,
            }
            if isinstance(result, dict) and isinstance(result.get("_meta"), dict):
                response_payload["_meta"] = result["_meta"]
            return _response(request_id, response_payload)

        return _error(request_id, -32601, f"method not found: {method}")


def main() -> None:
    server = AlarmViewerMcpServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = server.handle(request)
        except Exception as exc:
            response = _error(None, -32603, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
