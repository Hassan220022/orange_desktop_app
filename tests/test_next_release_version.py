from scripts.next_release_version import compute_next_release_version


def test_base_version_bumps_when_series_tag_exists():
    tags = ["v0.2.0"]

    assert compute_next_release_version("0.2.0", tags) == "0.2.1"


def test_ignores_other_series_and_non_release_tags():
    tags = ["v0.1.99", "build-123", "v0.3.0"]

    assert compute_next_release_version("0.2.0", tags) == "0.2.0"


def test_returns_base_version_when_no_matching_series_tags():
    assert compute_next_release_version("0.2.0", ["v1.0.0", "release-2026.01"]) == "0.2.0"


def test_chooses_max_patch_when_multiple_series_tags_exist():
    tags = ["v0.2.0", "v0.2.3", "v0.2.2", "v0.2.9"]

    assert compute_next_release_version("0.2.0", tags) == "0.2.10"
