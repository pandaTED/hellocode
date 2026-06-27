"""Session management panel."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .i18n import t


class SessionItem(QFrame):
    """A single session entry."""

    def __init__(self, session_id: str, title: str, timestamp: int, theme=None, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self._theme = theme
        self._setup_ui(session_id, title, timestamp)

    def _setup_ui(self, session_id: str, title: str, timestamp: int):
        th = self._theme
        text_color = th.text_primary if th else "#cdd6f4"
        muted_color = th.text_muted if th else "#6c7086"

        self.setStyleSheet("""
            SessionItem {
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 7)
        layout.setSpacing(4)

        title_text = title or t("new_session_title")
        if title_text in ("New Session", "新会话"):
            title_text = t("new_session_title")
        title_label = QLabel(title_text)
        title_label.setToolTip(title_text)
        title_label.setWordWrap(True)
        title_label.setMinimumHeight(38)
        title_label.setMaximumHeight(40)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        title_label.setStyleSheet(
            f"color: {text_color}; font-size: 13px; font-weight: 500;"
        )
        layout.addWidget(title_label)

        time_str = ""
        if timestamp:
            dt = datetime.fromtimestamp(timestamp / 1000)
            time_str = dt.strftime("%m-%d %H:%M")

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)

        meta_row.addStretch(1)

        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {muted_color}; font-size: 11px;")
        meta_row.addWidget(time_label, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(meta_row)

    def sizeHint(self) -> QSize:
        return QSize(220, 78)


class SessionPanel(QWidget):
    """Panel for session management."""

    session_selected = Signal(str)
    session_created = Signal()
    session_delete_requested = Signal(str)

    def __init__(self, storage, theme=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self._theme = theme
        self.setObjectName("sidePanel")
        self._current_session_id: str | None = None
        self._loading = False
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self.header_label = QLabel(t("sessions"))
        self.header_label.setObjectName("sectionTitle")
        header_layout.addWidget(self.header_label)

        self.new_btn = QPushButton("+")
        self.new_btn.setToolTip(t("new_session"))
        self.new_btn.setFixedSize(28, 28)
        self.new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {th.bg_elevated if th else '#313244'};
                color: {th.text_primary if th else '#cdd6f4'};
                border: 1px solid {th.border if th else '#45475a'};
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {th.bg_hover if th else '#45475a'};
                border-color: {th.accent if th else '#89b4fa'};
            }}
        """)
        self.new_btn.clicked.connect(self._on_new_session)
        header_layout.addWidget(self.new_btn)

        layout.addWidget(header_frame)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("sessionList")
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_widget)

    def load_sessions(self, project_id: str):
        self._loading = True
        old_blocked = self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            sessions = self.storage.list_sessions(project_id)
            for s in sessions:
                item = QListWidgetItem()
                widget = SessionItem(
                    s["id"],
                    s.get("title", ""),
                    s.get("time_updated", 0),
                    self._theme,
                )
                item.setSizeHint(widget.sizeHint())
                item.setData(Qt.ItemDataRole.UserRole, s["id"])
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)
        finally:
            self.list_widget.blockSignals(old_blocked)
            self._loading = False

    def set_current_session(self, session_id: str):
        self._current_session_id = session_id
        old_blocked = self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self.list_widget.setCurrentItem(item)
                break
        self.list_widget.blockSignals(old_blocked)

    def _on_selection_changed(self, row: int):
        if self._loading or row < 0:
            return
        item = self.list_widget.item(row)
        if item:
            session_id = item.data(Qt.ItemDataRole.UserRole)
            if session_id and session_id != self._current_session_id:
                self._current_session_id = session_id
                self.session_selected.emit(session_id)

    def _on_new_session(self):
        self.session_created.emit()

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if not session_id:
            return
        menu = QMenu(self)
        delete_action = menu.addAction(t("delete_session"))
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == delete_action:
            self.session_delete_requested.emit(session_id)

    def update_theme(self, theme) -> None:
        self._theme = theme
        self.new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.bg_elevated};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {theme.bg_hover};
                border-color: {theme.accent};
            }}
        """)

    def update_language(self) -> None:
        self.header_label.setText(t("sessions"))
        self.new_btn.setToolTip(t("new_session"))
