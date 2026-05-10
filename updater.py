"""
Check for application updates from GitHub Releases.
Queries the orange_desktop_app releases and compares against the current version.
"""

from __future__ import annotations

import json
import os
import platform
import tempfile
import urllib.request
from dataclasses import dataclass

from packaging.version import InvalidVersion, Version

try:
    from alarm_app.constants import APP_VERSION
except ImportError:
    from constants import APP_VERSION

GITHUB_API = "https://api.github.com/repos/Hassan220022/orange_desktop_app/releases/latest"


@dataclass
class ReleaseInfo:
    tag: str
    version: Version
    name: str
    assets: list[dict]

    @property
    def display_version(self) -> str:
        return f"v{self.tag}"


def _get_current_version() -> Version:
    try:
        return Version(APP_VERSION)
    except InvalidVersion:
        return Version("0.0.0")


def fetch_latest_release() -> ReleaseInfo | None:
    req = urllib.request.Request(GITHUB_API)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "AlarmViewer-UpdateCheck")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    tag = str(data.get("tag_name", "")).lstrip("v")
    try:
        version = Version(tag)
    except InvalidVersion:
        return None

    return ReleaseInfo(
        tag=tag,
        version=version,
        name=data.get("name", ""),
        assets=data.get("assets", []),
    )


def is_update_available(latest: ReleaseInfo) -> bool:
    return latest.version > _get_current_version()


def get_platform_asset(release: ReleaseInfo) -> dict | None:
    system = platform.system()
    if system == "Darwin":
        suffix = ".dmg"
    elif system == "Windows":
        suffix = ".exe"
    else:
        return None

    for asset in release.assets:
        if str(asset.get("name", "")).endswith(suffix):
            return asset
    return None


def download_release_asset(url: str, dest_dir: str | None = None) -> str:
    ext = ".dmg" if platform.system() == "Darwin" else ".exe"
    dest_dir = dest_dir or tempfile.gettempdir()

    asset_name = url.rsplit("/", 1)[-1] if "/" in url else f"AlarmViewer_Update{ext}"
    dest = os.path.join(dest_dir, asset_name)

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/octet-stream")
    req.add_header("User-Agent", "AlarmViewer-UpdateCheck")

    with urllib.request.urlopen(req, timeout=600) as resp:
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)

    return dest


def open_downloaded_file(filepath: str) -> None:
    system = platform.system()
    if system == "Darwin":
        import subprocess

        subprocess.Popen(["open", filepath])
    elif system == "Windows":
        os.startfile(filepath)
