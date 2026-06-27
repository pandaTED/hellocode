"""Workflow engine - structured workflow execution."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .storage import Storage


_DANGEROUS_NAMES = frozenset({
    "__subclasses__", "__bases__", "__mro__", "__class__",
    "__import__", "exec", "eval", "compile", "globals", "locals",
    "getattr", "setattr", "delattr", "__builtins__", "open",
    "input", "vars", "dir",
})


def _scan_script_safety(script: str) -> str | None:
    """Return an error message if the script contains dangerous patterns, else None."""
    try:
        tree = ast.parse(script)
    except SyntaxError as e:
        return f"Syntax error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "Imports are blocked in workflow sandbox"
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return f"Access to '{node.attr}' is blocked in workflow sandbox"
            if node.attr in _DANGEROUS_NAMES:
                return f"Access to '{node.attr}' is blocked in workflow sandbox"
        elif isinstance(node, ast.Name):
            if node.id.startswith("__"):
                return f"Use of '{node.id}' is blocked in workflow sandbox"
            if node.id in _DANGEROUS_NAMES:
                return f"Use of '{node.id}' is blocked in workflow sandbox"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_NAMES:
                return f"Call to '{node.func.id}' is blocked in workflow sandbox"
            if isinstance(node.func, ast.Attribute) and node.func.attr in _DANGEROUS_NAMES:
                return f"Call to '{node.func.attr}' is blocked in workflow sandbox"
    return None


def _blocked_import(*args, **kwargs):
    raise ImportError("Imports are blocked in workflow sandbox")


class _SafeType:
    """Proxy type that blocks __subclasses__ and similar introspection."""
    _BLOCKED_ATTRS = frozenset({
        "__subclasses__", "__bases__", "__mro__", "__class__",
        "__init_subclass__", "__mro_entries__",
    })

    def __init__(self, wrapped: type):
        object.__setattr__(self, "_wrapped", wrapped)

    def __getattr__(self, name: str):
        if name in _SafeType._BLOCKED_ATTRS:
            raise AttributeError(f"Access to '{name}' is blocked in workflow sandbox")
        return getattr(object.__getattribute__(self, "_wrapped"), name)

    def __call__(self, *args, **kwargs):
        return object.__getattribute__(self, "_wrapped")(*args, **kwargs)

    def __instancecheck__(self, instance):
        return isinstance(instance, object.__getattribute__(self, "_wrapped"))

    def __subclasscheck__(self, subclass):
        return issubclass(subclass, object.__getattribute__(self, "_wrapped"))


class WorkflowContext:
    def __init__(self, storage: Storage, session_id: str, workdir: Path):
        self.storage = storage
        self.session_id = session_id
        self.workdir = workdir
        self._results: dict[str, Any] = {}

    def set_result(self, key: str, value: Any) -> None:
        self._results[key] = value

    def get_result(self, key: str) -> Any:
        return self._results.get(key)


class WorkflowRunner:
    def __init__(self, storage: Storage):
        self.storage = storage

    async def run_workflow(
        self,
        session_id: str,
        script: str,
        args: Any = None,
        parent_actor_id: str | None = None,
    ) -> dict:
        run_id = self.storage.create_workflow_run(
            session_id=session_id,
            name="inline",
            args=args,
            parent_actor_id=parent_actor_id,
        )

        safety_error = _scan_script_safety(script)
        if safety_error:
            self.storage.update_workflow_run(run_id, status="failed", running=0, failed=1, error=safety_error)
            return {"run_id": run_id, "status": "failed", "error": safety_error}

        try:
            safe_builtins = {
                "print": print, "len": len, "range": range, "int": int,
                "float": float, "str": str, "bool": bool, "list": list,
                "dict": dict, "tuple": tuple, "set": set, "type": _SafeType(type),
                "isinstance": isinstance, "enumerate": enumerate, "zip": zip,
                "map": map, "filter": filter, "sorted": sorted, "reversed": reversed,
                "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
                "True": True, "False": False, "None": None,
                "Exception": Exception, "ValueError": ValueError,
                "TypeError": TypeError, "KeyError": KeyError,
                "__import__": _blocked_import,
            }
            ns: dict[str, Any] = {
                "__builtins__": safe_builtins,
                "args": args,
                "run_id": run_id,
                "session_id": session_id,
            }
            exec(compile(script, "<workflow>", "exec"), ns)

            meta = ns.get("meta", {})
            name = meta.get("name", "inline")

            self.storage.update_workflow_run(run_id, name=name, status="running", running=1)

            result = {"run_id": run_id, "name": name, "status": "completed"}
            self.storage.update_workflow_run(run_id, status="completed", running=0, succeeded=1)
            return result

        except Exception as e:
            self.storage.update_workflow_run(run_id, status="failed", running=0, failed=1, error=str(e))
            return {"run_id": run_id, "status": "failed", "error": str(e)}

    def get_status(self, run_id: str) -> dict | None:
        return self.storage._execute_one(
            "SELECT * FROM workflow_run WHERE id=?", (run_id,)
        )
