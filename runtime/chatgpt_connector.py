"""Managed ChatGPT MCP connector state and tunnel lifecycle."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode

try:
    from alarm_app.data import state
    from alarm_app.runtime.tunnels import CloudflaredTunnelProvider, TunnelProvider
except ImportError:
    from data import state  # type: ignore[no-redef]
    from runtime.tunnels import CloudflaredTunnelProvider, TunnelProvider  # type: ignore[no-redef]


@dataclass(frozen=True)
class ChatGPTConnectorStatus:
    enabled: bool
    public_url: str
    connector_url: str
    token_from_env: bool


class ChatGPTConnectorManager:
    def __init__(
        self,
        *,
        load_state: Callable[[], dict] = state.load_state,
        save_state: Callable[[dict], None] = state.save_state,
        tunnel_provider: TunnelProvider | None = None,
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        local_base_url: str = "http://127.0.0.1:8787",
    ):
        self._load_state = load_state
        self._save_state = save_state
        self._tunnel_provider = tunnel_provider or CloudflaredTunnelProvider()
        self._token_factory = token_factory
        self._local_base_url = local_base_url.rstrip("/")

    def enable(self) -> ChatGPTConnectorStatus:
        current = self._load_state() or {}
        env_token = os.environ.get("ALARM_MCP_TOKEN", "").strip()
        token_from_env = bool(env_token)
        token = env_token or str(current.get("chatgpt_mcp_token") or "").strip() or self._token_factory()

        public_base_url = self._tunnel_provider.start(self._local_base_url).rstrip("/")
        public_url = f"{public_base_url}/mcp"
        connector_url = f"{public_url}?{urlencode({'token': token})}"

        current["chatgpt_mcp_enabled"] = True
        current["chatgpt_mcp_public_url"] = public_url
        if token_from_env:
            current.pop("chatgpt_mcp_token", None)
        else:
            current["chatgpt_mcp_token"] = token
        self._save_state(current)

        return ChatGPTConnectorStatus(
            enabled=True,
            public_url=public_url,
            connector_url=connector_url,
            token_from_env=token_from_env,
        )

    def disable(self) -> ChatGPTConnectorStatus:
        self._tunnel_provider.stop()
        current = self._load_state() or {}
        current["chatgpt_mcp_enabled"] = False
        current["chatgpt_mcp_public_url"] = ""
        current.pop("chatgpt_mcp_token", None)
        self._save_state(current)
        return ChatGPTConnectorStatus(
            enabled=False,
            public_url="",
            connector_url="",
            token_from_env=bool(os.environ.get("ALARM_MCP_TOKEN", "").strip()),
        )
