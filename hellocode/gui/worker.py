"""Background workers for GUI operations."""

from __future__ import annotations

import asyncio
import logging
import threading

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("hellocode.gui.worker")


class AgentWorker(QObject):
    """Runs the agent loop in a background thread without moveToThread."""
    message_received = Signal(str, str)
    tool_call_started = Signal(str, dict)
    tool_call_finished = Signal(str, str, bool)
    finished = Signal(str)
    error = Signal(str)
    thread_finished = Signal()

    def __init__(self, agent_loop, session_id: str, user_input: str,
                 agent_name: str, workdir):
        super().__init__()
        self.agent_loop = agent_loop
        self.session_id = session_id
        self.user_input = user_input
        self.agent_name = agent_name
        self.workdir = workdir
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopped = False

    def start(self):
        self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            result = self._loop.run_until_complete(self._execute())
            if not self._stopped:
                self.finished.emit(result)
        except Exception as e:
            if not self._stopped:
                logger.error("Agent worker error: %s", e)
                self.error.emit(str(e))
        finally:
            self._cancel_pending_tasks()
            self._loop.close()
            self._loop = None
            self.thread_finished.emit()

    def _cancel_pending_tasks(self):
        if not self._loop or self._loop.is_closed():
            return
        to_cancel = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
        for task in to_cancel:
            task.cancel()
        if to_cancel:
            self._loop.run_until_complete(
                asyncio.gather(*to_cancel, return_exceptions=True)
            )

    def wait(self, timeout_ms: int = 3000) -> bool:
        if not self._thread or not self._thread.is_alive():
            return True
        self._thread.join(timeout=timeout_ms / 1000)
        return not self._thread.is_alive()

    async def _execute(self) -> str:
        async def on_message(kind: str, content: str):
            if not self._stopped:
                self.message_received.emit(kind, content)

        async def on_tool_call(name: str, args: dict):
            if not self._stopped:
                self.tool_call_started.emit(name, args)

        async def on_tool_result(name: str, result: str, success: bool = True):
            if not self._stopped:
                self.tool_call_finished.emit(name, result, success)

        return await self.agent_loop.run(
            session_id=self.session_id,
            user_input=self.user_input,
            agent_name=self.agent_name,
            workdir=self.workdir,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
            on_message=on_message,
        )

    def stop(self):
        self._stopped = True
        try:
            self.agent_loop.abort(self.session_id)
        except Exception:
            pass
        if self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(lambda: None)
            except Exception:
                pass
