"""Minimal stdio MCP server for local Alarm Viewer data."""

from __future__ import annotations

import json
import sys
from typing import Any

from .service import LocalDataService
from .tools import dispatch_tool, tool_definitions_for_mcp


SERVER_INFO = {"name": "alarm-viewer-local-data", "version": "0.1.0"}


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
        params = request.get("params") or {}

        if method == "initialize":
            return _response(request_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            })

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return _response(request_id, {"tools": tool_definitions_for_mcp()})

        if method == "tools/call":
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            result = dispatch_tool(self.service, name, arguments)
            return _response(request_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, default=str, ensure_ascii=False),
                    }
                ],
                "isError": isinstance(result, dict) and "error" in result,
            })

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
