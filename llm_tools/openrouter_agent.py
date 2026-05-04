"""OpenRouter-backed chat agent with local read/export tools."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

try:
    from alarm_app.runtime.env import load_local_env
except ImportError:
    from runtime.env import load_local_env  # type: ignore[no-redef]

from .service import LocalDataService
from .tools import dispatch_tool, tool_definitions_for_openrouter
from .openrouter_models import FREE_MODELS_ROUTER, normalize_free_model_id


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = FREE_MODELS_ROUTER
TOOL_CAPABLE_FALLBACK_MODEL = FREE_MODELS_ROUTER
SYSTEM_PROMPT = """You are the Alarm Viewer local data assistant.
Use tools to answer questions about local alarms, BDT validations, photos, and exports.
The tools are read-only except export_report, which may create files only in the controlled exports directory.

IMPORTANT RULES:
1. ALWAYS call a tool to check the database before answering any question about data. Never answer from memory or assumptions.
2. When the user asks to "show", "list", "display", or "get" items, keep the text answer brief and let the UI render the returned rows separately.
3. Provide aggregate summaries only when the user explicitly asks for "stats", "summary", or "count".
4. Never claim that missing data proves a condition; say when the local store has no matching records.
5. The alarm rows card starts collapsed and can expand up to 100 rows.
6. Use query_backup_times for questions about backup time, backup duration, or battery hold-up between Power and Down alarms.
7. Use the host clock context for any time-sensitive answer."""

SUMMARY_SYSTEM_PROMPT = """You compress Alarm Viewer assistant conversations.
Preserve all user goals, key facts, tool findings, decisions, generated files,
uploaded files, unresolved questions, and the most recent active topic.
Be dense and specific. Do not invent facts."""


def _runtime_context_message() -> str:
    local_now = datetime.now().astimezone()
    return f"Current local machine time: {local_now.isoformat(timespec='seconds')}"


def _chat_message(role: str, content: str) -> dict[str, Any]:
    return {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


class OpenRouterToolSupportError(RuntimeError):
    """Raised when OpenRouter cannot route tool calls for the selected model."""


class OpenRouterAgent:
    def __init__(self, *, api_key: str, model: str = DEFAULT_MODEL, service: LocalDataService | None = None):
        self.api_key = api_key
        self.model = normalize_free_model_id(model)
        self.service = service or LocalDataService()

    def ask(
        self,
        prompt: str,
        *,
        history: list[dict[str, Any]] | None = None,
        summary: str = "",
        system_context: str = "",
        max_tool_rounds: int = 6,
        on_tool_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": _runtime_context_message()},
        ]
        if system_context.strip():
            messages.append({"role": "system", "content": system_context.strip()})
        if summary.strip():
            messages.append({"role": "system", "content": f"Conversation summary:\n{summary.strip()}"})
        messages.extend(self._normalized_history(history or []))
        messages.append({"role": "user", "content": prompt})
        tools = tool_definitions_for_openrouter()

        active_model = self.model
        retried_tool_model = False

        for _ in range(max_tool_rounds):
            try:
                message = self._complete(messages, tools=tools, model=active_model)
            except OpenRouterToolSupportError:
                if retried_tool_model or active_model == TOOL_CAPABLE_FALLBACK_MODEL:
                    raise RuntimeError(
                        "The selected OpenRouter model/provider does not support tool use. "
                        f"Set OPENROUTER_MODEL={TOOL_CAPABLE_FALLBACK_MODEL} or choose a model from "
                        "OpenRouter's tool-calling collection."
                    ) from None
                active_model = TOOL_CAPABLE_FALLBACK_MODEL
                retried_tool_model = True
                continue
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
                if on_tool_event is not None:
                    on_tool_event({
                        "status": "running",
                        "tool_call_id": call.get("id"),
                        "name": name,
                        "args": args,
                    })
                result = dispatch_tool(self.service, name, args)
                if on_tool_event is not None:
                    on_tool_event({
                        "status": "error" if isinstance(result, dict) and "error" in result else "complete",
                        "tool_call_id": call.get("id"),
                        "name": name,
                        "args": args,
                        "result": result,
                    })
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, default=str, ensure_ascii=False),
                })
        return "The agent reached the tool-call limit before producing a final answer."

    def summarize_history(
        self,
        messages: list[dict[str, Any]],
        *,
        existing_summary: str = "",
        model: str | None = None,
    ) -> str:
        transcript = self._transcript(messages)
        if not transcript and not existing_summary.strip():
            return ""
        prompt = (
            "Existing summary:\n"
            f"{existing_summary.strip() or '(none)'}\n\n"
            "New conversation turns to absorb:\n"
            f"{transcript or '(none)'}\n\n"
            "Return one updated handoff summary. End with the most recent active topic."
        )
        response = self._complete(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            tools=[],
            model=model or self.model,
        )
        return str(response.get("content") or "").strip()

    @staticmethod
    def _normalized_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        expected = "user"
        for item in history:
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant"} or role != expected:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            normalized.append({"role": role, "content": content})
            expected = "assistant" if expected == "user" else "user"
        return normalized

    @staticmethod
    def _transcript(messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for item in messages:
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            timestamp = str(item.get("timestamp") or "").strip()
            prefix = role.title()
            if timestamp:
                prefix = f"{prefix} [{timestamp}]"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

    def _complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model": model or self.model,
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
            if exc.code == 404 and "support tool use" in body:
                raise OpenRouterToolSupportError(body) from exc
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
    load_local_env()
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
