"""Embedded local-data assistant panel with structured message rendering."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime

from PyQt5.QtCore import QEvent, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from ...llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent
    from ...runtime.env import load_local_env
except ImportError:
    try:
        from alarm_app.llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent
        from alarm_app.runtime.env import load_local_env
    except ImportError:
        from llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent  # type: ignore[no-redef]
        from runtime.env import load_local_env  # type: ignore[no-redef]


_BULLET_RE = re.compile(r"^\s*(?:[-*•])\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.*)$")
_KEY_VALUE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_ /()#%+-]{1,60})\s*:\s*(.+)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _format_inline_markdown(text: str) -> str:
    safe = html.escape(text)
    safe = _BOLD_RE.sub(r"<b>\1</b>", safe)
    safe = _INLINE_CODE_RE.sub(r"<code>\1</code>", safe)
    return safe


def _normalize_message_text(text: str) -> str:
    raw = text.strip()
    if raw.startswith("{") or raw.startswith("["):
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (TypeError, json.JSONDecodeError):
            return text
    return text


def _parse_markdown_blocks(text: str) -> list[tuple[str, str | list[str] | list[tuple[str, str]]]]:
    lines = text.splitlines()
    blocks: list[tuple[str, str | list[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            blocks.append(("code", "\n".join(code_lines)))
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            items: list[str] = []
            while i < len(lines):
                match = _BULLET_RE.match(lines[i])
                if not match:
                    break
                items.append(match.group(1).strip())
                i += 1
            blocks.append(("ul", items))
            continue

        numbered_match = _NUMBERED_RE.match(line)
        if numbered_match:
            items = []
            while i < len(lines):
                match = _NUMBERED_RE.match(lines[i])
                if not match:
                    break
                items.append(match.group(1).strip())
                i += 1
            blocks.append(("ol", items))
            continue

        key_value_match = _KEY_VALUE_RE.match(line)
        if key_value_match:
            pairs: list[tuple[str, str]] = []
            j = i
            while j < len(lines):
                match = _KEY_VALUE_RE.match(lines[j])
                if not match:
                    break
                pairs.append((match.group(1).strip(), match.group(2).strip()))
                j += 1
            if len(pairs) >= 2:
                blocks.append(("kv", pairs))
                i = j
                continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            nxt_stripped = nxt.strip()
            if (
                not nxt_stripped
                or nxt_stripped.startswith("```")
                or _BULLET_RE.match(nxt)
                or _NUMBERED_RE.match(nxt)
                or _KEY_VALUE_RE.match(nxt)
            ):
                break
            paragraph_lines.append(nxt_stripped)
            i += 1
        blocks.append(("p", " ".join(paragraph_lines)))
    return blocks


class ChatRequestThread(QThread):
    """Run one OpenRouter chat request without blocking the Qt event loop."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    tool_event = pyqtSignal(object)

    def __init__(self, *, prompt: str, model: str):
        super().__init__()
        self.prompt = prompt
        self.model = model

    def run(self):
        load_local_env()
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            self.error.emit("OPENROUTER_API_KEY is not set.")
            return
        try:
            answer = OpenRouterAgent(api_key=api_key, model=self.model).ask(
                self.prompt,
                on_tool_event=self.tool_event.emit,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(answer)


class ChatPanel(QWidget):
    """Embedded Copilot-like assistant panel for local app data."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._thread: ChatRequestThread | None = None
        self._messages: list[tuple[str, str]] = []
        self._tool_cards: dict[str, tuple[QFrame, QVBoxLayout]] = {}
        self._model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self._recommended_min_width = 350
        self._build()

    def _build(self):
        self.setObjectName("assistant_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        head = QFrame()
        head.setObjectName("assistant_toolbar")
        head_lay = QVBoxLayout(head)
        head_lay.setContentsMargins(10, 9, 10, 9)
        head_lay.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        title = QLabel("Copilot")
        title.setObjectName("assistant_title")
        title_row.addWidget(title, 1)

        self.lbl_status = QLabel(self._api_status_text())
        self.lbl_status.setObjectName("assistant_status")
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_row.addWidget(self.lbl_status)
        head_lay.addLayout(title_row)

        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(6)

        lbl_model = QLabel("Model")
        lbl_model.setObjectName("assistant_status")
        model_row.addWidget(lbl_model)

        self.edit_model = QLineEdit()
        self.edit_model.setObjectName("chat_model")
        self.edit_model.setPlaceholderText(DEFAULT_MODEL)
        self.edit_model.setText(self._model)
        self.edit_model.editingFinished.connect(self._sync_model)
        model_row.addWidget(self.edit_model, 1)
        head_lay.addLayout(model_row)

        tools_row = QHBoxLayout()
        tools_row.setContentsMargins(0, 0, 0, 0)
        tools_row.setSpacing(6)

        self.btn_sources = QPushButton("Data Sources")
        self.btn_sources.setObjectName("assistant_chip")
        self.btn_sources.clicked.connect(self.ask_data_sources)
        tools_row.addWidget(self.btn_sources)

        self.btn_alarm_stats = QPushButton("Alarm Stats")
        self.btn_alarm_stats.setObjectName("assistant_chip")
        self.btn_alarm_stats.clicked.connect(self.ask_alarm_stats)
        tools_row.addWidget(self.btn_alarm_stats)

        self.btn_clear = QPushButton("New Chat")
        self.btn_clear.setObjectName("assistant_chip")
        self.btn_clear.clicked.connect(self.clear_chat)
        tools_row.addWidget(self.btn_clear)
        head_lay.addLayout(tools_row)

        layout.addWidget(head)

        self._history_scroll = QScrollArea()
        self._history_scroll.setObjectName("assistant_history_scroll")
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.NoFrame)
        self._history_host = QWidget()
        self._history_host.setObjectName("assistant_history_host")
        self._history_layout = QVBoxLayout(self._history_host)
        self._history_layout.setContentsMargins(10, 10, 10, 10)
        self._history_layout.setSpacing(8)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_host)
        layout.addWidget(self._history_scroll, 1)

        composer = QFrame()
        composer.setObjectName("assistant_composer")
        composer_lay = QVBoxLayout(composer)
        composer_lay.setContentsMargins(10, 10, 10, 10)
        composer_lay.setSpacing(6)

        self.input = QTextEdit()
        self.input.setObjectName("chat_input")
        self.input.setPlaceholderText(
            "Ask about local alarms, BDT, photos, or exports…"
        )
        self.input.setAcceptRichText(False)
        self.input.setFixedHeight(78)
        self.input.installEventFilter(self)
        self.input.textChanged.connect(self._refresh_send_state)
        composer_lay.addWidget(self.input)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("assistant_send")
        self.btn_send.clicked.connect(self.send_current_message)
        actions.addWidget(self.btn_send)
        composer_lay.addLayout(actions)

        layout.addWidget(composer)

        self._append_system(
            "Ready. Ask naturally — I can inspect local alarm data, BDT results, photos, and exports."
        )
        self._refresh_send_state()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
                self.send_current_message()
                return True
        return super().eventFilter(obj, event)

    def _sync_model(self):
        model = (self.edit_model.text().strip() or DEFAULT_MODEL)
        self.edit_model.setText(model)
        self.set_model(model)

    def set_model(self, model: str):
        model = (model or DEFAULT_MODEL).strip()
        self._model = model
        if hasattr(self, "edit_model") and self.edit_model.text().strip() != model:
            self.edit_model.setText(model)
        self.lbl_status.setText(self._api_status_text())

    def model(self) -> str:
        return self._model

    def clear_chat(self):
        if self._thread and self._thread.isRunning():
            return
        self._messages.clear()
        self._tool_cards.clear()
        while self._history_layout.count() > 1:
            item = self._history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._append_system("Chat cleared.")

    def ask_data_sources(self):
        self.send_prompt("List the local data sources and tell me which ones have data.")

    def ask_alarm_stats(self):
        self.send_prompt("Show alarm stats summary: total, power, down, door, sites, and average duration.")

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
        self._append_message("You", text)
        self._set_busy(True)

        prompt = self._build_prompt()
        self._thread = ChatRequestThread(prompt=prompt, model=self._model)
        self._thread.tool_event.connect(self._on_tool_event)
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
        self._append_message("Assistant", answer)
        self._viewer._sbar.showMessage("Chat response received", 2500)

    def _on_error(self, error: str):
        self._append_message("Error", error)
        self._viewer._sbar.showMessage("Chat request failed", 3500)

    def _on_tool_event(self, event: object):
        if not isinstance(event, dict):
            return
        call_id = str(event.get("tool_call_id") or f"{event.get('name', 'tool')}-{len(self._tool_cards)}")
        card_data = self._tool_cards.get(call_id)
        if card_data is None:
            card = QFrame()
            card.setObjectName("tool_card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 9, 10, 10)
            card_layout.setSpacing(7)
            self._tool_cards[call_id] = (card, card_layout)
            self._history_layout.insertWidget(self._history_layout.count() - 1, card)
        else:
            card, card_layout = card_data
        if event.get("status") == "error":
            card.setObjectName("tool_card_error")
            card.style().unpolish(card)
            card.style().polish(card)
        self._render_tool_card(card_layout, event)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _render_tool_card(self, layout: QVBoxLayout, event: dict):
        self._clear_layout(layout)
        name = str(event.get("name") or "tool")
        status = str(event.get("status") or "running")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title = QLabel(self._tool_title(name))
        title.setObjectName("tool_title")
        header.addWidget(title, 1)

        status_label = QLabel(self._tool_status_text(status))
        status_label.setObjectName("tool_status_error" if status == "error" else "tool_status")
        header.addWidget(status_label)
        layout.addLayout(header)

        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        if args:
            layout.addWidget(self._make_rich_label("Input", object_name="tool_section"))
            layout.addWidget(self._kv_widget(args))

        if status == "running":
            layout.addWidget(self._make_rich_label("Running local data tool...", object_name="tool_body"))
            return

        result = event.get("result")
        if isinstance(result, dict) and "error" in result:
            layout.addWidget(self._make_rich_label(str(result.get("error")), object_name="tool_error"))
            return

        rendered = self._tool_result_widget(name, result)
        if rendered is not None:
            layout.addWidget(rendered)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            nested = item.layout()
            widget = item.widget()
            if nested is not None:
                ChatPanel._clear_layout(nested)
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _tool_title(name: str) -> str:
        return {
            "list_data_sources": "Data Sources",
            "alarm_stats": "Alarm Statistics",
            "query_alarms": "Alarm Rows",
            "query_bdt_results": "BDT Results",
            "get_bdt_detail": "BDT Detail",
            "get_photo_metadata": "Photo Metadata",
            "read_photo_blob": "Photo Blob",
            "export_report": "Export Report",
        }.get(name, name.replace("_", " ").title())

    @staticmethod
    def _tool_status_text(status: str) -> str:
        return {
            "running": "Running",
            "complete": "Complete",
            "error": "Error",
        }.get(status, status.title())

    def _tool_result_widget(self, name: str, result: object) -> QWidget | None:
        if not isinstance(result, dict):
            return self._make_rich_label(html.escape(str(result)), object_name="tool_body")
        if name == "alarm_stats":
            return self._stats_widget(result)
        if name == "list_data_sources":
            return self._data_sources_widget(result)
        if name in {"query_alarms", "query_bdt_results", "get_photo_metadata"}:
            rows = result.get("rows")
            if isinstance(rows, list):
                return self._rows_table_widget(rows)
        if name == "export_report":
            return self._kv_widget(result)
        if name == "get_bdt_detail":
            return self._bdt_detail_widget(result)
        return self._kv_widget(result)

    def _stats_widget(self, result: dict) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tool_metrics")
        grid = QGridLayout(frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        fields = [
            ("Total", result.get("total")),
            ("Power", result.get("power")),
            ("Down", result.get("down")),
            ("Door", result.get("door")),
            ("Sites", result.get("sites")),
            ("Avg Duration", result.get("avg_duration_secs")),
        ]
        for idx, (label, value) in enumerate(fields):
            cell = QFrame()
            cell.setObjectName("tool_metric")
            cell_lay = QVBoxLayout(cell)
            cell_lay.setContentsMargins(8, 6, 8, 6)
            cell_lay.setSpacing(2)
            key = QLabel(label)
            key.setObjectName("tool_metric_label")
            val = QLabel(self._format_tool_value(value))
            val.setObjectName("tool_metric_value")
            cell_lay.addWidget(key)
            cell_lay.addWidget(val)
            grid.addWidget(cell, idx // 2, idx % 2)
        return frame

    def _data_sources_widget(self, result: dict) -> QWidget:
        rows: list[dict] = []
        for source in result.get("duckdb", []) if isinstance(result.get("duckdb"), list) else []:
            rows.append({
                "source": "DuckDB",
                "path": source.get("path"),
                "rows": source.get("rows"),
                "status": source.get("error") or ("ready" if source.get("exists") else "missing"),
            })
        sqlite = result.get("sqlite")
        if isinstance(sqlite, dict):
            rows.append({
                "source": "SQLite",
                "path": sqlite.get("path"),
                "rows": sum(int(t.get("rows") or 0) for t in sqlite.get("tables", []) if isinstance(t, dict)),
                "status": sqlite.get("error") or ("ready" if sqlite.get("exists") else "missing"),
            })
        blob = result.get("blob_storage")
        if isinstance(blob, dict):
            rows.append({
                "source": "Blob Storage",
                "path": blob.get("path"),
                "rows": "",
                "status": "ready" if blob.get("exists") else "missing",
            })
        return self._rows_table_widget(rows, max_rows=6)

    def _bdt_detail_widget(self, result: dict) -> QWidget:
        bdt = result.get("bdt") if isinstance(result.get("bdt"), dict) else {}
        rules = result.get("rules") if isinstance(result.get("rules"), list) else []
        frame = QFrame()
        frame.setObjectName("tool_detail")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        lay.addWidget(self._kv_widget({
            "site_code": bdt.get("site_code"),
            "test_date": bdt.get("test_date"),
            "overall_verdict": result.get("overall_verdict"),
            "discharge_minutes": bdt.get("discharge_minutes"),
        }))
        if rules:
            lay.addWidget(self._rows_table_widget(rules, max_rows=8))
        return frame

    def _rows_table_widget(self, rows: list, *, max_rows: int = 8) -> QWidget:
        clean_rows = [r for r in rows if isinstance(r, dict)]
        if not clean_rows:
            return self._make_rich_label("No rows returned.", object_name="tool_body")
        columns = list(clean_rows[0].keys())[:6]
        table = QTableWidget(min(len(clean_rows), max_rows), len(columns))
        table.setObjectName("tool_table")
        table.setHorizontalHeaderLabels([str(c).replace("_", " ").title() for c in columns])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setMaximumHeight(220)
        for row_idx, row in enumerate(clean_rows[:max_rows]):
            for col_idx, col in enumerate(columns):
                table.setItem(row_idx, col_idx, QTableWidgetItem(self._format_tool_value(row.get(col))))
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        if len(clean_rows) > max_rows:
            wrapper = QFrame()
            wrapper.setObjectName("tool_detail")
            lay = QVBoxLayout(wrapper)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(5)
            lay.addWidget(table)
            lay.addWidget(self._make_rich_label(f"Showing {max_rows} of {len(clean_rows)} rows.", object_name="tool_body"))
            return wrapper
        return table

    def _kv_widget(self, data: dict) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tool_kv")
        grid = QGridLayout(frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        for idx, (key, value) in enumerate(data.items()):
            key_label = QLabel(str(key).replace("_", " ").title())
            key_label.setObjectName("tool_kv_key")
            value_label = QLabel(self._format_tool_value(value))
            value_label.setObjectName("tool_kv_value")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(key_label, idx, 0)
            grid.addWidget(value_label, idx, 1)
        return frame

    @staticmethod
    def _format_tool_value(value: object) -> str:
        if value is None:
            return "--"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _set_busy(self, busy: bool):
        self.btn_send.setEnabled(not busy and bool(self.input.toPlainText().strip()))
        self.btn_clear.setEnabled(not busy)
        self.btn_sources.setEnabled(not busy)
        self.btn_alarm_stats.setEnabled(not busy)
        self.edit_model.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.lbl_status.setText("Thinking..." if busy else self._api_status_text())

    def _refresh_send_state(self):
        busy = bool(self._thread and self._thread.isRunning())
        self.btn_send.setEnabled(not busy and bool(self.input.toPlainText().strip()))

    def _api_status_text(self) -> str:
        key_state = "API key ready" if os.environ.get("OPENROUTER_API_KEY", "").strip() else "API key missing"
        return f"{key_state} · Model: {self._model}"

    def _append_system(self, text: str):
        self._append_message("System", text, store=False)

    @staticmethod
    def _make_rich_label(text: str, *, object_name: str = "chat_text") -> QLabel:
        label = QLabel()
        label.setObjectName(object_name)
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setText(text)
        return label

    def _append_blocks(self, bubble_layout: QVBoxLayout, text: str):
        for kind, payload in _parse_markdown_blocks(text):
            if kind == "p":
                bubble_layout.addWidget(self._make_rich_label(_format_inline_markdown(str(payload))))
            elif kind == "ul":
                items = "".join(f"<li>{_format_inline_markdown(item)}</li>" for item in payload)
                bubble_layout.addWidget(self._make_rich_label(f"<ul style='margin:0 0 0 14px;'>{items}</ul>"))
            elif kind == "ol":
                items = "".join(f"<li>{_format_inline_markdown(item)}</li>" for item in payload)
                bubble_layout.addWidget(self._make_rich_label(f"<ol style='margin:0 0 0 14px;'>{items}</ol>"))
            elif kind == "code":
                code = html.escape(str(payload))
                bubble_layout.addWidget(self._make_rich_label(f"<pre>{code}</pre>", object_name="chat_code"))
            elif kind == "kv":
                rows = []
                for key, value in payload:
                    rows.append(
                        "<tr>"
                        f"<td style='padding:3px 10px 3px 0; vertical-align:top;'><b>{_format_inline_markdown(key)}</b></td>"
                        f"<td style='padding:3px 0; vertical-align:top;'>{_format_inline_markdown(value)}</td>"
                        "</tr>"
                    )
                bubble_layout.addWidget(
                    self._make_rich_label(
                        "<table style='border-spacing:0; width:100%;'>"
                        + "".join(rows)
                        + "</table>"
                    )
                )

    def _append_message(self, role: str, text: str, *, store: bool = True):
        role_key = role.lower()
        bubble_name = {
            "you": "chat_bubble_user",
            "assistant": "chat_bubble_assistant",
            "error": "chat_bubble_error",
            "system": "chat_bubble_system",
        }.get(role_key, "chat_bubble_assistant")
        meta_name = {
            "you": "chat_meta_user",
            "assistant": "chat_meta_assistant",
            "error": "chat_meta_error",
            "system": "chat_meta_system",
        }.get(role_key, "chat_meta_assistant")

        row = QWidget()
        row.setObjectName("chat_row")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName(bubble_name)
        if role_key == "you":
            bubble.setMaximumWidth(max(280, int(max(1, self.width()) * 0.82)))
            bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        else:
            bubble.setMaximumWidth(16777215)
            bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 9)
        bubble_layout.setSpacing(4)

        timestamp = datetime.now().strftime("%H:%M")
        meta = QLabel(f"{role} · {timestamp}")
        meta.setObjectName(meta_name)
        bubble_layout.addWidget(meta)

        normalized = _normalize_message_text(text)
        self._append_blocks(bubble_layout, normalized)

        if role_key == "you":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row_layout.addWidget(bubble, 1, Qt.AlignLeft)

        self._history_layout.insertWidget(self._history_layout.count() - 1, row)
        if store:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self._history_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
