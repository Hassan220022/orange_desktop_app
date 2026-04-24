"""Sidebar controls for the local data chat workspace."""

from __future__ import annotations

import os

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from ...llm_tools.openrouter_agent import DEFAULT_MODEL
except ImportError:
    try:
        from alarm_app.llm_tools.openrouter_agent import DEFAULT_MODEL
    except ImportError:
        from llm_tools.openrouter_agent import DEFAULT_MODEL  # type: ignore[no-redef]


class ChatWorkspacePanel(QWidget):
    """Side view for configuring and driving the chat agent."""

    def __init__(self, viewer, chat_panel, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._chat_panel = chat_panel
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(12)

        brand = QLabel("Orange Workspace")
        brand.setObjectName("sidebar_brand")
        lay.addWidget(brand)

        sec = QLabel("LOCAL DATA CHAT")
        sec.setObjectName("lbl_section")
        lay.addWidget(sec)

        title = QLabel("Ask the app data")
        title.setObjectName("sidebar_title")
        title.setWordWrap(True)
        lay.addWidget(title)

        summary = QLabel(
            "Chat with an OpenRouter model that can query local alarms, BDT results, photo metadata, and exports."
        )
        summary.setWordWrap(True)
        summary.setObjectName("sidebar_body")
        lay.addWidget(summary)

        model_card = QFrame()
        model_card.setObjectName("workspace_card")
        model_lay = QVBoxLayout(model_card)
        model_lay.setContentsMargins(12, 12, 12, 12)
        model_lay.setSpacing(8)

        model_title = QLabel("Model")
        model_title.setObjectName("workspace_card_title")
        model_lay.addWidget(model_title)

        self.edit_model = QLineEdit()
        self.edit_model.setPlaceholderText(DEFAULT_MODEL)
        self.edit_model.setText(os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
        self.edit_model.editingFinished.connect(self._sync_model)
        model_lay.addWidget(self.edit_model)
        lay.addWidget(model_card)

        status_card = QFrame()
        status_card.setObjectName("workspace_card")
        status_lay = QVBoxLayout(status_card)
        status_lay.setContentsMargins(12, 12, 12, 12)
        status_lay.setSpacing(8)

        status_title = QLabel("Connection")
        status_title.setObjectName("workspace_card_title")
        status_lay.addWidget(status_title)

        self.lbl_key = QLabel(self._key_status())
        self.lbl_key.setWordWrap(True)
        self.lbl_key.setObjectName("sidebar_body")
        status_lay.addWidget(self.lbl_key)

        btn_refresh = QPushButton("Refresh Status")
        btn_refresh.setObjectName("btn_dir")
        btn_refresh.clicked.connect(self._refresh_status)
        status_lay.addWidget(btn_refresh)
        lay.addWidget(status_card)

        actions_card = QFrame()
        actions_card.setObjectName("workspace_card")
        actions_lay = QVBoxLayout(actions_card)
        actions_lay.setContentsMargins(12, 12, 12, 12)
        actions_lay.setSpacing(8)

        actions_title = QLabel("Workflow")
        actions_title.setObjectName("workspace_card_title")
        actions_lay.addWidget(actions_title)

        btn_sources = QPushButton("Check Data Sources")
        btn_sources.setObjectName("btn_search")
        btn_sources.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_sources.clicked.connect(self._chat_panel.ask_data_sources)
        actions_lay.addWidget(btn_sources)

        btn_clear = QPushButton("New Chat")
        btn_clear.setObjectName("btn_dir")
        btn_clear.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_clear.clicked.connect(self._chat_panel.clear_chat)
        actions_lay.addWidget(btn_clear)
        lay.addWidget(actions_card)

        context_card = QFrame()
        context_card.setObjectName("workspace_card")
        context_lay = QVBoxLayout(context_card)
        context_lay.setContentsMargins(12, 12, 12, 12)
        context_lay.setSpacing(6)

        context_title = QLabel("Access")
        context_title.setObjectName("workspace_card_title")
        context_lay.addWidget(context_title)

        context = QLabel(
            "Read-only tools can inspect DuckDB alarms, SQLite BDT metadata, stored blob metadata, and create controlled exports."
        )
        context.setWordWrap(True)
        context.setObjectName("sidebar_body")
        context_lay.addWidget(context)
        lay.addWidget(context_card)

        lay.addStretch()

        self._adaptive_primary_buttons = [btn_refresh, btn_sources, btn_clear]
        self._refresh_responsive_metrics()

    def _sync_model(self):
        model = self.edit_model.text().strip() or DEFAULT_MODEL
        self.edit_model.setText(model)
        self._chat_panel.set_model(model)

    def _refresh_status(self):
        self._sync_model()
        self.lbl_key.setText(self._key_status())

    def _key_status(self) -> str:
        return (
            "OPENROUTER_API_KEY is set. Chat requests can run."
            if os.environ.get("OPENROUTER_API_KEY", "").strip()
            else "OPENROUTER_API_KEY is missing. Set it before sending chat requests."
        )

    def _refresh_responsive_metrics(self):
        primary_height = 0
        content_width = 0
        for btn in getattr(self, "_adaptive_primary_buttons", []):
            fm = btn.fontMetrics()
            primary_height = max(primary_height, int(fm.height() * 2.25))
            content_width = max(content_width, fm.horizontalAdvance(btn.text()) + 56)
        primary_height = max(primary_height, 40)
        for btn in getattr(self, "_adaptive_primary_buttons", []):
            btn.setMinimumHeight(primary_height)

        model_width = self.edit_model.fontMetrics().horizontalAdvance(self.edit_model.text() or DEFAULT_MODEL) + 60
        self._recommended_min_width = max(320, min(560, max(content_width + 24, model_width + 40)))
        self.setMinimumWidth(self._recommended_min_width)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {QEvent.FontChange, QEvent.StyleChange, QEvent.PaletteChange}:
            self._refresh_responsive_metrics()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_responsive_metrics()
