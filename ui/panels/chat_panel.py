"""Embedded local-data assistant panel with structured message rendering."""

from __future__ import annotations

import html
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QDate, QEvent, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
    from alarm_app.constants import DISPLAY_COLUMNS
    from alarm_app.llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent, _chat_message
    from alarm_app.llm_tools.openrouter_models import (
        FALLBACK_FREE_MODELS,
        OpenRouterModelOption,
        fetch_free_tool_models,
        normalize_free_model_id,
    )
    from alarm_app.ui.flow_layout import FlowLayout
except ImportError:
    from constants import DISPLAY_COLUMNS
    from llm_tools.openrouter_agent import DEFAULT_MODEL, OpenRouterAgent, _chat_message
    from llm_tools.openrouter_models import (
        FALLBACK_FREE_MODELS,
        OpenRouterModelOption,
        fetch_free_tool_models,
        normalize_free_model_id,
    )
    from ui.flow_layout import FlowLayout

_BULLET_RE = re.compile(r"^\s*(?:[-*•])\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.*)$")
_KEY_VALUE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_ /()#%+-]{1,60})\s*:\s*(.+)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\|\s*(:?-+:?\s*\|\s*)+$")
MAX_SAVED_SESSIONS = 50
CHAT_SUMMARY_TRIGGER_TURNS = 14
CHAT_SUMMARY_BATCH_TURNS = 6


def _format_inline_markdown(text: str) -> str:
    safe = html.escape(text)
    safe = _BOLD_RE.sub(r"<b>\1</b>", safe)
    safe = _INLINE_CODE_RE.sub(r"<code>\1</code>", safe)
    return safe


def _parse_table_cells(row: str) -> list[str]:
    """Parse a markdown table row into cell contents."""
    # Remove leading/trailing | and split by |
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _strip_table_blocks(text: str) -> str:
    blocks = _parse_markdown_blocks(text)
    if not any(kind == "table" for kind, _payload in blocks):
        return text
    pieces: list[str] = []
    for kind, payload in blocks:
        if kind == "table":
            continue
        if kind == "p":
            pieces.append(str(payload))
        elif kind == "ul":
            pieces.extend(f"- {item}" for item in payload)
        elif kind == "ol":
            pieces.extend(f"1. {item}" for item in payload)
        elif kind == "code":
            pieces.append(f"```\n{payload}\n```")
        elif kind == "kv":
            pieces.extend(f"{key}: {value}" for key, value in payload)
    cleaned = "\n".join(pieces).strip()
    return cleaned or "(rows shown below)"


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

        # Table detection: lines starting and ending with |
        if _TABLE_ROW_RE.match(line):
            table_lines: list[str] = []
            while i < len(lines):
                tbl_line = lines[i]
                if _TABLE_ROW_RE.match(tbl_line):
                    table_lines.append(tbl_line)
                    i += 1
                else:
                    break
            # Filter out separator lines (|---|---|)
            table_rows = [ln for ln in table_lines if not _TABLE_SEP_RE.match(ln)]
            if table_rows:
                blocks.append(("table", table_rows))
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
                or _TABLE_ROW_RE.match(nxt)
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


class _ZoomableImageView(QGraphicsView):
    """Graphics view with mouse-wheel zoom and reset support."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self._scale_factor = 1.0
        self._min_scale = 0.25
        self._max_scale = 4.0
        self._did_initial_fit = False

    def _fit_initial(self):
        if self.viewport().width() <= 0 or self.viewport().height() <= 0:
            return
        self.fitInView(self._item, Qt.KeepAspectRatio)
        self._scale_factor = 1.0

    def reset_zoom(self):
        self.resetTransform()
        self._fit_initial()
        self.centerOn(self._item)

    def zoom(self, factor: float):
        new_scale = self._scale_factor * factor
        if new_scale < self._min_scale or new_scale > self._max_scale:
            return
        self.scale(factor, factor)
        self._scale_factor = new_scale

    def zoom_in(self):
        self.zoom(1.2)

    def zoom_out(self):
        self.zoom(1 / 1.2)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._did_initial_fit:
            self._fit_initial()
            self.centerOn(self._item)
            self._did_initial_fit = True


class _ImagePreviewDialog(QDialog):
    """Zoomable preview for generated charts and local images."""

    def __init__(self, image_path: str, *, title: str | None = None, parent=None):
        super().__init__(parent)
        self._path = str(image_path)
        self.setWindowTitle(title or Path(self._path).name)
        self.setMinimumSize(860, 640)

        pixmap = QPixmap(self._path)
        if pixmap.isNull():
            raise ValueError(f"Could not load image: {self._path}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        btn_zoom_in = _make_assistant_button("Zoom In")
        btn_zoom_out = _make_assistant_button("Zoom Out")
        btn_reset = _make_assistant_button("Reset")
        btn_open = _make_assistant_button("Open File")
        toolbar.addWidget(btn_zoom_in)
        toolbar.addWidget(btn_zoom_out)
        toolbar.addWidget(btn_reset)
        toolbar.addStretch(1)
        toolbar.addWidget(btn_open)
        layout.addLayout(toolbar)

        info = QLabel(self._path)
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.setObjectName("tool_body")
        layout.addWidget(info)

        self._view = _ZoomableImageView(pixmap, self)
        self._view.setObjectName("image_preview_view")
        layout.addWidget(self._view, 1)

        btn_zoom_in.clicked.connect(self._view.zoom_in)
        btn_zoom_out.clicked.connect(self._view.zoom_out)
        btn_reset.clicked.connect(self._view.reset_zoom)
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._path)))


def _make_assistant_button(text: str, *, minimum_width: int = 0) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("assistant_chip")
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(max(32, button.fontMetrics().height() + 14))
    button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    if minimum_width:
        button.setMinimumWidth(minimum_width)
    return button


def _rows_preview_limit(total_rows: int, requested_rows: int, *, max_rows: int = 100) -> int:
    if total_rows <= 0:
        return 0
    requested_rows = max(1, requested_rows)
    return min(total_rows, max_rows, requested_rows)


def _rows_summary_text(visible: int, total: int, max_visible: int) -> str:
    if total <= visible:
        return f"Showing all {total} rows."
    if max_visible <= 100:
        return f"Showing {visible} of {total} rows. Expand to 100 rows if needed."
    return f"Showing {visible} of {total} rows."


def _alarm_row_columns(rows: list[dict], source_name: str = "") -> list[str]:
    if not rows:
        return []
    if source_name == "query_alarms" or any("alarm_id" in row or "alarm_name" in row for row in rows):
        return [name for name, _label in DISPLAY_COLUMNS]
    return list(rows[0].keys())


def _set_combo_text(combo: object, text: str):
    if combo is None or not hasattr(combo, "findText") or not hasattr(combo, "setCurrentIndex"):
        return
    idx = combo.findText(text)
    if idx >= 0:
        if hasattr(combo, "blockSignals"):
            combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        if hasattr(combo, "blockSignals"):
            combo.blockSignals(False)


class ChatRequestThread(QThread):
    """Run one OpenRouter chat request without blocking the Qt event loop."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    tool_event = pyqtSignal(object)

    def __init__(
        self,
        *,
        prompt: str,
        model: str,
        api_key: str,
        history: list[dict] | None = None,
        summary: str = "",
        system_context: str = "",
    ):
        super().__init__()
        self.prompt = prompt
        self.model = model
        self.api_key = api_key
        self.history = list(history or [])
        self.summary = summary
        self.system_context = system_context

    def run(self):
        api_key = self.api_key.strip()
        if not api_key:
            self.error.emit("OpenRouter API key is not set in Settings.")
            return
        try:
            answer = OpenRouterAgent(api_key=api_key, model=self.model).ask(
                self.prompt,
                history=self.history,
                summary=self.summary,
                system_context=self.system_context,
                on_tool_event=self.tool_event.emit,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(answer)


class ChatSummaryThread(QThread):
    """Compact older chat turns without blocking the Qt event loop."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, *, messages: list[dict], existing_summary: str, model: str, api_key: str):
        super().__init__()
        self.messages = list(messages)
        self.existing_summary = existing_summary
        self.model = model
        self.api_key = api_key

    def run(self):
        api_key = self.api_key.strip()
        if not api_key:
            self.error.emit("OpenRouter API key is not set in Settings.")
            return
        try:
            summary = OpenRouterAgent(api_key=api_key, model=self.model).summarize_history(
                self.messages,
                existing_summary=self.existing_summary,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(summary)


class FreeModelsThread(QThread):
    """Fetch OpenRouter's current free tool-capable model list off the UI thread."""

    finished = pyqtSignal(object)

    def run(self):
        self.finished.emit(fetch_free_tool_models())



class ChatHistoryDialog(QDialog):
    """Lists saved chat sessions and lets the user restore one."""

    session_selected = pyqtSignal(dict)

    def __init__(self, sessions: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat History")
        self.setMinimumSize(420, 340)
        self._sessions = list(sessions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        if not self._sessions:
            layout.addWidget(QLabel("No saved conversations yet."))
        else:
            self._list = QListWidget()
            self._list.setObjectName("chat_history_list")
            for sess in self._sessions:
                title = str(sess.get("title") or "Untitled chat")
                ts = str(sess.get("saved_at") or "")
                turn_count = len(sess.get("messages") or [])
                label = f"{title}  ({turn_count} turns)"
                if ts:
                    label += f"  —  {ts[:16]}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, sess)
                self._list.addItem(item)
            self._list.itemDoubleClicked.connect(self._on_double_click)
            layout.addWidget(self._list, 1)

        buttons = QDialogButtonBox()
        self._btn_restore = buttons.addButton("Restore", QDialogButtonBox.AcceptRole)
        self._btn_delete = buttons.addButton("Delete", QDialogButtonBox.DestructiveRole)
        buttons.addButton(QDialogButtonBox.Close)
        self._btn_restore.setEnabled(bool(self._sessions))
        self._btn_delete.setEnabled(bool(self._sessions))
        buttons.accepted.connect(self._restore_selected)
        buttons.rejected.connect(self.reject)
        self._btn_delete.clicked.connect(self._delete_selected)
        layout.addWidget(buttons)

    def _restore_selected(self):
        if not hasattr(self, "_list"):
            return
        item = self._list.currentItem()
        if item is None and self._list.count():
            item = self._list.item(0)
        if item is None:
            return
        self.session_selected.emit(item.data(Qt.UserRole))
        self.accept()

    def _on_double_click(self, item: QListWidgetItem):
        self.session_selected.emit(item.data(Qt.UserRole))
        self.accept()

    def _delete_selected(self):
        if not hasattr(self, "_list"):
            return
        row = self._list.currentRow()
        if row < 0:
            return
        self._list.takeItem(row)
        if 0 <= row < len(self._sessions):
            self._sessions.pop(row)
        self._btn_restore.setEnabled(self._list.count() > 0)
        self._btn_delete.setEnabled(self._list.count() > 0)

    def remaining_sessions(self) -> list[dict]:
        return list(self._sessions)


class ChatPanel(QWidget):
    """Embedded Copilot-like assistant panel for local app data."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._thread: ChatRequestThread | None = None
        self._summary_thread: ChatSummaryThread | None = None
        self._messages: list[dict[str, str]] = []
        self._conversation_summary = ""
        self._tool_cards: dict[str, tuple[QFrame, QVBoxLayout]] = {}
        self._pending_tool_events: dict[str, dict] = {}
        self._pending_tool_order: list[str] = []
        self._pending_tool_seq = 0
        self._uploaded_files: list[dict[str, str]] = []
        self._saved_sessions: list[dict] = []
        self._models_thread: FreeModelsThread | None = None
        self._model = DEFAULT_MODEL
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
        self.lbl_status.setMinimumWidth(0)
        self.lbl_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
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
        self.edit_model.setMinimumWidth(0)
        self.edit_model.setSizeAdjustPolicy(QComboBox.AdjustToContents)
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

        self.btn_history = _make_assistant_button("Chat History", minimum_width=118)
        self.btn_history.clicked.connect(self.show_chat_history)
        tools_grid.addWidget(self.btn_history, 2, 0, 1, 2)

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

        self._adaptive_buttons = [
            self.btn_sources,
            self.btn_alarm_stats,
            self.btn_upload,
            self.btn_clear,
            self.btn_history,
            self.btn_send,
        ]
        self._refresh_responsive_metrics()
        self._refresh_send_state()
        self.refresh_free_models()

    def _refresh_responsive_metrics(self):
        content_width = 0
        content_height = 0
        for btn in getattr(self, "_adaptive_buttons", []):
            fm = btn.fontMetrics()
            content_width = max(content_width, fm.horizontalAdvance(btn.text()) + 42)
            content_height = max(content_height, int(fm.height() * 2.2))
        content_height = max(content_height, 30)
        for btn in getattr(self, "_adaptive_buttons", []):
            btn.setMinimumHeight(content_height)
        two_column_tools = (content_width * 2) + 48
        self._recommended_min_width = max(310, two_column_tools)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {QEvent.FontChange, QEvent.StyleChange, QEvent.PaletteChange}:
            self._refresh_responsive_metrics()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_responsive_metrics()
        if hasattr(self, "_history_scroll"):
            bar = self._history_scroll.verticalScrollBar()
            if bar.value() >= bar.maximum() - 8:
                self._schedule_scroll_to_bottom()

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
        if model != self._model:
            self._prepare_model_switch(model)
        self._model = model
        if hasattr(self, "edit_model"):
            self._select_model_option(model)
        self.lbl_status.setText(self._api_status_text())

    def model(self) -> str:
        return self._model

    def clear_chat(self):
        if self._thread and self._thread.isRunning():
            return
        if self._summary_thread and self._summary_thread.isRunning():
            return
        self._archive_current_session()
        self._messages.clear()
        self._conversation_summary = ""
        self._tool_cards.clear()
        self._pending_tool_events.clear()
        self._pending_tool_order.clear()
        self._pending_tool_seq = 0
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

    def show_chat_history(self):
        if self._chat_work_in_progress():
            self._viewer._sbar.showMessage("Wait for the current chat task to finish before opening history.", 3500)
            return
        original_ids = {str(session.get("id") or "") for session in self._saved_sessions}
        dialog = ChatHistoryDialog(self._saved_sessions, parent=self)
        dialog.session_selected.connect(self._restore_session)
        dialog.exec_()
        remaining = dialog.remaining_sessions()
        remaining_ids = {str(session.get("id") or "") for session in remaining}
        archived_now = [
            session for session in self._saved_sessions
            if str(session.get("id") or "") not in original_ids | remaining_ids
        ]
        self._saved_sessions = (archived_now + remaining)[:MAX_SAVED_SESSIONS]

    def _chat_work_in_progress(self) -> bool:
        try:
            thread = self._thread
        except (AttributeError, RuntimeError):
            thread = None
        if thread is not None and thread.isRunning():
            return True
        try:
            summary_thread = self._summary_thread
        except (AttributeError, RuntimeError):
            summary_thread = None
        return bool(summary_thread is not None and summary_thread.isRunning())

    def _archive_current_session(self):
        if not self._messages:
            return
        first_user = next(
            (m["content"] for m in self._messages if m.get("role") == "user"),
            "Untitled chat",
        )
        title = (first_user[:60] + "…") if len(first_user) > 60 else first_user
        session = {
            "id": str(uuid.uuid4()),
            "title": title,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "messages": list(self._messages),
            "summary": self._conversation_summary,
            "uploaded_files": list(self._uploaded_files),
            "model": self._model,
        }
        self._saved_sessions.insert(0, session)
        self._saved_sessions = self._saved_sessions[:MAX_SAVED_SESSIONS]

    def _restore_session(self, session: dict):
        if self._chat_work_in_progress():
            self._viewer._sbar.showMessage("Wait for the current chat task to finish before restoring history.", 3500)
            return
        self._archive_current_session()
        self._messages.clear()
        self._conversation_summary = ""
        self._tool_cards.clear()
        self._pending_tool_events.clear()
        self._pending_tool_order.clear()
        self._pending_tool_seq = 0
        self._uploaded_files.clear()
        while self._history_layout.count() > 1:
            item = self._history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.restore_chat_state(session)
        self._viewer._sbar.showMessage("Chat session restored", 2500)

    def refresh_free_models(self):
        if self._models_thread and self._models_thread.isRunning():
            return
        self._models_thread = FreeModelsThread()
        self._models_thread.finished.connect(self._on_free_models_loaded)
        self._models_thread.start()

    def chat_state(self) -> dict[str, object]:
        return {
            "summary": self._conversation_summary,
            "messages": list(self._messages),
            "uploaded_files": list(self._uploaded_files),
            "saved_sessions": list(self._saved_sessions),
            "model": self._model,
        }

    def restore_chat_state(self, data: object):
        if not isinstance(data, dict):
            return
        model = str(data.get("model") or "").strip()
        if model:
            self.set_model(model)
        self._conversation_summary = str(data.get("summary") or "")
        messages = data.get("messages")
        if isinstance(messages, list):
            restored: list[dict[str, str]] = []
            for item in messages:
                if isinstance(item, dict):
                    role = str(item.get("role") or "").strip().lower()
                    content = str(item.get("content") or "").strip()
                    if role in {"user", "assistant"} and content:
                        restored.append({
                            "role": role,
                            "content": content,
                            "timestamp": str(item.get("timestamp") or ""),
                        })
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    role_name = str(item[0]).strip().lower()
                    role = "assistant" if role_name == "assistant" else "user"
                    content = str(item[1]).strip()
                    if content:
                        restored.append(_chat_message(role, content))
            self._messages = restored
        uploads = data.get("uploaded_files")
        if isinstance(uploads, list):
            self._uploaded_files = [
                {"name": str(item.get("name") or ""), "path": str(item.get("path") or ""), "kind": str(item.get("kind") or "")}
                for item in uploads
                if isinstance(item, dict) and item.get("path")
            ]
        sessions = data.get("saved_sessions")
        if isinstance(sessions, list):
            self._saved_sessions = [s for s in sessions if isinstance(s, dict)][:MAX_SAVED_SESSIONS]
        self._rehydrate_history()

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
        if self._summary_thread and self._summary_thread.isRunning():
            return
        api_key = self._viewer.openrouter_api_key()
        if not api_key:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("OpenRouter API Key Missing")
            box.setTextFormat(Qt.RichText)
            box.setText(
                'Open Settings and enter your OpenRouter API key before using the chat agent.<br><br>'
                'Get your key from <a href="https://openrouter.ai/settings/keys">OpenRouter API Keys</a>.'
            )
            box.setStandardButtons(QMessageBox.Ok)
            box.exec_()
            self.lbl_status.setText(self._api_status_text())
            return

        self.input.clear()
        history = list(self._messages)
        summary = self._conversation_summary
        self._messages.append(_chat_message("user", text))
        self._append_message("You", text)
        self._pending_tool_events.clear()
        self._pending_tool_order.clear()
        self._pending_tool_seq = 0
        self._set_busy(True)

        self._thread = ChatRequestThread(
            prompt=text,
            model=self._model,
            api_key=api_key,
            history=history,
            summary=summary,
            system_context=self._build_system_context(),
        )
        self._thread.tool_event.connect(self._on_tool_event)
        self._thread.finished.connect(self._on_answer)
        self._thread.error.connect(self._on_error)
        self._thread.finished.connect(lambda _answer: self._set_busy(False))
        self._thread.error.connect(lambda _error: self._set_busy(False))
        self._thread.start()

    def _build_system_context(self) -> str:
        lines = [
            "You are answering inside the Alarm Viewer desktop app.",
            "ALWAYS call a tool to check the database before answering any question about data. Never answer from memory or assumptions.",
            "When the user asks to \"show\", \"list\", \"display\", or \"get\" items, keep the text answer brief and let the UI render the returned rows separately.",
            "Provide aggregate summaries only when the user explicitly asks for \"stats\", \"summary\", or \"count\".",
            "Do not repeat full row tables in the text reply when the alarm rows card is shown.",
            "The alarm rows card starts collapsed and can be expanded up to 100 rows.",
            "For generated files, call export_report instead of describing a manual process.",
            "Supported export_report report_type values include alarms, bdt_results, photo_manifest, site_alarm_report, accepted_pm_report, and bdt_export.",
            "Use site_alarm_report for uploaded VIP/site lists, accepted_pm_report for uploaded Accepted PM lists, and bdt_export for BDT validation workbook exports.",
            "Use get_site_dossier when the user asks for everything about one site: all alarms, BDT tests, rule details, photos, and discharge content.",
            "Use generate_graph when the user asks for graphs/charts/trends; it creates a PNG chart from local data.",
            "Use query_backup_times when the user asks for backup time, backup duration, or battery hold-up between Power and Down alarms.",
        ]
        if self._uploaded_files:
            lines.append("Uploaded local files available to tools:")
            for idx, upload in enumerate(self._uploaded_files[-5:], start=1):
                lines.append(f"{idx}. {upload['name']} -> {upload['path']}")
            lines.append("When using an uploaded file, pass its path as source_file_path.")
        return "\n".join(lines)

    def _rehydrate_history(self):
        try:
            history_layout = self._history_layout
        except RuntimeError:
            return
        except AttributeError:
            return
        while history_layout.count() > 1:
            item = history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._conversation_summary.strip():
            self._append_system("Earlier chat summarized and will be included in future replies.")
        if self._uploaded_files:
            names = ", ".join(str(upload.get("name") or upload.get("path") or "file") for upload in self._uploaded_files[-5:])
            self._append_system(f"Restored uploaded files available to tools: {names}")
        for item in self._messages:
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "")
            if role == "user":
                self._append_message("You", content)
            elif role == "assistant":
                self._append_message("Assistant", content)

    def _on_answer(self, answer: str):
        answer = answer.strip() or "(no answer)"
        if any((self._pending_tool_events.get(call_id) or {}).get("name") in {"query_alarms", "query_bdt_results", "query_backup_times"} for call_id in self._pending_tool_order):
            answer = _strip_table_blocks(answer)
        self._messages.append(_chat_message("assistant", answer))
        self._append_message("Assistant", answer)
        self._flush_pending_tool_events()
        self._maybe_start_summary()
        self._schedule_scroll_to_bottom()
        self._viewer._sbar.showMessage("Chat response received", 2500)

    def _on_error(self, error: str):
        self._pending_tool_events.clear()
        self._pending_tool_order.clear()
        self._messages.append(_chat_message("assistant", "The previous request failed before an assistant answer was received."))
        self._append_message("Error", error)
        self._schedule_scroll_to_bottom()
        self._viewer._sbar.showMessage("Chat request failed", 3500)

    def _prepare_model_switch(self, new_model: str):
        if not self._messages:
            return
        if self._summary_thread and self._summary_thread.isRunning():
            return
        raw_count = min(len(self._messages), CHAT_SUMMARY_BATCH_TURNS)
        self._start_summary(
            self._messages[:-raw_count],
            keep_tail=raw_count,
            model=self._model,
            status=f"Preparing handoff summary for {new_model}",
        )

    def _maybe_start_summary(self):
        if len(self._messages) <= CHAT_SUMMARY_TRIGGER_TURNS:
            return
        self._start_summary(
            self._messages[:CHAT_SUMMARY_BATCH_TURNS],
            keep_tail=len(self._messages) - CHAT_SUMMARY_BATCH_TURNS,
            model=self._model,
            status="Summarizing older chat turns",
        )

    def _start_summary(self, messages: list[dict[str, str]], *, keep_tail: int, model: str, status: str):
        if not messages:
            return
        if self._summary_thread and self._summary_thread.isRunning():
            return
        messages = OpenRouterAgent._normalized_history(messages)
        if not messages:
            return
        self._summary_thread = ChatSummaryThread(
            messages=messages,
            existing_summary=self._conversation_summary,
            model=model,
            api_key=self._viewer.openrouter_api_key(),
        )
        self._summary_thread.finished.connect(lambda summary, keep_tail=keep_tail: self._on_summary_ready(summary, keep_tail))
        self._summary_thread.error.connect(self._on_summary_error)
        self._summary_thread.start()
        self._viewer._sbar.showMessage(status, 2500)
        self._refresh_send_state()

    def _on_summary_ready(self, summary: str, keep_tail: int):
        summary = summary.strip()
        if summary:
            self._conversation_summary = summary
            if keep_tail > 0:
                self._messages = self._messages[-keep_tail:]
            else:
                self._messages.clear()
        self._summary_thread = None
        self._viewer._sbar.showMessage("Chat summary updated", 2500)
        self._set_busy(False)

    def _on_summary_error(self, error: str):
        self._summary_thread = None
        self._viewer._sbar.showMessage(f"Chat summary skipped: {error}", 3500)
        self._set_busy(False)

    def _on_tool_event(self, event: object):
        if not isinstance(event, dict):
            return
        call_id = str(event.get("tool_call_id") or "")
        if not call_id:
            call_id = f"{event.get('name', 'tool')}-{self._pending_tool_seq}"
            self._pending_tool_seq += 1
            event = dict(event)
            event["tool_call_id"] = call_id
        if call_id not in self._pending_tool_order:
            self._pending_tool_order.append(call_id)
        self._pending_tool_events[call_id] = dict(event)

    def _flush_pending_tool_events(self):
        if not self._pending_tool_order:
            return
        for call_id in self._pending_tool_order:
            event = self._pending_tool_events.get(call_id)
            if not event:
                continue
            if event.get("status") == "running":
                continue
            self._render_tool_event(event)
        self._pending_tool_events.clear()
        self._pending_tool_order.clear()
        self._schedule_scroll_to_bottom()

    def _render_tool_event(self, event: dict):
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
            "query_backup_times": "Backup Time Sites",
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
        if name in {"query_alarms", "query_backup_times", "query_bdt_results"}:
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
        row = FlowLayout(frame, hspacing=4, vspacing=4)
        row.setContentsMargins(0, 0, 0, 0)

        # Primary action: Copy (always shown)
        btn_copy = _make_assistant_button("Copy", minimum_width=52)
        btn_copy.clicked.connect(lambda _checked=False, payload=result: self._copy_text(_json_output_text(payload)))
        row.addWidget(btn_copy)

        if self._can_show_alarm_results_in_viewer(event):
            btn_show = _make_assistant_button("Show in Alarms")
            btn_show.clicked.connect(lambda _checked=False, payload=event: self._show_alarm_results_in_viewer(payload))
            row.addWidget(btn_show)

        # Show file actions only if there are paths
        paths = [path for path in _output_paths(result) if Path(path).exists()]
        if paths:
            btn_open = _make_assistant_button("Open")
            btn_open.clicked.connect(lambda _checked=False, p=paths[0]: self._open_path(p))
            row.addWidget(btn_open)

            btn_folder = _make_assistant_button("Folder")
            btn_folder.clicked.connect(lambda _checked=False, p=paths[0]: self._open_folder(p))
            row.addWidget(btn_folder)

        return frame

    @staticmethod
    def _can_show_alarm_results_in_viewer(event: dict) -> bool:
        result = event.get("result")
        args = event.get("args")
        return (
            isinstance(args, dict)
            and isinstance(result, dict)
            and event.get("name") in {"query_alarms", "query_backup_times"}
            and isinstance(result.get("rows"), list)
            and bool(result.get("rows"))
        )

    def _show_alarm_results_in_viewer(self, event: dict):
        if not self._can_show_alarm_results_in_viewer(event):
            return
        viewer = self._viewer
        result = event["result"]
        args = event["args"]
        rows = result["rows"]
        if hasattr(viewer, "_set_workspace_view"):
            viewer._set_workspace_view(0)

        if hasattr(viewer, "_edit_site"):
            site_ids = result.get("site_ids") if isinstance(result.get("site_ids"), list) else []
            if event.get("name") == "query_backup_times" and site_ids:
                site_text = ", ".join(str(site).strip() for site in site_ids if str(site).strip())
            else:
                site_text = str(args.get("site_text") or args.get("site_id") or "").strip()
            viewer._edit_site.setText(site_text)
        _set_combo_text(getattr(viewer, "_cb_cat", None), str(args.get("category") or "All"))
        _set_combo_text(getattr(viewer, "_cb_net", None), str(args.get("network_type") or "All"))
        _set_combo_text(getattr(viewer, "_cb_vnd", None), str(args.get("vendor") or "All"))
        if hasattr(viewer, "_chk_mindur"):
            viewer._chk_mindur.setChecked(False)
        if hasattr(viewer, "_edit_days"):
            viewer._edit_days.clear()

        if hasattr(viewer, "_chk_date"):
            date_from = str(args.get("date_from") or "").strip()
            date_to = str(args.get("date_to") or "").strip()
            use_date = bool(date_from or date_to)
            viewer._chk_date.setChecked(use_date)
            if hasattr(viewer, "_chk_date_range"):
                viewer._chk_date_range.setChecked(use_date)
            if hasattr(viewer, "_chk_date_days"):
                viewer._chk_date_days.setChecked(False)
            if use_date:
                if date_from and hasattr(viewer, "_d_from"):
                    q_from = QDate.fromString(date_from[:10], "yyyy-MM-dd")
                    if q_from.isValid():
                        viewer._d_from.setDate(q_from)
                if date_to and hasattr(viewer, "_d_to"):
                    q_to = QDate.fromString(date_to[:10], "yyyy-MM-dd")
                    if q_to.isValid():
                        viewer._d_to.setDate(q_to)

        if hasattr(viewer, "_both_pd_active"):
            viewer._both_pd_active = False
        if hasattr(viewer, "_col_filters"):
            viewer._col_filters.clear()
        if hasattr(viewer, "_btn_both"):
            viewer._btn_both.setStyleSheet("")

        page_size = max(1, min(500, int(args.get("limit") or result.get("row_count") or len(rows) or 1)))
        offset = max(0, int(args.get("offset") or 0))
        if hasattr(viewer, "_page_size"):
            viewer._page_size = page_size
        if hasattr(viewer, "_page_offset"):
            viewer._page_offset = offset
        if hasattr(viewer, "_table") and hasattr(viewer, "_current_alarm_columns"):
            cols = viewer._current_alarm_columns()
            sort_by = str(args.get("sort_by") or "occurred_on")
            if sort_by in cols:
                header = viewer._table.horizontalHeader()
                header.setSortIndicator(
                    cols.index(sort_by),
                    Qt.DescendingOrder if bool(args.get("sort_desc")) else Qt.AscendingOrder,
                )

        if hasattr(viewer, "_load_alarm_page"):
            viewer._load_alarm_page(offset=offset, status_message="Assistant results shown in Alarms")
        elif hasattr(viewer, "_search"):
            viewer._search()

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

    def _open_image_preview(self, path: str, *, title: str | None = None):
        try:
            dialog = _ImagePreviewDialog(path, title=title, parent=self)
        except ValueError as exc:
            QMessageBox.warning(self, "Image Missing", str(exc))
            return
        dialog.exec_()

    @staticmethod
    def _display_graph_type(value: object) -> str:
        text = str(value or "--").strip().replace("_", " ")
        return text.title() if text != "--" else text

    def _graph_preview_width(self) -> int:
        viewport = self._history_scroll.viewport() if hasattr(self, "_history_scroll") else None
        width = viewport.width() if viewport is not None else self.width()
        return max(320, min(900, int(width) - 48))

    def _open_photo_preview(self, path: str):
        self._open_image_preview(path)

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
        lay.addWidget(self._kv_widget({
            "graph_type": self._display_graph_type(result.get("graph_type")),
            "points": result.get("points"),
        }))
        path = str(result.get("path") or "")
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            btn_zoom = _make_assistant_button("Zoom Image")
            btn_zoom.clicked.connect(lambda _checked=False, p=path: self._open_image_preview(p, title=Path(p).name))
            preview_width = self._graph_preview_width()
            preview = QLabel()
            preview.setObjectName("tool_body")
            preview.setAlignment(Qt.AlignCenter)
            preview.setMaximumWidth(preview_width)
            preview.setPixmap(pixmap.scaledToWidth(preview_width, Qt.SmoothTransformation))
            preview.setCursor(Qt.PointingHandCursor)
            preview.mousePressEvent = lambda event, p=path: self._open_image_preview(p, title=Path(p).name)
            lay.addWidget(preview)
            lay.addWidget(btn_zoom, 0, Qt.AlignLeft)
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

    def _rows_table_widget(self, rows: list, *, max_rows: int = 10, source_name: str = "") -> QWidget:
        clean_rows = [r for r in rows if isinstance(r, dict)]
        if not clean_rows:
            return self._make_rich_label("No rows returned.", object_name="tool_body")
        columns = _alarm_row_columns(clean_rows, source_name)
        if not columns:
            columns = list(clean_rows[0].keys())
        wrapper = QFrame()
        wrapper.setObjectName("tool_detail")
        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        base_rows = _rows_preview_limit(len(clean_rows), max_rows)
        visible_rows = base_rows
        max_visible_rows = min(len(clean_rows), 100)

        table = QTableWidget(visible_rows, len(columns))
        table.setObjectName("tool_table")
        table.setHorizontalHeaderLabels([str(c).replace("_", " ").title() for c in columns])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setProperty("assistant_rows", clean_rows)
        table.setProperty("assistant_source", source_name)
        table.cellClicked.connect(lambda row, _col, tbl=table: self._activate_tool_table_row(tbl, row))
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        info = self._make_rich_label("", object_name="tool_body")
        actions = QFrame()
        actions.setObjectName("tool_detail")
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(4)
        btn_expand = _make_assistant_button("Show more")
        btn_collapse = _make_assistant_button("Collapse")
        actions_row.addWidget(btn_expand)
        actions_row.addWidget(btn_collapse)
        actions_row.addStretch(1)

        state = {"visible": visible_rows}

        def refresh():
            visible = state["visible"]
            table.setRowCount(visible)
            for row_idx, row in enumerate(clean_rows[:visible]):
                for col_idx, col in enumerate(columns):
                    table.setItem(row_idx, col_idx, QTableWidgetItem(self._format_tool_value(row.get(col))))
            table.setMaximumHeight(min(420, 54 + visible * 28))
            info.setText(_rows_summary_text(visible, len(clean_rows), max_visible_rows))
            can_expand = visible < max_visible_rows
            btn_expand.setEnabled(can_expand)
            btn_collapse.setEnabled(visible > base_rows)
            btn_expand.setText("Show 10 more" if can_expand else "Show more")

        def expand_rows():
            state["visible"] = _rows_preview_limit(len(clean_rows), state["visible"] + 10)
            refresh()

        def collapse_rows():
            state["visible"] = base_rows
            refresh()

        btn_expand.clicked.connect(lambda _checked=False: expand_rows())
        btn_collapse.clicked.connect(lambda _checked=False: collapse_rows())
        refresh()

        lay.addWidget(table)
        lay.addWidget(info)
        if max_visible_rows > _rows_preview_limit(len(clean_rows), max_rows):
            lay.addWidget(actions)
        elif len(clean_rows) > visible_rows:
            lay.addWidget(actions)
        return wrapper

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
        summary_busy = bool(self._summary_thread and self._summary_thread.isRunning())
        effective_busy = busy or summary_busy
        self.btn_send.setEnabled(not effective_busy and bool(self.input.toPlainText().strip()))
        self.btn_clear.setEnabled(not effective_busy)
        self.btn_sources.setEnabled(not effective_busy)
        self.btn_alarm_stats.setEnabled(not effective_busy)
        self.btn_upload.setEnabled(not effective_busy)
        self.btn_history.setEnabled(not effective_busy)
        self.edit_model.setEnabled(not effective_busy)
        self.input.setEnabled(not effective_busy)
        self.lbl_status.setText("Thinking..." if busy else self._api_status_text())

    def _refresh_send_state(self):
        busy = bool(
            (self._thread and self._thread.isRunning())
            or (self._summary_thread and self._summary_thread.isRunning())
        )
        self.btn_send.setEnabled(not busy and bool(self.input.toPlainText().strip()))

    def _api_status_text(self) -> str:
        key_state = "API key ready" if self._viewer.openrouter_api_key() else "API key missing"
        return f"{key_state} · Model: {self._model}"

    def refresh_settings(self):
        self.lbl_status.setText(self._api_status_text())

    def _append_system(self, text: str):
        self._append_message("System", text, store=False)

    @staticmethod
    def _make_rich_label(text: str, *, object_name: str = "chat_text") -> QLabel:
        label = QLabel()
        label.setObjectName(object_name)
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
            elif kind == "table":
                # Render markdown table as HTML table
                table_rows = payload  # type: ignore[assignment]
                if not table_rows:
                    continue
                html_rows = []
                for row_idx, tbl_row in enumerate(table_rows):
                    cells = _parse_table_cells(str(tbl_row))
                    if not cells:
                        continue
                    cell_tag = "th" if row_idx == 0 else "td"
                    cell_html = "".join(
                        f"<{cell_tag} style='padding:4px 8px; border:1px solid #2a4060; text-align:left;'>{_format_inline_markdown(cell)}</{cell_tag}>"
                        for cell in cells
                    )
                    html_rows.append(f"<tr>{cell_html}</tr>")
                if html_rows:
                    bubble_layout.addWidget(
                        self._make_rich_label(
                            "<table style='border-collapse:collapse; width:100%; margin:4px 0;'>"
                            + "".join(html_rows)
                            + "</table>",
                            object_name="chat_table"
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
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName(bubble_name)
        bubble.setMaximumWidth(self._message_bubble_width(self.width(), role_key))
        bubble.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Preferred,
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(6)

        normalized = _normalize_message_text(text)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        timestamp = datetime.now().strftime("%H:%M")
        meta = QLabel(f"{role} · {timestamp}")
        meta.setObjectName(meta_name)
        header.addWidget(meta)
        header.addStretch(1)
        bubble_layout.addLayout(header)

        self._append_blocks(bubble_layout, normalized)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(4)
        footer.addStretch(1)
        footer.addWidget(self._message_actions_widget(role, normalized))
        bubble_layout.addLayout(footer)

        if role_key == "you":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row_layout.addWidget(bubble, 1, Qt.AlignLeft)

        self._history_layout.insertWidget(self._history_layout.count() - 1, row)
        if store:
            self._schedule_scroll_to_bottom()

    def _message_actions_widget(self, role: str, text: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("tool_detail")
        row = FlowLayout(frame, hspacing=4, vspacing=4)
        row.setContentsMargins(0, 0, 0, 0)

        btn_copy = _make_assistant_button("Copy", minimum_width=52)
        btn_copy.clicked.connect(lambda _checked=False, t=text: self._copy_text(t))
        row.addWidget(btn_copy)

        return frame

    @staticmethod
    def _message_bubble_width(available_width: int, role_key: str) -> int:
        available_width = max(available_width, 0)
        ratio = {
            "you": 0.74,
            "system": 0.82,
            "error": 0.82,
        }.get(role_key, 0.80)
        return max(280, min(int(available_width * ratio), 760))

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

    def _schedule_scroll_to_bottom(self):
        QTimer.singleShot(0, self._scroll_to_bottom)
        QTimer.singleShot(50, self._scroll_to_bottom)
