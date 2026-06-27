"""Tool execution panel showing real-time tool calls."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QFrame, QPushButton,
    QDialog, QDialogButtonBox, QPlainTextEdit,
)

if TYPE_CHECKING:
    from .themes import ThemeColors

from .i18n import t


class ToolEntry(QFrame):
    """A single tool execution entry."""

    def __init__(self, name: str, args: dict, theme: "ThemeColors", parent=None):
        super().__init__(parent)
        self.tool_name = name
        self._args = args
        self._result = ""
        self._success: bool | None = None
        self._theme = theme
        self._start_time = datetime.now()
        self._setup_ui(name, args)

    def _setup_ui(self, name: str, args: dict):
        th = self._theme
        self.setStyleSheet(f"""
            ToolEntry {{
                background-color: {th.bg_surface};
                border-bottom: 1px solid {th.border};
                padding: 8px;
            }}
            ToolEntry:hover {{
                background-color: {th.bg_hover};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)

        self.status_icon = QLabel("...")
        self.status_icon.setStyleSheet(f"color: {th.text_muted}; font-size: 12px; font-weight: bold;")
        header.addWidget(self.status_icon)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"color: {th.accent}; font-weight: bold; font-size: 13px;")
        header.addWidget(name_label)

        header.addStretch()

        self.time_label = QLabel("")
        self.time_label.setStyleSheet(f"color: {th.text_muted}; font-size: 11px;")
        header.addWidget(self.time_label)

        self.details_btn = QPushButton(t("details"))
        self.details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {th.accent};
                border: 1px solid {th.border};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {th.bg_hover};
            }}
        """)
        self.details_btn.clicked.connect(self.show_details)
        header.addWidget(self.details_btn)

        layout.addLayout(header)

        # Args preview
        args_str = json.dumps(args, indent=2, ensure_ascii=False)
        if len(args_str) > 150:
            args_str = args_str[:150] + "..."
        self.args_label = QLabel(args_str)
        self.args_label.setStyleSheet(f"color: {th.text_muted}; font-size: 11px; font-family: monospace;")
        self.args_label.setWordWrap(True)
        layout.addWidget(self.args_label)

        # Result (hidden initially)
        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"color: {th.text_secondary}; font-size: 11px;")
        self.result_label.setWordWrap(True)
        self.result_label.hide()
        layout.addWidget(self.result_label)

    def set_success(self, result: str):
        th = self._theme
        self._success = True
        self._result = result
        elapsed = (datetime.now() - self._start_time).total_seconds()
        self.status_icon.setText(t("tool_ok"))
        self.status_icon.setStyleSheet(f"color: {th.success}; font-size: 12px; font-weight: bold;")
        self.time_label.setText(f"{elapsed:.1f}s")
        if result:
            truncated = result[:200] + "..." if len(result) > 200 else result
            self.result_label.setText(truncated)
            self.result_label.show()

    def set_error(self, result: str):
        th = self._theme
        self._success = False
        self._result = result
        elapsed = (datetime.now() - self._start_time).total_seconds()
        self.status_icon.setText(t("tool_fail"))
        self.status_icon.setStyleSheet(f"color: {th.error}; font-size: 12px; font-weight: bold;")
        self.time_label.setText(f"{elapsed:.1f}s")
        if result:
            self.result_label.setText(result[:200])
            self.result_label.setStyleSheet(f"color: {th.error}; font-size: 11px;")
            self.result_label.show()

    def show_details(self):
        if self._success is None:
            status = t("tool_status_pending")
        else:
            status = t("tool_status_success") if self._success else t("tool_status_error")
        payload = [
            f"{t('tool_label')}{self.tool_name}",
            f"{t('status_label_plain')}{status}",
            "",
            t("arguments_label"),
            json.dumps(self._args, indent=2, ensure_ascii=False),
            "",
            t("result_label"),
            self._result or t("no_result"),
        ]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"{t('tool_details')} - {self.tool_name}")
        dialog.resize(760, 560)
        th = self._theme
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {th.bg_surface};
                color: {th.text_primary};
            }}
            QPlainTextEdit {{
                background-color: {th.bg_panel};
                color: {th.text_primary};
                border: 1px solid {th.border};
                border-radius: 6px;
                selection-background-color: {th.selection};
            }}
            QPushButton {{
                background-color: {th.bg_elevated};
                color: {th.text_primary};
                border: 1px solid {th.border};
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {th.bg_hover};
            }}
        """)
        layout = QVBoxLayout(dialog)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(payload))
        text.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {th.bg_panel};
                color: {th.text_primary};
                border: 1px solid {th.border};
                border-radius: 6px;
                font-family: "Cascadia Mono", "Cascadia Code", Consolas, monospace;
                font-size: 12px;
                padding: 8px;
            }}
        """)
        layout.addWidget(text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button:
            close_button.setText(t("close"))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()


class ToolPanel(QWidget):
    """Panel showing tool execution history."""

    def __init__(self, theme: "ThemeColors", parent=None):
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self._theme = theme
        self._entries: list[ToolEntry] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_label = QLabel(t("tool_execution"))
        self.header_label.setObjectName("sectionTitle")
        layout.addWidget(self.header_label)

        self.empty_label = QLabel(t("no_tool_calls"))
        self.empty_label.setStyleSheet(f"""
            color: {self._theme.text_muted};
            font-size: 11px;
            padding: 0 14px 8px;
        """)
        layout.addWidget(self.empty_label)

        # Tool list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("toolList")
        self.list_widget.setSpacing(0)
        self.list_widget.itemDoubleClicked.connect(self._show_item_details)
        layout.addWidget(self.list_widget)

    def add_tool_call(self, name: str, args: dict) -> ToolEntry:
        entry = ToolEntry(name, args, self._theme)
        self._entries.append(entry)
        self.empty_label.hide()

        item = QListWidgetItem()
        item.setSizeHint(entry.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, entry)

        # Keep max 50 entries to avoid memory issues
        if self.list_widget.count() > 50:
            old_item = self.list_widget.takeItem(0)
            if old_item:
                old_item_widget = self.list_widget.itemWidget(old_item)
                if old_item_widget:
                    old_item_widget.deleteLater()

        self.list_widget.scrollToBottom()
        return entry

    def _show_item_details(self, item: QListWidgetItem):
        widget = self.list_widget.itemWidget(item)
        if isinstance(widget, ToolEntry):
            widget.show_details()

    def update_theme(self, theme: "ThemeColors"):
        self._theme = theme
        self.empty_label.setStyleSheet(f"""
            color: {theme.text_muted};
            font-size: 11px;
            padding: 0 14px 8px;
        """)

    def update_language(self) -> None:
        self.header_label.setText(t("tool_execution"))
        self.empty_label.setText(t("no_tool_calls"))

    def clear(self):
        self.list_widget.clear()
        self._entries.clear()
        self.empty_label.show()

    def get_stats(self) -> dict:
        total = len(self._entries)
        success = sum(1 for e in self._entries if e._success is True)
        error = sum(1 for e in self._entries if e._success is False)
        return {"total": total, "success": success, "error": error, "pending": total - success - error}
