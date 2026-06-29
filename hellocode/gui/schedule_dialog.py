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
        self._setup_ui()
        self._load_schedules()

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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            t("name"), t("task_type"), t("cron_expression"),
            t("last_run"), t("actions"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
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
            last_run = ""
            if s.get("last_run_at"):
                from datetime import datetime
                last_run = datetime.fromtimestamp(s["last_run_at"] / 1000).strftime("%m-%d %H:%M")
            self.table.setItem(i, 3, QTableWidgetItem(last_run))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            toggle_btn = QPushButton(t("disable") if s.get("enabled") else t("enable"))
            toggle_btn.setFixedHeight(24)
            toggle_btn.clicked.connect(lambda _, sid=s["id"], en=s.get("enabled"): self._toggle(sid, en))
            actions_layout.addWidget(toggle_btn)

            delete_btn = QPushButton(t("delete"))
            delete_btn.setFixedHeight(24)
            delete_btn.clicked.connect(lambda _, sid=s["id"]: self._delete(sid))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(i, 4, actions_widget)

        enabled = sum(1 for s in schedules if s.get("enabled"))
        self.status_label.setText(
            f"{t('total')}: {len(schedules)} {t('schedules')}, {enabled} {t('enabled')}"
        )

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
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
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

        self.cron_radio = QRadioButton(t("cron_expression"))
        self.interval_radio = QRadioButton(t("interval_seconds"))
        self.cron_radio.setChecked(True)
        schedule_layout.addWidget(self.cron_radio)

        cron_row = QHBoxLayout()
        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("0 9 * * *")
        cron_row.addWidget(self.cron_edit)
        schedule_layout.addLayout(cron_row)

        schedule_layout.addWidget(self.interval_radio)
        interval_row = QHBoxLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 86400)
        self.interval_spin.setValue(3600)
        self.interval_spin.setSuffix(" s")
        interval_row.addWidget(self.interval_spin)
        schedule_layout.addLayout(interval_row)

        self._schedule_group = QButtonGroup()
        self._schedule_group.addButton(self.cron_radio)
        self._schedule_group.addButton(self.interval_radio)

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
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, t("error"), t("name_required"))
            return

        task_type = self.type_combo.currentText()
        payload = self.payload_edit.toPlainText()
        cron = self.cron_edit.text().strip() if self.cron_radio.isChecked() else None
        interval = self.interval_spin.value() if self.interval_radio.isChecked() else None

        if not cron and not interval:
            QMessageBox.warning(self, t("error"), t("schedule_required"))
            return

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
