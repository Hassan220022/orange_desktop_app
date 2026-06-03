---
title: History Dialog — Search Filter & Session Preview
label: ready-for-agent
type: AFK
priority: P3
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 006 — History Dialog: Search Filter & Session Preview

## Problem addressed

13. `ChatHistoryDialog` shows up to 50 sessions as a flat unsearchable list. With many sessions, finding a past conversation requires manual scrolling. Session entries also lack context (no last-message preview, no model badge).

## Acceptance criteria

- [ ] A `QLineEdit` search box is added at the top of `ChatHistoryDialog`. It filters the `QListWidget` in real time (case-insensitive substring match on the session title). Clearing the search restores the full list.
- [ ] Each list item label is enriched to show:
  - Title (up to 60 chars, truncated)
  - Turn count `(N turns)`
  - Saved-at date `YYYY-MM-DD HH:MM`
  - Model name (short, e.g., the last segment after `/`, up to 20 chars)
  - Example: `"Site ABC alarms (8 turns) — 2026-05-18 14:32  [gemma-3-27b]"`
- [ ] Delete and Restore still work correctly after filtering (they operate on the currently selected item in the filtered list, not the raw index).
- [ ] The dialog minimum width is increased to `520px` to accommodate the richer labels.
- [ ] `python -c "from ui.panels.chat_panel import ChatHistoryDialog; print('ok')"` passes.

## Constraints

- Edit only `ui/panels/chat_panel.py`.
- Do not touch `styles.py`, `core/`, `data/`, `db/`, or `bdt/`.
- Do not change `ChatPanel.show_chat_history()` call signature.
- `remaining_sessions()` must still return the correct (non-filtered, non-deleted) session list.

## Context

Class: `ChatHistoryDialog` starting at line ~683.
The `QListWidget` is `self._list`. Items store the session dict via `item.setData(Qt.UserRole, sess)`.
The filter should call `self._list.setRowHidden(row, not matches)` for each row rather than rebuilding the list.

Model short name helper:

```python
def _short_model(model_id: str) -> str:
    return (model_id.split("/")[-1] or model_id)[:20]
```

`remaining_sessions()` currently returns `list(self._sessions)`.
After adding filter, it should still return sessions whose items are NOT hidden AND NOT deleted — i.e., iterate `self._list` items, skip hidden rows, collect `item.data(Qt.UserRole)`.

## Verification

```
cd /Users/mikawi/Developer/orange/alarm_app
python -c "from ui.panels.chat_panel import ChatHistoryDialog; print('ok')"
```

---

## GPT-5.5 Agent Prompt

```
## Outcome

Improve ChatHistoryDialog in ui/panels/chat_panel.py with a live search
filter and richer session labels.

## Success criteria

1. A QLineEdit is added at the top of ChatHistoryDialog. Typing in it filters
   the QListWidget in real time using setRowHidden (case-insensitive substring
   match on title). Clearing restores all rows.

2. Each list item label shows:
   "Title (N turns) — YYYY-MM-DD HH:MM  [short-model]"
   where short-model is the last path segment of the model ID, up to 20 chars.

3. Restore and Delete work on the currently selected visible item regardless
   of filter state.

4. remaining_sessions() returns sessions from non-hidden, non-deleted list
   items (iterates self._list, skips hidden rows).

5. Dialog minimum width is 520px.

6. python -c "from ui.panels.chat_panel import ChatHistoryDialog; print('ok')"
   passes.

## Constraints

- Edit only ui/panels/chat_panel.py.
- Use setRowHidden for filtering — do not rebuild the list on each keystroke.
- Do not change show_chat_history() in ChatPanel or remaining_sessions()
  return type (still list[dict]).
- No changes to styles.py, core/, data/, db/, or bdt/.

## Context

File: /Users/mikawi/Developer/orange/alarm_app/ui/panels/chat_panel.py
Class: ChatHistoryDialog at ~line 683.
self._list is the QListWidget; items store session dict via Qt.UserRole.

## Verification

python -c "from ui.panels.chat_panel import ChatHistoryDialog; print('ok')"
Scope: single-class edit — import check only.

## Stop condition

Done when all six criteria pass. Do not modify ChatPanel or other classes.
```
