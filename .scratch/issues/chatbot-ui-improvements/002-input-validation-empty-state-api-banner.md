---
title: Input Validation, Empty State & API Key Banner
label: ready-for-agent
type: AFK
priority: P1
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 002 — Input Validation, Empty State & API Key Banner

## Problems addressed

3. `lbl_char_count` shows `"N / 4000"` but sending is never blocked above 4000 chars — the limit is a lie.
4. When the chat has no messages the scroll area is completely blank — no onboarding hint.
5. `lbl_status` shows `"API key missing"` in 11px text at the top-right corner. Users miss it until they send and hit the warning box.

## Acceptance criteria

- [ ] `_refresh_send_state()` disables `btn_send` when `len(text) > 4000` (in addition to when text is empty or busy). The char count label turns a warning colour (use the red/error colour from the Catppuccin palette already in the theme) when over 4000.
- [ ] When `_messages` is empty and `_conversation_summary` is empty, a centred placeholder widget is visible inside `_history_host`. It shows: the "Copilot" label, a one-line description ("Ask about alarms, BDT tests, site data, or generate reports"), and three example prompt chips ("Show alarm stats", "List data sources", "Site dossier for…"). Clicking a chip calls `send_prompt()` with the chip text.
- [ ] The placeholder is removed the first time any message is appended (`_append_message`). It is re-shown when `clear_chat()` clears all messages.
- [ ] When the API key is absent, a banner `QFrame` (object name `"chat_api_banner"`) is shown inside the chat history at the top (below any existing messages, if present). The banner contains a label "OpenRouter API key is not set" and a button "Open Settings" that calls `self._viewer._open_settings()` (or equivalent). The banner is hidden/removed once a key is present (refresh on `refresh_settings()`).
- [ ] No regression to existing send logic — the only new send-block condition is `len > 4000`.

## Constraints

- Edit only `ui/panels/chat_panel.py` and `styles.py`.
- Do not touch `core/`, `data/`, `db/`, or `bdt/`.
- Do not change any existing `objectName` values.
- The API key check uses the existing `self._viewer.openrouter_api_key()` method.

## Context

Key methods:

- `_refresh_send_state()` — add length check here.
- `_append_message()` — remove the empty-state placeholder on first call.
- `clear_chat()` — re-show the empty-state placeholder after clearing.
- `refresh_settings()` — update banner visibility here.
- `_build()` — insert placeholder into `_history_host` initially; insert banner slot.

Empty-state placeholder tracking: `self._empty_state_widget: QWidget | None`.
API banner tracking: `self._api_banner_widget: QWidget | None`.

For the warning colour on over-limit char count:
The error colour is already used in `QLabel#chat_meta_error` and `QFrame#chat_bubble_error` — inspect the palette to reuse the same token rather than hard-coding a hex.

The `"Open Settings"` button should try these in order:

```python
if hasattr(self._viewer, "_open_settings"):
    self._viewer._open_settings()
elif hasattr(self._viewer, "_settings_action"):
    self._viewer._settings_action.trigger()
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

Fix three input-quality issues in ui/panels/chat_panel.py:
1. Enforce the 4000-char limit (currently cosmetic only).
2. Show an onboarding empty state when the chat history is blank.
3. Show a prominent in-chat banner when the OpenRouter API key is missing.

## Success criteria

1. _refresh_send_state disables btn_send when len(input text) > 4000.
   lbl_char_count changes to a warning colour (reuse the error colour already
   in the Catppuccin palette) when over the limit.

2. When _messages and _conversation_summary are both empty, a centred
   placeholder widget (self._empty_state_widget) is visible in _history_host.
   It has a short description and three example prompt chips. Clicking a chip
   calls send_prompt() with that chip's text. The placeholder disappears on
   the first _append_message call and reappears after clear_chat().

3. When openrouter_api_key() returns falsy, a QFrame "chat_api_banner" is
   shown in the chat history with a label and an "Open Settings" button that
   triggers the settings dialog. The banner is hidden when a key is present.
   refresh_settings() updates banner visibility.

4. python -c "from ui.panels.chat_panel import ChatPanel; print('ok')" passes.

## Constraints

- Edit only ui/panels/chat_panel.py and styles.py.
- Do not rename existing objectNames.
- Do not touch core/, data/, db/, or bdt/.
- The only new send-block condition is len > 4000; do not alter other guards.

## Context

File: /Users/mikawi/Developer/orange/alarm_app/ui/panels/chat_panel.py
Key methods: _refresh_send_state, _append_message, clear_chat,
refresh_settings, _build.
API key access: self._viewer.openrouter_api_key()
Settings trigger (try in order):
  self._viewer._open_settings() or self._viewer._settings_action.trigger()
Style file: /Users/mikawi/Developer/orange/alarm_app/styles.py

## Verification

python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
Scope: single-file edit — focused import check only.

## Stop condition

Done when all three success criteria pass and the import check succeeds.
Do not refactor other methods or expand scope.
```
