"""Application version helpers."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

DEFAULT_APP_VERSION = "0.2.0"
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")


def _default_version_paths() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "_MEIPASS", None):
        paths.append(Path(sys._MEIPASS) / "VERSION")
    paths.append(Path(__file__).resolve().parent / "VERSION")
    paths.append(Path(sys.executable).resolve().parent / "VERSION")
    return paths


def _is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None))


def _parse_semver(value: str) -> tuple[int, int, int] | None:
    text = str(value).strip()
    if not _SEMVER_RE.match(text):
        return None
    major, minor, patch = (int(part) for part in text.split("."))
    return major, minor, patch


def _max_semver(*candidates: str, default: str) -> str:
    best: tuple[int, int, int] | None = None
    best_text = default

    for candidate in candidates:
        parsed = _parse_semver(candidate)
        if parsed is None:
            continue
        if best is None or parsed > best:
            best = parsed
            best_text = candidate.strip()

    return best_text


def _read_version_files(version_paths: Iterable[Path]) -> list[str]:
    versions: list[str] = []
    for path in version_paths:
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if _parse_semver(value) is not None:
            versions.append(value)
    return versions


def _latest_git_release_version(repo_root: Path | None = None) -> str | None:
    root = repo_root or Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "v*.*.*", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        tag = line.strip()
        match = _TAG_RE.match(tag)
        if match is None:
            continue
        version = match.group("version")
        if _parse_semver(version) is not None:
            return version
    return None


def resolve_app_version(
    *,
    env_version: str = "",
    file_versions: Iterable[str] = (),
    git_version: str | None = None,
    default: str = DEFAULT_APP_VERSION,
) -> str:
    override = str(env_version).strip()
    if override and _parse_semver(override) is not None:
        return override

    candidates = [default, *file_versions]
    if git_version:
        candidates.append(git_version)
    return _max_semver(*candidates, default=default)


def get_app_version(
    default: str = DEFAULT_APP_VERSION,
    *,
    env: dict[str, str] | None = None,
    version_paths: Iterable[Path] | None = None,
    git_version: str | None | object = ...,
    frozen: bool | None = None,
) -> str:
    env = env or os.environ
    file_versions = _read_version_files(version_paths or _default_version_paths())

    resolved_git: str | None = None
    is_frozen = frozen if frozen is not None else _is_frozen_build()
    if not is_frozen:
        if git_version is ...:
            resolved_git = _latest_git_release_version()
        elif isinstance(git_version, str):
            resolved_git = git_version

    return resolve_app_version(
        env_version=str(env.get("ALARM_APP_VERSION", "")),
        file_versions=file_versions,
        git_version=resolved_git,
        default=default,
    )
