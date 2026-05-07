"""OpenRouter model catalog helpers for free tool-capable chat models."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
FREE_MODELS_ROUTER = "openrouter/free"


@dataclass(frozen=True)
class OpenRouterModelOption:
    id: str
    name: str
    context_length: int | None = None

    @property
    def label(self) -> str:
        if self.id == self.name:
            return self.id
        return f"{self.name} — {self.id}"


FALLBACK_FREE_MODELS: tuple[OpenRouterModelOption, ...] = (
    OpenRouterModelOption(FREE_MODELS_ROUTER, "Free Models Router"),
)


def is_free_model_id(model_id: str) -> bool:
    model = str(model_id or "").strip()
    return model == FREE_MODELS_ROUTER or model.endswith(":free")


def normalize_free_model_id(model_id: str | None) -> str:
    model = str(model_id or "").strip()
    return model if is_free_model_id(model) else FREE_MODELS_ROUTER


def fetch_free_tool_models(*, timeout: int = 20) -> list[OpenRouterModelOption]:
    """Fetch current zero-price OpenRouter models that advertise tool support."""
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={
            "Accept": "application/json",
            "HTTP-Referer": "https://github.com/Hassan220022/orange_desktop_app",
            "X-Title": "Alarm Viewer Local Data Assistant",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return list(FALLBACK_FREE_MODELS)

    rows = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return list(FALLBACK_FREE_MODELS)

    options = {FREE_MODELS_ROUTER: FALLBACK_FREE_MODELS[0]}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("id") or "").strip()
        if not model_id:
            continue
        if not _is_zero_price(row):
            continue
        if not _supports_tools(row):
            continue
        options[model_id] = OpenRouterModelOption(
            model_id,
            str(row.get("name") or model_id),
            _int_or_none(row.get("context_length")),
        )
    return sorted(
        options.values(),
        key=lambda option: (0 if option.id == FREE_MODELS_ROUTER else 1, option.name.lower()),
    )


def _supports_tools(row: dict[str, Any]) -> bool:
    params = row.get("supported_parameters")
    if isinstance(params, list) and "tools" in {str(param) for param in params}:
        return True
    architecture = row.get("architecture")
    if isinstance(architecture, dict):
        features = architecture.get("features")
        if isinstance(features, list) and "tools" in {str(feature) for feature in features}:
            return True
    return False


def _is_zero_price(row: dict[str, Any]) -> bool:
    pricing = row.get("pricing")
    if not isinstance(pricing, dict):
        return is_free_model_id(str(row.get("id") or ""))
    return _float_value(pricing.get("prompt")) == 0.0 and _float_value(pricing.get("completion")) == 0.0


def _float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
