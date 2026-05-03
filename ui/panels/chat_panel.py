"""Embedded local-data assistant panel with structured message rendering."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QEvent, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
    from ...llm_tools.openrouter_models import (
        FALLBACK_FREE_MODELS,
        OpenRouterModelOption,
        fetch_free_tool_models,
        normalize_free_model_id,
    )
    from ...runtime.env import load_local_env
except ImportError:
    try:
        from alarm_app.llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent
        from alarm_app.llm_tools.openrouter_models import (
            FALLBACK_FREE_MODELS,
            OpenRouterModelOption,
            fetch_free_tool_models,
            normalize_free_model_id,
        )
        from alarm_app.runtime.env import load_local_env
    except ImportError:
        from llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent  # type: ignore[no-redef]
        from llm_tools.openrouter_models import (  # type: ignore[no-redef]
            FALLBACK_FREE_MODELS,
            OpenRouterModelOption,
            fetch_free_tool_models,
            normalize_free_model_id,
        )
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


def _photo_group_summary(rows: list[dict]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        category = str(row.get("slot_category") or "other").strip().lower() or "other"
        counts[category] = counts.get(category, 0) + 1
    return ", ".join(f"{category}: {count}" for category, count in sorted(counts.items()))


def _json_output_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _output_paths(value: object) -> list[str]:
    paths: list[str] = []

    def visit(node: object):
        if isinstance(node, dict):
            for key, child in node.items():
                if key in {"path", "export_path", "local_path", "source_file_path"} and child:
                    paths.append(str(child))
                else:
                    visit(child)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _make_assistant_button(text: str, *, minimum_width: int = 0) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("assistant_chip")
    button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    if minimum_width:
        button.setMinimumWidth(minimum_width)
    return button


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


class FreeModelsThread(QThread):
    """Fetch OpenRouter's current free tool-capable model list off the UI thread."""

    finished = pyqtSignal(object)

    def run(self):
        self.finished.emit(fetch_free_tool_models())


class ChatPanel(QWidget):
    """Embedded Copilot-like assistant panel for local app data."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._thread: ChatRequestThread | None = None
        self._messages: list[tuple[str, str]] = []
        self._tool_cards: dict[str, tuple[QFrame, QVBoxLayout]] = {}
        self._uploaded_files: list[dict[str, str]] = []
        self._models_thread: FreeModelsThread | None = None
        self._model = normalize_free_model_id(os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
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

        self.edit_model = QComboBox()
        self.edit_model.setObjectName("chat_model")
        self.edit_model.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._populate_model_options(list(FALLBACK_FREE_MODELS))
        self.edit_model.currentIndexChanged.connect(self._sync_model)
        model_row.addWidget(self.edit_model, 1)
        head_lay.addLayout(model_row)

        tools_grid = QGridLayout()
        tools_grid.setContentsMargins(0, 0, 0, 0)
        tools_grid.setHorizontalSpacing(6)
        tools_grid.setVerticalSpacing(6)

        self.btn_sources = _make_assistant_button("Data Sources", minimum_width=118)
        self.btn_sources.clicked.connect(self.ask_data_sources)
        tools_grid.addWidget(self.btn_sources, 0, 0)

        self.btn_alarm_stats = _make_assistant_button("Alarm Stats", minimum_width=118)
        self.btn_alarm_stats.clicked.connect(self.ask_alarm_stats)
        tools_grid.addWidget(self.btn_alarm_stats, 0, 1)

        self.btn_upload = _make_assistant_button("Upload List", minimum_width=118)
        self.btn_upload.clicked.connect(self.upload_list)
        tools_grid.addWidget(self.btn_upload, 1, 0)

        self.btn_clear = _make_assistant_button("New Chat", minimum_width=118)
        self.btn_clear.clicked.connect(self.clear_chat)
        tools_grid.addWidget(self.btn_clear, 1, 1)
        tools_grid.setColumnStretch(0, 1)
        tools_grid.setColumnStretch(1, 1)
        head_lay.addLayout(tools_grid)

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
        self.refresh_free_models()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
                self.send_current_message()
                return True
        return super().eventFilter(obj, event)

    def _sync_model(self):
        model = normalize_free_model_id(self.edit_model.currentData() or self.edit_model.currentText())
        self.set_model(model)

    def set_model(self, model: str):
        model = normalize_free_model_id(model)
        self._model = model
        if hasattr(self, "edit_model"):
            self._select_model_option(model)
        self.lbl_status.setText(self._api_status_text())

    def model(self) -> str:
        return self._model

    def clear_chat(self):
        if self._thread and self._thread.isRunning():
            return
        self._messages.clear()
        self._tool_cards.clear()
        self._uploaded_files.clear()
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

    def refresh_free_models(self):
        if self._models_thread and self._models_thread.isRunning():
            return
        self._models_thread = FreeModelsThread()
        self._models_thread.finished.connect(self._on_free_models_loaded)
        self._models_thread.start()

    def _on_free_models_loaded(self, options: object):
        if isinstance(options, list) and options:
            clean = [option for option in options if isinstance(option, OpenRouterModelOption)]
            if clean:
                self._populate_model_options(clean)

    def _populate_model_options(self, options: list[OpenRouterModelOption]):
        current = self._model
        self.edit_model.blockSignals(True)
        self.edit_model.clear()
        seen: set[str] = set()
        for option in options:
            if option.id in seen:
                continue
            seen.add(option.id)
            self.edit_model.addItem(option.label, option.id)
        if current not in seen:
            self.edit_model.addItem(current, current)
        self._select_model_option(current)
        self.edit_model.blockSignals(False)

    def _select_model_option(self, model: str):
        idx = self.edit_model.findData(model)
        if idx < 0:
            self.edit_model.addItem(model, model)
            idx = self.edit_model.findData(model)
        if idx >= 0 and self.edit_model.currentIndex() != idx:
            self.edit_model.blockSignals(True)
            self.edit_model.setCurrentIndex(idx)
            self.edit_model.blockSignals(False)

    def upload_list(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Upload VIP / Site / Accepted PM List",
            "",
            "Data lists (*.xlsx *.xls *.csv);;Excel files (*.xlsx *.xls);;CSV files (*.csv)",
        )
        if not path:
            return
        file_path = Path(path).expanduser()
        upload = {
            "name": file_path.name,
            "path": str(file_path),
            "kind": "uploaded_list",
        }
        self._uploaded_files.append(upload)
        self._append_system(
            "Uploaded list available to the assistant tools:\n"
            f"Name: {upload['name']}\n"
            f"Path: {upload['path']}\n"
            "Ask me to generate a VIP site alarm report, Accepted PM report, or BDT export from it."
        )
        self.input.setFocus(Qt.OtherFocusReason)

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
            "For generated files, call export_report instead of describing a manual process.",
            "Supported export_report report_type values include alarms, bdt_results, photo_manifest, site_alarm_report, accepted_pm_report, and bdt_export.",
            "Use site_alarm_report for uploaded VIP/site lists, accepted_pm_report for uploaded Accepted PM lists, and bdt_export for BDT validation workbook exports.",
            "Use get_site_dossier when the user asks for everything about one site: all alarms, BDT tests, rule details, photos, and discharge content.",
            "Use generate_graph when the user asks for graphs/charts/trends; it creates a PNG chart from local data.",
        ]
        if self._uploaded_files:
            lines.append("Uploaded local files available to tools:")
            for idx, upload in enumerate(self._uploaded_files[-5:], start=1):
                lines.append(f"{idx}. {upload['name']} -> {upload['path']}")
            lines.append("When using an uploaded file, pass its path as source_file_path.")
        lines.append("Conversation:")
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
        layout.addWidget(self._tool_actions_widget(event))

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
            "get_site_dossier": "Site Dossier",
            "generate_graph": "Generated Graph",
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
        if name == "get_photo_metadata":
            rows = result.get("rows")
            if isinstance(rows, list):
                return self._photo_metadata_widget(rows)
        if name in {"query_alarms", "query_bdt_results"}:
            rows = result.get("rows")
            if isinstance(rows, list):
                return self._rows_table_widget(rows, source_name=name)
        if name == "get_site_dossier":
            return self._site_dossier_widget(result)
        if name == "generate_graph":
            return self._graph_widget(result)
        if name == "export_report":
            return self._kv_widget(result)
        if name == "get_bdt_detail":
            return self._bdt_detail_widget(result)
        return self._kv_widget(result)

    def _tool_actions_widget(self, event: dict) -> QWidget:
        result = event.get("result")
        frame = QFrame()
        frame.setObjectName("tool_detail")
        row = QGridLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(6)
        index = 0

        btn_copy = _make_assistant_button("Copy Output")
        btn_copy.clicked.connect(lambda _checked=False, payload=result: self._copy_text(_json_output_text(payload)))
        row.addWidget(btn_copy, index // 3, index % 3)
        index += 1

        btn_save = _make_assistant_button("Export Output")
        btn_save.clicked.connect(lambda _checked=False, payload=result: self._save_text_output(payload))
        row.addWidget(btn_save, index // 3, index % 3)
        index += 1

        paths = [path for path in _output_paths(result) if Path(path).exists()]
        if paths:
            btn_open = _make_assistant_button("Open")
            btn_open.clicked.connect(lambda _checked=False, p=paths[0]: self._open_path(p))
            row.addWidget(btn_open, index // 3, index % 3)
            index += 1

            btn_folder = _make_assistant_button("Open Folder")
            btn_folder.clicked.connect(lambda _checked=False, p=paths[0]: self._open_folder(p))
            row.addWidget(btn_folder, index // 3, index % 3)
            index += 1

            btn_path = _make_assistant_button("Copy Path")
            btn_path.clicked.connect(lambda _checked=False, p="\n".join(paths): self._copy_text(p))
            row.addWidget(btn_path, index // 3, index % 3)

        for col in range(3):
            row.setColumnStretch(col, 1)
        return frame

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

    def _photo_metadata_widget(self, rows: list) -> QWidget:
        clean_rows = [row for row in rows if isinstance(row, dict)]
        if not clean_rows:
            return self._make_rich_label("No photo records returned.", object_name="tool_body")

        frame = QFrame()
        frame.setObjectName("tool_detail")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._make_rich_label(
            f"{len(clean_rows)} photo records. {_photo_group_summary(clean_rows)}",
            object_name="tool_body",
        ))

        grid_frame = QFrame()
        grid_frame.setObjectName("tool_metrics")
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        shown = 0
        for row in clean_rows:
            path = str(row.get("local_path") or "")
            pixmap = QPixmap(path)
            if pixmap.isNull():
                continue
            card = QPushButton()
            card.setObjectName("tool_metric")
            card.setCursor(Qt.PointingHandCursor)
            card.setToolTip(path)
            card.clicked.connect(lambda _checked=False, p=path: self._open_photo_preview(p))
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(8, 8, 8, 8)
            card_lay.setSpacing(5)
            image = QLabel()
            image.setAlignment(Qt.AlignCenter)
            image.setPixmap(pixmap.scaled(150, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            caption = QLabel(
                f"{row.get('slot_category') or 'photo'} · slot {row.get('slot_index') or '--'}\n"
                f"{str(row.get('test_date') or '')[:10]}"
            )
            caption.setObjectName("tool_metric_label")
            caption.setAlignment(Qt.AlignCenter)
            card_lay.addWidget(image)
            card_lay.addWidget(caption)
            grid.addWidget(card, shown // 3, shown % 3)
            shown += 1
            if shown >= 12:
                break
        if shown:
            lay.addWidget(grid_frame)
            if len(clean_rows) > shown:
                lay.addWidget(self._make_rich_label(f"Showing {shown} thumbnail(s) of {len(clean_rows)} records.", object_name="tool_body"))
        else:
            lay.addWidget(self._make_rich_label("No local image files were available for thumbnails.", object_name="tool_body"))
        lay.addWidget(self._rows_table_widget(clean_rows, max_rows=6))
        return frame

    def _open_photo_preview(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Image Missing", f"Could not load image:\n{path}")
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle(Path(path).name)
        dialog.setText(path)
        screen = QApplication.primaryScreen()
        max_width = 900
        max_height = 700
        if screen is not None:
            size = screen.availableGeometry().size()
            max_width = min(max_width, int(size.width() * 0.75))
            max_height = min(max_height, int(size.height() * 0.75))
        dialog.setIconPixmap(pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        dialog.exec_()

    def _copy_text(self, text: str):
        QApplication.clipboard().setText(text)
        self._viewer._sbar.showMessage("Copied to clipboard", 2500)

    def _save_text_output(self, payload: object):
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Assistant Output",
            str(Path.home() / "assistant-output.json"),
            "JSON files (*.json);;Text files (*.txt)",
        )
        if not path:
            return
        out_path = Path(path)
        text = _json_output_text(payload)
        out_path.write_text(text, encoding="utf-8")
        self._viewer._sbar.showMessage(f"Exported assistant output to {out_path}", 3500)

    def _open_path(self, path: str):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path))))

    def _open_folder(self, path: str):
        target = Path(path)
        folder = target if target.is_dir() else target.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _site_dossier_widget(self, result: dict) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tool_detail")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        lay.addWidget(self._kv_widget({
            "site_code": result.get("site_code"),
            "alarm_total": result.get("alarm_total"),
            "bdt_total": result.get("bdt_total"),
            "export_path": result.get("export_path"),
        }))
        alarm_rows = result.get("alarm_rows")
        if isinstance(alarm_rows, list) and alarm_rows:
            lay.addWidget(self._make_rich_label("Alarm Preview", object_name="tool_section"))
            lay.addWidget(self._rows_table_widget(alarm_rows, max_rows=8, source_name="query_alarms"))
        bdt_rows = result.get("bdt_rows")
        if isinstance(bdt_rows, list) and bdt_rows:
            lay.addWidget(self._make_rich_label("BDT Preview", object_name="tool_section"))
            lay.addWidget(self._rows_table_widget(bdt_rows, max_rows=8, source_name="query_bdt_results"))
        return frame

    def _graph_widget(self, result: dict) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tool_detail")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        path = str(result.get("path") or "")
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            label = QLabel()
            label.setObjectName("tool_body")
            label.setAlignment(Qt.AlignCenter)
            label.setPixmap(pixmap.scaledToWidth(520, Qt.SmoothTransformation))
            lay.addWidget(label)
        lay.addWidget(self._kv_widget({
            "path": path,
            "graph_type": result.get("graph_type"),
            "points": result.get("points"),
        }))
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

    def _rows_table_widget(self, rows: list, *, max_rows: int = 8, source_name: str = "") -> QWidget:
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
        table.setProperty("assistant_rows", clean_rows[:max_rows])
        table.setProperty("assistant_source", source_name)
        table.cellClicked.connect(lambda row, _col, tbl=table: self._activate_tool_table_row(tbl, row))
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

    def _activate_tool_table_row(self, table: QTableWidget, row_index: int):
        rows = table.property("assistant_rows")
        source = str(table.property("assistant_source") or "")
        if not isinstance(rows, list) or row_index < 0 or row_index >= len(rows):
            return
        row = rows[row_index]
        if not isinstance(row, dict):
            return
        if source == "query_bdt_results" or "validation_run_id" in row or "bdt_test_id" in row:
            self._open_bdt_from_assistant_row(row)
            return
        if source == "query_alarms" or {"site_id", "occurred_on"} & set(row):
            self._open_alarm_from_assistant_row(row)

    def _open_bdt_from_assistant_row(self, row: dict):
        viewer = self._viewer
        if hasattr(viewer, "_set_workspace_view"):
            viewer._set_workspace_view(1)
        target_run_id = str(row.get("validation_run_id") or "").strip()
        target_bdt_id = str(row.get("bdt_test_id") or "").strip()
        target_site = str(row.get("site_code") or "").strip().upper()
        target_date = str(row.get("test_date") or "")[:10]
        panel = getattr(viewer, "_bdt_validation_panel", None)
        if panel is None:
            return
        results = list(getattr(viewer, "_bdt_results", []) or [])
        match_index = -1
        for idx, result in enumerate(results):
            result_run_id = str(getattr(result, "validation_run_id", "") or getattr(result, "run_id", "") or "")
            bdt = getattr(result, "bdt_data", None)
            result_bdt_id = str(getattr(bdt, "id", "") or getattr(result, "bdt_test_id", "") or "")
            result_site = str(getattr(result, "site_code", "") or "").strip().upper()
            result_date = str(getattr(result, "test_date", "") or "")[:10]
            if target_run_id and result_run_id == target_run_id:
                match_index = idx
                break
            if target_bdt_id and result_bdt_id == target_bdt_id:
                match_index = idx
                break
            if target_site and target_date and result_site == target_site and result_date == target_date:
                match_index = idx
                break
        if match_index < 0:
            viewer._sbar.showMessage("BDT row is not currently loaded in the validation table", 3500)
            return
        page_size = max(int(getattr(panel, "_bdt_page_size", 500)), 1)
        panel._bdt_page_offset = (match_index // page_size) * page_size
        panel.bdt_search.clear()
        panel._populate_bdt_table()
        visible_row = match_index - panel._bdt_page_offset
        if 0 <= visible_row < panel.bdt_table.rowCount():
            panel.bdt_table.selectRow(visible_row)
            panel._on_bdt_row_clicked(panel.bdt_table.model().index(visible_row, 0))
            viewer._sbar.showMessage("Opened BDT validation from assistant output", 2500)

    def _open_alarm_from_assistant_row(self, row: dict):
        viewer = self._viewer
        if hasattr(viewer, "_set_workspace_view"):
            viewer._set_workspace_view(0)
        site = str(row.get("site_id") or "").strip()
        if hasattr(viewer, "_site_input") and site:
            viewer._site_input.setText(site)
        if hasattr(viewer, "_load_alarm_page"):
            viewer._page_offset = 0
            viewer._load_alarm_page(offset=0, status_message="Opened alarm context from assistant output")
        self._select_alarm_row_from_assistant(row)

    def _select_alarm_row_from_assistant(self, row: dict):
        model = getattr(self._viewer, "_model", None)
        table = getattr(self._viewer, "_table", None)
        df = getattr(model, "_df", None)
        if df is None or table is None or getattr(df, "empty", True):
            return
        candidates = df.copy()
        for col in ("site_id", "alarm_id", "alarm_name", "occurred_on"):
            if col in row and col in candidates.columns and row.get(col) not in (None, ""):
                left = candidates[col].astype(str).str[:19]
                right = str(row.get(col))[:19]
                candidates = candidates[left == right]
        if candidates.empty:
            return
        idx = int(candidates.index[0])
        table.selectRow(idx)
        table.scrollTo(model.index(idx, 0))
        self._viewer._sbar.showMessage("Opened alarm row from assistant output", 2500)

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
        self.btn_upload.setEnabled(not busy)
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
        bubble_layout.addWidget(self._message_actions_widget(role, normalized))

        if role_key == "you":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row_layout.addWidget(bubble, 1, Qt.AlignLeft)

        self._history_layout.insertWidget(self._history_layout.count() - 1, row)
        if store:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _message_actions_widget(self, role: str, text: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tool_detail")
        row = QGridLayout(frame)
        row.setContentsMargins(0, 4, 0, 0)
        row.setHorizontalSpacing(6)
        row.setVerticalSpacing(6)

        btn_copy = _make_assistant_button("Copy")
        btn_copy.clicked.connect(lambda _checked=False, t=text: self._copy_text(t))
        row.addWidget(btn_copy, 0, 0)

        btn_save = _make_assistant_button("Export")
        btn_save.clicked.connect(lambda _checked=False, r=role, t=text: self._save_message_output(r, t))
        row.addWidget(btn_save, 0, 1)

        row.setColumnStretch(0, 1)
        row.setColumnStretch(1, 1)
        return frame

    def _save_message_output(self, role: str, text: str):
        default_name = f"assistant-{role.lower()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Message",
            str(Path.home() / default_name),
            "Text files (*.txt);;Markdown files (*.md)",
        )
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self._viewer._sbar.showMessage(f"Exported message to {path}", 3500)

    def _scroll_to_bottom(self):
        bar = self._history_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
