"""Application version helpers."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_APP_VERSION = "0.1.8"
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _default_version_paths() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "_MEIPASS", None):
        paths.append(Path(sys._MEIPASS) / "VERSION")
    paths.append(Path(__file__).resolve().parent / "VERSION")
    paths.append(Path(sys.executable).resolve().parent / "VERSION")
    return paths


def get_app_version(
    default: str = DEFAULT_APP_VERSION,
    *,
    env: dict[str, str] | None = None,
    version_paths: Iterable[Path] | None = None,
) -> str:
    env = env or os.environ
    override = str(env.get("ALARM_APP_VERSION", "")).strip()
    if override:
        return override

    for path in version_paths or _default_version_paths():
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if _SEMVER_RE.match(value):
            return value
    return default
