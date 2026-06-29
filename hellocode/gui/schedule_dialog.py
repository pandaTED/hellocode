"""Schedule management dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QSpinBox, QPushButton,
    QFormLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QRadioButton, QButtonGroup,
    QGroupBox, QMessageBox,
)

from .i18n import t


class ScheduleDialog(QDialog):
    """Dialog for managing scheduled tasks."""

    schedule_changed = Signal()

    def __init__(self, storage, parent=None, theme=None):
        super().__init__(parent)
        self.storage = storage
        self._theme = theme
        self.setWindowTitle(t("schedules"))
        self.setMinimumSize(700, 450)
        self._apply_theme()
        self._setup_ui()
        self._load_schedules()

    def _apply_theme(self):
        th = self._theme
        if not th:
            return
        bg = th.bg_panel if hasattr(th, 'bg_panel') else "#1e1e2e"
        text = th.text_primary if hasattr(th, 'text_primary') else "#cdd6f4"
        muted = th.text_muted if hasattr(th, 'text_muted') else "#6c7086"
        border = th.border if hasattr(th, 'border') else "#45475a"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {text};
            }}
            QLabel {{
                color: {text};
            }}
            QTableWidget {{
                background-color: {th.bg_secondary if hasattr(th, 'bg_secondary') else "#313244"};
                color: {text};
                border: 1px solid {border};
                gridline-color: {border};
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {th.accent if hasattr(th, 'accent') else "#89b4fa"};
            }}
            QHeaderView::section {{
                background-color: {th.bg_secondary if hasattr(th, 'bg_secondary') else "#313244"};
                color: {text};
                border: 1px solid {border};
                padding: 4px;
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {th.bg_secondary if hasattr(th, 'bg_secondary') else "#313244"};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton(t("new_schedule"))
        self.add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            t("name"), t("task_type"), t("cron_expression"),
            t("next_run"), t("last_run"), t("actions"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {th.text_muted if th else '#6c7086'}; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _load_schedules(self):
        schedules = self.storage.list_schedules()
        self.table.setRowCount(len(schedules))
        for i, s in enumerate(schedules):
            self.table.setItem(i, 0, QTableWidgetItem(s.get("name", "")))
            self.table.setItem(i, 1, QTableWidgetItem(s.get("task_type", "")))
            schedule_str = s.get("cron_expression") or f"{s.get('interval_seconds', 0)}s"
            self.table.setItem(i, 2, QTableWidgetItem(schedule_str))

            next_run = ""
            if s.get("next_run_at"):
                from datetime import datetime
                next_run = datetime.fromtimestamp(s["next_run_at"] / 1000).strftime("%m-%d %H:%M")
            self.table.setItem(i, 3, QTableWidgetItem(next_run))

            last_run = ""
            if s.get("last_run_at"):
                from datetime import datetime
                last_run = datetime.fromtimestamp(s["last_run_at"] / 1000).strftime("%m-%d %H:%M")
            self.table.setItem(i, 4, QTableWidgetItem(last_run))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            history_btn = QPushButton(t("history"))
            history_btn.setFixedHeight(24)
            history_btn.clicked.connect(lambda _, sid=s["id"], name=s.get("name", ""): self._show_history(sid, name))
            actions_layout.addWidget(history_btn)

            toggle_btn = QPushButton(t("disable") if s.get("enabled") else t("enable"))
            toggle_btn.setFixedHeight(24)
            toggle_btn.clicked.connect(lambda _, sid=s["id"], en=s.get("enabled"): self._toggle(sid, en))
            actions_layout.addWidget(toggle_btn)

            delete_btn = QPushButton(t("delete"))
            delete_btn.setFixedHeight(24)
            delete_btn.clicked.connect(lambda _, sid=s["id"]: self._delete(sid))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(i, 5, actions_widget)

        enabled = sum(1 for s in schedules if s.get("enabled"))
        self.status_label.setText(
            f"{t('total')}: {len(schedules)} {t('schedules')}, {enabled} {t('enabled')}"
        )

    def _show_history(self, schedule_id: str, schedule_name: str):
        runs = self.storage.get_schedule_runs(schedule_id, limit=20)
        if not runs:
            QMessageBox.information(self, t("execution_history"), f"{schedule_name}: {t('no_execution_history')}")
            return
        from datetime import datetime
        lines = []
        for r in runs:
            started = datetime.fromtimestamp(r["started_at"] / 1000).strftime("%m-%d %H:%M:%S") if r.get("started_at") else "?"
            status = r.get("status", "?")
            result = (r.get("result") or "")[:200]
            error = (r.get("error_message") or "")[:100]
            lines.append(f"[{started}] {status}\n{result}\n{error}\n{'─' * 40}")
        QMessageBox.information(self, f"{t('execution_history')} - {schedule_name}", "\n".join(lines))

    def _on_add(self):
        dialog = ScheduleEditDialog(self.storage, self._theme, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_schedules()
            self.schedule_changed.emit()

    def _toggle(self, schedule_id: str, currently_enabled: bool):
        self.storage.update_schedule(schedule_id, enabled=0 if currently_enabled else 1)
        self._load_schedules()
        self.schedule_changed.emit()

    def _delete(self, schedule_id: str):
        reply = QMessageBox.question(
            self, t("confirm"), t("delete_schedule_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.storage.delete_schedule(schedule_id)
            self._load_schedules()
            self.schedule_changed.emit()


class ScheduleEditDialog(QDialog):
    """Dialog for creating/editing a schedule."""

    def __init__(self, storage, theme=None, parent=None, schedule: dict | None = None):
        super().__init__(parent)
        self.storage = storage
        self._theme = theme
        self.schedule = schedule
        self.setWindowTitle(t("new_schedule") if not schedule else t("edit_schedule"))
        self.setMinimumSize(450, 380)
        self._apply_theme()
        self._setup_ui()

    def _apply_theme(self):
        th = self._theme
        if not th:
            return
        bg = th.bg_panel if hasattr(th, 'bg_panel') else "#1e1e2e"
        text = th.text_primary if hasattr(th, 'text_primary') else "#cdd6f4"
        muted = th.text_muted if hasattr(th, 'text_muted') else "#6c7086"
        border = th.border if hasattr(th, 'border') else "#45475a"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {text};
            }}
            QLabel {{
                color: {text};
            }}
            QGroupBox {{
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QLineEdit, QSpinBox, QTextEdit, QComboBox {{
                background-color: {th.bg_secondary if hasattr(th, 'bg_secondary') else "#313244"};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid {th.accent if hasattr(th, 'accent') else "#89b4fa"};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {th.bg_secondary if hasattr(th, 'bg_secondary') else "#313244"};
                color: {text};
                border: 1px solid {border};
                selection-background-color: {th.accent if hasattr(th, 'accent') else "#89b4fa"};
            }}
            QPushButton {{
                background-color: {th.bg_secondary if hasattr(th, 'bg_secondary') else "#313244"};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
            QPushButton#saveBtn {{
                background-color: {th.accent if hasattr(th, 'accent') else "#89b4fa"};
                color: {th.bg if hasattr(th, 'bg') else "#1e1e2e"};
                border: none;
                font-weight: bold;
            }}
            QPushButton#saveBtn:hover {{
                background-color: {th.accent_hover if hasattr(th, 'accent_hover') else "#74c7ec"};
            }}
            QRadioButton {{
                color: {text};
                spacing: 6px;
            }}
            QRadioButton::indicator {{
                width: 14px;
                height: 14px;
            }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(t("schedule_name_placeholder"))
        form.addRow(t("name") + ":", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["shell_command", "agent_prompt", "workflow"])
        form.addRow(t("task_type") + ":", self.type_combo)

        schedule_group = QGroupBox(t("schedule_method"))
        schedule_layout = QVBoxLayout(schedule_group)

        freq_row = QHBoxLayout()
        freq_label = QLabel(t("execution_frequency") + ":")
        self.freq_combo = QComboBox()
        self.freq_combo.addItems([t("freq_second"), t("freq_minute"), t("freq_hour"), t("freq_day"), t("freq_custom_cron")])
        self.freq_combo.currentIndexChanged.connect(self._on_freq_changed)
        freq_row.addWidget(freq_label)
        freq_row.addWidget(self.freq_combo, 1)
        schedule_layout.addLayout(freq_row)

        self.freq_spin = QSpinBox()
        self.freq_spin.setRange(1, 365)
        self.freq_spin.setValue(1)
        self.freq_spin.setSuffix("")
        self.freq_spin_label = QLabel(t("multiplier") + ":")
        self.freq_layout = QHBoxLayout()
        self.freq_layout.addWidget(self.freq_spin_label)
        self.freq_layout.addWidget(self.freq_spin, 1)
        schedule_layout.addLayout(self.freq_layout)

        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("min hour day month weekday (e.g.: 0 9 * * *)")
        self.cron_edit.setVisible(False)
        schedule_layout.addWidget(self.cron_edit)

        form.addRow(schedule_group)

        self.payload_edit = QTextEdit()
        self.payload_edit.setPlaceholderText(t("schedule_payload_placeholder"))
        self.payload_edit.setMaximumHeight(120)
        form.addRow(t("payload") + ":", self.payload_edit)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton(t("save"))
        save_btn.setObjectName("saveBtn")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_freq_changed(self, index):
        is_custom = index == 4
        self.freq_spin.setVisible(not is_custom)
        self.freq_spin_label.setVisible(not is_custom)
        self.cron_edit.setVisible(is_custom)
        if is_custom:
            self.freq_spin_label.setText("")
        else:
            self.freq_spin_label.setText(t("interval_desc"))

    def _get_interval_seconds(self) -> int | None:
        freq_index = self.freq_combo.currentIndex()
        if freq_index == 4:
            return None
        multi = self.freq_spin.value()
        base = [1, 60, 3600, 86400]
        return base[freq_index] * multi

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, t("error"), t("name_required"))
            return

        task_type = self.type_combo.currentText()
        payload = self.payload_edit.toPlainText()
        cron = self.cron_edit.text().strip() if self.freq_combo.currentIndex() == 4 else None
        interval = self._get_interval_seconds()

        if not cron and not interval:
            QMessageBox.warning(self, t("error"), t("schedule_required"))
            return

        if cron:
            fields = cron.split()
            if len(fields) != 5:
                QMessageBox.warning(self, t("error"), t("cron_validation_error"))
                return

        try:
            if self.schedule:
                self.storage.update_schedule(
                    self.schedule["id"], name=name, task_type=task_type,
                    payload=payload, cron_expression=cron, interval_seconds=interval,
                )
            else:
                from ..scheduler import next_cron_time, next_interval_time
                now = self.storage.now()
                if cron:
                    next_run = next_cron_time(cron, now)
                else:
                    next_run = next_interval_time(interval, now)
                self.storage.create_schedule(
                    id=self.storage.uid(), name=name, task_type=task_type,
                    payload=payload, cron_expression=cron, interval_seconds=interval,
                    next_run_at=next_run,
                )
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, t("error"), f"{t('save_failed')} {e}")
