"""Task management panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QFrame,
)

if TYPE_CHECKING:
    from .themes import ThemeColors

from .i18n import t


STATUS_ICONS = {
    "open": "○",
    "in_progress": "●",
    "blocked": "!",
    "done": "✓",
    "abandoned": "×",
}


class TaskItem(QFrame):
    """A single task entry."""

    def __init__(self, task_id: str, summary: str, status: str, theme: "ThemeColors" = None, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self._theme = theme
        self._setup_ui(task_id, summary, status)

    def _setup_ui(self, task_id: str, summary: str, status: str):
        th = self._theme
        icon = STATUS_ICONS.get(status, "?")

        # Map status to theme colors
        if th:
            color_map = {
                "open": th.text_muted,
                "in_progress": th.accent,
                "blocked": th.error,
                "done": th.success,
                "abandoned": th.error,
            }
        else:
            color_map = {
                "open": "#6c7086",
                "in_progress": "#89b4fa",
                "blocked": "#f38ba8",
                "done": "#a6e3a1",
                "abandoned": "#f38ba8",
            }
        color = color_map.get(status, th.text_muted if th else "#6c7086")
        text_color = th.text_primary if th else "#cdd6f4"
        muted_color = th.text_muted if th else "#6c7086"

        self.setStyleSheet(f"""
            TaskItem {{
                padding: 4px;
                border-left: 3px solid {color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        summary_label = QLabel(summary or t("no_summary"))
        summary_label.setStyleSheet(f"color: {text_color}; font-size: 12px;")
        summary_label.setWordWrap(True)
        text_layout.addWidget(summary_label)

        id_label = QLabel(task_id)
        id_label.setStyleSheet(f"color: {muted_color}; font-size: 10px;")
        text_layout.addWidget(id_label)

        layout.addLayout(text_layout, 1)

        status_label = QLabel(t(f"status_{status}"))
        status_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
        layout.addWidget(status_label)


class TaskPanel(QWidget):
    """Panel for task management."""

    def __init__(self, storage, theme: "ThemeColors" = None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self._theme = theme
        self.setObjectName("sidePanel")
        self._current_session_id: str | None = None
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
        muted_color = th.text_muted if th else "#6c7086"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header_label = QLabel(t("tasks"))
        self.header_label.setObjectName("sectionTitle")
        layout.addWidget(self.header_label)

        # Stats bar
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {muted_color}; font-size: 11px; padding: 4px 12px;")
        layout.addWidget(self.stats_label)

        # Task list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("taskList")
        layout.addWidget(self.list_widget)

    def load_tasks(self, session_id: str):
        self._current_session_id = session_id
        self.list_widget.clear()

        tasks = self.storage.list_tasks(session_id)
        if not tasks:
            empty = QLabel(t("no_tasks"))
            th = self._theme
            muted_color = th.text_muted if th else "#6c7086"
            empty.setStyleSheet(f"color: {muted_color}; padding: 16px; font-style: italic;")
            self.list_widget.addItem("")
            self.list_widget.setItemWidget(self.list_widget.item(0), empty)
            self.stats_label.setText("")
            return

        open_count = sum(1 for task in tasks if task.get("status") == "open")
        progress_count = sum(1 for task in tasks if task.get("status") == "in_progress")
        done_count = sum(1 for task in tasks if task.get("status") == "done")
        self.stats_label.setText(
            t(
                "task_stats",
                total=len(tasks),
                open=open_count,
                active=progress_count,
                done=done_count,
            )
        )

        # Sort: in_progress first, then open, then blocked, then done, then abandoned
        status_order = {"in_progress": 0, "open": 1, "blocked": 2, "done": 3, "abandoned": 4}
        tasks.sort(key=lambda task: status_order.get(task.get("status", "open"), 5))

        for task in tasks:
            item = QListWidgetItem()
            widget = TaskItem(
                task["id"],
                task.get("summary", ""),
                task.get("status", "open"),
                self._theme,
            )
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def refresh(self):
        if self._current_session_id:
            self.load_tasks(self._current_session_id)

    def update_theme(self, theme: "ThemeColors") -> None:
        self._theme = theme
        self.refresh()

    def update_language(self) -> None:
        self.header_label.setText(t("tasks"))
        self.refresh()
