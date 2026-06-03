---
title: Style Polish (Qt Uppercase, Tool Card Margins, Composer Separator)
label: ready-for-agent
type: AFK
priority: P3
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 007 — Style Polish

## Problems addressed

8. `QLabel#tool_section` in `styles.py` has `text-transform: uppercase` — this CSS property has **no effect** in Qt's QSS. The section labels render in lowercase/mixed case.
9. Same as 8 — the `.upper()` call is missing from Python code that sets section label text.
10. `QFrame#tool_card` has `margin: 2px 0px` which gives very little breathing room between consecutive tool result cards.
11. `QFrame#assistant_composer` and `QFrame#assistant_toolbar` share the same background, causing the two sections to visually merge at the bottom of the panel.

## Acceptance criteria

- [ ] Every call to `_make_rich_label(text, object_name="tool_section")` in `chat_panel.py` has `text.upper()` applied before passing to the label. Section labels like `"Input"`, `"Alarm Preview"`, `"BDT Preview"` render in ALL CAPS at runtime.
- [ ] `QLabel#tool_section` in `styles.py` has the `text-transform: uppercase` line **removed** (it was dead code).
- [ ] `QFrame#tool_card` margin in `styles.py` is changed from `2px 0px` to `6px 0px`.
- [ ] `QFrame#assistant_composer` gets a visual separator from `assistant_toolbar`: add `margin-top: 4px` to its style in `styles.py` (or a 1px top border using the existing border-colour token).
- [ ] `python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"` passes after both file edits.

## Constraints

- Edit only `ui/panels/chat_panel.py` and `styles.py`.
- Do not touch `core/`, `data/`, `db/`, or `bdt/`.
- Do not change any existing `objectName` values.
- Only add `.upper()` to calls where `object_name="tool_section"` — do not uppercase other labels.

## Context

In `chat_panel.py`, search for all occurrences of `object_name="tool_section"`:

```python
layout.addWidget(self._make_rich_label("Input", object_name="tool_section"))
layout.addWidget(self._make_rich_label("Alarm Preview", object_name="tool_section"))
# ... etc
```

Each must become `self._make_rich_label("Input".upper(), ...)` or equivalently add the `.upper()` inline.

In `styles.py`:

- Remove `text-transform: uppercase;` from `QLabel#tool_section` block (line ~709).
- Change `margin: 2px 0px;` to `margin: 6px 0px;` in `QFrame#tool_card` (line ~666).
- Add `margin-top: 4px;` to `QFrame#assistant_composer` block or split it from `QFrame#assistant_toolbar, QFrame#assistant_composer` into a separate rule.

## Verification

```
cd /Users/mikawi/Developer/orange/alarm_app
python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
python -c "
import pathlib
css = pathlib.Path('styles.py').read_text()
assert 'text-transform' not in css, 'dead text-transform still present'
print('ok')
"
```

---

## GPT-5.5 Agent Prompt

```
## Outcome

Fix four visual/style issues in ui/panels/chat_panel.py and styles.py:
1. Section labels (tool_section) must render in UPPERCASE at runtime.
2. Remove the dead text-transform CSS property from styles.py.
3. Increase tool card vertical margin from 2px to 6px.
4. Add visual separation between assistant_toolbar and assistant_composer.

## Success criteria

1. Every _make_rich_label call with object_name="tool_section" in
   chat_panel.py has .upper() applied to the text argument.

2. The string "text-transform" no longer appears in styles.py.

3. QFrame#tool_card margin in styles.py is "6px 0px" (was "2px 0px").

4. QFrame#assistant_composer in styles.py has margin-top: 4px (either as a
   standalone rule or by splitting it from the combined toolbar rule).

5. python -c "from ui.panels.chat_panel import ChatPanel; print('ok')" passes.
   python -c "
   import pathlib
   css = pathlib.Path('styles.py').read_text()
   assert 'text-transform' not in css
   print('ok')
   " passes.

## Constraints

- Edit only ui/panels/chat_panel.py and styles.py.
- Only add .upper() where object_name="tool_section". No other labels.
- Do not rename objectNames or change any selector logic.
- No changes to core/, data/, db/, or bdt/.

## Context

chat_panel.py: search for object_name="tool_section" to find all call sites.
styles.py: QLabel#tool_section at ~line 704; QFrame#tool_card at ~line 662;
QFrame#assistant_toolbar, QFrame#assistant_composer combined rule at ~line 530.

## Verification

Both python commands in success criteria must pass.
Scope: two-file edit — import + string check only.

## Stop condition

Done when all five criteria pass. Do not refactor other styles or methods.
```
