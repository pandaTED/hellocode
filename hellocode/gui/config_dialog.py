"""Configuration dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QSpinBox, QPushButton,
    QFormLayout, QWidget, QTabWidget,
)

from ..config import DEFAULT_PROVIDER_PRESETS
from .themes import get_theme_names
from .i18n import t


class ConfigDialog(QDialog):
    """Configuration dialog for settings."""

    config_changed = Signal()
    theme_changed = Signal(str)

    def __init__(self, config, parent=None, config_path: Path | None = None, theme=None):
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        self._theme = theme
        self.setWindowTitle(t("settings_title"))
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        # Tabs
        tabs = QTabWidget()

        # Provider tab
        provider_tab = QWidget()
        provider_layout = QFormLayout(provider_tab)

        self.provider_combo = QComboBox()
        self.provider_combo.setEditable(True)
        self.provider_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.provider_combo.setMaxVisibleItems(8)
        self.provider_combo.addItems(self._provider_names())
        self.provider_combo.setCurrentText(self.config.provider.default)
        completer = self.provider_combo.completer()
        if completer:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
        provider_layout.addRow(t("provider_default"), self.provider_combo)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        provider_layout.addRow(t("api_key"), self.api_key_input)

        self.model_input = QLineEdit()
        provider_layout.addRow(t("model"), self.model_input)

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.openai.com/v1")
        provider_layout.addRow(t("base_url"), self.base_url_input)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1024, 131072)
        self.max_tokens_spin.setSingleStep(1024)
        provider_layout.addRow(t("max_tokens"), self.max_tokens_spin)
        self._load_provider_fields(self.config.provider.default)
        self.provider_combo.activated.connect(
            lambda _index: self._load_provider_fields(self.provider_combo.currentText())
        )
        self.provider_combo.lineEdit().editingFinished.connect(self._load_current_provider_if_known)

        tabs.addTab(provider_tab, t("tab_provider"))

        # Agent tab
        agent_tab = QWidget()
        agent_layout = QFormLayout(agent_tab)

        self.temp_spin = QSpinBox()
        self.temp_spin.setRange(0, 200)
        self.temp_spin.setValue(70)
        self.temp_spin.setSuffix("%")
        agent_layout.addRow(t("temperature"), self.temp_spin)

        self.agent_max_tokens_spin = QSpinBox()
        self.agent_max_tokens_spin.setRange(1024, 131072)
        self.agent_max_tokens_spin.setValue(4096)
        self.agent_max_tokens_spin.setSingleStep(1024)
        agent_layout.addRow(t("agent_max_tokens"), self.agent_max_tokens_spin)

        tabs.addTab(agent_tab, t("tab_agent"))

        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QFormLayout(appearance_tab)

        self.theme_combo = QComboBox()
        for name in get_theme_names():
            self.theme_combo.addItem(t(f"theme_{name}"), name)
        if self._theme:
            index = self.theme_combo.findData(self._theme.name)
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)
        appearance_layout.addRow(t("theme_label"), self.theme_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(13)
        appearance_layout.addRow(t("font_size"), self.font_size_spin)

        tabs.addTab(appearance_tab, t("tab_appearance"))

        layout.addWidget(tabs)

        self.error_label = QLabel("")
        error_color = self._theme.error if self._theme else "#f38ba8"
        self.error_label.setStyleSheet(f"color: {error_color}; padding: 0 2px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton(t("save"))
        save_btn.setObjectName("sendButton")
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _provider_names(self) -> list[str]:
        names = {
            *DEFAULT_PROVIDER_PRESETS.keys(),
            *self.config.provider.providers.keys(),
            self.config.provider.default,
        }
        return sorted(n for n in names if n)

    def _load_provider_fields(self, provider_name: str):
        provider_name = provider_name.strip()
        provider_cfg = {
            **DEFAULT_PROVIDER_PRESETS.get(provider_name, {}),
            **self.config.provider.providers.get(provider_name, {}),
        }
        self.api_key_input.setText(str(provider_cfg.get("apiKey", "")))
        self.model_input.setText(str(provider_cfg.get("model", "")))
        self.base_url_input.setText(str(provider_cfg.get("base_url", "")))
        self.max_tokens_spin.setValue(int(provider_cfg.get("max_tokens", 4096)))

    def _load_current_provider_if_known(self) -> None:
        provider_name = self.provider_combo.currentText().strip()
        if provider_name in DEFAULT_PROVIDER_PRESETS or provider_name in self.config.provider.providers:
            self._load_provider_fields(provider_name)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def _save(self):
        # Save provider config
        provider_name = self.provider_combo.currentText().strip()
        if not provider_name:
            self._show_error(t("provider_name_required"))
            self.provider_combo.setFocus()
            return
        model = self.model_input.text().strip()
        if not model:
            self._show_error(t("provider_model_required"))
            self.model_input.setFocus()
            return
        self._clear_error()
        self.config.provider.default = provider_name

        provider_cfg = self.config.ensure_provider(provider_name)

        provider_cfg["apiKey"] = self.api_key_input.text().strip()
        provider_cfg["model"] = model
        provider_cfg["max_tokens"] = self.max_tokens_spin.value()

        base_url = self.base_url_input.text().strip()
        if base_url:
            provider_cfg["base_url"] = base_url
        else:
            provider_cfg.pop("base_url", None)

        if self.config_path:
            self.config.save_provider_config(self.config_path)

        self.config_changed.emit()
        self.theme_changed.emit(self.theme_combo.currentData())
        self.accept()
