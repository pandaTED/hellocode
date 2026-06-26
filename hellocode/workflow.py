"""Workflow engine - structured workflow execution."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .storage import Storage


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
        script_sha = hashlib.sha256(script.encode()).hexdigest()[:16]
        run_id = self.storage.create_workflow_run(
            session_id=session_id,
            name="inline",
            args=args,
            parent_actor_id=parent_actor_id,
        )

        try:
            # Sandboxed execution: restrict dangerous builtins
            safe_builtins = {
                "print": print, "len": len, "range": range, "int": int,
                "float": float, "str": str, "bool": bool, "list": list,
                "dict": dict, "tuple": tuple, "set": set, "type": type,
                "isinstance": isinstance, "enumerate": enumerate, "zip": zip,
                "map": map, "filter": filter, "sorted": sorted, "reversed": reversed,
                "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
                "True": True, "False": False, "None": None,
                "Exception": Exception, "ValueError": ValueError,
                "TypeError": TypeError, "KeyError": KeyError,
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
        rows = self.storage.conn.execute(
            "SELECT * FROM workflow_run WHERE id=?", (run_id,)
        ).fetchone()
        return dict(rows) if rows else None
