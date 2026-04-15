"""Cloud data reader -- fetch alarm data from the API instead of local DB."""

import json
import logging
import os
import urllib.error
import urllib.request

import pandas as pd

_log = logging.getLogger(__name__)
BACKEND_URL = os.environ.get("ALARM_SYNC_URL", "http://127.0.0.1:8787")


def fetch_alarms_from_api() -> pd.DataFrame | None:
    """Fetch alarm records from the cloud API.

    Returns a DataFrame matching the local schema, or None on failure.
    """
    url = f"{BACKEND_URL}/v1/alarms/query"

    try:
        req = urllib.request.Request(
            url, method="GET", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "alarms" in data and data["alarms"]:
                return pd.DataFrame(data["alarms"])
    except Exception:
        _log.warning("Failed to fetch alarms from API", exc_info=True)
    return None


def fetch_validation_run(run_id: int) -> dict | None:
    """Fetch a single PM validation run from the API."""
    url = f"{BACKEND_URL}/v1/pm/runs/{run_id}"

    try:
        req = urllib.request.Request(
            url, method="GET", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        _log.warning("Failed to fetch validation run from API", exc_info=True)
        return None
