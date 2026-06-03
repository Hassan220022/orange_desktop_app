---
title: Compact Model Selector
label: ready-for-agent
type: AFK
priority: P3
blocked_by: None
parent: ../../prds/chatbot-ui-improvements.md
---

# 005 — Compact Model Selector

## Problem addressed

9. At 320px width the `model_row` (`"Model" label + QComboBox`) occupies a full line of the header. Model IDs like `google/gemma-3-27b-it:free` are long. The combo's `AdjustToContents` sizing makes the panel too wide.

## Acceptance criteria

- [ ] The `model_row` is replaced by a single `QPushButton` (object name `"chat_model_btn"`) that shows the current model's **short label** (the `label` field from `OpenRouterModelOption`, truncated at 28 chars with `…`).
- [ ] Clicking `chat_model_btn` opens a `QDialog` (or `QMenu`) that lists all available model options. The user selects one and the panel's model updates identically to how it did before (calls `set_model()`).
- [ ] `self.edit_model` (the QComboBox) is removed. All existing callers of `self.edit_model` (`_populate_model_options`, `_select_model_option`, `set_model`, `_sync_model`, `_set_busy`) are updated to work with the new button-based approach.
- [ ] `self._model` still holds the current model ID. `self.model()` still returns it. `set_model()` still normalises via `normalize_chat_model_id`.
- [ ] `chat_state()` and `restore_chat_state()` are unaffected — they read/write `self._model` directly.
- [ ] `python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"` passes.
- [ ] The toolbar height decreases by one row compared to before (model + label row removed).

## Constraints

- Edit only `ui/panels/chat_panel.py` and `styles.py`.
- Do not touch `core/`, `data/`, `db/`, or `bdt/`.
- Do not change `self._model`, `self.model()`, `set_model()`, or the model normalisation logic.
- `_on_free_models_loaded` and `refresh_free_models` must still work — they populate the model list that the picker dialog/menu reads from.
- Store the model options list as `self._model_options: list[OpenRouterModelOption]` so the picker can read it at open time.

## Context

Key methods to change:

- `_build()` — remove `model_row` layout, add `chat_model_btn` QPushButton to `head_lay` or inline in the title row.
- `_populate_model_options()` — instead of filling a QComboBox, update `self._model_options` and refresh the button label.
- `_select_model_option()` — update button label only.
- `_sync_model()` — driven by the picker dialog; may be renamed or removed.
- `_set_busy()` — disable `chat_model_btn` instead of `self.edit_model`.
- `set_model()` — update `self._model` and button label.

Model picker: a simple `QDialog` with a `QListWidget` of options is sufficient.
Button label helper: `label[:28] + "…" if len(label) > 28 else label`.

## Verification

```
cd /Users/mikawi/Developer/orange/alarm_app
python -c "from ui.panels.chat_panel import ChatPanel; print('ok')"
python -c "
import ast, pathlib
src = pathlib.Path('ui/panels/chat_panel.py').read_text()
assert 'edit_model' not in src, 'old QComboBox reference remains'
print('ok')
"
```

---

## GPT-5.5 Agent Prompt

```
## Outcome

Replace the model QComboBox in ChatPanel with a compact button that opens a
model-picker dialog, reducing toolbar height and fixing narrow-panel overflow.

## Success criteria

1. self.edit_model (QComboBox) is removed. A QPushButton "chat_model_btn"
   takes its place in the header. Its label shows the current model's short
   label (≤28 chars, truncated with …).

2. Clicking chat_model_btn opens a modal QDialog with a QListWidget of
   available models. Selecting one calls set_model() with the chosen model ID.

3. self._model_options: list[OpenRouterModelOption] stores the current option
   list. _populate_model_options and _on_free_models_loaded update it.

4. _set_busy disables/enables chat_model_btn instead of edit_model.
   set_model, model(), chat_state, restore_chat_state are functionally
   unchanged.

5. python -c "from ui.panels.chat_panel import ChatPanel; print('ok')" passes.
   python -c "
   import pathlib
   src = pathlib.Path('ui/panels/chat_panel.py').read_text()
   assert 'edit_model' not in src
   print('ok')
   " passes.

## Constraints

- Edit only ui/panels/chat_panel.py and styles.py.
- Do not change self._model, model(), set_model(), normalize_chat_model_id.
- Do not touch core/, data/, db/, or bdt/.

## Context

File: /Users/mikawi/Developer/orange/alarm_app/ui/panels/chat_panel.py
Methods to update: _build, _populate_model_options, _select_model_option,
_sync_model, _set_busy, set_model.
Style file: /Users/mikawi/Developer/orange/alarm_app/styles.py — add
QPushButton#chat_model_btn style near the assistant_chip block.

## Verification

Both python commands in success criteria must pass.
Scope: single-file edit — import + attribute check only.

## Stop condition

Done when all five criteria pass. Do not refactor unrelated methods.
```
