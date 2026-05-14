import io
import time

import pytest

from alarm_app.runtime.tunnels import CloudflaredTunnelProvider, TunnelStartError


class _FakeProcess:
    def __init__(self, lines=None, returncode=None):
        self.stdout = io.StringIO("".join(lines or []))
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class _BlockingStdout:
    def readline(self):
        time.sleep(0.2)
        return ""


def test_cloudflared_start_builds_command_and_parses_public_url():
    calls = []
    process = _FakeProcess([
        "2026-05-14T12:00:00Z INF Starting tunnel\n",
        "2026-05-14T12:00:01Z INF https://alarm-test.trycloudflare.com\n",
    ])

    def process_factory(args, **kwargs):
        calls.append((args, kwargs))
        return process

    provider = CloudflaredTunnelProvider(
        binary_path="/opt/alarm/bin/cloudflared",
        process_factory=process_factory,
        startup_timeout_seconds=0.1,
    )

    public_url = provider.start("http://127.0.0.1:8787")

    assert public_url == "https://alarm-test.trycloudflare.com"
    assert calls[0][0] == [
        "/opt/alarm/bin/cloudflared",
        "tunnel",
        "--url",
        "http://127.0.0.1:8787",
        "--http-host-header",
        "alarm-viewer-mcp.local",
    ]
    assert calls[0][1]["stdout"] == -1
    assert calls[0][1]["stderr"] == -2
    assert calls[0][1]["text"] is True


def test_cloudflared_start_reports_missing_binary():
    def process_factory(args, **kwargs):
        raise FileNotFoundError("missing cloudflared")

    provider = CloudflaredTunnelProvider(
        binary_path="missing-cloudflared",
        process_factory=process_factory,
    )

    with pytest.raises(TunnelStartError, match="cloudflared"):
        provider.start("http://127.0.0.1:8787")


def test_cloudflared_stop_terminates_running_process():
    process = _FakeProcess([
        "INF https://alarm-test.trycloudflare.com\n",
    ])
    provider = CloudflaredTunnelProvider(
        binary_path="cloudflared",
        process_factory=lambda *args, **kwargs: process,
        startup_timeout_seconds=0.1,
    )

    provider.start("http://127.0.0.1:8787")
    provider.stop()

    assert process.terminated is True
    assert process.killed is False


def test_cloudflared_start_fails_when_no_public_url_is_reported():
    process = _FakeProcess([
        "INF Starting tunnel\n",
        "ERR failed to connect\n",
    ], returncode=1)
    provider = CloudflaredTunnelProvider(
        binary_path="cloudflared",
        process_factory=lambda *args, **kwargs: process,
        startup_timeout_seconds=0.1,
    )

    with pytest.raises(TunnelStartError, match="public HTTPS URL"):
        provider.start("http://127.0.0.1:8787")


def test_cloudflared_start_timeout_does_not_block_on_stdout_readline():
    process = _FakeProcess()
    process.stdout = _BlockingStdout()
    provider = CloudflaredTunnelProvider(
        binary_path="cloudflared",
        process_factory=lambda *args, **kwargs: process,
        startup_timeout_seconds=0.02,
    )

    started = time.monotonic()
    with pytest.raises(TunnelStartError, match="public HTTPS URL"):
        provider.start("http://127.0.0.1:8787")

    assert time.monotonic() - started < 0.15
    assert process.terminated is True
