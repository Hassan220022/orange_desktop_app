"""OpenRouter-backed chat agent with local read/export tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    from alarm_app.runtime.env import load_local_env
except ImportError:
    from runtime.env import load_local_env

from .openrouter_models import (
    DEEPSEEK_V4_PRO_MODEL,
    DEFAULT_CHAT_MODEL,
    normalize_chat_model_id,
)
from .service import (
    _LOCAL_PATH_REDACTED,
    LocalDataService,
    _looks_like_local_path,
    _sanitize_local_paths_in_text,
)
from .tools import dispatch_tool, tool_definitions_for_openrouter

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = DEFAULT_CHAT_MODEL
TOOL_CAPABLE_FALLBACK_MODEL = DEEPSEEK_V4_PRO_MODEL
LLM_RESPONSE_LOG_FILENAME = "llm_responses.jsonl"
LLM_RESPONSE_LOG_PATH_ENV = "ALARM_APP_LLM_RESPONSE_LOG_PATH"
_log = logging.getLogger(__name__)
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

CONTEXT_BUDGET_MAX_CHARS = 400_000
CONTEXT_MESSAGE_MAX_CHARS = 120_000
CONTEXT_MIN_RECENT_MESSAGES = 8
CONTEXT_TRUNCATION_MARKER = "\n\n[truncated to fit context budget]\n\n"
CONTEXT_TOO_LARGE_MESSAGE = (
    "OpenRouter request was too large after automatic context trimming. "
    "Start a new chat or ask about a narrower slice of data, and export large "
    "result sets instead of asking the assistant to repeat them."
)


def _runtime_context_message() -> str:
    local_now = datetime.now().astimezone()
    return f"Current local machine time: {local_now.isoformat(timespec='seconds')}"


def _chat_message(role: str, content: str) -> dict[str, Any]:
    return {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


PATH_KEYS = {"path", "local_path", "source_file_path", "source_path", "original_path", "file_path"}


def default_llm_response_log_path() -> Path:
    try:
        from alarm_app.logging_config import LOG_DIR
    except ImportError:
        from logging_config import LOG_DIR  # type: ignore[no-redef]
    return Path(LOG_DIR) / LLM_RESPONSE_LOG_FILENAME


def _resolve_llm_response_log_path(path: str | os.PathLike[str] | None) -> Path | None:
    if path is not None:
        return Path(path).expanduser()
    env_path = os.environ.get(LLM_RESPONSE_LOG_PATH_ENV, "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return None


def _safe_log_text(value: object) -> str:
    return _redact_model_bound_text(str(value or ""))


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append_llm_response_log(path: Path, record: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, default=str)
            handle.write("\n")
    except OSError as exc:
        _log.warning("Failed to write LLM response eval log at %s: %s", path, exc)


def _redact_model_bound_text(value: str) -> str:
    text = str(value)
    stripped = text.strip()
    if os.path.isabs(stripped) or _looks_like_local_path(stripped):
        return _LOCAL_PATH_REDACTED
    return _sanitize_local_paths_in_text(text)


def _model_safe_tool_result(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in PATH_KEYS or key_text.endswith("_path"):
                redacted[key_text] = _LOCAL_PATH_REDACTED if item else item
            else:
                redacted[key_text] = _model_safe_tool_result(item)
        return redacted
    if isinstance(value, list):
        return [_model_safe_tool_result(item) for item in value]
    if isinstance(value, str):
        return _redact_model_bound_text(value)
    return value


def _truncate_text_to_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    marker = CONTEXT_TRUNCATION_MARKER
    if max_chars <= len(marker) + 20:
        return marker.strip()[:max_chars]
    available = max_chars - len(marker)
    head_chars = max(1, available // 2)
    tail_chars = max(0, available - head_chars)
    tail = text[-tail_chars:] if tail_chars else ""
    return f"{text[:head_chars]}{marker}{tail}"


def _payload_char_count(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str,
) -> int:
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return len(json.dumps(payload, ensure_ascii=False, default=str))


def _bounded_openrouter_messages(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str,
    *,
    max_chars: int | None = None,
) -> list[dict[str, Any]]:
    budget = CONTEXT_BUDGET_MAX_CHARS if max_chars is None else max_chars
    bounded: list[dict[str, Any]] = []
    for message in messages:
        copied = dict(message)
        content = copied.get("content")
        if isinstance(content, str):
            copied["content"] = _truncate_text_to_chars(content, min(CONTEXT_MESSAGE_MAX_CHARS, budget))
        bounded.append(copied)

    if _payload_char_count(bounded, tools, model) <= budget:
        return bounded

    protected_tail_count = min(CONTEXT_MIN_RECENT_MESSAGES, max(2, len(bounded) // 2))
    protected_tail_start = max(0, len(bounded) - protected_tail_count)
    dropped: set[int] = set()
    for idx, message in enumerate(bounded):
        if idx >= protected_tail_start or idx in dropped:
            continue
        if message.get("role") == "system":
            continue
        if message.get("tool_call_id") or message.get("tool_calls"):
            continue
        dropped.add(idx)
        next_idx = idx + 1
        if next_idx < protected_tail_start:
            next_message = bounded[next_idx]
            if (
                next_message.get("role") in {"user", "assistant"}
                and not next_message.get("tool_call_id")
                and not next_message.get("tool_calls")
            ):
                dropped.add(next_idx)
        candidate = [item for item_idx, item in enumerate(bounded) if item_idx not in dropped]
        if _payload_char_count(candidate, tools, model) <= budget:
            return candidate

    bounded = [item for item_idx, item in enumerate(bounded) if item_idx not in dropped]
    while _payload_char_count(bounded, tools, model) > budget:
        largest_idx = -1
        largest_len = 0
        for idx, message in enumerate(bounded):
            content = message.get("content")
            if isinstance(content, str) and len(content) > largest_len:
                largest_idx = idx
                largest_len = len(content)
        min_content_chars = len(CONTEXT_TRUNCATION_MARKER) + 80
        if largest_idx < 0 or largest_len <= min_content_chars:
            break
        excess = _payload_char_count(bounded, tools, model) - budget
        next_limit = max(min_content_chars, largest_len - excess - 1_000)
        if next_limit >= largest_len:
            next_limit = max(min_content_chars, largest_len // 2)
        bounded[largest_idx] = dict(bounded[largest_idx])
        bounded[largest_idx]["content"] = _truncate_text_to_chars(
            str(bounded[largest_idx].get("content") or ""),
            next_limit,
        )

    if _payload_char_count(bounded, tools, model) > budget:
        raise RuntimeError(CONTEXT_TOO_LARGE_MESSAGE)
    return bounded


class OpenRouterToolSupportError(RuntimeError):
    """Raised when OpenRouter cannot route tool calls for the selected model."""


class OpenRouterAgent:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        service: LocalDataService | None = None,
        upload_allowlist: dict[str, Any] | None = None,
        response_log_path: str | os.PathLike[str] | None = None,
    ):
        self.api_key = api_key
        self.model = normalize_chat_model_id(model)
        self.service = service or LocalDataService(upload_allowlist=upload_allowlist)
        self.response_log_path = _resolve_llm_response_log_path(response_log_path)

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
        run_id = uuid4().hex
        tool_events: list[dict[str, Any]] = []

        def _emit_tool_event(event: dict[str, Any]) -> None:
            tool_events.append(_model_safe_tool_result(event))
            if on_tool_event is not None:
                on_tool_event(event)

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
                answer = str(message.get("content") or "")
                self._write_response_log(
                    run_id=run_id,
                    prompt=prompt,
                    response=answer,
                    requested_model=self.model,
                    response_model=active_model,
                    fallback_used=retried_tool_model,
                    history_turns=len(history or []),
                    summary_present=bool(summary.strip()),
                    system_context_present=bool(system_context.strip()),
                    max_tool_rounds=max_tool_rounds,
                    tool_events=tool_events,
                    finish_reason="final_answer",
                )
                return answer
            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                raw_args = function.get("arguments", {})
                if raw_args is None:
                    raw_args = {}
                args_error = ""
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except (TypeError, json.JSONDecodeError):
                    args = {}
                    args_error = "arguments must be valid JSON"
                if not args_error and not isinstance(args, dict):
                    args = {}
                    args_error = "arguments must be an object"
                _emit_tool_event({
                    "status": "running",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "args": args,
                })
                if args_error:
                    result = {"error": f"invalid arguments for {name}: {args_error}"}
                else:
                    result = dispatch_tool(self.service, name, args)
                _emit_tool_event({
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
                    "content": json.dumps(_model_safe_tool_result(result), default=str, ensure_ascii=False),
                })
        answer = "The agent reached the tool-call limit before producing a final answer."
        self._write_response_log(
            run_id=run_id,
            prompt=prompt,
            response=answer,
            requested_model=self.model,
            response_model=active_model,
            fallback_used=retried_tool_model,
            history_turns=len(history or []),
            summary_present=bool(summary.strip()),
            system_context_present=bool(system_context.strip()),
            max_tool_rounds=max_tool_rounds,
            tool_events=tool_events,
            finish_reason="tool_limit",
        )
        return answer

    def _write_response_log(
        self,
        *,
        run_id: str,
        prompt: str,
        response: str,
        requested_model: str,
        response_model: str,
        fallback_used: bool,
        history_turns: int,
        summary_present: bool,
        system_context_present: bool,
        max_tool_rounds: int,
        tool_events: list[dict[str, Any]],
        finish_reason: str,
    ) -> None:
        if self.response_log_path is None:
            return
        safe_prompt = _safe_log_text(prompt)
        safe_response = _safe_log_text(response)
        record = {
            "event": "llm_response",
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "run_id": run_id,
            "requested_model": requested_model,
            "response_model": response_model,
            "fallback_used": fallback_used,
            "finish_reason": finish_reason,
            "prompt": safe_prompt,
            "prompt_sha256": _text_sha256(safe_prompt),
            "response": safe_response,
            "response_sha256": _text_sha256(safe_response),
            "history_turns": history_turns,
            "summary_present": summary_present,
            "system_context_present": system_context_present,
            "max_tool_rounds": max_tool_rounds,
            "tool_events": tool_events,
        }
        _append_llm_response_log(self.response_log_path, record)

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
        active_model = model or self.model
        bounded_messages = _bounded_openrouter_messages(messages, tools, active_model)
        payload = {
            "model": active_model,
            "messages": bounded_messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
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
