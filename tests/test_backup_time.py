"""Tests for backup_time.compute_backup_times()."""

import pandas as pd
import pytest

from alarm_app.core.backup_time import compute_backup_times


def _make_df(rows):
    """Build a DataFrame from a list of dicts with sensible defaults."""
    defaults = {
        "site_id": "SITE_A",
        "occurred_on": None,
        "cleared_on": None,
        "alarm_category": "Power",
        "network_type": "4G",
        "vendor": "Huawei",
    }
    records = []
    for r in rows:
        rec = {**defaults, **r}
        for col in ("occurred_on", "cleared_on"):
            if isinstance(rec[col], str):
                rec[col] = pd.Timestamp(rec[col])
        records.append(rec)
    return pd.DataFrame(records)


# ── Basic match ─────────────────────────────────────────────────
class TestBasicMatch:
    def test_power_then_down_30min(self):
        """Down alarm 30 min after Power on same site yields backup_time=00:30:00."""
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 14:00:00",
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 10:30:00",
                "cleared_on": "2025-01-01 13:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "00:30:00"
        assert result.iloc[0]["site_id"] == "SITE_A"


# ── Down outside power window ──────────────────────────────────
class TestOutsideWindow:
    def test_down_before_power_no_match(self):
        """Down alarm occurring before the Power window yields no match."""
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 14:00:00",
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 08:00:00",
                "cleared_on": "2025-01-01 09:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "04:00:00"
        assert result.iloc[0]["end_event_type"] == "Power→Cleared"

    def test_down_after_power_cleared_no_match(self):
        """Down alarm after Power cleared_on yields no match."""
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 14:00:00",
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 15:00:00",
                "cleared_on": "2025-01-01 16:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "04:00:00"
        assert result.iloc[0]["end_event_type"] == "Power→Cleared"


# ── Multiple Down alarms in same window → keep longest ─────────
class TestKeepLongest:
    def test_keeps_longest_backup_time(self):
        """Two Down alarms in same window: the later one (longer backup) is kept."""
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 18:00:00",
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 10:15:00",  # 15 min backup
                "cleared_on": "2025-01-01 12:00:00",
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 11:00:00",  # 60 min backup
                "cleared_on": "2025-01-01 14:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "01:00:00"


# ── Edge-case: no Power / no Down / empty ──────────────────────
class TestEdgeCases:
    def test_no_power_alarms(self):
        df = _make_df([
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 10:30:00",
                "cleared_on": "2025-01-01 12:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert result.empty
        assert "No Power alarms" in err

    def test_no_down_alarms(self):
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 14:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "04:00:00"
        assert result.iloc[0]["end_event_type"] == "Power→Cleared"

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result, err = compute_backup_times(df)
        assert result.empty
        assert "No data loaded" in err

    def test_empty_dataframe_with_columns(self):
        df = pd.DataFrame(columns=[
            "site_id", "occurred_on", "cleared_on",
            "alarm_category", "network_type", "vendor",
        ])
        result, err = compute_backup_times(df)
        assert result.empty
        assert "No data loaded" in err

    def test_power_without_cleared_uses_same_day_down(self):
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": None,
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 12:30:00",
                "cleared_on": "2025-01-01 13:00:00",
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-02 12:30:00",
                "cleared_on": "2025-01-02 13:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "02:30:00"
        assert result.iloc[0]["end_event_type"] == "Power→Down"


# ── Multiple sites ─────────────────────────────────────────────
class TestMultipleSites:
    def test_separate_matches_per_site(self):
        """Each site gets its own independent match."""
        df = _make_df([
            # Site A: Power + Down
            {
                "site_id": "SITE_A",
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 18:00:00",
            },
            {
                "site_id": "SITE_A",
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 10:20:00",
                "cleared_on": "2025-01-01 12:00:00",
            },
            # Site B: Power + Down (different backup time)
            {
                "site_id": "SITE_B",
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 08:00:00",
                "cleared_on": "2025-01-01 16:00:00",
            },
            {
                "site_id": "SITE_B",
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 09:00:00",
                "cleared_on": "2025-01-01 11:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 2
        sites = set(result["site_id"].tolist())
        assert sites == {"SITE_A", "SITE_B"}

        row_a = result[result["site_id"] == "SITE_A"].iloc[0]
        assert row_a["backup_time"] == "00:20:00"

        row_b = result[result["site_id"] == "SITE_B"].iloc[0]
        assert row_b["backup_time"] == "01:00:00"

    def test_cross_site_no_leak(self):
        """Down alarm on Site B must not match Power on Site A."""
        df = _make_df([
            {
                "site_id": "SITE_A",
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 18:00:00",
            },
            {
                "site_id": "SITE_B",
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 10:30:00",
                "cleared_on": "2025-01-01 12:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["site_id"] == "SITE_A"
        assert result.iloc[0]["backup_time"] == "08:00:00"
        assert result.iloc[0]["end_event_type"] == "Power→Cleared"


# ── Power alarm without cleared_on ────────────────────────────
class TestNoClearedOn:
    def test_power_without_cleared_is_dropped(self):
        """Power alarm without cleared_on can still match a same-day Down alarm."""
        df = _make_df([
            {
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": None,  # still active
            },
            {
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 10:30:00",
                "cleared_on": "2025-01-01 12:00:00",
            },
        ])
        result, err = compute_backup_times(df)
        assert err == ""
        assert len(result) == 1
        assert result.iloc[0]["backup_time"] == "00:30:00"
        assert result.iloc[0]["end_event_type"] == "Power→Down"
