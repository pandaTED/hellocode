"""Knowledge base management panel."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QVBoxLayout, QWidget, QFileDialog,
)

from .i18n import t

logger = logging.getLogger("hellocode.gui.knowledge_panel")


class _IndexWorker(QThread):
    finished = Signal(str, dict)

    def __init__(self, engine, source_id):
        super().__init__()
        self.engine = engine
        self.source_id = source_id

    def run(self):
        try:
            result = self.engine.index_source(self.source_id)
            self.finished.emit(self.source_id, result)
        except Exception as e:
            self.finished.emit(self.source_id, {"error": str(e)})


class KnowledgeSourceItem(QFrame):
    """A single knowledge source entry."""

    def __init__(self, source: dict, theme=None, parent=None):
        super().__init__(parent)
        self.source = source
        self._theme = theme
        self._setup_ui(source)

    def _setup_ui(self, source: dict):
        th = self._theme
        text_color = th.text_primary if th else "#cdd6f4"
        muted_color = th.text_muted if th else "#6c7086"
        accent_color = th.accent if th else "#89b4fa"

        self.setStyleSheet("KnowledgeSourceItem { padding: 4px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 7)
        layout.setSpacing(4)

        name = source.get("name", "Unknown")
        path = source.get("path", "")
        icon = "📁" if source.get("type") == "folder" else "📄"

        title_label = QLabel(f"{icon} {name}")
        title_label.setToolTip(path)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"color: {text_color}; font-size: 13px; font-weight: 500;")
        layout.addWidget(title_label)

        status = source.get("status", "active")
        file_count = source.get("file_count", 0)
        if status == "active":
            status_text = f"{t('indexed')} {file_count} {t('files')}"
            status_color = accent_color
        elif status == "error":
            status_text = t("index_error")
            status_color = "#f38ba8"
        else:
            status_text = status
            status_color = muted_color

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color}; font-size: 11px;")
        layout.addWidget(status_label)


class KnowledgePanel(QWidget):
    """Panel for knowledge base management."""

    source_added = Signal(str)
    source_removed = Signal(str)
    search_requested = Signal(str)

    def __init__(self, storage, data_dir: Path, theme=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.data_dir = data_dir
        self._theme = theme
        self._engine = None
        self.setObjectName("sidePanel")
        self._setup_ui()

    def _get_engine(self):
        if self._engine is None:
            from ..knowledge import KnowledgeEngine
            self._engine = KnowledgeEngine(self.storage, self.data_dir)
        return self._engine

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self.header_label = QLabel(t("knowledge_base"))
        self.header_label.setObjectName("sectionTitle")
        header_layout.addWidget(self.header_label)

        self.add_btn = QPushButton("+")
        self.add_btn.setToolTip(t("add_source"))
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setStyleSheet(f"""
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
        self.add_btn.clicked.connect(self._on_add_source)
        header_layout.addWidget(self.add_btn)

        layout.addWidget(header_frame)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("knowledgeList")
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_widget)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {th.text_muted if th else '#6c7086'}; font-size: 11px; padding: 6px 12px;")
        layout.addWidget(self.status_label)

    def load_sources(self):
        self.list_widget.clear()
        try:
            engine = self._get_engine()
            sources = engine.list_sources()
            for source in sources:
                item = QListWidgetItem()
                widget = KnowledgeSourceItem(source, self._theme)
                item.setSizeHint(widget.sizeHint())
                item.setData(Qt.ItemDataRole.UserRole, source["id"])
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)

            stats = engine.get_stats()
            self.status_label.setText(
                f"{t('total')}: {stats['documents']} {t('documents')}, "
                f"{stats['chunks']} {t('chunks')}"
            )
        except Exception as e:
            logger.error("Failed to load knowledge sources: %s", e)
            self.status_label.setText("")

    def _on_add_source(self):
        menu = QMenu(self)
        folder_action = menu.addAction(t("add_folder"))
        file_action = menu.addAction(t("add_file"))
        action = menu.exec(self.add_btn.mapToGlobal(self.add_btn.rect().bottomLeft()))
        if action == folder_action:
            folder = QFileDialog.getExistingDirectory(self, t("select_folder"))
            if folder:
                self._add_source(Path(folder).name, Path(folder))
        elif action == file_action:
            file_path, _ = QFileDialog.getOpenFileName(
                self, t("select_file"), "",
                "Supported Files (*.md *.txt *.pdf *.docx *.xlsx *.pptx *.csv *.json *.yaml);;All Files (*)"
            )
            if file_path:
                p = Path(file_path)
                self._add_source(p.name, p)

    def _add_source(self, name: str, path: Path):
        try:
            engine = self._get_engine()
            source = engine.add_source(name, path)
            self.source_added.emit(source["id"])
            self.load_sources()
            self._index_source(source["id"])
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        source_id = item.data(Qt.ItemDataRole.UserRole)
        if not source_id:
            return
        menu = QMenu(self)
        index_action = menu.addAction(t("rebuild_index"))
        remove_action = menu.addAction(t("remove_source"))
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == index_action:
            self._index_source(source_id)
        elif action == remove_action:
            self._remove_source(source_id)

    def _index_source(self, source_id: str):
        try:
            engine = self._get_engine()
            self.status_label.setText(t("indexing") + "...")
            self._index_worker = _IndexWorker(engine, source_id)
            self._index_worker.finished.connect(self._on_index_finished)
            self._index_worker.start()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _on_index_finished(self, source_id: str, result: dict):
        if "error" in result:
            self.status_label.setText(f"Error: {result['error']}")
        else:
            indexed = result.get("indexed", 0)
            skipped = result.get("skipped", 0)
            errors = result.get("errors", 0)
            self.status_label.setText(f"{t('indexed')}: {indexed}, {t('skipped')}: {skipped}, {t('errors')}: {errors}")
        self.load_sources()

    def _remove_source(self, source_id: str):
        try:
            engine = self._get_engine()
            engine.remove_source(source_id)
            self.source_removed.emit(source_id)
            self.load_sources()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def update_theme(self, theme) -> None:
        self._theme = theme
        self.add_btn.setStyleSheet(f"""
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
        self.header_label.setText(t("knowledge_base"))
