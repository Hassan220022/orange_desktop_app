---
title: Message Rendering Fixes (Timestamps, Headings, Table Border)
label: ready-for-agent
type: AFK
priority: P2
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 004 — Message Rendering Fixes

## Problems addressed

6. Timestamps are stored in `_chat_message()` but discarded on rehydration — every message shows the current time when the app is reopened, not the original send time.
7. Markdown headings (`##`, `###`) are parsed as plain paragraphs by `_parse_markdown_blocks`. LLM responses frequently use headings.
8. The markdown table cell border uses a hard-coded hex colour `#2a4060` in Python — invisible on light themes and doesn't match the palette.

## Acceptance criteria

- [ ] `_append_message(role, text, *, store=True)` gains an optional `timestamp: str | None = None` parameter. When provided, it is shown in the bubble meta label instead of `datetime.now()`. Existing callers that omit it are unaffected.
- [ ] `_rehydrate_history()` passes `item.get("timestamp")` as the `timestamp` kwarg when calling `_append_message`.
- [ ] `_parse_markdown_blocks()` recognises lines starting with `#`, `##`, or `###` (with a space after) and emits a new block type `("h1"|"h2"|"h3", text_content)`.
- [ ] `_append_blocks()` renders heading blocks as `<span>` with scaled font sizes: h1=16px bold, h2=14px bold, h3=13px bold (using inline style within the RichLabel HTML, consistent with how `<ul>` and `<ol>` are currently rendered).
- [ ] The table cell border in `_append_blocks` uses `border: 1px solid {palette_border}` where `palette_border` is replaced by a reference to the same border token already used in `QFrame#chat_bubble_assistant` — not a hard-coded hex. Implementation: replace the inline hex with a CSS variable or, simpler, use `#tool_table`'s `gridline-color` equivalent by reading it from `QApplication.palette()` or just using the existing `chat_table` QLabel border colour via `objectName="chat_table"` on a wrapper.
  - Simplest acceptable fix: change the hard-coded `#2a4060` to `currentColor` or use `palette().mid().color().name()` at render time.
- [ ] `python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"` passes.

## Constraints

- Edit only `ui/panels/chat_panel.py`.
- Do not touch `styles.py`, `core/`, `data/`, `db/`, or `bdt/`.
- Do not change existing `objectName` values.
- The `timestamp` parameter must be keyword-only and default to `None` so no existing call sites break.

## Context

Key methods:

- `_chat_message(role, content)` at top of file — already includes `"timestamp": datetime.now().isoformat()`.
- `_append_message(role, text, *, store=True)` at line ~2269 — shows `datetime.now().strftime("%H:%M")` unconditionally.
- `_rehydrate_history()` at line ~1283 — calls `_append_message("user"/"assistant", content)` without timestamp.
- `_parse_markdown_blocks(text)` at line ~150.
- `_append_blocks(bubble_layout, text)` at line ~2214.
- The hard-coded border: search for `#2a4060` in the file.

Heading detection regex: `r'^(#{1,3})\s+(.+)$'`
Block type emitted: `("h1", text)`, `("h2", text)`, or `("h3", text)` based on the number of `#` chars.

## Verification

```
cd /Users/mikawi/Developer/orange/alarm_app
python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
# Also verify no hard-coded hex remains:
python -c "
import re, pathlib
src = pathlib.Path('ui/panels/chat_panel.py').read_text()
assert '#2a4060' not in src, 'hard-coded colour still present'
print('colour check ok')
"
```

---

## GPT-5.5 Agent Prompt

```
## Outcome

Fix three message rendering issues in ui/panels/chat_panel.py:
1. Preserve original send timestamps through session save/restore.
2. Parse and render markdown headings (##, ###).
3. Remove the hard-coded table cell border colour #2a4060.

## Success criteria

1. _append_message gains an optional keyword-only timestamp: str | None = None
   parameter. When provided, the bubble meta label shows it instead of
   datetime.now(). _rehydrate_history passes item.get("timestamp") as this
   kwarg. All existing callers without the kwarg are unaffected.

2. _parse_markdown_blocks recognises lines matching r'^(#{1,3})\s+(.+)$' and
   emits ("h1"|"h2"|"h3", text) blocks. _append_blocks renders them as inline
   HTML with font sizes: h1=16px bold, h2=14px bold, h3=13px bold.

3. The string "#2a4060" no longer appears in the file. Replace it with
   QApplication.palette().mid().color().name() or an equivalent themed value.

4. python -c "from ui.panels.chat_panel import ChatPanel; print('ok')" passes.
   python -c "
   import pathlib
   src = pathlib.Path('ui/panels/chat_panel.py').read_text()
   assert '#2a4060' not in src
   print('ok')
   " passes.

## Constraints

- Edit only ui/panels/chat_panel.py.
- timestamp param must be keyword-only (after *) and default None.
- Do not rename existing objectNames.
- No changes to styles.py, core/, data/, db/, or bdt/.

## Context

File: /Users/mikawi/Developer/orange/alarm_app/ui/panels/chat_panel.py
_append_message at ~line 2269; _rehydrate_history at ~line 1283;
_parse_markdown_blocks at ~line 150; _append_blocks at ~line 2214.
Hard-coded colour: search for #2a4060.

## Verification

Both python commands in the Success criteria section must pass.
Scope: single-file edit — no full test suite required.

## Stop condition

Done when all four success criteria pass. Do not refactor other methods.
```
