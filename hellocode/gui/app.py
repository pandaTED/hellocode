"""Main GUI application window."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Slot, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFrame, QLabel, QPushButton,
    QMessageBox, QFileDialog, QMenuBar, QTabBar, QStackedWidget,
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
from .knowledge_panel import KnowledgePanel
from .schedule_dialog import ScheduleDialog
from .schedule_log_panel import ScheduleLogPanel
from .terminal_panel import TerminalPanel
from .performance_panel import PerformancePanel
from .chat_export import export_chat_to_markdown
from .bookmarks import BookmarkManager
from .themes import get_theme, get_theme_names, generate_stylesheet
from .i18n import t, set_language, get_language, get_language_names

logger = logging.getLogger("hellocode.gui.app")


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


@dataclass
class TabState:
    tab_id: str
    session_id: str
    workdir: Path
    chat_panel: ChatPanel
    tool_panel: ToolPanel
    task_panel: TaskPanel
    worker: AgentWorker | None = None
    agent_name: str = "build"
    _tool_entries: list = None

    def __post_init__(self):
        if self._tool_entries is None:
            self._tool_entries = []


class HelloCodeGUI(QMainWindow):
    """Main application window."""

    def __init__(self, config: Config, storage: Storage, provider: LLMProvider,
                 memory: MemorySystem, agent_loop: AgentLoop,
                 actor_manager: ActorManager, workdir: Path,
                 project: dict, session_id: str, theme_name: str = "midnight",
                 scheduler=None):
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
        self._tabs: dict[str, TabState] = {}
        self._active_tab_id: str | None = None
        self._scheduler = scheduler
        self._bookmark_manager = BookmarkManager(storage)

        self._setup_window()
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._create_initial_tab()
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

        schedules = QAction(t("schedules"), self)
        schedules.setShortcut(QKeySequence("Ctrl+Shift+S"))
        schedules.triggered.connect(self._open_schedules)
        file_menu.addAction(schedules)

        export_chat = QAction(t("export_chat"), self)
        export_chat.setShortcut(QKeySequence("Ctrl+E"))
        export_chat.triggered.connect(self._export_chat)
        file_menu.addAction(export_chat)

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

        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close)
        self._tab_bar.tabBarClicked.connect(self._on_tab_clicked)
        self._tab_bar.setStyleSheet(f"""
            QTabBar {{
                background: {self._theme.bg_window};
                border-bottom: 1px solid {self._theme.border};
            }}
            QTabBar::tab {{
                background: {self._theme.bg_panel};
                color: {self._theme.text_muted};
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 100px;
            }}
            QTabBar::tab:selected {{
                color: {self._theme.text_primary};
                border-bottom: 2px solid {self._theme.accent};
                background: {self._theme.bg_surface};
            }}
            QTabBar::tab:hover {{
                color: {self._theme.text_primary};
                background: {self._theme.bg_hover};
            }}
        """)
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)
        tab_row.addWidget(self._tab_bar, 1)

        new_tab_btn = QPushButton("+")
        new_tab_btn.setFixedSize(28, 28)
        new_tab_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {self._theme.text_muted};
                border: 1px solid {self._theme.border}; border-radius: 4px;
                font-size: 16px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {self._theme.bg_hover}; color: {self._theme.text_primary}; }}
        """)
        new_tab_btn.clicked.connect(self._new_tab)
        tab_row.addWidget(new_tab_btn)
        root_layout.addLayout(tab_row)

        content = QWidget()
        main_layout = QHBoxLayout(content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

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

        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_stack = QStackedWidget()
        center_layout.addWidget(self._chat_stack)
        self.main_splitter.addWidget(center_panel)

        right_panel = QFrame()
        right_panel.setObjectName("sidePanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.tool_panel = ToolPanel(self._theme)
        right_splitter.addWidget(self.tool_panel)
        self.schedule_log_panel = ScheduleLogPanel(self.storage, self._theme)
        right_splitter.addWidget(self.schedule_log_panel)
        self.terminal_panel = TerminalPanel(self.workdir, self._theme)
        right_splitter.addWidget(self.terminal_panel)
        self.performance_panel = PerformancePanel(self.storage, self._theme)
        right_splitter.addWidget(self.performance_panel)
        self.knowledge_panel = KnowledgePanel(self.storage, self.config.data_dir, self._theme)
        right_splitter.addWidget(self.knowledge_panel)
        self.file_browser = FileBrowser(self._theme)
        self.file_browser.file_selected.connect(self._on_file_selected)
        self.file_browser.workdir_changed.connect(self._on_workdir_changed)
        right_splitter.addWidget(self.file_browser)
        right_splitter.setSizes([100, 100, 120, 100, 100, 140])
        right_layout.addWidget(right_splitter)
        self.main_splitter.addWidget(right_panel)

        self.main_splitter.setSizes([250, 700, 300])
        main_layout.addWidget(self.main_splitter)
        root_layout.addWidget(content, 1)

        self._left_panel = left_panel
        self._right_panel = right_panel

    def _setup_title_bar(self, root_layout: QVBoxLayout):
        th = self._theme
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
        self.title_label.setStyleSheet(f"color: {th.text_secondary}; font-size: 13px; font-weight: 600; padding: 0;")
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_menu_host = QWidget()
        self.title_menu_host.setFixedHeight(34)
        self.title_menu_layout = QHBoxLayout(self.title_menu_host)
        self.title_menu_layout.setContentsMargins(4, 0, 0, 0)
        self.title_menu_layout.setSpacing(0)
        layout.addWidget(self.title_menu_host, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.setFixedSize(34, 34)
        self.new_tab_btn.setToolTip(t("new_session"))
        self.new_tab_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {th.text_secondary};
                border: none;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {th.text_primary};
                background-color: {th.border};
            }}
        """)
        self.new_tab_btn.clicked.connect(self._new_session)
        layout.addWidget(self.new_tab_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.min_button = WindowControlButton("minimize", th.warning)
        self.max_button = WindowControlButton("maximize", th.success)
        self.close_button = WindowControlButton("close", th.error)
        self.min_button.clicked.connect(self.showMinimized)
        self.max_button.clicked.connect(self._toggle_maximized)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.min_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.max_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)
        root_layout.addWidget(title_bar)

    def _style_title_bar(self) -> None:
        th = self._theme
        self.title_bar.setStyleSheet(f"""
            QFrame#titleBar {{
                background-color: {th.bg_panel};
                border-bottom: 1px solid {th.border};
            }}
        """)
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(
                f"color: {th.text_secondary}; font-size: 13px; font-weight: 600; padding: 0;"
            )
        if hasattr(self, "min_button"):
            self.min_button.set_color(th.warning)
            self.max_button.set_color(th.success)
            self.close_button.set_color(th.error)

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

    # ── Tab Management ──

    def _create_initial_tab(self):
        tab_id = str(uuid.uuid4())[:8]
        chat = ChatPanel(self._theme)
        chat.message_sent.connect(self._on_message_sent)
        tool = ToolPanel(self._theme)
        task = TaskPanel(self.storage, self._theme)
        tab = TabState(
            tab_id=tab_id, session_id=self.session_id, workdir=self.workdir,
            chat_panel=chat, tool_panel=tool, task_panel=task,
        )
        self._tabs[tab_id] = tab
        self._chat_stack.addWidget(chat)
        self._tab_bar.addTab(tab_id[:8])
        self._tab_bar.setTabData(0, tab_id)
        self._active_tab_id = tab_id

    def _new_tab(self):
        session = self.storage.create_session(self.project["id"], str(self.workdir), t("new_session_title"))
        tab_id = str(uuid.uuid4())[:8]
        chat = ChatPanel(self._theme)
        chat.message_sent.connect(self._on_message_sent)
        tool = ToolPanel(self._theme)
        task = TaskPanel(self.storage, self._theme)
        tab = TabState(
            tab_id=tab_id, session_id=session["id"], workdir=self.workdir,
            chat_panel=chat, tool_panel=tool, task_panel=task,
        )
        self._tabs[tab_id] = tab
        self._chat_stack.addWidget(chat)
        idx = self._tab_bar.addTab(tab_id[:8])
        self._tab_bar.setTabData(idx, tab_id)
        self._switch_to_tab(tab_id)

    def _switch_to_tab(self, tab_id: str):
        if tab_id not in self._tabs:
            return
        self._active_tab_id = tab_id
        tab = self._tabs[tab_id]
        self._chat_stack.setCurrentWidget(tab.chat_panel)
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == tab_id:
                self._tab_bar.setCurrentIndex(i)
                break
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(tab.session_id)
        self.task_panel.load_tasks(tab.session_id)
        self.file_browser.set_root(tab.workdir)
        self._load_chat_history(tab.session_id, tab.chat_panel)
        self.model_label.setText(f"{t('model_label')}{self.config.get_provider_model(tab.agent_name)}")

    def _on_tab_close(self, index: int):
        tab_id = self._tab_bar.tabData(index)
        if not tab_id or tab_id not in self._tabs:
            return
        tab = self._tabs[tab_id]
        if tab.worker:
            reply = QMessageBox.question(
                self, t("confirm"), t("tab_running_confirm"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            tab.worker.stop()
            tab.worker.wait(3000)
        self._chat_stack.removeWidget(tab.chat_panel)
        tab.chat_panel.deleteLater()
        del self._tabs[tab_id]
        self._tab_bar.removeTab(index)
        if self._active_tab_id == tab_id:
            if self._tab_bar.count() > 0:
                self._switch_to_tab(self._tab_bar.tabData(0))
            else:
                self._create_initial_tab()
                self._load_data()

    def _on_tab_clicked(self, index: int):
        tab_id = self._tab_bar.tabData(index)
        if tab_id and tab_id != self._active_tab_id:
            self._switch_to_tab(tab_id)

    def _get_active_tab(self) -> TabState | None:
        if self._active_tab_id and self._active_tab_id in self._tabs:
            return self._tabs[self._active_tab_id]
        return None

    def _load_chat_history(self, session_id: str, chat_panel: ChatPanel):
        chat_panel.clear()
        messages = self.storage.list_messages(session_id)
        for msg in messages:
            data = msg.get("data", {})
            role = data.get("role", "")
            if role == "user":
                content = data.get("content", "")
                if content:
                    chat_panel.add_user_message(content)
            elif role == "assistant":
                content = data.get("content", "")
                if content:
                    chat_panel.add_assistant_message(content)

    def _load_data(self):
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)
        self.file_browser.set_root(self.workdir)
        self.knowledge_panel.load_sources()
        tab = self._get_active_tab()
        if tab:
            self.task_panel.load_tasks(tab.session_id)
            self._load_chat_history(tab.session_id, tab.chat_panel)

        if not hasattr(self, '_schedule_log_timer') or self._schedule_log_timer is None:
            self._schedule_log_timer = QTimer(self)
            self._schedule_log_timer.timeout.connect(self._refresh_schedule_logs)
            self._schedule_log_timer.start(30000)

    @Slot(str)
    def _on_message_sent(self, text: str):
        tab = self._get_active_tab()
        if not tab:
            return
        try:
            self._maybe_generate_session_title(text, tab)
            self.status_label.setText(t("thinking"))
            tab.chat_panel.set_input_enabled(False)

            self._worker = AgentWorker(
                self.agent_loop, tab.session_id, text,
                tab.agent_name, tab.workdir,
            )
            self._worker.message_received.connect(lambda k, c: self._on_agent_message(k, c, tab))
            self._worker.tool_call_started.connect(lambda n, a: self._on_tool_call(n, a, tab))
            self._worker.tool_call_finished.connect(lambda n, r, s: self._on_tool_result(n, r, s, tab))
            self._worker.finished.connect(lambda r: self._on_agent_finished(r, tab))
            self._worker.error.connect(lambda e: self._on_agent_error(e, tab))
            self._worker.thread_finished.connect(self._on_worker_thread_finished)
            tab.worker = self._worker
            self._worker.start()
        except Exception as e:
            logger.error("Failed to start worker: %s", e, exc_info=True)
            tab.chat_panel.add_system_message(f"{t('error_prefix')}{e}")
            tab.chat_panel.set_input_enabled(True)

    def _make_session_title(self, text: str) -> str:
        cleaned = " ".join(str(text).split())
        cleaned = cleaned.strip(" \t\r\n.,，。!?！？;；:：、")
        if not cleaned:
            return t("new_session_title")
        if len(cleaned) > 18:
            cleaned = cleaned[:18].rstrip() + "..."
        return cleaned

    def _maybe_generate_session_title(self, text: str, tab: TabState):
        session = self.storage.get_session(tab.session_id)
        current_title = (session or {}).get("title") or ""
        if current_title and current_title not in {"New Session", "新会话", t("new_session_title")}:
            return
        title = self._make_session_title(text)
        if not title or title == current_title:
            return
        self.storage.update_session(tab.session_id, title=title)
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(tab.session_id)

    @Slot(str, str)
    def _on_agent_message(self, kind: str, content: str, tab: TabState):
        if kind == "stream":
            if not tab.chat_panel._current_assistant:
                tab.chat_panel.start_assistant_stream()
            tab.chat_panel.append_stream(content)
        elif kind == "finish":
            tab.chat_panel.finish_stream()
        elif kind == "error":
            tab.chat_panel.add_system_message(f"{t('error_prefix')}{content}")

    @Slot(str, dict)
    def _on_tool_call(self, name: str, args: dict, tab: TabState):
        tab._tool_entries.append(self.tool_panel.add_tool_call(name, args))
        if name == "question":
            tab.chat_panel.add_tool_call(name, args)

    @Slot(str, str, bool)
    def _on_tool_result(self, name: str, result: str, success: bool, tab: TabState):
        entries = getattr(tab, "_tool_entries", [])
        if entries:
            entry = entries[-1]
            if success:
                entry.set_success(result)
            else:
                entry.set_error(result)

    @Slot(str)
    def _on_agent_finished(self, result: str, tab: TabState):
        if tab.chat_panel._stream_buffer:
            tab.chat_panel.finish_stream()
        streamed = tab.chat_panel.consume_stream_finalized()
        if result and not streamed:
            tab.chat_panel.add_assistant_message(result)
        tab.chat_panel.set_input_enabled(True)
        estimated_tokens = len(result) // 4 if result else 0
        self.performance_panel.record_request(estimated_tokens, 0)
        tab.worker = None
        self.status_label.setText(t("ready"))
        self.task_panel.load_tasks(tab.session_id)

    @Slot(str)
    def _on_agent_error(self, error: str, tab: TabState):
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
        tab.chat_panel.add_system_message(f"{t('error_prefix')}{friendly}")
        tab.chat_panel.set_input_enabled(True)
        tab.worker = None
        self.status_label.setText(t("error"))

    @Slot()
    def _on_worker_thread_finished(self):
        self._worker = None

    @Slot(str)
    def _on_session_selected(self, session_id: str):
        tab = self._get_active_tab()
        if not tab:
            return
        tab.session_id = session_id
        tab.chat_panel.clear()
        tab.tool_panel.clear()
        self.task_panel.load_tasks(session_id)
        self._load_chat_history(session_id, tab.chat_panel)

    def _new_session(self):
        tab = self._get_active_tab()
        if not tab:
            return
        session = self.storage.create_session(
            self.project["id"], str(self.workdir), t("new_session_title")
        )
        tab.session_id = session["id"]
        tab.chat_panel.clear()
        tab.tool_panel.clear()
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(tab.session_id)
        self.task_panel.load_tasks(tab.session_id)

    def _delete_session(self, session_id: str):
        tab = self._get_active_tab()
        if tab and tab.worker and session_id == tab.session_id:
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
        tab = self._get_active_tab()
        if tab:
            tab.session_id = next_session_id
            tab.chat_panel.clear()
            tab.tool_panel.clear()
            self.session_panel.load_sessions(self.project["id"])
            self.session_panel.set_current_session(self.session_id)
            self.task_panel.load_tasks(self.session_id)
            self._load_chat_history(self.session_id, tab.chat_panel)

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
        tab = self._get_active_tab()
        if tab:
            tab.workdir = workdir
            tab.session_id = session_id
            tab.chat_panel.clear()
            tab.tool_panel.clear()
            self.file_browser.set_root(self.workdir)
            self.terminal_panel.set_workdir(self.workdir)
            self.session_panel.load_sessions(self.project["id"])
            self.session_panel.set_current_session(self.session_id)
            self.task_panel.load_tasks(self.session_id)
            self._load_chat_history(self.session_id, tab.chat_panel)

    def _open_settings(self):
        dialog = ConfigDialog(self.config, self, self.workdir / "hellocode.json", self._theme)
        dialog.config_changed.connect(self._on_config_changed)
        dialog.theme_changed.connect(self._switch_theme)
        dialog.exec()

    def _open_schedules(self):
        dialog = ScheduleDialog(self.storage, self, self._theme)
        dialog.schedule_changed.connect(self._refresh_schedule_logs)
        dialog.exec()

    def _refresh_schedule_logs(self):
        if hasattr(self, 'schedule_log_panel'):
            self.schedule_log_panel.refresh()

    def _export_chat(self):
        tab = self._get_active_tab()
        if tab:
            export_chat_to_markdown(tab.chat_panel, tab.session_id, self)

    def _on_config_changed(self):
        self.provider = LLMProvider(self.config)
        self.agent_loop.provider = self.provider
        self.actor_manager.provider = self.provider
        self.model_label.setText(f"{t('model_label')}{self.config.get_provider_model()}")

    def _clear_chat(self):
        for tab in self._tabs.values():
            if tab.worker:
                self._show_warning(t("wait_current_run_clear_sessions"))
                return
        if not self._confirm_action(
            t("delete_all_sessions_title"),
            t("delete_all_sessions_confirm"),
            t("clear"),
        ):
            return

        self.storage.delete_all_sessions(self.project["id"])

        session = self.storage.create_session(
            self.project["id"], str(self.workdir), t("new_session_title")
        )
        self.session_id = session["id"]
        tab = self._get_active_tab()
        if tab:
            tab.session_id = session["id"]
            tab.chat_panel.clear()
            tab.tool_panel.clear()
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
        self._tab_bar.setStyleSheet(f"""
            QTabBar {{
                background: {self._theme.bg_window};
                border-bottom: 1px solid {self._theme.border};
            }}
            QTabBar::tab {{
                background: {self._theme.bg_panel};
                color: {self._theme.text_muted};
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 100px;
            }}
            QTabBar::tab:selected {{
                color: {self._theme.text_primary};
                border-bottom: 2px solid {self._theme.accent};
                background: {self._theme.bg_surface};
            }}
            QTabBar::tab:hover {{
                color: {self._theme.text_primary};
                background: {self._theme.bg_hover};
            }}
        """)
        for tab in self._tabs.values():
            tab.chat_panel.update_theme(self._theme)
            tab.tool_panel.update_theme(self._theme)
        if hasattr(self, 'tool_panel'):
            self.tool_panel.update_theme(self._theme)
        if hasattr(self, 'task_panel'):
            self.task_panel.update_theme(self._theme)
        if hasattr(self, 'session_panel'):
            self.session_panel.update_theme(self._theme)
            self.session_panel.load_sessions(self.project["id"])
        if hasattr(self, 'file_browser'):
            self.file_browser.update_theme(self._theme)
        if hasattr(self, 'knowledge_panel'):
            self.knowledge_panel.update_theme(self._theme)
            self.knowledge_panel.load_sources()
        if hasattr(self, 'schedule_log_panel'):
            self.schedule_log_panel.update_theme(self._theme)
        if hasattr(self, 'terminal_panel'):
            self.terminal_panel.update_theme(self._theme)
        if hasattr(self, 'performance_panel'):
            self.performance_panel.update_theme(self._theme)

    def _switch_language(self, lang: str):
        set_language(lang)
        self._setup_menu()
        self.model_label.setText(f"{t('model_label')}{self.config.get_provider_model()}")
        for tab in self._tabs.values():
            tab.chat_panel.update_language()
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
        if hasattr(self, 'knowledge_panel'):
            self.knowledge_panel.update_language()
            self.knowledge_panel.load_sources()
        if hasattr(self, 'schedule_log_panel'):
            self.schedule_log_panel.update_language()
        if hasattr(self, 'terminal_panel'):
            self.terminal_panel.update_language()
        if hasattr(self, 'performance_panel'):
            self.performance_panel.update_language()

    @Slot(str)
    def _on_file_selected(self, file_path: str):
        """Handle file selection from browser."""
        self.status_label.setText(f"{t('file_label')}{file_path}")

    @Slot(str)
    def _on_workdir_changed(self, new_workdir: str):
        """Handle workdir change from file browser."""
        self.workdir = Path(new_workdir)
        self.project = self.storage.find_project_by_worktree(str(self.workdir))
        if not self.project:
            self.project = self.storage.create_project(str(self.workdir), self.workdir.name)

        sessions = self.storage.list_sessions(self.project["id"], limit=1)
        if sessions:
            self.session_id = sessions[0]["id"]
        else:
            session = self.storage.create_session(
                self.project["id"], str(self.workdir), t("new_session_title")
            )
            self.session_id = session["id"]

        tab = self._get_active_tab()
        if tab:
            tab.workdir = self.workdir
            tab.session_id = self.session_id
            tab.chat_panel.workdir = self.workdir
            tab.chat_panel.clear()
            tab.tool_panel.clear()
        self.terminal_panel.set_workdir(self.workdir)
        self.session_panel.load_sessions(self.project["id"])
        self.session_panel.set_current_session(self.session_id)
        self.task_panel.load_tasks(self.session_id)
        if tab:
            self._load_chat_history(self.session_id, tab.chat_panel)

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
        for tab in self._tabs.values():
            if tab.worker:
                tab.worker.stop()
                tab.worker.wait(3000)
                tab.worker = None
        if self._worker:
            self._worker.stop()
            self._worker.wait(3000)
            self._worker = None
        if hasattr(self, 'terminal_panel'):
            self.terminal_panel.cleanup()
        if self._scheduler:
            self._scheduler._running = False
        try:
            self.storage.close()
        except Exception:
            pass
        event.accept()
