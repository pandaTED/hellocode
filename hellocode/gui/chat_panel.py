"""Chat panel with markdown rendering and streaming support."""

from __future__ import annotations

import json
import re
import html as html_mod
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QFont, QTextOption
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QScrollArea, QLabel,
    QFrame, QSizePolicy,
)

if TYPE_CHECKING:
    from .themes import ThemeColors

from .i18n import t

UI_FONT = (
    '"Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", "Segoe UI", '
    '"PingFang SC", "Noto Sans CJK SC", "SimHei", "SimSun", '
    '"DengXian", "Helvetica Neue", Arial, sans-serif'
)
MONO_FONT = (
    '"Cascadia Mono", "Cascadia Code", "JetBrains Mono", '
    '"SFMono-Regular", Consolas, monospace'
)


def _split_markdown_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_markdown_table_separator(line: str) -> bool:
    cells = _split_markdown_table_row(line)
    if len(cells) < 2:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _render_markdown_tables(text: str, theme: "ThemeColors | None" = None) -> str:
    t = theme
    border = t.border if t else "#45475a"
    header_bg = t.bg_elevated if t else "#313244"
    row_bg = t.bg_panel if t else "#1e1e2e"
    fg_text = t.text_primary if t else "#cdd6f4"

    lines = text.splitlines()
    rendered: list[str] = []
    i = 0
    while i < len(lines):
        if (
            i + 1 < len(lines)
            and "|" in lines[i]
            and _is_markdown_table_separator(lines[i + 1])
        ):
            headers = _split_markdown_table_row(lines[i])
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row = _split_markdown_table_row(lines[i])
                if len(row) < len(headers):
                    row.extend([""] * (len(headers) - len(row)))
                rows.append(row[:len(headers)])
                i += 1

            table = [
                (
                    f'<table cellspacing="0" cellpadding="6" '
                    f'style="border-collapse:collapse;color:{fg_text};'
                    f'margin:6px 0 8px 0;">'
                ),
                "<thead><tr>",
            ]
            for header in headers:
                table.append(
                    f'<th style="background:{header_bg};border:1px solid {border};'
                    f'font-weight:600;text-align:left;">{header}</th>'
                )
            table.append("</tr></thead><tbody>")
            for row in rows:
                table.append("<tr>")
                for cell in row:
                    table.append(
                        f'<td style="background:{row_bg};border:1px solid {border};'
                        f'text-align:left;">{cell}</td>'
                    )
                table.append("</tr>")
            table.append("</tbody></table>")
            rendered.append("".join(table))
            continue

        rendered.append(lines[i])
        i += 1

    return "\n".join(rendered)


def _render_markdown_html(text: str, theme: "ThemeColors | None" = None) -> str:
    """Convert simple markdown to HTML for QTextEdit."""
    t = theme
    bg_code = t.bg_elevated if t else "#313244"
    fg_code = t.success if t else "#a6e3a1"
    fg_inline = t.error if t else "#f38ba8"
    fg_text = t.text_primary if t else "#cdd6f4"

    # First, extract code blocks to protect them from other parsing
    code_blocks = []
    def replace_code_block(match):
        lang = match.group(1)
        code = match.group(2)
        code_blocks.append((lang, code))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    text = re.sub(r'```(\w*)\n(.*?)```', replace_code_block, text, flags=re.DOTALL)
    text = re.sub(r'```(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # Escape HTML
    text = html_mod.escape(text)

    text = _render_markdown_tables(text, theme)

    # Restore code blocks with proper styling
    for i, (lang, code) in enumerate(code_blocks):
        is_diagram = lang.lower() in {"mermaid", "graphviz", "dot"}
        label = "diagram" if is_diagram else lang
        lang_label = f'<span style="color:{fg_text};font-size:11px;">{label}</span><br>' if label else ''
        html_code = html_mod.escape(code)
        border = f"border:1px solid {t.accent if t and is_diagram else bg_code};"
        block = f'<pre style="background:{bg_code};{border}padding:10px;border-radius:6px;color:{fg_code};font-family:{MONO_FONT};font-size:13px;white-space:pre-wrap;word-wrap:break-word;">{lang_label}<code>{html_code}</code></pre>'
        text = text.replace(f"__CODE_BLOCK_{i}__", block)

    # Inline code
    text = re.sub(
        r'`([^`]+)`',
        rf'<code style="background:{bg_code};padding:2px 5px;border-radius:4px;color:{fg_inline};font-family:{MONO_FONT};font-size:13px;">\1</code>',
        text,
    )
    # Images and links
    text = re.sub(
        r'!\[([^\]]*)\]\(([^)\s]+)\)',
        r'<img src="\2" alt="\1">',
        text,
    )
    text = re.sub(
        r'(?<!!)\[([^\]]+)\]\(([^)\s]+)\)',
        rf'<a style="color:{fg_inline};" href="\2">\1</a>',
        text,
    )
    # Bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    # Headers
    text = re.sub(r'^### (.+)$', rf'<h3 style="color:{fg_text};margin:8px 0 4px;">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', rf'<h2 style="color:{fg_text};margin:10px 0 4px;">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', rf'<h1 style="color:{fg_text};margin:12px 0 4px;">\1</h1>', text, flags=re.MULTILINE)
    # Lists
    text = re.sub(r'^- (.+)$', r'&bull; \1', text, flags=re.MULTILINE)
    # Line breaks
    text = text.replace('\n', '<br>')
    return text


class MessageInput(QTextEdit):
    """Multi-line composer: Enter sends, Shift+Enter inserts a newline."""

    send_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont()
        font.setPointSize(13)
        self.setFont(font)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumHeight(44)
        self.setMaximumHeight(140)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                event.accept()
            return
        super().keyPressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(320, 44)


class ChatMessage(QFrame):
    """A single chat message widget with markdown support."""

    def __init__(self, role: str, content: str, theme: "ThemeColors", parent=None):
        super().__init__(parent)
        self.role = role
        self._content = content
        self._theme = theme
        self._timestamp = datetime.now().strftime("%H:%M")
        self._setup_ui(content)

    def _setup_ui(self, content: str):
        th = self._theme
        self.setStyleSheet("ChatMessage { background: transparent; border: none; }")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName("messageBubble")
        self._bubble = bubble
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(5)

        # Message meta row
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)

        role_label = QLabel(t("you") if self.role == "user" else t("assistant"))
        role_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        role_label.setStyleSheet(f"""
            color: {th.user_color if self.role == 'user' else th.assistant_color};
            font-weight: 600;
            font-size: 12px;
        """)
        meta_row.addWidget(role_label)

        time_label = QLabel(self._timestamp)
        time_label.setStyleSheet(f"color: {th.text_muted}; font-size: 11px;")
        meta_row.addWidget(time_label)
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        # Content using QLabel - perfect auto-sizing for text
        self.content_label = QLabel()
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.content_label.setTextFormat(Qt.TextFormat.RichText)
        self.content_label.setOpenExternalLinks(True)
        self.content_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.content_label.setStyleSheet(f"""
            QLabel {{
                color: {th.text_primary};
                font-family: {UI_FONT};
                font-size: 14px;
                padding: 2px 0;
            }}
        """)
        if content:
            self.content_label.setText(_render_markdown_html(content, th))
        layout.addWidget(self.content_label)

        # Message bubble styling
        bg = th.bg_elevated if self.role == "user" else th.bg_assistant_msg
        border = th.border if self.role == "user" else "transparent"
        bubble.setStyleSheet(f"""
            QFrame#messageBubble {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)

        if self.role == "user":
            row.addStretch(1)
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        else:
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            row.addStretch(1)
        self._update_bubble_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bubble_width()

    def _update_bubble_width(self):
        if not hasattr(self, "_bubble"):
            return
        available = max(0, self.width() - 40)
        if available <= 0:
            return
        if self.role == "assistant":
            minimum = max(420, int(available * 0.64))
            maximum = max(minimum, min(1180, int(available * 0.82)))
        else:
            minimum = max(360, int(available * 0.5))
            maximum = max(minimum, min(760, int(available * 0.62)))
        self._bubble.setMinimumWidth(minimum)
        self._bubble.setMaximumWidth(maximum)

    def append_content(self, text: str, render_markdown: bool = True):
        self._content += text
        if hasattr(self, 'content_label'):
            if render_markdown:
                self.content_label.setText(_render_markdown_html(self._content, self._theme))
            else:
                self.content_label.setText(html_mod.escape(self._content).replace("\n", "<br>"))

    def append_buffered_content(self, text: str):
        self._content += text

    def render_final(self):
        if hasattr(self, 'content_label'):
            self.content_label.setText(_render_markdown_html(self._content, self._theme))


class ToolCallMessage(QFrame):
    """Displays a tool call and its result."""

    def __init__(self, name: str, args: dict, theme: "ThemeColors", parent=None):
        super().__init__(parent)
        self.tool_name = name
        self._theme = theme
        self._setup_ui(name, args)

    def _setup_ui(self, name: str, args: dict):
        th = self._theme
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setStyleSheet(f"""
            ToolCallMessage {{
                background-color: {th.bg_tool_msg};
                border: 1px solid {th.border};
                border-radius: 8px;
                margin: 4px 48px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Tool name and status
        header = QHBoxLayout()
        name_label = QLabel(f"  {name}")
        name_label.setStyleSheet(f"color: {th.accent}; font-weight: bold; font-size: 12px;")
        header.addWidget(name_label)

        self.status_label = QLabel("...")
        self.status_label.setStyleSheet(f"color: {th.text_muted}; font-size: 12px;")
        header.addStretch()
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Args preview
        args_str = json.dumps(args, indent=2, ensure_ascii=False)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        args_label = QLabel(args_str)
        args_label.setStyleSheet(f"color: {th.text_muted}; font-size: 11px;")
        args_label.setWordWrap(True)
        layout.addWidget(args_label)

        # Result (hidden initially)
        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"color: {th.text_secondary}; font-size: 11px;")
        self.result_label.setWordWrap(True)
        self.result_label.hide()
        layout.addWidget(self.result_label)

    def set_success(self, result: str):
        th = self._theme
        self.status_label.setText(t("tool_ok"))
        self.status_label.setStyleSheet(f"color: {th.success}; font-weight: bold; font-size: 12px;")
        if result:
            truncated = result[:300] + "..." if len(result) > 300 else result
            self.result_label.setText(truncated)
            self.result_label.show()

    def set_error(self, result: str):
        th = self._theme
        self.status_label.setText(t("tool_fail"))
        self.status_label.setStyleSheet(f"color: {th.error}; font-weight: bold; font-size: 12px;")
        if result:
            self.result_label.setText(result[:300])
            self.result_label.setStyleSheet(f"color: {th.error}; font-size: 11px;")
            self.result_label.show()


class QuestionWidget(QFrame):
    """Renders a question tool call as clickable option buttons."""

    option_selected = Signal(str)

    def __init__(self, args: dict, theme: "ThemeColors", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._args = args
        self._setup_ui(args)

    def _setup_ui(self, args: dict):
        th = self._theme
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setStyleSheet(f"""
            QuestionWidget {{
                background-color: {th.bg_tool_msg};
                border: 1px solid {th.border};
                border-radius: 8px;
                margin: 4px 48px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header with question
        header = QLabel(f"  [{t('tool_question')}]")
        header.setStyleSheet(f"color: {th.accent}; font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        # Question text
        question = args.get("question", "")
        if question:
            q_label = QLabel(question)
            q_label.setStyleSheet(f"color: {th.text_primary}; font-size: 13px; padding: 4px 0;")
            q_label.setWordWrap(True)
            layout.addWidget(q_label)

        # Header/title
        header_text = args.get("header", "")
        if header_text:
            h_label = QLabel(header_text)
            h_label.setStyleSheet(f"color: {th.text_secondary}; font-size: 11px; font-weight: bold;")
            layout.addWidget(h_label)

        # Options as clickable buttons
        options = args.get("options", [])
        if options:
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(8)
            for opt in options:
                label = opt.get("label", opt.get("description", str(opt)))
                btn = QPushButton(label)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {th.bg_elevated};
                        color: {th.text_primary};
                        border: 1px solid {th.border};
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {th.accent};
                        color: {th.bg_window};
                        border-color: {th.accent};
                    }}
                """)
                btn.clicked.connect(lambda checked, l=label: self.option_selected.emit(l))
                btn_layout.addWidget(btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {th.text_muted}; font-size: 11px;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"color: {th.text_secondary}; font-size: 11px;")
        self.result_label.hide()
        layout.addWidget(self.result_label)

    def set_selected(self, option: str):
        theme = self._theme
        # Clean up the option text - remove JSON formatting if present
        clean_option = str(option).strip()
        if clean_option.startswith("{") or clean_option.startswith('"'):
            # Try to extract readable text from JSON
            try:
                import json as _json
                parsed = _json.loads(clean_option)
                if isinstance(parsed, dict):
                    clean_option = parsed.get("label", parsed.get("description", str(parsed)))
            except Exception:
                pass
        self.result_label.setText(t("tool_selected", option=clean_option))
        self.result_label.setStyleSheet(f"color: {theme.success}; font-size: 11px;")
        self.result_label.show()

    def set_success(self, result: str):
        th = self._theme
        self.status_label.setText(t("tool_ok"))
        self.status_label.setStyleSheet(f"color: {th.success}; font-weight: bold; font-size: 12px;")
        if result:
            truncated = result[:300] + "..." if len(result) > 300 else result
            self.result_label.setText(truncated)
            self.result_label.show()

    def set_error(self, result: str):
        th = self._theme
        self.status_label.setText(t("tool_fail"))
        self.status_label.setStyleSheet(f"color: {th.error}; font-weight: bold; font-size: 12px;")
        if result:
            self.result_label.setText(result[:300])
            self.result_label.setStyleSheet(f"color: {th.error}; font-size: 11px;")
            self.result_label.show()


class ChatPanel(QWidget):
    """Main chat panel with message display and input."""

    message_sent = Signal(str)
    option_selected = Signal(str)

    def __init__(self, theme: "ThemeColors", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._current_assistant: ChatMessage | None = None
        self._stream_buffer = ""
        self._stream_active = False
        self._stream_finalized = False
        self._stream_render_pending = False
        self._pending_question: QuestionWidget | None = None
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chat area background
        self.setObjectName("chatArea")

        # Scroll area for messages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {th.bg_surface};
                border: none;
            }}
        """)

        self.messages_widget = QWidget()
        self.messages_widget.setStyleSheet(f"background-color: {th.bg_surface};")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(20, 20, 20, 20)
        self.messages_layout.setSpacing(10)
        self.empty_state = QLabel("HelloCode")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setStyleSheet(f"""
            color: {th.text_muted};
            font-size: 18px;
            padding: 120px 16px;
        """)
        self.messages_layout.addWidget(self.empty_state)
        self.messages_layout.addStretch(1)

        self.scroll_area.setWidget(self.messages_widget)
        layout.addWidget(self.scroll_area, 1)

        # Input area
        input_frame = QFrame()
        input_frame.setObjectName("inputArea")
        input_frame.setStyleSheet(f"""
            QFrame#inputArea {{
                background-color: {th.bg_panel};
                border-top: 1px solid {th.border};
            }}
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 10, 16, 10)
        input_layout.setSpacing(8)

        self.input_field = MessageInput()
        self.input_field.setObjectName("chatInput")
        self.input_field.setPlaceholderText(t("input_placeholder"))
        self.input_field.setStyleSheet(f"""
            QTextEdit#chatInput {{
                background-color: {th.bg_elevated};
                color: {th.text_primary};
                border: 1px solid {th.border};
                border-radius: 8px;
                padding: 9px 12px;
                font-family: {UI_FONT};
                font-size: 14px;
                selection-background-color: {th.selection};
            }}
            QTextEdit#chatInput:focus {{
                border-color: {th.border_focus};
            }}
        """)
        self.input_field.send_requested.connect(self._on_send)
        input_layout.addWidget(self.input_field, 1)

        self.send_button = QPushButton(t("send"))
        self.send_button.setObjectName("sendButton")
        self.send_button.setStyleSheet(f"""
            QPushButton#sendButton {{
                background-color: {th.accent};
                color: {th.bg_window};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton#sendButton:hover {{
                background-color: {th.accent_hover};
            }}
            QPushButton#sendButton:pressed {{
                background-color: {th.accent_pressed};
            }}
            QPushButton#sendButton:disabled {{
                background-color: {th.bg_elevated};
                color: {th.text_muted};
            }}
        """)
        self.send_button.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_button)

        layout.addWidget(input_frame)

    def _on_send(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        self.input_field.clear()
        self.add_user_message(text)
        self.message_sent.emit(text)

    def add_user_message(self, content: str):
        msg = ChatMessage("user", content, self._theme)
        self._insert_message(msg)

    def add_assistant_message(self, content: str):
        msg = ChatMessage("assistant", content, self._theme)
        self._insert_message(msg)
        self._current_assistant = None
        self._stream_buffer = ""
        self._stream_finalized = False

    def start_assistant_stream(self):
        msg = ChatMessage("assistant", "", self._theme)
        self._insert_message(msg)
        self._current_assistant = msg
        self._stream_buffer = ""
        self._stream_active = True
        self._stream_finalized = False
        self._stream_render_pending = False

    def append_stream(self, token: str):
        if self._current_assistant and self._stream_active:
            self._stream_buffer += token
            self._current_assistant.append_buffered_content(token)
            if not self._stream_render_pending:
                self._stream_render_pending = True
                QTimer.singleShot(60, self._render_stream_markdown)
            self._scroll_to_bottom()

    def _render_stream_markdown(self):
        self._stream_render_pending = False
        if self._current_assistant and self._stream_active:
            self._current_assistant.render_final()
            self._scroll_to_bottom()

    def finish_stream(self):
        had_stream = bool(self._current_assistant)
        if self._current_assistant and self._stream_buffer:
            self._current_assistant.render_final()
        self._current_assistant = None
        self._stream_buffer = ""
        self._stream_active = False
        self._stream_finalized = had_stream
        self._stream_render_pending = False

    def consume_stream_finalized(self) -> bool:
        was_finalized = self._stream_finalized
        self._stream_finalized = False
        return was_finalized

    def add_tool_call(self, name: str, args: dict):
        if name == "question":
            widget = QuestionWidget(args, self._theme)
            widget.option_selected.connect(self._on_option_selected)
            self._pending_question = widget
            self._insert_message(widget)
            return widget
        else:
            msg = ToolCallMessage(name, args, self._theme)
            self._insert_message(msg)
            return msg

    def _on_option_selected(self, option: str):
        if self._pending_question:
            self._pending_question.set_selected(option)
            self._pending_question = None
        # Send just the option label, not the full args
        self.add_user_message(str(option))
        self.message_sent.emit(str(option))

    def add_system_message(self, content: str):
        th = self._theme
        label = QLabel(content)
        label.setStyleSheet(f"""
            color: {th.text_muted};
            font-size: 11px;
            padding: 4px 16px;
            font-style: italic;
        """)
        label.setWordWrap(True)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, label)
        self._scroll_to_bottom()

    def _insert_message(self, widget: QWidget):
        self.empty_state.hide()
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, widget)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(10, self._do_scroll)

    def _do_scroll(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_theme(self, theme: "ThemeColors"):
        self._theme = theme
        self.setStyleSheet(f"background-color: {theme.bg_surface};")
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {theme.bg_surface};
                border: none;
            }}
        """)
        self.messages_widget.setStyleSheet(f"background-color: {theme.bg_surface};")
        self.empty_state.setStyleSheet(f"""
            color: {theme.text_muted};
            font-size: 18px;
            padding: 120px 16px;
        """)

    def update_language(self) -> None:
        self.input_field.setPlaceholderText(t("input_placeholder"))
        self.send_button.setText(t("send"))

    def clear(self):
        while self.messages_layout.count() > 2:
            item = self.messages_layout.takeAt(self.messages_layout.count() - 2)
            if item.widget():
                item.widget().deleteLater()
        self._current_assistant = None
        self._stream_buffer = ""
        self._stream_active = False
        self._stream_finalized = False
        self._stream_render_pending = False
        self.empty_state.show()

    def set_input_enabled(self, enabled: bool):
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if enabled:
            self.input_field.setFocus()

    def get_messages(self) -> list[dict]:
        messages = []
        for i in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, ChatMessage):
                role = "user" if widget._is_user else "assistant"
                content = widget._content if hasattr(widget, '_content') else ""
                messages.append({"role": role, "content": content})
        return messages
