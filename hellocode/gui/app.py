"""Main GUI application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFrame, QLabel, QPushButton,
    QMessageBox, QFileDialog, QMenuBar,
)

from ..config import Config
from ..storage import Storage
from ..provider import LLMProvider
from ..memory import MemorySystem
from ..agent import AgentLoop, ActorManager

from .chat_panel import ChatPanel
from .tool_panel import ToolPanel
from .session_panel import SessionPanel
from .task_panel import TaskPanel
from .file_browser import FileBrowser
from .config_dialog import ConfigDialog
from .worker import AgentWorker
from .themes import get_theme, get_theme_names, generate_stylesheet
from .i18n import t, set_language, get_language, get_language_names


class WindowControlButton(QPushButton):
    def __init__(self, kind: str, color: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.color = QColor(color)
        self.setFixedSize(24, 24)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none; padding: 0;")

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.rect().center()
        radius = 8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)
        painter.drawEllipse(center, radius, radius)

        icon_color = QColor("#1e1e2e")
        icon_color.setAlpha(190 if self.underMouse() else 120)
        pen = QPen(icon_color, 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        cx, cy = center.x(), center.y()
        if self.kind == "close":
            painter.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
            painter.drawLine(cx + 4, cy - 4, cx - 4, cy + 4)
        elif self.kind == "minimize":
            painter.drawLine(cx - 5, cy, cx + 5, cy)
        elif self.kind == "maximize":
            painter.drawRect(cx - 4, cy - 4, 8, 8)


class HelloCodeGUI(QMainWindow):
    """Main application window."""

    def __init__(self, config: Config, storage: Storage, provider: LLMProvider,
                 memory: MemorySystem, agent_loop: AgentLoop,
                 actor_manager: ActorManager, workdir: Path,
                 project: dict, session_id: str, theme_name: str = "midnight"):
        super().__init__()
        self.config = config
        self.storage = storage
        self.provider = provider
        self.memory = memory
        self.agent_loop = agent_loop
        self.actor_manager = actor_manager
        self.workdir = workdir
        self.project = project
        self.session_id = session_id
        self._worker: AgentWorker | None = None
        self._current_tool_entry = None
        self._theme = get_theme(theme_name)
        self._drag_pos: QPoint | None = None

        self._setup_window()
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._load_data()

    def _setup_window(self):
        self.setWindowTitle("HelloCode")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.setStyleSheet(generate_stylesheet(self._theme))

    def _setup_menu(self):
        if not hasattr(self, "_menu_bar"):
            self._menu_bar = QMenuBar(self.title_menu_host)
            self._menu_bar.setNativeMenuBar(False)
            self._menu_bar.setFixedHeight(34)
            self.title_menu_layout.addWidget(self._menu_bar)
        self._style_menu_bar()
        menubar = self._menu_bar
        menubar.clear()

        # File menu
        file_menu = menubar.addMenu(t("menu_file"))

        new_session = QAction(t("new_session"), self)
        new_session.setShortcut(QKeySequence("Ctrl+N"))
        new_session.triggered.connect(self._new_session)
        file_menu.addAction(new_session)

        open_folder = QAction(t("open_folder"), self)
        open_folder.setShortcut(QKeySequence("Ctrl+O"))
        open_folder.triggered.connect(self._open_folder)
        file_menu.addAction(open_folder)

        file_menu.addSeparator()

        settings = QAction(t("settings"), self)
        settings.setShortcut(QKeySequence("Ctrl+,"))
        settings.triggered.connect(self._open_settings)
        file_menu.addAction(settings)

        file_menu.addSeparator()

        quit_action = QAction(t("quit"), self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu(t("menu_edit"))

        clear_chat = QAction(t("clear_chat"), self)
        clear_chat.setShortcut(QKeySequence("Ctrl+L"))
        clear_chat.triggered.connect(self._clear_chat)
        edit_menu.addAction(clear_chat)

        # View menu
        view_menu = menubar.addMenu(t("menu_view"))

        toggle_tools = QAction(t("toggle_tool_panel"), self)
        toggle_tools.setShortcut(QKeySequence("Ctrl+T"))
        toggle_tools.triggered.connect(self._toggle_tool_panel)
        view_menu.addAction(toggle_tools)

        toggle_files = QAction(t("toggle_file_browser"), self)
        toggle_files.setShortcut(QKeySequence("Ctrl+B"))
        toggle_files.triggered.connect(self._toggle_file_browser)
        view_menu.addAction(toggle_files)

        # Theme submenu
        theme_menu = view_menu.addMenu(t("menu_theme"))
        for name in get_theme_names():
            action = QAction(t(f"theme_{name}"), self)
            action.triggered.connect(lambda checked, n=name: self._switch_theme(n))
            theme_menu.addAction(action)

        # Language submenu
        lang_menu = view_menu.addMenu(t("menu_language"))
        for lang in get_language_names():
            label = "中文" if lang == "zh" else t("language_english")
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(lang == get_language())
            action.triggered.connect(lambda checked, l=lang: self._switch_language(l))
            lang_menu.addAction(action)

        # Help menu
        help_menu = menubar.addMenu(t("menu_help"))

        about = QAction(t("about"), self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _style_menu_bar(self) -> None:
        self._menu_bar.setStyleSheet(f"""
            QMenuBar {{
                background-color: transparent;
                color: {self._theme.text_secondary};
                border: none;
                padding: 0;
                font-size: 13px;
            }}
            QMenuBar::item {{
                padding: 8px 10px;
                margin: 0;
                background-color: transparent;
            }}
            QMenuBar::item:selected {{
                background-color: {self._theme.selection};
                color: {self._theme.text_primary};
            }}
        """)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._setup_title_bar(root_layout)

        content = QWidget()
        main_layout = QHBoxLayout(content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel (sessions + tasks)
        left_panel = QFrame()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        left_splitter = QSplitter(Qt.Orientation.Vertical)

        self.session_panel = SessionPanel(self.storage, self._theme)
        self.session_panel.session_selected.connect(self._on_session_selected)
        self.session_panel.session_created.connect(self._new_session)
        self.session_panel.session_delete_requested.connect(self._delete_session)
        left_splitter.addWidget(self.session_panel)

        self.task_panel = TaskPanel(self.storage, self._theme)
        left_splitter.addWidget(self.task_panel)

        left_splitter.setSizes([300, 200])
        left_layout.addWidget(left_splitter)
        self.main_splitter.addWidget(left_panel)

        # Center panel (chat)
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.chat_panel = ChatPanel(self._theme)
        self.chat_panel.message_sent.connect(self._on_message_sent)
        center_layout.addWidget(self.chat_panel)

        self.main_splitter.addWidget(center_panel)

        # Right panel (tools + files)
        right_panel = QFrame()
        right_panel.setObjectName("sidePanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.tool_panel = ToolPanel(self._theme)
        right_splitter.addWidget(self.tool_panel)

        self.file_browser = FileBrowser(self._theme)
        self.file_browser.file_selected.connect(self._on_file_selected)
        right_splitter.addWidget(self.file_browser)

        self.right_splitter = right_splitter
        right_splitter.setSizes([140, 360])
        right_layout.addWidget(right_splitter)
        self.main_splitter.addWidget(right_panel)

        # Set splitter sizes
        self.main_splitter.setSizes([250, 700, 300])

        main_layout.addWidget(self.main_splitter)
        root_layout.addWidget(content, 1)

        # Store references for toggling
        self._left_panel = left_panel
        self._right_panel = right_panel

    def _setup_title_bar(self, root_layout: QVBoxLayout):
        t = self._theme
        self.title_bar = QFrame()
        title_bar = self.title_bar
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(34)
        self._style_title_bar()
        title_bar.mousePressEvent = self._title_mouse_press
        title_bar.mouseMoveEvent = self._title_mouse_move
        title_bar.mouseReleaseEvent = self._title_mouse_release
        title_bar.mouseDoubleClickEvent = self._title_mouse_double_click

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self.title_label = QLabel("HelloCode")
        self.title_label.setFixedHeight(34)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setStyleSheet(f"color: {t.text_secondary}; font-size: 13px; font-weight: 600; padding: 0;")
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_menu_host = QWidget()
        self.title_menu_host.setFixedHeight(34)
        self.title_menu_layout = QHBoxLayout(self.title_menu_host)
        self.title_menu_layout.setContentsMargins(4, 0, 0, 0)
        self.title_menu_layout.setSpacing(0)
        layout.addWidget(self.title_menu_host, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        self.min_button = WindowControlButton("minimize", t.warning)
        self.max_button = WindowControlButton("maximize", t.success)
        self.close_button = WindowControlButton("close", t.error)
        self.min_button.clicked.connect(self.showMinimized)
        self.max_button.clicked.connect(self._toggle_maximized)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.min_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.max_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)
        root_layout.addWidget(title_bar)

    def _style_title_bar(self) -> None:
        t = self._theme
        self.title_bar.setStyleSheet(f"""
            QFrame#titleBar {{
                background-color: {t.bg_panel};
                border-bottom: 1px solid {t.border};
            }}
        """)
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(
                f"color: {t.text_secondary}; font-size: 13px; font-weight: 600; padding: 0;"
            )
        if hasattr(self, "min_button"):
            self.min_button.set_color(t.warning)
            self.max_button.set_color(t.success)
            self.close_button.set_color(t.error)

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_mouse_move(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self.isMaximized():
                return
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _title_mouse_release(self, event):
        self._drag_pos = None
        event.accept()

    def _title_mouse_double_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximized()
            event.accept()

    def _setup_status_bar(self):
        status_bar = self.statusBar()
        self.model_label = QLabel(f"{t('model_label')}{self.config.get_provider_model()}")
        self.session_label = QLabel("")
        self.status_label = QLabel(t("ready"))

        status_bar.addWidget(self.model_label)
        status_bar.addPermanentWidget(self.status_label)

    def _load_data(self):
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)
        self.task_panel.load_tasks(self.session_id)
        self.file_browser.set_root(self.workdir)

        # Load chat history
        messages = self.storage.list_messages(self.session_id)
        for msg in messages:
            data = msg.get("data", {})
            role = data.get("role", "")
            if role == "user":
                content = data.get("content", "")
                if content:
                    self.chat_panel.add_user_message(content)
            elif role == "assistant":
                content = data.get("content", "")
                if content:
                    self.chat_panel.add_assistant_message(content)

    @Slot(str)
    def _on_message_sent(self, text: str):
        try:
            self._maybe_generate_session_title(text)
            self.status_label.setText(t("thinking"))
            self.chat_panel.set_input_enabled(False)

            # Create new worker
            self._worker = AgentWorker(
                self.agent_loop,
                self.session_id,
                text,
                "build",
                self.workdir,
            )
            self._worker.message_received.connect(self._on_agent_message)
            self._worker.tool_call_started.connect(self._on_tool_call)
            self._worker.tool_call_finished.connect(self._on_tool_result)
            self._worker.finished.connect(self._on_agent_finished)
            self._worker.error.connect(self._on_agent_error)
            self._worker.thread_finished.connect(self._on_worker_thread_finished)
            self._worker.start()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.chat_panel.add_system_message(f"启动错误: {e}")
            self.chat_panel.set_input_enabled(True)

    def _make_session_title(self, text: str) -> str:
        cleaned = " ".join(str(text).split())
        cleaned = cleaned.strip(" \t\r\n.,，。!?！？;；:：、")
        if not cleaned:
            return t("new_session_title")
        if len(cleaned) > 18:
            cleaned = cleaned[:18].rstrip() + "..."
        return cleaned

    def _maybe_generate_session_title(self, text: str):
        session = self.storage.get_session(self.session_id)
        current_title = (session or {}).get("title") or ""
        if current_title and current_title not in {"New Session", "新会话", t("new_session_title")}:
            return
        title = self._make_session_title(text)
        if not title or title == current_title:
            return
        self.storage.update_session(self.session_id, title=title)
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)

    @Slot(str, str)
    def _on_agent_message(self, kind: str, content: str):
        if kind == "stream":
            if not self.chat_panel._current_assistant:
                self.chat_panel.start_assistant_stream()
            self.chat_panel.append_stream(content)
        elif kind == "finish":
            self.chat_panel.finish_stream()
        elif kind == "error":
            self.chat_panel.add_system_message(f"{t('error_prefix')}{content}")

    @Slot(str, dict)
    def _on_tool_call(self, name: str, args: dict):
        # Add to tool panel
        entry = self.tool_panel.add_tool_call(name, args)
        self._current_tool_entry = entry

        # For question tool, also render in chat area
        if name == "question":
            self.chat_panel.add_tool_call(name, args)

    @Slot(str, str, bool)
    def _on_tool_result(self, name: str, result: str, success: bool):
        # Update tool panel entry
        if hasattr(self, "_current_tool_entry") and self._current_tool_entry:
            if success:
                self._current_tool_entry.set_success(result)
            else:
                self._current_tool_entry.set_error(result)
            self._current_tool_entry = None

    @Slot(str)
    def _on_agent_finished(self, result: str):
        # If streaming was active, the message is already displayed.
        # Only add a new message if no streaming happened.
        if self.chat_panel._stream_buffer:
            # Finalize the streamed message
            self.chat_panel.finish_stream()
        streamed = self.chat_panel.consume_stream_finalized()
        if result and not streamed:
            self.chat_panel.add_assistant_message(result)
        self.chat_panel.set_input_enabled(True)
        self.status_label.setText(t("ready"))
        self.task_panel.refresh()

    @Slot(str)
    def _on_agent_error(self, error: str):
        # Friendly error messages
        if "429" in error or "Too Many Requests" in error:
            friendly = t("error_rate_limit")
        elif "401" in error or "Unauthorized" in error:
            friendly = t("error_auth")
        elif "404" in error or "Not Found" in error:
            friendly = t("error_not_found")
        elif "timeout" in error.lower():
            friendly = t("error_timeout")
        else:
            friendly = error
        self.chat_panel.add_system_message(f"{t('error_prefix')}{friendly}")
        self.chat_panel.set_input_enabled(True)
        self.status_label.setText(t("error"))

    @Slot()
    def _on_worker_thread_finished(self):
        self._worker = None

    @Slot(str)
    def _on_session_selected(self, session_id: str):
        self.session_id = session_id
        self.chat_panel.clear()
        self.tool_panel.clear()
        self.task_panel.load_tasks(session_id)
        self._load_chat_history(session_id)

    def _load_chat_history(self, session_id: str):
        messages = self.storage.list_messages(session_id)
        for msg in messages:
            data = msg.get("data", {})
            role = data.get("role", "")
            if role == "user":
                content = data.get("content", "")
                if content:
                    self.chat_panel.add_user_message(content)
            elif role == "assistant":
                content = data.get("content", "")
                tool_calls = data.get("tool_calls")
                if content:
                    self.chat_panel.add_assistant_message(content)
                # Note: tool calls from history are not re-rendered to avoid
                # re-executing them. They are already in the tool panel.

    def _new_session(self):
        session = self.storage.create_session(
            self.project["id"], str(self.workdir), t("new_session_title")
        )
        self.session_id = session["id"]
        self.chat_panel.clear()
        self.tool_panel.clear()
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)
        self.task_panel.load_tasks(self.session_id)

    def _delete_session(self, session_id: str):
        if self._worker and session_id == self.session_id:
            self._show_warning(t("wait_current_run_delete_session"))
            return
        if not self._confirm_action(
            t("delete_session_title"),
            t("delete_session_confirm"),
            t("delete"),
        ):
            return

        self.storage.delete_session(session_id)
        sessions = self.storage.list_sessions(self.project["id"], limit=1)
        if sessions:
            next_session_id = sessions[0]["id"]
        else:
            session = self.storage.create_session(self.project["id"], str(self.workdir), t("new_session_title"))
            next_session_id = session["id"]

        self.session_id = next_session_id
        self.chat_panel.clear()
        self.tool_panel.clear()
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)
        self.task_panel.load_tasks(self.session_id)
        self._load_chat_history(self.session_id)

    def _open_folder(self):
        if self._worker:
            self._show_warning(t("wait_current_run_open_folder"))
            return
        folder = QFileDialog.getExistingDirectory(self, t("open_folder_dialog"), str(self.workdir))
        if folder:
            self._switch_workdir(Path(folder).resolve())

    def _switch_workdir(self, workdir: Path):
        project = self.storage.find_project_by_worktree(str(workdir))
        if not project:
            project = self.storage.create_project(str(workdir), workdir.name)

        sessions = self.storage.list_sessions(project["id"], limit=1)
        if sessions:
            session_id = sessions[0]["id"]
        else:
            session = self.storage.create_session(project["id"], str(workdir), t("new_session_title"))
            session_id = session["id"]

        self.workdir = workdir
        self.project = project
        self.session_id = session_id
        self.chat_panel.clear()
        self.tool_panel.clear()
        self.file_browser.set_root(self.workdir)
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)
        self.task_panel.load_tasks(self.session_id)
        self._load_chat_history(self.session_id)

    def _open_settings(self):
        dialog = ConfigDialog(self.config, self, self.workdir / "hellocode.json", self._theme)
        dialog.config_changed.connect(self._on_config_changed)
        dialog.theme_changed.connect(self._switch_theme)
        dialog.exec()

    def _on_config_changed(self):
        self.provider = LLMProvider(self.config)
        self.agent_loop.provider = self.provider
        self.actor_manager.provider = self.provider
        self.model_label.setText(f"{t('model_label')}{self.config.get_provider_model()}")

    def _clear_chat(self):
        if self._worker:
            self._show_warning(t("wait_current_run_clear_sessions"))
            return
        if not self._confirm_action(
            t("delete_all_sessions_title"),
            t("delete_all_sessions_confirm"),
            t("clear"),
        ):
            return

        for session in self.storage.list_sessions(self.project["id"], limit=10000):
            self.storage.delete_session(session["id"])

        session = self.storage.create_session(
            self.project["id"], str(self.workdir), t("new_session_title")
        )
        self.session_id = session["id"]
        self.chat_panel.clear()
        self.tool_panel.clear()
        self.task_panel.load_tasks(self.session_id)
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)

    def _toggle_tool_panel(self):
        self._right_panel.setVisible(not self._right_panel.isVisible())

    def _toggle_file_browser(self):
        self.file_browser.setVisible(not self.file_browser.isVisible())

    def _switch_theme(self, theme_name: str):
        self._theme = get_theme(theme_name)
        self.setStyleSheet(generate_stylesheet(self._theme))
        self._style_title_bar()
        self._style_menu_bar()
        # Notify all child panels to update their colors
        if hasattr(self, 'chat_panel'):
            self.chat_panel.update_theme(self._theme)
        if hasattr(self, 'tool_panel'):
            self.tool_panel.update_theme(self._theme)
        if hasattr(self, 'task_panel'):
            self.task_panel.update_theme(self._theme)
        if hasattr(self, 'session_panel'):
            self.session_panel.update_theme(self._theme)
            self.session_panel.load_sessions(self.project["id"])
        if hasattr(self, 'file_browser'):
            self.file_browser.update_theme(self._theme)

    def _switch_language(self, lang: str):
        set_language(lang)
        # Rebuild menu to reflect new language
        self._setup_menu()
        # Update status bar
        self.model_label.setText(f"{t('model_label')}{self.config.get_provider_model()}")
        # Update chat input placeholder
        if hasattr(self, 'chat_panel'):
            self.chat_panel.update_language()
        if hasattr(self, 'tool_panel'):
            self.tool_panel.update_language()
        if hasattr(self, 'task_panel'):
            self.task_panel.update_language()
        if hasattr(self, 'session_panel'):
            self.session_panel.update_language()
            self.session_panel.load_sessions(self.project["id"])
            self.session_panel.set_current_session(self.session_id)
        if hasattr(self, 'file_browser'):
            self.file_browser.update_language()

    @Slot(str)
    def _on_file_selected(self, file_path: str):
        """Handle file selection from browser."""
        self.status_label.setText(f"{t('file_label')}{file_path}")

    def _confirm_action(self, title: str, message: str, confirm_text: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(message)
        cancel_btn = box.addButton(t("cancel"), QMessageBox.ButtonRole.RejectRole)
        confirm_btn = box.addButton(confirm_text, QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        return box.clickedButton() == confirm_btn

    def _show_warning(self, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("HelloCode")
        box.setText(message)
        box.addButton(t("ok"), QMessageBox.ButtonRole.AcceptRole)
        box.exec()

    def _show_about(self):
        from .. import __version__
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(t("about_title"))
        box.setText(t("about_text", version=__version__))
        box.addButton(t("ok"), QMessageBox.ButtonRole.AcceptRole)
        box.exec()

    def closeEvent(self, event):
        # Stop any running worker
        if self._worker:
            self._worker.stop()
            self._worker.wait(3000)
            self._worker = None
        # Close storage
        try:
            self.storage.close()
        except Exception:
            pass
        event.accept()
