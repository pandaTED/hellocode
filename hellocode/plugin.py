"""Plugin system with hook architecture."""

from __future__ import annotations

import asyncio
import importlib
import logging
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("hellocode.plugin")

from .config import Config


class PluginHooks:
    """Available hook points."""
    ACTOR_PRE_STOP = "actor.preStop"
    ACTOR_POST_STOP = "actor.postStop"
    EVENT = "event"
    CONFIG = "config"
    INPUT = "input"
    OUTPUT = "output"


class Plugin:
    def __init__(self, name: str, path: Path | None = None):
        self.name = name
        self.path = path
        self._hooks: dict[str, Callable] = {}
        self._failures = 0
        self._circuit_open = False
        self._circuit_open_until = 0.0

    def register_hook(self, hook_name: str, handler: Callable) -> None:
        self._hooks[hook_name] = handler

    def has_hook(self, hook_name: str) -> bool:
        return hook_name in self._hooks

    async def run_hook(self, hook_name: str, *args, **kwargs) -> Any:
        if self._circuit_open:
            if time.time() < self._circuit_open_until:
                return None
            self._circuit_open = False
            self._failures = 0

        handler = self._hooks.get(hook_name)
        if not handler:
            return None

        try:
            if asyncio.iscoroutinefunction(handler):
                coro = handler(*args, **kwargs)
            else:
                coro = asyncio.to_thread(handler, *args, **kwargs)
            result = await asyncio.wait_for(coro, timeout=5.0)
            self._failures = 0
            return result
        except Exception:
            self._failures += 1
            if self._failures >= 3:
                self._circuit_open = True
                self._circuit_open_until = time.time() + 5.0
            return None


class PluginManager:
    def __init__(self, config: Config):
        self.config = config
        self._plugins: list[Plugin] = []

    def load_plugins(self) -> None:
        for path_str in self.config.plugin_paths:
            path = Path(path_str)
            if not path.exists():
                continue
            if path.is_file() and path.suffix == ".py":
                self._load_python_plugin(path)
            elif path.is_dir():
                for f in path.glob("*.py"):
                    self._load_python_plugin(f)

    def _load_python_plugin(self, path: Path) -> None:
        try:
            spec = importlib.util.spec_from_file_location(path.stem, str(path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                plugin = Plugin(name=path.stem, path=path)
                if hasattr(mod, "register"):
                    mod.register(plugin)
                self._plugins.append(plugin)
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", path, e)

    def add_plugin(self, plugin: Plugin) -> None:
        self._plugins.append(plugin)

    async def run_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        results = []
        for plugin in self._plugins:
            if plugin.has_hook(hook_name):
                result = await plugin.run_hook(hook_name, *args, **kwargs)
                results.append(result)
        return results

    def get_plugins(self) -> list[Plugin]:
        return list(self._plugins)
