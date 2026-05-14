"""Local tunnel providers for desktop connector workflows."""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Protocol


class TunnelStartError(RuntimeError):
    """Raised when a local tunnel cannot be started."""


class TunnelProvider(Protocol):
    def start(self, local_base_url: str) -> str:
        """Start a tunnel and return the public HTTPS base URL."""

    def stop(self) -> None:
        """Stop the active tunnel if one is running."""


ProcessFactory = Callable[..., subprocess.Popen]


def bundled_cloudflared_path() -> str:
    """Return the bundled cloudflared path when packaged, else PATH lookup name."""
    bundle_root = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else None
    if bundle_root is not None:
        candidate = bundle_root / "bin" / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
        if candidate.exists():
            return str(candidate)
    return "cloudflared"


class CloudflaredTunnelProvider:
    _URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        origin_host_header: str | None = None,
        process_factory: ProcessFactory = subprocess.Popen,
        startup_timeout_seconds: float = 20.0,
    ):
        self._binary_path = binary_path or bundled_cloudflared_path()
        self._origin_host_header = origin_host_header or os.environ.get(
            "ALARM_MCP_TUNNEL_HOST_HEADER",
            "alarm-viewer-mcp.local",
        )
        self._process_factory = process_factory
        self._startup_timeout_seconds = startup_timeout_seconds
        self._process = None

    def start(self, local_base_url: str) -> str:
        self.stop()
        args = [
            self._binary_path,
            "tunnel",
            "--url",
            local_base_url,
            "--http-host-header",
            self._origin_host_header,
        ]
        try:
            process = self._process_factory(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError as exc:
            raise TunnelStartError("cloudflared was not found. Install or bundle cloudflared to enable ChatGPT MCP.") from exc

        self._process = process
        output_queue: queue.Queue[str] = queue.Queue()
        if getattr(process, "stdout", None) is not None:
            threading.Thread(
                target=self._read_stdout_lines,
                args=(process.stdout, output_queue),
                daemon=True,
            ).start()
        deadline = time.monotonic() + self._startup_timeout_seconds
        output_lines: list[str] = []
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                line = output_queue.get(timeout=min(0.05, remaining))
            except queue.Empty:
                line = ""
            if line:
                output_lines.append(line.rstrip())
                match = self._URL_RE.search(line)
                if match:
                    return match.group(0)
                continue
            if process.poll() is not None:
                break
            time.sleep(0.01)

        self.stop()
        detail = "\n".join(output_lines[-5:])
        suffix = f": {detail}" if detail else ""
        raise TunnelStartError(f"cloudflared did not report a public HTTPS URL{suffix}")

    @staticmethod
    def _read_stdout_lines(stdout, output_queue: queue.Queue[str]) -> None:
        while True:
            line = stdout.readline()
            if not line:
                return
            output_queue.put(line)

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
