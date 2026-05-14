"""HTTP MCP endpoint for ChatGPT connectors."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

try:
    from alarm_app.llm_tools.mcp_server import AlarmViewerMcpServer
    from alarm_app.data import state
except ImportError:
    from llm_tools.mcp_server import AlarmViewerMcpServer  # type: ignore[no-redef]
    from data import state  # type: ignore[no-redef]


router = APIRouter(tags=["mcp"])


def _expected_token() -> str:
    env_token = os.environ.get("ALARM_MCP_TOKEN", "").strip()
    if env_token:
        return env_token
    saved = state.load_state() or {}
    return str(saved.get("chatgpt_mcp_token") or "").strip()


def _supplied_token(request: Request, query_token: str | None) -> str:
    if query_token:
        return query_token.strip()
    auth = request.headers.get("authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() == "bearer":
        return value.strip()
    return ""


def _require_token(request: Request, query_token: str | None) -> None:
    expected = _expected_token()
    if not expected:
        raise HTTPException(status_code=503, detail="ChatGPT MCP connector token is not configured")
    supplied = _supplied_token(request, query_token)
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/mcp")
def handle_mcp_request(body: dict[str, Any], request: Request, token: str | None = None):
    _require_token(request, token)
    if body.get("jsonrpc") != "2.0":
        raise HTTPException(status_code=400, detail="MCP requests must use JSON-RPC 2.0")

    result = AlarmViewerMcpServer().handle(body)
    if result is None:
        return Response(status_code=202)
    return result
