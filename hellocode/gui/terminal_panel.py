"""Built-in terminal emulator panel."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QComboBox,
)

from .i18n import t


class TerminalPanel(QWidget):
    """Built-in terminal emulator."""

    command_executed = Signal(str, str)  # command, output

    def __init__(self, workdir: Path = None, theme=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self._workdir = workdir or Path.cwd()
        self._theme = theme
        self._process: subprocess.Popen | None = None
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 4)
        header_label = QLabel(t("terminal"))
        header_label.setStyleSheet(f"""
            color: {th.text_secondary if th else '#a6adc8'};
            font-size: 13px;
            font-weight: 600;
        """)
        header.addWidget(header_label)
        header.addStretch()

        self.clear_btn = QPushButton(t("clear"))
        self.clear_btn.setStyleSheet(f"""
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
        self.clear_btn.clicked.connect(self._clear_output)
        header.addWidget(self.clear_btn)

        layout.addLayout(header)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("Consolas", 10))
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {th.bg_panel if th else '#1e1e2e'};
                color: {th.text_primary if th else '#cdd6f4'};
                border: none;
                padding: 8px;
                selection-background-color: {th.accent if th else '#89b4fa'};
            }}
        """)
        layout.addWidget(self.output_area)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(12, 4, 12, 8)
        input_layout.setSpacing(8)

        self.path_label = QLabel(f"❯")
        self.path_label.setStyleSheet(f"""
            color: {th.success if th else '#a6e3a1'};
            font-family: Consolas, monospace;
            font-size: 12px;
            font-weight: bold;
        """)
        input_layout.addWidget(self.path_label)

        self.input_edit = QTextEdit()
        self.input_edit.setMaximumHeight(32)
        self.input_edit.setFont(QFont("Consolas", 10))
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {th.bg_surface if th else '#313244'};
                color: {th.text_primary if th else '#cdd6f4'};
                border: 1px solid {th.border if th else '#45475a'};
                border-radius: 4px;
                padding: 4px 8px;
            }}
        """)
        self.input_edit.setPlaceholderText(t("terminal_placeholder"))
        self.input_edit.installEventFilter(self)
        input_layout.addWidget(self.input_edit, 1)

        self.send_btn = QPushButton("⏎")
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {th.accent if th else '#89b4fa'};
                color: {th.bg_panel if th else '#1e1e2e'};
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {th.accent_hover if th else '#74c7ec'};
            }}
        """)
        self.send_btn.clicked.connect(self._execute_command)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

        self._command_history: list[str] = []
        self._history_index: int = -1
        self._append_output(f"[Terminal] {t('workdir')}: {self._workdir}\n")

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._execute_command()
                return True
            elif event.key() == Qt.Key.Key_Up:
                self._navigate_history(-1)
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._navigate_history(1)
                return True
        return super().eventFilter(obj, event)

    def _execute_command(self):
        command = self.input_edit.toPlainText().strip()
        if not command:
            return

        self._command_history.append(command)
        self._history_index = len(self._command_history)

        self.input_edit.clear()
        self._append_output(f"❯ {command}\n")

        if command in ("clear", "cls"):
            self._clear_output()
            return

        if command.startswith("cd "):
            path = command[3:].strip()
            try:
                new_path = Path(path).resolve() if os.path.isabs(path) else (self._workdir / path).resolve()
                if new_path.is_dir():
                    self._workdir = new_path
                    self.path_label.setText(f"❯")
                    self._append_output(f"[{t('changed_to')} {self._workdir}]\n")
                else:
                    self._append_output(f"[{t('error')}] {t('dir_not_found')}: {path}\n")
            except Exception as e:
                self._append_output(f"[{t('error')}] {e}\n")
            return

        try:
            if sys.platform == "win32":
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(self._workdir),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(self._workdir),
                    text=True,
                )

            output, _ = proc.communicate(timeout=30)
            if output:
                self._append_output(output)
            if proc.returncode != 0:
                self._append_output(f"[{t('exit_code')}: {proc.returncode}]\n")

            self.command_executed.emit(command, output or "")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self._append_output(f"[{t('timeout')}] {t('timeout_message')}\n")
        except Exception as e:
            self._append_output(f"[{t('error')}] {e}\n")

    def _append_output(self, text: str):
        self.output_area.moveCursor(QTextCursor.MoveOperation.End)
        self.output_area.insertPlainText(text)
        self.output_area.moveCursor(QTextCursor.MoveOperation.End)

    def _clear_output(self):
        self.output_area.clear()

    def _navigate_history(self, direction: int):
        if not self._command_history:
            return
        self._history_index += direction
        self._history_index = max(0, min(self._history_index, len(self._command_history)))
        if self._history_index < len(self._command_history):
            self.input_edit.setPlainText(self._command_history[self._history_index])

    def set_workdir(self, path: Path):
        self._workdir = path
        self._append_output(f"\n[{t('changed_to')} {path}]\n")

    def cleanup(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                self._process.kill()

    def update_theme(self, theme):
        self._theme = theme

    def update_language(self):
        if hasattr(self, 'header_label'):
            self.header_label.setText(t("terminal"))
        if hasattr(self, 'clear_btn'):
            self.clear_btn.setText(t("clear"))
