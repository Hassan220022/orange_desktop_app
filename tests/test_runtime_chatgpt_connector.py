from alarm_app.runtime.chatgpt_connector import ChatGPTConnectorManager


class _FakeTunnelProvider:
    def __init__(self, public_base_url="https://alarm-test.trycloudflare.com"):
        self.public_base_url = public_base_url
        self.started_with = []
        self.stop_calls = 0

    def start(self, local_base_url):
        self.started_with.append(local_base_url)
        return self.public_base_url

    def stop(self):
        self.stop_calls += 1


def test_enable_generates_token_starts_tunnel_and_saves_public_url_without_token(monkeypatch):
    monkeypatch.delenv("ALARM_MCP_TOKEN", raising=False)
    saved = {}
    tunnel = _FakeTunnelProvider()
    manager = ChatGPTConnectorManager(
        load_state=lambda: dict(saved),
        save_state=lambda data: saved.update(data),
        tunnel_provider=tunnel,
        token_factory=lambda: "generated-token",
        local_base_url="http://127.0.0.1:8787",
    )

    status = manager.enable()

    assert tunnel.started_with == ["http://127.0.0.1:8787"]
    assert status.public_url == "https://alarm-test.trycloudflare.com/mcp"
    assert status.connector_url == "https://alarm-test.trycloudflare.com/mcp?token=generated-token"
    assert status.enabled is True
    assert saved["chatgpt_mcp_enabled"] is True
    assert saved["chatgpt_mcp_public_url"] == "https://alarm-test.trycloudflare.com/mcp"
    assert saved["chatgpt_mcp_token"] == "generated-token"


def test_enable_uses_env_token_without_persisting_it(monkeypatch):
    monkeypatch.setenv("ALARM_MCP_TOKEN", "env-token")
    saved = {"chatgpt_mcp_token": "old-saved-token"}
    tunnel = _FakeTunnelProvider()
    manager = ChatGPTConnectorManager(
        load_state=lambda: dict(saved),
        save_state=lambda data: saved.clear() or saved.update(data),
        tunnel_provider=tunnel,
        token_factory=lambda: "generated-token",
        local_base_url="http://127.0.0.1:8787",
    )

    status = manager.enable()

    assert status.connector_url == "https://alarm-test.trycloudflare.com/mcp?token=env-token"
    assert saved["chatgpt_mcp_enabled"] is True
    assert saved["chatgpt_mcp_public_url"] == "https://alarm-test.trycloudflare.com/mcp"
    assert "chatgpt_mcp_token" not in saved


def test_disable_stops_tunnel_and_clears_saved_connector_state(monkeypatch):
    monkeypatch.delenv("ALARM_MCP_TOKEN", raising=False)
    saved = {
        "chatgpt_mcp_enabled": True,
        "chatgpt_mcp_public_url": "https://old.trycloudflare.com/mcp",
        "chatgpt_mcp_token": "saved-token",
    }
    tunnel = _FakeTunnelProvider()
    manager = ChatGPTConnectorManager(
        load_state=lambda: dict(saved),
        save_state=lambda data: saved.clear() or saved.update(data),
        tunnel_provider=tunnel,
        token_factory=lambda: "unused-token",
        local_base_url="http://127.0.0.1:8787",
    )

    status = manager.disable()

    assert tunnel.stop_calls == 1
    assert status.enabled is False
    assert status.public_url == ""
    assert status.connector_url == ""
    assert saved["chatgpt_mcp_enabled"] is False
    assert saved["chatgpt_mcp_public_url"] == ""
    assert "chatgpt_mcp_token" not in saved
