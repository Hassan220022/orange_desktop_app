from pathlib import Path

from alarm_app.versioning import (
    DEFAULT_APP_VERSION,
    get_app_version,
    resolve_app_version,
)


def test_get_app_version_prefers_environment_override():
    assert get_app_version(default="0.0.0", env={"ALARM_APP_VERSION": "0.1.9"}) == "0.1.9"


def test_get_app_version_reads_version_file(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.8\n", encoding="utf-8")

    assert (
        get_app_version(
            default="0.0.0",
            env={},
            version_paths=[version_file],
            git_version=None,
            frozen=True,
        )
        == "0.1.8"
    )


def test_get_app_version_falls_back_to_default_for_invalid_version(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("not-a-version\n", encoding="utf-8")

    assert (
        get_app_version(
            default="0.1.8",
            env={},
            version_paths=[version_file],
            git_version=None,
            frozen=True,
        )
        == "0.1.8"
    )


def test_resolve_app_version_prefers_latest_git_tag_over_version_file():
    assert (
        resolve_app_version(
            file_versions=["0.2.0"],
            git_version="0.2.7",
            default="0.1.8",
        )
        == "0.2.7"
    )


def test_resolve_app_version_uses_version_file_when_git_missing():
    assert (
        resolve_app_version(
            file_versions=["0.2.3"],
            git_version=None,
            default="0.1.8",
        )
        == "0.2.3"
    )


def test_get_app_version_uses_git_tags_when_not_frozen(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.2.0\n", encoding="utf-8")

    assert (
        get_app_version(
            default="0.1.8",
            env={},
            version_paths=[version_file],
            git_version="0.2.7",
            frozen=False,
        )
        == "0.2.7"
    )


def test_get_app_version_skips_git_in_frozen_builds(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.2.5\n", encoding="utf-8")

    assert (
        get_app_version(
            default="0.1.8",
            env={},
            version_paths=[version_file],
            git_version="0.2.7",
            frozen=True,
        )
        == "0.2.5"
    )


def test_default_app_version_matches_release_series():
    assert DEFAULT_APP_VERSION == "0.2.0"


def test_get_app_version_resolves_latest_local_git_tag():
    version = get_app_version(
        env={},
        version_paths=[Path(__file__).resolve().parents[1] / "VERSION"],
        frozen=False,
    )
    assert version >= "0.2.0"
