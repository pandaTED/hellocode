"""Theme definitions for HelloCode GUI.

Five carefully designed themes with consistent color palettes.
Each theme defines colors and generates a complete QSS stylesheet.
"""

from __future__ import annotations
from dataclasses import dataclass

UI_FONT = (
    '"Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", "Segoe UI", '
    '"PingFang SC", "Noto Sans CJK SC", "SimHei", "SimSun", '
    '"DengXian", "Helvetica Neue", Arial, sans-serif'
)
MONO_FONT = (
    '"Cascadia Mono", "Cascadia Code", "JetBrains Mono", '
    '"SFMono-Regular", Consolas, monospace'
)


@dataclass
class ThemeColors:
    """Color palette for a theme."""
    name: str
    display_name: str

    # Backgrounds
    bg_window: str        # Main window background
    bg_panel: str         # Side panels
    bg_surface: str       # Cards, message bubbles
    bg_elevated: str      # Input fields, elevated surfaces
    bg_hover: str         # Hover states

    # Chat specific
    bg_user_msg: str      # User message bubble
    bg_assistant_msg: str # Assistant message bubble
    bg_tool_msg: str      # Tool call message

    # Text
    text_primary: str     # Main text
    text_secondary: str   # Dimmed text
    text_muted: str       # Very dim text

    # Accent colors
    accent: str           # Primary accent (buttons, links)
    accent_hover: str     # Accent hover
    accent_pressed: str   # Accent pressed

    # Semantic colors
    success: str          # Green for success
    error: str            # Red for errors
    warning: str          # Yellow/orange for warnings
    info: str             # Blue for info

    # User/Assistant labels
    user_color: str       # "You" label color
    assistant_color: str  # "Assistant" label color

    # Borders
    border: str           # Default border
    border_focus: str     # Focused input border

    # Scrollbar
    scrollbar_handle: str
    scrollbar_hover: str

    # Selection
    selection: str


# ── Theme 1: Midnight (Catppuccin Mocha) ──

MIDNIGHT = ThemeColors(
    name="midnight",
    display_name="Midnight",
    bg_window="#1e1e2e",
    bg_panel="#181825",
    bg_surface="#1e1e2e",
    bg_elevated="#313244",
    bg_hover="#45475a",
    bg_user_msg="#313244",
    bg_assistant_msg="#1e1e2e",
    bg_tool_msg="#181825",
    text_primary="#cdd6f4",
    text_secondary="#a6adc8",
    text_muted="#6c7086",
    accent="#89b4fa",
    accent_hover="#74c7ec",
    accent_pressed="#89dceb",
    success="#a6e3a1",
    error="#f38ba8",
    warning="#fab387",
    info="#89b4fa",
    user_color="#a6e3a1",
    assistant_color="#89b4fa",
    border="#313244",
    border_focus="#89b4fa",
    scrollbar_handle="#45475a",
    scrollbar_hover="#585b70",
    selection="#45475a",
)

# ── Theme 2: Ocean ──

OCEAN = ThemeColors(
    name="ocean",
    display_name="Ocean",
    bg_window="#0d1117",
    bg_panel="#0d1117",
    bg_surface="#161b22",
    bg_elevated="#21262d",
    bg_hover="#30363d",
    bg_user_msg="#1c2333",
    bg_assistant_msg="#0d1117",
    bg_tool_msg="#0d1117",
    text_primary="#e6edf3",
    text_secondary="#8b949e",
    text_muted="#484f58",
    accent="#58a6ff",
    accent_hover="#79c0ff",
    accent_pressed="#a5d6ff",
    success="#3fb950",
    error="#f85149",
    warning="#d29922",
    info="#58a6ff",
    user_color="#3fb950",
    assistant_color="#58a6ff",
    border="#21262d",
    border_focus="#58a6ff",
    scrollbar_handle="#30363d",
    scrollbar_hover="#484f58",
    selection="#1f3a5f",
)

# ── Theme 3: Nord ──

NORD = ThemeColors(
    name="nord",
    display_name="Nord",
    bg_window="#2e3440",
    bg_panel="#2e3440",
    bg_surface="#3b4252",
    bg_elevated="#434c5e",
    bg_hover="#4c566a",
    bg_user_msg="#3b4252",
    bg_assistant_msg="#2e3440",
    bg_tool_msg="#2e3440",
    text_primary="#eceff4",
    text_secondary="#d8dee9",
    text_muted="#4c566a",
    accent="#88c0d0",
    accent_hover="#8fbcbb",
    accent_pressed="#81a1c1",
    success="#a3be8c",
    error="#bf616a",
    warning="#ebcb8b",
    info="#88c0d0",
    user_color="#a3be8c",
    assistant_color="#88c0d0",
    border="#3b4252",
    border_focus="#88c0d0",
    scrollbar_handle="#4c566a",
    scrollbar_hover="#5e81ac",
    selection="#434c5e",
)

# ── Theme 4: Sunset ──

SUNSET = ThemeColors(
    name="sunset",
    display_name="Sunset",
    bg_window="#1a1412",
    bg_panel="#1a1412",
    bg_surface="#241c18",
    bg_elevated="#2d2319",
    bg_hover="#3d2f22",
    bg_user_msg="#2d2319",
    bg_assistant_msg="#1a1412",
    bg_tool_msg="#1a1412",
    text_primary="#f5e6d3",
    text_secondary="#c9a882",
    text_muted="#7a6552",
    accent="#e07c4f",
    accent_hover="#e8956a",
    accent_pressed="#f0ad85",
    success="#7cb87f",
    error="#d65d5d",
    warning="#d4a84b",
    info="#6a9fd8",
    user_color="#7cb87f",
    assistant_color="#e07c4f",
    border="#2d2319",
    border_focus="#e07c4f",
    scrollbar_handle="#3d2f22",
    scrollbar_hover="#5a4535",
    selection="#3d2f22",
)

# ── Theme 5: Forest ──

FOREST = ThemeColors(
    name="forest",
    display_name="Forest",
    bg_window="#141a14",
    bg_panel="#141a14",
    bg_surface="#1c261c",
    bg_elevated="#243024",
    bg_hover="#2d3b2d",
    bg_user_msg="#243024",
    bg_assistant_msg="#141a14",
    bg_tool_msg="#141a14",
    text_primary="#d4e8d4",
    text_secondary="#98b898",
    text_muted="#5a7a5a",
    accent="#6aad6a",
    accent_hover="#7ec47e",
    accent_pressed="#92d892",
    success="#6aad6a",
    error="#c75c5c",
    warning="#c9a84b",
    info="#5a9ac7",
    user_color="#6aad6a",
    assistant_color="#5a9ac7",
    border="#243024",
    border_focus="#6aad6a",
    scrollbar_handle="#2d3b2d",
    scrollbar_hover="#3d503d",
    selection="#2d3b2d",
)


# ── Theme Registry ──

THEMES: dict[str, ThemeColors] = {
    "midnight": MIDNIGHT,
    "ocean": OCEAN,
    "nord": NORD,
    "sunset": SUNSET,
    "forest": FOREST,
}


def get_theme(name: str) -> ThemeColors:
    return THEMES.get(name, MIDNIGHT)


def get_theme_names() -> list[str]:
    return list(THEMES.keys())


def generate_stylesheet(theme: ThemeColors) -> str:
    """Generate a complete QSS stylesheet from a theme's color palette."""
    t = theme
    return f"""
QMainWindow {{
    background-color: {t.bg_window};
}}

QWidget {{
    color: {t.text_primary};
    font-family: {UI_FONT};
    font-size: 13px;
}}

QSplitter::handle {{
    background-color: {t.border};
    width: 2px;
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {t.scrollbar_hover};
}}

/* ── Chat Area ── */
QWidget#chatArea {{
    background-color: {t.bg_surface};
}}

QLineEdit#chatInput {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 14px;
    selection-background-color: {t.selection};
}}

QLineEdit#chatInput:focus {{
    border-color: {t.border_focus};
}}

QPushButton#sendButton {{
    background-color: {t.accent};
    color: {t.bg_window};
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
}}

QPushButton#sendButton:hover {{
    background-color: {t.accent_hover};
}}

QPushButton#sendButton:pressed {{
    background-color: {t.accent_pressed};
}}

QPushButton#sendButton:disabled {{
    background-color: {t.bg_elevated};
    color: {t.text_muted};
}}

/* ── Side Panels ── */
QWidget#sidePanel {{
    background-color: {t.bg_panel};
}}

QTreeWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    color: {t.text_primary};
    font-size: 13px;
}}

QTreeWidget::item {{
    padding: 5px 8px;
    border-radius: 4px;
}}

QTreeWidget::item:selected {{
    background-color: {t.selection};
}}

QTreeWidget::item:hover {{
    background-color: {t.bg_hover};
}}

QTreeWidget::branch {{
    background-color: transparent;
}}

/* ── Lists (Tool, Task, Session) ── */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    color: {t.text_primary};
    font-size: 13px;
}}

QListWidget::item {{
    padding: 7px 10px;
    border-bottom: 1px solid {t.border};
}}

QListWidget::item:selected {{
    background-color: {t.selection};
}}

QListWidget::item:hover {{
    background-color: {t.bg_hover};
}}

/* ── Labels ── */
QLabel#sectionTitle {{
    color: {t.text_secondary};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 10px 14px 6px;
}}

QLabel#toolName {{
    color: {t.accent};
    font-weight: bold;
}}

/* ── Status Bar ── */
QStatusBar {{
    background-color: {t.bg_panel};
    color: {t.text_muted};
    border-top: 1px solid {t.border};
    padding: 2px 8px;
    font-size: 12px;
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {t.scrollbar_handle};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {t.scrollbar_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {t.scrollbar_handle};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {t.scrollbar_hover};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Tab Widget ── */
QTabWidget::pane {{
    border: none;
    background-color: {t.bg_surface};
}}

QTabBar::tab {{
    background-color: {t.bg_panel};
    color: {t.text_muted};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {t.text_primary};
    border-bottom-color: {t.accent};
}}

QTabBar::tab:hover {{
    color: {t.text_secondary};
}}

/* ── Dialogs ── */
QDialog {{
    background-color: {t.bg_surface};
}}

QGroupBox {{
    border: 1px solid {t.border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: {t.text_secondary};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 6px 16px;
}}

QPushButton:hover {{
    background-color: {t.bg_hover};
    border-color: {t.scrollbar_hover};
}}

QPushButton:pressed {{
    background-color: {t.scrollbar_handle};
}}

/* ── Input Fields ── */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: {t.selection};
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {t.border_focus};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {t.text_muted};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 4px;
    outline: none;
    padding: 4px;
    selection-background-color: {t.selection};
    selection-color: {t.text_primary};
}}

QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 4px 8px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {t.bg_hover};
}}

QAbstractItemView {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    selection-background-color: {t.selection};
    selection-color: {t.text_primary};
    outline: none;
}}

/* ── Progress Bar ── */
QProgressBar {{
    background-color: {t.bg_elevated};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: {t.text_primary};
    height: 8px;
}}

QProgressBar::chunk {{
    background-color: {t.accent};
    border-radius: 4px;
}}

/* ── Menu ── */
QMenuBar {{
    background-color: {t.bg_panel};
    border-bottom: 1px solid {t.border};
    color: {t.text_secondary};
}}

QMenuBar::item {{
    padding: 4px 10px;
}}

QMenuBar::item:selected {{
    background-color: {t.selection};
}}

QMenu {{
    background-color: {t.bg_surface};
    border: 1px solid {t.border};
    color: {t.text_primary};
}}

QMenu::item {{
    padding: 6px 24px;
}}

QMenu::item:selected {{
    background-color: {t.selection};
}}

/* ── Checkbox / Radio ── */
QCheckBox, QRadioButton {{
    color: {t.text_primary};
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}

/* ── ToolTip ── */
QToolTip {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
