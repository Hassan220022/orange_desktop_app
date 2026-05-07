"""Tests for cloud reader."""

import json
import urllib.error
from unittest.mock import MagicMock, patch


class TestFetchAlarms:
    def test_returns_dataframe_on_success(self):
        from alarm_app.data.cloud_reader import fetch_alarms_from_api

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "alarms": [
                {"site_id": "S1", "alarm_name": "Power"},
                {"site_id": "S2", "alarm_name": "Down"},
            ]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            df = fetch_alarms_from_api()
            assert df is not None
            assert len(df) == 2
            assert list(df.columns) == ["site_id", "alarm_name"]

    def test_returns_none_on_failure(self):
        from alarm_app.data.cloud_reader import fetch_alarms_from_api

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("fail"),
        ):
            df = fetch_alarms_from_api()
            assert df is None

    def test_returns_none_on_empty_response(self):
        from alarm_app.data.cloud_reader import fetch_alarms_from_api

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"alarms": []}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            df = fetch_alarms_from_api()
            assert df is None

    def test_returns_none_on_missing_key(self):
        from alarm_app.data.cloud_reader import fetch_alarms_from_api

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"error": "nope"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            df = fetch_alarms_from_api()
            assert df is None


class TestFetchValidationRun:
    def test_returns_dict_on_success(self):
        from alarm_app.data.cloud_reader import fetch_validation_run

        payload = {"run_id": 1, "overall_verdict": "pass"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_validation_run(1)
            assert result == payload

    def test_returns_none_on_failure(self):
        from alarm_app.data.cloud_reader import fetch_validation_run

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("fail"),
        ):
            result = fetch_validation_run(999)
            assert result is None
