"""Schedule log panel showing scheduled task execution results."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QFrame, QDialog, QPlainTextEdit, QTextBrowser, QScrollArea,
)

from .i18n import t
from .chat_panel import _render_markdown_html


class ScheduleLogEntry(QFrame):
    """A single schedule execution entry."""

    def __init__(self, run: dict, schedule_name: str, schedule: dict = None, theme=None, parent=None):
        super().__init__(parent)
        self._run = run
        self._theme = theme
        self._schedule_name = schedule_name
        self._schedule = schedule or {}
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
        bg = th.bg_surface if th else "#313244"
        border = th.border if th else "#45475a"
        self.setStyleSheet(f"""
            ScheduleLogEntry {{
                background-color: {bg};
                border-bottom: 1px solid {border};
                padding: 6px 10px;
            }}
            ScheduleLogEntry:hover {{
                background-color: {th.bg_hover if th else "#45475a"};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        status = self._run.get("status", "unknown")
        if status == "success":
            icon = "✓"
            color = th.success if th else "#a6e3a1"
        elif status == "running":
            icon = "⏳"
            color = th.warning if th else "#f9e2af"
        else:
            icon = "✗"
            color = th.error if th else "#f38ba8"

        status_label = QLabel(icon)
        status_label.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
        layout.addWidget(status_label)

        name_label = QLabel(self._schedule_name)
        name_label.setStyleSheet(f"color: {th.text_primary if th else '#cdd6f4'}; font-weight: bold; font-size: 12px;")
        layout.addWidget(name_label)

        layout.addStretch()

        started = self._run.get("started_at")
        if started:
            time_str = datetime.fromtimestamp(started / 1000).strftime("%m-%d %H:%M:%S")
        else:
            time_str = ""
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {th.text_muted if th else '#6c7086'}; font-size: 11px;")
        layout.addWidget(time_label)

        detail_btn = QLabel("📋")
        detail_btn.setStyleSheet(f"font-size: 12px; padding: 2px;")
        layout.addWidget(detail_btn)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self._show_detail_dialog()
            super().mousePressEvent(event)
        except RuntimeError:
            pass

    def _show_detail_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{t('execution_history')} - {self._schedule_name}")
        dialog.setMinimumSize(600, 400)
        dialog.resize(700, 500)

        th = self._theme
        bg = th.bg_panel if th else "#1e1e2e"
        surface = th.bg_surface if th else "#313244"
        text = th.text_primary if th else "#cdd6f4"
        muted = th.text_muted if th else "#6c7086"
        border = th.border if th else "#45475a"

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {text};
            }}
            QLabel {{
                color: {text};
            }}
            QPlainTextEdit {{
                background-color: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
            }}
            QTextBrowser {{
                background-color: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 8px;
            }}
            QPushButton {{
                background-color: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        status = self._run.get("status", "unknown")
        if status == "success":
            status_text = "✓ " + t("status_done")
            status_color = th.success if th else "#a6e3a1"
        elif status == "running":
            status_text = "⏳ " + t("status_in_progress")
            status_color = th.warning if th else "#f9e2af"
        else:
            status_text = "✗ " + t("error")
            status_color = th.error if th else "#f38ba8"

        header = QHBoxLayout()
        header.setSpacing(12)

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color}; font-size: 16px; font-weight: bold;")
        header.addWidget(status_label)

        started = self._run.get("started_at")
        if started:
            time_str = datetime.fromtimestamp(started / 1000).strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "-"
        time_label = QLabel(f"{t('last_run')}: {time_str}")
        time_label.setStyleSheet(f"color: {muted}; font-size: 12px;")
        header.addWidget(time_label)

        header.addStretch()
        layout.addLayout(header)

        info_group = QLabel(f"{t('name')}: {self._schedule_name}")
        info_group.setStyleSheet(f"color: {text}; font-size: 13px; padding: 4px 0;")
        layout.addWidget(info_group)

        task_type = self._schedule.get("task_type", "unknown")
        payload = self._schedule.get("payload", "")
        type_label = QLabel(f"{t('task_type_label')} {task_type}")
        type_label.setStyleSheet(f"color: {muted}; font-size: 12px;")
        layout.addWidget(type_label)

        if payload:
            payload_preview = payload[:200] + "..." if len(payload) > 200 else payload
            payload_label = QLabel(f"{t('task_content_label')} {payload_preview}")
            payload_label.setStyleSheet(f"color: {muted}; font-size: 12px; font-family: monospace;")
            payload_label.setWordWrap(True)
            layout.addWidget(payload_label)

        result = self._run.get("result") or ""
        error = self._run.get("error_message") or ""

        if error:
            error_label = QLabel(t("error_info") + ":")
            error_label.setStyleSheet(f"color: {th.error if th else '#f38ba8'}; font-weight: bold;")
            layout.addWidget(error_label)

            error_text = QPlainTextEdit()
            error_text.setPlainText(error)
            error_text.setReadOnly(True)
            error_text.setMaximumHeight(150)
            layout.addWidget(error_text)

        if result:
            result_label = QLabel(t("execution_result") + ":")
            result_label.setStyleSheet(f"color: {th.accent if th else '#89b4fa'}; font-weight: bold;")
            layout.addWidget(result_label)

            result_browser = QTextBrowser()
            result_browser.setOpenExternalLinks(True)
            result_browser.setHtml(_render_markdown_html(result, th))
            result_browser.setMinimumHeight(200)
            layout.addWidget(result_browser)
        elif not error:
            no_result = QLabel(t("no_schedule_result"))
            no_result.setStyleSheet(f"color: {muted}; font-style: italic;")
            layout.addWidget(no_result)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(t("close"))
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()


class ScheduleLogPanel(QWidget):
    """Panel showing scheduled task execution logs."""

    def __init__(self, storage, theme=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self._storage = storage
        self._theme = theme
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 4)
        self.header_label = QLabel(t("schedule_log"))
        self.header_label.setStyleSheet(f"""
            color: {th.text_secondary if th else '#a6adc8'};
            font-size: 13px;
            font-weight: 600;
        """)
        header.addWidget(self.header_label)
        header.addStretch()

        self.refresh_btn = QPushButton(t("refresh"))
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {th.text_muted if th else '#6c7086'};
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {th.text_primary if th else '#cdd6f4'};
            }}
        """)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        self.log_list = QListWidget()
        self.log_list.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: none;
            }}
            QListWidget::item {{
                padding: 0px;
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: {th.bg_hover if th else '#45475a'};
            }}
        """)
        layout.addWidget(self.log_list)

    def refresh(self):
        self.log_list.clear()
        schedules = self._storage.list_schedules()
        for schedule in schedules:
            schedule_id = schedule.get("id", "")
            schedule_name = schedule.get("name", "")
            runs = self._storage.get_schedule_runs(schedule_id, limit=5)
            for run in runs:
                entry = ScheduleLogEntry(run, schedule_name, schedule, self._theme)
                item = QListWidgetItem()
                item.setSizeHint(entry.sizeHint())
                self.log_list.addItem(item)
                self.log_list.setItemWidget(item, entry)

        if self.log_list.count() == 0:
            empty_label = QLabel(t("no_logs"))
            empty_label.setStyleSheet(f"""
                color: {self._theme.text_muted if self._theme else '#6c7086'};
                font-size: 12px;
                padding: 20px;
                text-align: center;
            """)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item = QListWidgetItem()
            item.setSizeHint(empty_label.sizeHint())
            self.log_list.addItem(item)
            self.log_list.setItemWidget(item, empty_label)

    def update_theme(self, theme):
        self._theme = theme
        self.refresh()

    def update_language(self):
        if hasattr(self, 'header_label'):
            self.header_label.setText(t("schedule_log"))
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.setText(t("refresh"))
        self.refresh()
