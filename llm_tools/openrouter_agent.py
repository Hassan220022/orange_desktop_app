"""OpenRouter-backed chat agent with local read/export tools."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from .service import LocalDataService
from .tools import dispatch_tool, tool_definitions_for_openrouter


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4.1-mini"
SYSTEM_PROMPT = """You are the Alarm Viewer local data assistant.
Use tools to answer questions about local alarms, BDT validations, photos, and exports.
The tools are read-only except export_report, which may create files only in the controlled exports directory.
Prefer aggregate answers before requesting large row sets. Never claim that missing data proves a condition; say when the local store has no matching records."""


class OpenRouterAgent:
    def __init__(self, *, api_key: str, model: str = DEFAULT_MODEL, service: LocalDataService | None = None):
        self.api_key = api_key
        self.model = model
        self.service = service or LocalDataService()

    def ask(self, prompt: str, *, max_tool_rounds: int = 6) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        tools = tool_definitions_for_openrouter()

        for _ in range(max_tool_rounds):
            message = self._complete(messages, tools=tools)
            messages.append(message)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return str(message.get("content") or "")
            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                raw_args = function.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (TypeError, json.JSONDecodeError):
                    args = {}
                result = dispatch_tool(self.service, name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, default=str, ensure_ascii=False),
                })
        return "The agent reached the tool-call limit before producing a final answer."

    def _complete(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Hassan220022/orange_desktop_app",
                "X-Title": "Alarm Viewer Local Data Assistant",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter request failed: {exc.code} {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter response had no choices: {data}")
        return dict(choices[0].get("message") or {})


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(prog="alarm-app-openrouter-agent")
    parser.add_argument("prompt", nargs="*", help="Question to ask. If omitted, reads stdin.")
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY is required", file=sys.stderr)
        return 2
    prompt = " ".join(args.prompt).strip() or sys.stdin.read().strip()
    if not prompt:
        print("prompt is required", file=sys.stderr)
        return 2
    answer = OpenRouterAgent(api_key=api_key, model=args.model).ask(prompt)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
