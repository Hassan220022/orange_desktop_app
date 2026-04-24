"""Interactive local-data chat panel backed by OpenRouter tools."""

from __future__ import annotations

import html
import os
from datetime import datetime

from PyQt5.QtCore import QEvent, QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from ...llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent
except ImportError:
    try:
        from alarm_app.llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent
    except ImportError:
        from llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent  # type: ignore[no-redef]


class ChatRequestThread(QThread):
    """Run one OpenRouter chat request without blocking the Qt event loop."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, *, prompt: str, model: str):
        super().__init__()
        self.prompt = prompt
        self.model = model

    def run(self):
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            self.error.emit("OPENROUTER_API_KEY is not set.")
            return
        try:
            answer = OpenRouterAgent(api_key=api_key, model=self.model).ask(self.prompt)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(answer)


class ChatPanel(QWidget):
    """Main chat workspace for asking questions about local app data."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._thread: ChatRequestThread | None = None
        self._messages: list[tuple[str, str]] = []
        self._model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("workspace_card")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(14, 12, 14, 12)
        hero_lay.setSpacing(5)

        title = QLabel("Local Data Chat")
        title.setObjectName("sidebar_title")
        hero_lay.addWidget(title)

        desc = QLabel(
            "Ask questions about alarms, BDT validations, stored photos, and exports. "
            "The agent can read local DB/blob data and create report files, but it cannot modify records."
        )
        desc.setWordWrap(True)
        desc.setObjectName("sidebar_body")
        hero_lay.addWidget(desc)
        layout.addWidget(hero)

        self.transcript = QTextBrowser()
        self.transcript.setObjectName("chat_transcript")
        self.transcript.setOpenExternalLinks(False)
        layout.addWidget(self.transcript, 1)

        composer = QFrame()
        composer.setObjectName("workspace_card")
        composer_lay = QVBoxLayout(composer)
        composer_lay.setContentsMargins(12, 12, 12, 12)
        composer_lay.setSpacing(8)

        self.input = QTextEdit()
        self.input.setObjectName("chat_input")
        self.input.setPlaceholderText(
            "Ask about local data... e.g. 'How many rejected BDT validations do we have?'"
        )
        self.input.setAcceptRichText(False)
        self.input.setFixedHeight(92)
        self.input.installEventFilter(self)
        self.input.textChanged.connect(self._refresh_send_state)
        composer_lay.addWidget(self.input)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.lbl_status = QLabel(self._api_status_text())
        self.lbl_status.setObjectName("sidebar_body")
        actions.addWidget(self.lbl_status, 1)

        self.btn_clear = QPushButton("Clear Chat")
        self.btn_clear.setObjectName("btn_dir")
        self.btn_clear.clicked.connect(self.clear_chat)
        actions.addWidget(self.btn_clear)

        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("btn_search")
        self.btn_send.clicked.connect(self.send_current_message)
        actions.addWidget(self.btn_send)

        composer_lay.addLayout(actions)
        layout.addWidget(composer)

        self._append_system(
            "Ready. Set OPENROUTER_API_KEY before sending. Use the side panel to change the model."
        )
        self._refresh_send_state()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
                self.send_current_message()
                return True
        return super().eventFilter(obj, event)

    def set_model(self, model: str):
        model = (model or DEFAULT_MODEL).strip()
        self._model = model
        self.lbl_status.setText(self._api_status_text())

    def model(self) -> str:
        return self._model

    def clear_chat(self):
        if self._thread and self._thread.isRunning():
            return
        self._messages.clear()
        self.transcript.clear()
        self._append_system("Chat cleared.")

    def ask_data_sources(self):
        self.send_prompt("List the local data sources and tell me which ones have data.")

    def send_current_message(self):
        self.send_prompt(self.input.toPlainText())

    def send_prompt(self, text: str):
        text = text.strip()
        if not text or (self._thread and self._thread.isRunning()):
            return
        if not os.environ.get("OPENROUTER_API_KEY", "").strip():
            QMessageBox.warning(
                self,
                "OpenRouter API Key Missing",
                "Set OPENROUTER_API_KEY before using the chat agent.",
            )
            self.lbl_status.setText(self._api_status_text())
            return

        self.input.clear()
        self._messages.append(("User", text))
        self._append_message("You", text, accent="#89b4fa")
        self._set_busy(True)

        prompt = self._build_prompt()
        self._thread = ChatRequestThread(prompt=prompt, model=self._model)
        self._thread.finished.connect(self._on_answer)
        self._thread.error.connect(self._on_error)
        self._thread.finished.connect(lambda _answer: self._set_busy(False))
        self._thread.error.connect(lambda _error: self._set_busy(False))
        self._thread.start()

    def _build_prompt(self) -> str:
        recent = self._messages[-10:]
        lines = [
            "You are answering inside the Alarm Viewer desktop app.",
            "Use the local tools whenever data is needed. Keep answers concise and concrete.",
            "Conversation:",
        ]
        for role, content in recent:
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _on_answer(self, answer: str):
        answer = answer.strip() or "(no answer)"
        self._messages.append(("Assistant", answer))
        self._append_message("Assistant", answer, accent="#a6e3a1")
        self._viewer._sbar.showMessage("Chat response received", 2500)

    def _on_error(self, error: str):
        self._append_message("Error", error, accent="#f38ba8")
        self._viewer._sbar.showMessage("Chat request failed", 3500)

    def _set_busy(self, busy: bool):
        self.btn_send.setEnabled(not busy and bool(self.input.toPlainText().strip()))
        self.btn_clear.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.lbl_status.setText("Thinking..." if busy else self._api_status_text())

    def _refresh_send_state(self):
        busy = bool(self._thread and self._thread.isRunning())
        self.btn_send.setEnabled(not busy and bool(self.input.toPlainText().strip()))

    def _api_status_text(self) -> str:
        key_state = "API key ready" if os.environ.get("OPENROUTER_API_KEY", "").strip() else "API key missing"
        return f"{key_state} · Model: {self._model}"

    def _append_system(self, text: str):
        self._append_message("System", text, accent="#fab387", store=False)

    def _append_message(self, role: str, text: str, *, accent: str, store: bool = True):
        timestamp = datetime.now().strftime("%H:%M")
        safe_text = html.escape(text).replace("\n", "<br>")
        safe_role = html.escape(role)
        self.transcript.append(
            "<div style='margin:10px 0; padding:10px 12px; border-radius:10px;'>"
            f"<div style='color:{accent}; font-weight:700; font-size:12px;'>{safe_role} · {timestamp}</div>"
            f"<div style='margin-top:6px;'>{safe_text}</div>"
            "</div>"
        )
        if store:
            self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())
