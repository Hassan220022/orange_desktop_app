#!/usr/bin/env python3
"""Compute the next patch version for the current release series."""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def parse_version(text: str) -> tuple[int, int, int]:
    """Parse a strict semantic version string (major.minor.patch)."""

    match = SEMVER_RE.match(text.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {text!r}")

    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def parse_tag(tag: str) -> tuple[int, int, int] | None:
    match = TAG_RE.match(tag.strip())
    if not match:
        return None

    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def compute_next_release_version(base_version: str, tags: Iterable[str]) -> str:
    """Return the next patch release for the base series."""

    major, minor, _ = parse_version(base_version)
    matching = []
    for tag in tags:
        parsed = parse_tag(tag)
        if parsed and parsed[0] == major and parsed[1] == minor:
            matching.append(parsed[2])

    if not matching:
        return base_version

    return f"{major}.{minor}.{max(matching) + 1}"


def read_version_file(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"Unable to read VERSION file at {path}: {exc}") from exc

    try:
        parse_version(value)
    except ValueError as exc:
        raise ValueError(f"Invalid VERSION in {path}: {value!r}") from exc

    return value


def list_git_tags() -> list[str]:
    command = ["git", "tag", "--list"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Unable to list git tags: {result.stderr.strip()}")

    lines = result.stdout.splitlines()
    return [line.strip() for line in lines if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute next patch release version")
    parser.add_argument(
        "--version-file",
        default="VERSION",
        help="Path to the VERSION file (default: VERSION)",
    )
    args = parser.parse_args(argv)

    try:
        base_version = read_version_file(Path(args.version_file))
        tags = list_git_tags()
        next_version = compute_next_release_version(base_version, tags)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(next_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
