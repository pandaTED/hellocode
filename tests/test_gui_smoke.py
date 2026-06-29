"""GUI smoke tests — launch app, verify widgets, capture screenshot."""
from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

TEST_DIR = Path(tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_config():
    from hellocode.config import Config
    return Config()


def _make_storage():
    from hellocode.storage import Storage
    return Storage(TEST_DIR / "test.db")


def _make_provider(config):
    from hellocode.provider import LLMProvider
    return LLMProvider(config)


def _make_memory(storage):
    from hellocode.memory import MemorySystem
    return MemorySystem(storage, TEST_DIR)


def _make_tools():
    from hellocode.tools import create_registry
    return create_registry()


def _make_agent_loop(config, storage, provider, tools, memory):
    from hellocode.agent import AgentLoop, ActorManager
    loop = AgentLoop(config, storage, provider, tools, memory)
    am = ActorManager(storage, provider, tools, memory, config)
    am.set_loop(loop)
    loop.actor_manager = am
    return loop, am


results = []


def run_tests():
    from hellocode.gui.app import HelloCodeGUI, TabState

    config = _make_config()
    storage = _make_storage()
    provider = _make_provider(config)
    memory = _make_memory(storage)
    tools = _make_tools()
    agent_loop, actor_manager = _make_agent_loop(config, storage, provider, tools, memory)

    project = storage.find_project_by_worktree(str(TEST_DIR))
    if not project:
        project = storage.create_project(str(TEST_DIR), "test")
    session = storage.create_session(project["id"], str(TEST_DIR), "Test Session")

    app = QApplication.instance() or QApplication(sys.argv)

    window = HelloCodeGUI(
        config=config, storage=storage, provider=provider, memory=memory,
        agent_loop=agent_loop, actor_manager=actor_manager,
        workdir=TEST_DIR, project=project, session_id=session["id"],
    )

    # Test 1: Window created
    assert window is not None
    results.append(("Window created", True))

    # Test 2: Window title
    assert window.windowTitle() == "HelloCode"
    results.append(("Window title", True))

    # Test 3: Central widget exists
    assert window.centralWidget() is not None
    results.append(("Central widget", True))

    # Test 4: Tab bar exists
    assert hasattr(window, "_tab_bar")
    assert window._tab_bar is not None
    results.append(("Tab bar exists", True))

    # Test 5: Tab count (initial tab)
    assert window._tab_bar.count() >= 1
    results.append(("Initial tab created", True))

    # Test 6: Active tab
    tab = window._get_active_tab()
    assert tab is not None
    results.append(("Active tab exists", True))

    # Test 7: Chat panel in tab
    assert tab.chat_panel is not None
    results.append(("Chat panel in tab", True))

    # Test 8: Tool panel in tab
    assert tab.tool_panel is not None
    results.append(("Tool panel in tab", True))

    # Test 9: Session panel
    assert window.session_panel is not None
    results.append(("Session panel", True))

    # Test 10: Knowledge panel
    assert window.knowledge_panel is not None
    results.append(("Knowledge panel", True))

    # Test 11: File browser
    assert window.file_browser is not None
    results.append(("File browser", True))

    # Test 12: Main splitter
    assert window.main_splitter is not None
    results.append(("Main splitter", True))

    # Test 13: Menu bar
    assert window._menu_bar is not None
    results.append(("Menu bar", True))

    # Test 14: Status bar
    assert window.statusBar() is not None
    results.append(("Status bar", True))

    # Test 15: Theme switching
    window._switch_theme("ocean")
    assert window._theme.name == "ocean"
    results.append(("Theme switch", True))

    # Test 16: Language switching
    window._switch_language("en")
    from hellocode.gui.i18n import get_language
    assert get_language() == "en"
    results.append(("Language switch", True))

    # Test 17: New tab
    initial_count = window._tab_bar.count()
    window._new_tab()
    assert window._tab_bar.count() == initial_count + 1
    results.append(("New tab created", True))

    # Test 18: Switch tab
    new_tab = window._get_active_tab()
    assert new_tab is not None
    assert new_tab.session_id != tab.session_id
    results.append(("Tab switch", True))

    # Test 19: Schedule dialog (without exec)
    from hellocode.gui.schedule_dialog import ScheduleDialog
    dialog = ScheduleDialog(storage, window, window._theme)
    assert dialog is not None
    results.append(("Schedule dialog", True))

    # Test 20: closeEvent doesn't crash
    from PySide6.QtGui import QCloseEvent
    event = QCloseEvent()
    window.closeEvent(event)
    results.append(("closeEvent", True))

    # Print results
    print("\n" + "=" * 50)
    print("GUI SMOKE TEST RESULTS")
    print("=" * 50)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    print(f"\n  Total: {passed} passed, {failed} failed out of {len(results)}")
    print("=" * 50)

    storage.close()
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
