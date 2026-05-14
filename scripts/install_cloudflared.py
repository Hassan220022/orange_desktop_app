#!/usr/bin/env python3
"""Install the pinned cloudflared binary used by packaged builds."""

from __future__ import annotations

import hashlib
import os
import platform
import stat
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

VERSION = "2026.5.0"
ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = Path(os.environ.get("ALARM_CLOUDFLARED_DEST_DIR", ROOT / "vendor" / "cloudflared"))


@dataclass(frozen=True)
class CloudflaredAsset:
    filename: str
    sha256: str
    archive: bool = False


ASSETS: dict[tuple[str, str], CloudflaredAsset] = {
    ("darwin", "x64"): CloudflaredAsset(
        filename="cloudflared-darwin-amd64.tgz",
        sha256="7f2c4c8c86e787226804694112682aefacd4cfb98f54508f1a5a841a78bbbef9",
        archive=True,
    ),
    ("darwin", "arm64"): CloudflaredAsset(
        filename="cloudflared-darwin-arm64.tgz",
        sha256="116ef11a59fc4f31e7f1bcc4378070cd7ca053fa37b4484b1432bb150b358219",
        archive=True,
    ),
    ("linux", "x64"): CloudflaredAsset(
        filename="cloudflared-linux-amd64",
        sha256="0095e46fdc88855d801c4d304cb1f5dd4bd656116c47ab94c2ad0ae7cda1c7ec",
    ),
    ("linux", "arm64"): CloudflaredAsset(
        filename="cloudflared-linux-arm64",
        sha256="2dc0945345677d27de3ae390a31c3b168866b48766da5f4cfd3fc473ce572303",
    ),
    ("windows", "x64"): CloudflaredAsset(
        filename="cloudflared-windows-amd64.exe",
        sha256="f141cded099c239171ad2cea6fb5da0fdaa2bd36104c3074d883f9546519eba7",
    ),
}


def _normalise_system() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    raise SystemExit(f"Unsupported OS for cloudflared bundle: {platform.system()}")


def _normalise_arch() -> str:
    arch = os.environ.get("RUNNER_ARCH", platform.machine()).lower()
    if arch in {"x64", "amd64", "x86_64"}:
        return "x64"
    if arch in {"arm64", "aarch64"}:
        return "arm64"
    raise SystemExit(f"Unsupported architecture for cloudflared bundle: {arch}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(asset: CloudflaredAsset, target: Path) -> None:
    url = f"https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/{asset.filename}"
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as handle:
        handle.write(response.read())

    actual = _sha256(target)
    if actual != asset.sha256:
        target.unlink(missing_ok=True)
        raise SystemExit(f"Checksum mismatch for {asset.filename}: expected {asset.sha256}, got {actual}")


def _extract_archive(archive_path: Path, dest: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        member = next((item for item in archive.getmembers() if Path(item.name).name == "cloudflared"), None)
        if member is None:
            raise SystemExit(f"cloudflared binary missing from {archive_path.name}")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise SystemExit(f"Could not extract cloudflared from {archive_path.name}")
        with dest.open("wb") as handle:
            handle.write(extracted.read())


def install() -> Path:
    system = _normalise_system()
    arch = _normalise_arch()
    asset = ASSETS.get((system, arch))
    if asset is None:
        raise SystemExit(f"No cloudflared asset configured for {system}/{arch}")

    binary_name = "cloudflared.exe" if system == "windows" else "cloudflared"
    dest = DEST_DIR / binary_name
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cloudflared-") as tmp:
        download_path = Path(tmp) / asset.filename
        _download(asset, download_path)
        if asset.archive:
            _extract_archive(download_path, dest)
        else:
            dest.write_bytes(download_path.read_bytes())

    if system != "windows":
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    try:
        display_path = dest.relative_to(ROOT)
    except ValueError:
        display_path = dest
    print(f"Installed cloudflared {VERSION} to {display_path}")
    return dest


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:  # noqa: BLE001 - fail with a concise CI message.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
