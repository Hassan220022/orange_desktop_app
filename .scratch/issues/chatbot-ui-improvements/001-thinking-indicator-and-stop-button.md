---
title: Thinking Indicator & Stop Button
label: ready-for-agent
type: AFK
priority: P1
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 001 — Thinking Indicator & Stop Button

## Problems addressed

1. When a request is in-flight, nothing appears in the chat history. Only `lbl_status` switches to `"Thinking..."` in the header. Users can't see that anything is happening.
2. There is no way to cancel a running request. `_set_busy(True)` disables all inputs but offers no escape.

## Acceptance criteria

- [ ] When `send_prompt()` fires, a "thinking" bubble is inserted into the chat history immediately — before the response arrives. The bubble is visually distinct from user and assistant bubbles (use the existing `chat_bubble_system` style or add `chat_bubble_thinking`).
- [ ] The thinking bubble is replaced (not appended to) when `_on_answer` or `_on_error` fires.
- [ ] A **Stop** button appears in the composer row while the request is running and is hidden when idle. Clicking Stop calls `self._thread.quit()` / `self._thread.wait(timeout=2000)`, appends a system message `"Generation stopped."`, and calls `_set_busy(False)`.
- [ ] Stop button is not shown when only `_summary_thread` is running (summaries run silently in the background).
- [ ] No regression: `Ctrl+Enter` to send still works; `btn_send` re-enables when input is non-empty after stop.
- [ ] The thinking bubble is never left visible after the panel is cleared (`clear_chat`).

## Constraints

- Edit only `ui/panels/chat_panel.py` and `styles.py`.
- Do not touch `core/`, `data/`, `db/`, or `bdt/`.
- Do not change any existing `objectName` values — QSS selectors in `styles.py` must match.
- `_set_busy(True/False)` must remain the single control point for enabling/disabling inputs.
- The architecture rule: `core/` and `data/` never import from `ui/`.

## Context

Key methods to modify:

- `_build()` — add `btn_stop` to the composer actions row (hidden by default)
- `send_prompt()` — insert thinking bubble after `_append_message("You", text)`, before `self._thread.start()`
- `_on_answer()` — remove thinking bubble, insert assistant bubble
- `_on_error()` — remove thinking bubble, insert error bubble
- `_set_busy()` — show/hide `btn_stop`
- `clear_chat()` — remove any orphaned thinking bubble

Thinking bubble tracking: store a reference as `self._thinking_widget: QWidget | None = None`.
Use `self._history_layout.insertWidget(self._history_layout.count() - 1, widget)` to insert into the history (before the stretch item at the end).
Remove with `widget.deleteLater(); self._thinking_widget = None`.

The `btn_stop` QSS object name should be `"assistant_stop"`. Add a style entry in `styles.py` near the `QPushButton#assistant_send` block.

## Verification

After the change, a Python import check must pass:

```
cd /Users/mikawi/Developer/orange/alarm_app
source .venv/bin/activate 2>/dev/null || true
python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
```

No new `AttributeError` or `TypeError` at import.

---

## GPT-5.5 Agent Prompt

```
## Outcome

Add a real-time thinking indicator and a stop button to the ChatPanel in
ui/panels/chat_panel.py so users can see when the assistant is working and
cancel in-flight requests.

## Success criteria

1. A thinking widget (object name "chat_bubble_thinking") is inserted into
   _history_layout immediately when send_prompt() fires and removed when
   _on_answer() or _on_error() fires.
2. A QPushButton (object name "assistant_stop") is added to the composer
   actions row; it is visible only while _thread.isRunning(). Clicking it
   terminates the thread (quit + wait(2000)), appends a system message
   "Generation stopped.", and calls _set_busy(False).
3. clear_chat() removes any orphaned thinking widget.
4. Existing send behaviour, Ctrl+Enter shortcut, and _set_busy logic are
   unchanged.
5. python -c "from ui.panels.chat_panel import ChatPanel; print('ok')" passes
   with no exceptions.

## Constraints

- Edit only ui/panels/chat_panel.py and styles.py.
- Do not rename existing objectNames.
- _set_busy must remain the single enable/disable control point.
- No imports from core/, data/, db/, or bdt/.

## Context

File: /Users/mikawi/Developer/orange/alarm_app/ui/panels/chat_panel.py
Relevant methods: _build, send_prompt, _on_answer, _on_error, _set_busy,
clear_chat, _append_message.
Thinking widget tracking: self._thinking_widget: QWidget | None = None.
Insert into history with:
  self._history_layout.insertWidget(self._history_layout.count() - 1, widget)
Remove with: widget.deleteLater(); self._thinking_widget = None.
Style file: /Users/mikawi/Developer/orange/alarm_app/styles.py — add
"assistant_stop" button style near the "assistant_send" block.

## Verification

Run: python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
Expected output: ok
Scope: single-file edit — no full test suite required.

## Stop condition

Done when all success criteria pass and the import check succeeds.
Do not refactor other panel methods or expand to other files.
```
