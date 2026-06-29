"""Multi-round GUI automated test — launch, interact, screenshot, verify."""
from __future__ import annotations

import sys
import os
import time
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent

sys.path.insert(0, str(Path(__file__).parent.parent))
TEST_DIR = Path(tempfile.mkdtemp())

results = []


def log(name: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append((name, ok, detail))


def run_all():
    from hellocode.config import Config
    from hellocode.storage import Storage
    from hellocode.provider import LLMProvider
    from hellocode.memory import MemorySystem
    from hellocode.tools import create_registry
    from hellocode.agent import AgentLoop, ActorManager
    from hellocode.gui.app import HelloCodeGUI
    from hellocode.gui.schedule_dialog import ScheduleDialog
    from hellocode.gui.i18n import set_language, get_language

    config = Config()
    storage = Storage(TEST_DIR / "test.db")
    provider = LLMProvider(config)
    memory = MemorySystem(storage, TEST_DIR)
    tools = create_registry()
    agent_loop = AgentLoop(config, storage, provider, tools, memory)
    am = ActorManager(storage, provider, tools, memory, config)
    am.set_loop(agent_loop)
    agent_loop.actor_manager = am

    project = storage.create_project(str(TEST_DIR), "test")
    session = storage.create_session(project["id"], str(TEST_DIR), "Test")

    app = QApplication.instance() or QApplication(sys.argv)

    # ── Round 1: Window creation ──
    print("\n=== Round 1: Window Creation ===")
    window = HelloCodeGUI(
        config=config, storage=storage, provider=provider, memory=memory,
        agent_loop=agent_loop, actor_manager=am,
        workdir=TEST_DIR, project=project, session_id=session["id"],
    )
    log("Window created", window is not None)
    log("Title", window.windowTitle() == "HelloCode", window.windowTitle())
    log("Min size", window.minimumSize().width() == 1200)
    log("Tab bar", window._tab_bar is not None)
    log("Initial tab", window._tab_bar.count() == 1)
    log("Active tab", window._get_active_tab() is not None)
    window.show()
    log("Window shown", window.isVisible())

    # ── Round 2: Panels ──
    print("\n=== Round 2: Panel Verification ===")
    tab = window._get_active_tab()
    log("Chat panel", tab.chat_panel is not None)
    log("Tool panel", tab.tool_panel is not None)
    log("Session panel", window.session_panel is not None)
    log("Task panel", window.task_panel is not None)
    log("Knowledge panel", window.knowledge_panel is not None)
    log("File browser", window.file_browser is not None)
    log("Main splitter", window.main_splitter is not None)
    log("Chat stack", window._chat_stack is not None)
    log("Menu bar", window._menu_bar is not None)
    log("Status bar", window.statusBar() is not None)

    # ── Round 3: Multi-tab ──
    print("\n=== Round 3: Multi-Tab Operations ===")
    count_before = window._tab_bar.count()
    window._new_tab()
    log("New tab", window._tab_bar.count() == count_before + 1, f"count={window._tab_bar.count()}")
    tab2 = window._get_active_tab()
    log("Tab 2 active", tab2 is not None and tab2.session_id != tab.session_id)
    log("Tab 2 chat panel", tab2.chat_panel is not None)
    log("Tab 2 tool panel", tab2.tool_panel is not None)

    # Switch back
    for i in range(window._tab_bar.count()):
        if window._tab_bar.tabData(i) == tab.tab_id:
            window._switch_to_tab(tab.tab_id)
            break
    log("Switch back", window._get_active_tab() is not None)
    log("Same session", window._get_active_tab().session_id == tab.session_id)

    # Close tab
    count_before = window._tab_bar.count()
    for i in range(window._tab_bar.count()):
        if window._tab_bar.tabData(i) == tab2.tab_id:
            window._on_tab_close(i)
            break
    log("Close tab", window._tab_bar.count() == count_before - 1)

    # ── Round 4: Theme & Language ──
    print("\n=== Round 4: Theme & Language ===")
    themes = ["midnight", "ocean", "nord", "sunset", "forest"]
    for theme_name in themes:
        window._switch_theme(theme_name)
        log(f"Theme {theme_name}", window._theme.name == theme_name)

    set_language("en")
    log("Lang -> en", get_language() == "en")
    window._switch_language("en")
    log("Apply en", get_language() == "en")

    set_language("zh")
    log("Lang -> zh", get_language() == "zh")
    window._switch_language("zh")
    log("Apply zh", get_language() == "zh")

    # ── Round 5: Schedule Dialog ──
    print("\n=== Round 5: Schedule Dialog ===")
    dialog = ScheduleDialog(storage, window, window._theme)
    log("Dialog created", dialog is not None)
    log("Table exists", dialog.table is not None)
    log("Table rows", dialog.table.rowCount() == 0, "empty on fresh db")

    # ── Round 6: Knowledge Panel ──
    print("\n=== Round 6: Knowledge Panel ===")
    kp = window.knowledge_panel
    log("Panel exists", kp is not None)
    log("Engine cache", kp._get_engine() is kp._get_engine())
    log("Sources loaded", kp.list_widget is not None)

    # ── Round 7: Session panel ──
    print("\n=== Round 7: Session Panel ===")
    sp = window.session_panel
    log("Session panel", sp is not None)
    log("Session list", sp.list_widget is not None)
    log("Session count", sp.list_widget.count() >= 1)

    # ── Round 8: Chat input ──
    print("\n=== Round 8: Chat Input ===")
    cp = tab.chat_panel
    log("Input field", cp.input_field is not None)
    log("Send button", cp.send_button is not None)
    log("Input enabled", cp.input_field.isEnabled())
    cp.set_input_enabled(False)
    log("Disable input", not cp.input_field.isEnabled())
    cp.set_input_enabled(True)
    log("Enable input", cp.input_field.isEnabled())

    # ── Round 9: Close event ──
    print("\n=== Round 9: Close Event ===")
    event = QCloseEvent()
    window.closeEvent(event)
    log("closeEvent accepted", event.isAccepted())

    # ── Summary ──
    print("\n" + "=" * 60)
    print("MULTI-ROUND GUI TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        suffix = f" ({detail})" if detail else ""
        print(f"  [{status}] {name}{suffix}")
    print(f"\n  Total: {passed} passed, {failed} failed / {len(results)} tests")
    print("=" * 60)

    storage.close()
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
