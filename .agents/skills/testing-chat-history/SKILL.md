---
name: testing-chat-history
description: Test Alarm Viewer Copilot Chat History archive, restore, and persistence flows end-to-end in the PyQt desktop app.
---

# Testing Chat History

Use this skill when validating changes to the Copilot panel chat history, saved sessions, chat-state persistence, or model-switch handoff UI behavior.

## Devin Secrets Needed

- `OPENROUTER_API_KEY`: Required only for live LLM requests or validating real model-switch response quality. Not required for deterministic UI archive/restore/persistence tests.

## Local GUI Setup

1. Use the repo virtualenv and parent-package import path:
   ```bash
   PYTHONPATH=/home/ubuntu/repos /home/ubuntu/repos/orange_desktop_app/.venv/bin/python ...
   ```
2. If launching the PyQt desktop app on this VM, set the PyQt plugin path before importing `alarm_app.main`. This avoids `cv2/qt/plugins` taking over Qt plugin discovery and causing an `xcb` startup failure:
   ```bash
   PYTHONPATH=/home/ubuntu/repos /home/ubuntu/repos/orange_desktop_app/.venv/bin/python - <<'PY'
   from PyQt5.QtCore import QLibraryInfo
   import os
   import alarm_app.main as app_main
   plugins = QLibraryInfo.location(QLibraryInfo.PluginsPath)
   os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = str(plugins + '/platforms')
   os.environ['QT_PLUGIN_PATH'] = str(plugins)
   os.environ['QT_QPA_PLATFORM'] = 'xcb'
   raise SystemExit(app_main.main([]))
   PY
   ```
3. Back up `~/.alarm_viewer/alarm_viewer.db` before seeding test state, then restore it after testing.

## Deterministic State Seeding

For Chat History UI tests that should not depend on OpenRouter availability, seed `chat_state` through `alarm_app.data.state.save_state()` with two messages:

```python
existing.update({
    'assistant_open': True,
    'assistant_width': 520,
    'workspace_view': 0,
    'chat_model': 'deepseek/deepseek-chat-v3-0324:free',
    'chat_state': {
        'summary': '',
        'messages': [
            {'role': 'user', 'content': 'History seed: active user question', 'timestamp': '2026-05-04T08:40:00+00:00'},
            {'role': 'assistant', 'content': 'History seed: active assistant reply', 'timestamp': '2026-05-04T08:40:01+00:00'},
        ],
        'uploaded_files': [],
        'saved_sessions': [],
    },
})
```

This lets the test prove visible rehydration, archive, restore, and relaunch persistence without making a live LLM call.

## Primary GUI Flow

Record one focused desktop session and annotate the following:

1. Launch Alarm Viewer and confirm the Copilot panel is open.
2. Verify the `Chat History` button appears below `Upload List` / `New Chat`.
3. Verify seeded bubbles are visible:
   - `History seed: active user question`
   - `History seed: active assistant reply`
4. Click `New Chat`.
   - Expected: active bubbles disappear and `Chat cleared.` appears.
5. Click `Chat History`.
   - Expected: modal titled `Chat History` lists the archived seeded session with `(2 turns)`.
6. Select the archived session and click `Restore`.
   - Expected: exact seeded user/assistant bubbles reappear.
7. Close via the app confirmation dialog, relaunch, and verify the restored bubbles remain visible.

## Evidence to Capture

- Screen recording with annotations for launch, clear/archive, history dialog, restore, and relaunch persistence.
- Full-screen screenshots:
  - initial rehydrated chat
  - cleared chat after `New Chat`
  - `Chat History` dialog with archived session
  - restored chat
  - relaunch persistence

## Useful Commands

Focused unit tests for chat/LLM behavior:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=/home/ubuntu/repos \
  /home/ubuntu/repos/orange_desktop_app/.venv/bin/python -m pytest \
  /home/ubuntu/repos/orange_desktop_app/tests/test_chat_panel.py \
  /home/ubuntu/repos/orange_desktop_app/tests/test_llm_tools.py
```

Syntax check for edited chat files:

```bash
/home/ubuntu/repos/orange_desktop_app/.venv/bin/python -m compileall \
  /home/ubuntu/repos/orange_desktop_app/ui/panels/chat_panel.py \
  /home/ubuntu/repos/orange_desktop_app/tests/test_chat_panel.py
```
