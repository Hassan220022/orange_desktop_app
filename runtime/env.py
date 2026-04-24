"""Environment-file helpers for local CLI/desktop startup."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[7:].lstrip()
    if "=" not in text:
        return None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not key:
        return None
    raw_value = raw_value.strip()
    if raw_value.startswith('"') and raw_value.endswith('"') and len(raw_value) >= 2:
        value = raw_value[1:-1]
    elif raw_value.startswith("'") and raw_value.endswith("'") and len(raw_value) >= 2:
        value = raw_value[1:-1]
    else:
        value = raw_value.split(" #", 1)[0].strip()
    return key, value


def load_local_env(*, override: bool = False) -> Path | None:
    """Load .env vars from CWD first, then package root, without overriding by default."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    seen: set[Path] = set()
    for path in candidates:
        normalized = path.resolve()
        if normalized in seen or not normalized.is_file():
            seen.add(normalized)
            continue
        for line in normalized.read_text(encoding="utf-8-sig").splitlines():
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if override or key not in os.environ:
                os.environ[key] = value
        return normalized
    return None

