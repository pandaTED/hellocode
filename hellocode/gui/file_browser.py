"""File browser panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton,
)

from .i18n import t


class FileBrowser(QWidget):
    """File browser with tree view."""

    file_selected = Signal(str)  # file path

    def __init__(self, theme=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self._theme = theme
        self._root_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        th = self._theme
        muted_color = th.text_muted if th else "#6c7086"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with refresh button
        header_layout = QHBoxLayout()
        self.header_label = QLabel(t("files"))
        self.header_label.setObjectName("sectionTitle")
        header_layout.addWidget(self.header_label)

        self.refresh_btn = QPushButton("刷新" if t("refresh_files") == "刷新文件" else "R")
        self.refresh_btn.setToolTip(t("refresh_files"))
        self.refresh_btn.setFixedSize(36, 24)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {muted_color};
                border: none;
                font-size: 16px;
            }}
            QPushButton:hover {{
                color: {th.text_primary if th else "#cdd6f4"};
            }}
        """)
        self.refresh_btn.clicked.connect(self._refresh)
        header_layout.addWidget(self.refresh_btn)
        header_layout.addStretch()

        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget)

        # Path display
        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color: {muted_color}; font-size: 11px; padding: 4px 12px;")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setRootIsDecorated(True)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

    def set_root(self, path: Path):
        self._root_path = path
        self.path_label.setText(str(path))
        self._refresh()

    def _refresh(self):
        if not self._root_path:
            return
        self.tree.clear()
        self._add_items(self.tree, self._root_path)

    def _add_items(self, parent, path: Path, max_depth: int = 2, current_depth: int = 0, max_files: int = 300):
        if current_depth >= max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except (PermissionError, OSError):
            return

        # Skip hidden and common non-essential directories
        skip = {".git", "__pycache__", ".mypy_cache", ".pytest_cache",
                "node_modules", ".tox", ".venv", "venv", ".env"}

        file_count = 0
        for entry in entries:
            if file_count >= max_files:
                item = QTreeWidgetItem(parent)
                item.setText(0, f"... ({len(entries) - file_count} more)")
                item.setForeground(0, self._muted_brush())
                break

            if entry.name.startswith(".") and entry.name not in (".github",):
                continue
            if entry.name in skip:
                continue

            item = QTreeWidgetItem(parent)
            item.setText(0, entry.name)
            item.setData(0, Qt.ItemDataRole.UserRole, str(entry))

            if entry.is_dir():
                item.setIcon(0, self._folder_icon())
                item.setExpanded(False)
                self._add_items(item, entry, max_depth, current_depth + 1, max_files - file_count)
            else:
                item.setIcon(0, self._file_icon(entry.suffix))
                file_count += 1

    def _muted_brush(self):
        from PySide6.QtGui import QBrush, QColor
        color = self._theme.text_muted if self._theme else "#6c7086"
        return QBrush(QColor(color))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and Path(path).is_file():
            self.file_selected.emit(path)

    def _folder_icon(self) -> QIcon:
        # Use a simple colored icon
        from PySide6.QtGui import QPixmap, QColor
        pixmap = QPixmap(16, 16)
        color = self._theme.info if self._theme else "#89b4fa"
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def _file_icon(self, suffix: str) -> QIcon:
        from PySide6.QtGui import QPixmap, QColor
        th = self._theme
        colors = {
            ".py": th.success if th else "#a6e3a1",
            ".js": th.warning if th else "#f9e2af",
            ".ts": th.info if th else "#89b4fa",
            ".json": th.warning if th else "#fab387",
            ".md": th.accent if th else "#cba6f7",
            ".txt": th.text_primary if th else "#cdd6f4",
            ".yml": th.error if th else "#f38ba8",
            ".yaml": th.error if th else "#f38ba8",
        }
        color = colors.get(suffix.lower(), th.text_muted if th else "#6c7086")
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def update_theme(self, theme) -> None:
        self._theme = theme
        muted_color = theme.text_muted
        self.path_label.setStyleSheet(
            f"color: {muted_color}; font-size: 11px; padding: 4px 12px;"
        )
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {muted_color};
                border: none;
                font-size: 16px;
            }}
            QPushButton:hover {{
                color: {theme.text_primary};
            }}
        """)
        self._refresh()

    def update_language(self) -> None:
        self.header_label.setText(t("files"))
        self.refresh_btn.setText("刷新" if t("refresh_files") == "刷新文件" else "R")
        self.refresh_btn.setToolTip(t("refresh_files"))
