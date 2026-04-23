from pathlib import Path

from alarm_app.versioning import get_app_version


def test_get_app_version_prefers_environment_override():
    assert get_app_version(default="0.0.0", env={"ALARM_APP_VERSION": "0.1.9"}) == "0.1.9"


def test_get_app_version_reads_version_file(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.8\n", encoding="utf-8")

    assert get_app_version(default="0.0.0", env={}, version_paths=[version_file]) == "0.1.8"


def test_get_app_version_falls_back_to_default_for_invalid_version(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("not-a-version\n", encoding="utf-8")

    assert get_app_version(default="0.1.8", env={}, version_paths=[version_file]) == "0.1.8"
