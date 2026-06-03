---
title: Error Retry Button & Message Actions Cleanup
label: ready-for-agent
type: AFK
priority: P2
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 003 — Error Retry Button & Message Actions Cleanup

## Problems addressed

5. Error bubbles show a `Copy` button but no way to retry the failed prompt. Users must retype.
6. System messages (`"Chat cleared."`, `"Chat session restored"`, upload confirmations) each get a `Copy` button footer. This is noise for informational messages.

## Acceptance criteria

- [ ] Error bubbles get a **Retry** button (next to Copy) in `_message_actions_widget`. Clicking Retry calls `self.send_prompt(last_user_text)` where `last_user_text` is the most recent user message in `self._messages`. If `_messages` is empty the button is disabled.
- [ ] `_message_actions_widget` returns an empty/invisible widget (or `None` is handled) for `role == "system"`. System messages have no footer action row.
- [ ] `_message_actions_widget` is unchanged for `role == "you"` and `role == "assistant"`.
- [ ] The Retry button is disabled (not hidden) while `_thread.isRunning()` — consistent with all other controls.
- [ ] No regression to `_on_error` behaviour: error message is still stored and displayed correctly.

## Constraints

- Edit only `ui/panels/chat_panel.py`.
- Do not touch `styles.py`, `core/`, `data/`, `db/`, or `bdt/`.
- Do not change any existing `objectName` values.
- `send_prompt()` is the only entry point for retrying — do not duplicate its logic.

## Context

Key methods:

- `_message_actions_widget(role, text)` — current implementation at line ~2341. Returns a `QFrame` with a `Copy` button always. Needs role-awareness.
- `_on_error(error)` — currently appends `_chat_message("assistant", ...)` and calls `_append_message("Error", error)`. The last user message is always `self._messages[-2]` if the error message was appended, or find it by scanning `self._messages` for `role == "user"` from the end.
- `_append_message(role, text)` — calls `_message_actions_widget(role, normalized)`. Passes `role` already.

Retry button retrieves last user prompt:

```python
last_user = next(
    (m["content"] for m in reversed(self._messages) if m.get("role") == "user"),
    None
)
```

## Verification

```
cd /Users/mikawi/Developer/orange/alarm_app
python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
```

---

## GPT-5.5 Agent Prompt

```
## Outcome

Improve message action buttons in ChatPanel (ui/panels/chat_panel.py):
1. Add a Retry button to error bubbles so users can re-send without retyping.
2. Remove the Copy button footer from system informational messages.

## Success criteria

1. _message_actions_widget returns a widget with Copy + Retry for role "error".
   Retry's on-click retrieves the last user message from self._messages and
   calls self.send_prompt(last_user_text). If no user message exists, Retry
   is disabled. Retry is also disabled while _thread.isRunning().

2. _message_actions_widget returns an empty QWidget (no visible buttons) for
   role "system".

3. Behaviour for roles "you" and "assistant" is unchanged (Copy only).

4. python -c "from ui.panels.chat_panel import ChatPanel; print('ok')" passes.

## Constraints

- Edit only ui/panels/chat_panel.py.
- Do not rename existing objectNames.
- Do not duplicate send_prompt logic — call it directly.
- No changes to styles.py, core/, data/, db/, or bdt/.

## Context

File: /Users/mikawi/Developer/orange/alarm_app/ui/panels/chat_panel.py
Key method: _message_actions_widget(self, role, text) at ~line 2341.
Last user message retrieval:
  next((m["content"] for m in reversed(self._messages)
        if m.get("role") == "user"), None)

## Verification

python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
Scope: single-method edit — import check only.

## Stop condition

Done when success criteria pass and import check succeeds.
Do not refactor other methods or expand scope.
```
