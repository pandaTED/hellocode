"""Memory system - file-based memory with FTS5 search."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .storage import Storage


class MemorySystem:
    def __init__(self, storage: Storage, data_dir: Path):
        self.storage = storage
        self.data_dir = data_dir / "memory"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "global").mkdir(exist_ok=True)
        (self.data_dir / "projects").mkdir(exist_ok=True)
        (self.data_dir / "sessions").mkdir(exist_ok=True)
        self._fingerprints: dict[str, str] = self.storage.load_memory_fingerprints()
        self._last_reindex: float = 0

    def get_project_memory_path(self, project_id: str) -> Path:
        p = self.data_dir / "projects" / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p / "MEMORY.md"

    def get_session_dir(self, session_id: str) -> Path:
        d = self.data_dir / "sessions" / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_checkpoint_path(self, session_id: str) -> Path:
        return self.get_session_dir(session_id) / "checkpoint.md"

    def get_notes_path(self, session_id: str) -> Path:
        return self.get_session_dir(session_id) / "notes.md"

    def get_task_progress_path(self, session_id: str, task_id: str) -> Path:
        d = self.get_session_dir(session_id) / "tasks" / task_id
        d.mkdir(parents=True, exist_ok=True)
        return d / "progress.md"

    def get_global_memory_path(self) -> Path:
        return self.data_dir / "global" / "MEMORY.md"

    def read_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def append_to_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

    def reindex(self) -> int:
        count = 0
        for scope, pattern in [
            ("global", "global/*.md"),
            ("projects", "projects/*/MEMORY.md"),
            ("sessions", "sessions/*/checkpoint.md"),
            ("sessions", "sessions/*/notes.md"),
            ("sessions", "sessions/*/tasks/*/progress.md"),
        ]:
            for fp in self.data_dir.glob(pattern):
                rel = str(fp.relative_to(self.data_dir))
                try:
                    stat = fp.stat()
                except OSError:
                    continue
                fingerprint = f"{stat.st_size}-{int(stat.st_mtime * 1000)}"
                stored = self._fingerprints.get(rel)
                if stored == fingerprint:
                    continue
                parts = fp.relative_to(self.data_dir).parts
                scope_id = parts[1] if len(parts) > 1 else ""
                mtype = fp.stem.lower()
                try:
                    body = fp.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                self.storage.index_memory(rel, scope, scope_id, mtype, body, fingerprint)
                self._fingerprints[rel] = fingerprint
                count += 1
        # Remove entries for deleted files
        to_remove = [p for p in self._fingerprints if not (self.data_dir / p).exists()]
        for p in to_remove:
            del self._fingerprints[p]
            count += 1
        return count

    def search(self, query: str, scope: str | None = None, scope_id: str | None = None, mtype: str | None = None, limit: int = 10) -> list[dict]:
        now = time.time()
        # Reindex at most once every 5 seconds
        if now - self._last_reindex > 5:
            self.reindex()
            self._last_reindex = now
        return self.storage.search_memory(query, scope, scope_id, mtype, limit)

    def write_checkpoint(self, session_id: str, content: str) -> None:
        self.write_file(self.get_checkpoint_path(session_id), content)

    def read_checkpoint(self, session_id: str) -> str:
        return self.read_file(self.get_checkpoint_path(session_id))

    def write_notes(self, session_id: str, content: str) -> None:
        self.write_file(self.get_notes_path(session_id), content)

    def read_notes(self, session_id: str) -> str:
        return self.read_file(self.get_notes_path(session_id))

    def append_notes(self, session_id: str, content: str) -> None:
        self.append_to_file(self.get_notes_path(session_id), content)

    def write_project_memory(self, project_id: str, content: str) -> None:
        self.write_file(self.get_project_memory_path(project_id), content)

    def read_project_memory(self, project_id: str) -> str:
        return self.read_file(self.get_project_memory_path(project_id))

    def write_task_progress(self, session_id: str, task_id: str, content: str) -> None:
        self.write_file(self.get_task_progress_path(session_id, task_id), content)

    def read_task_progress(self, session_id: str, task_id: str) -> str:
        return self.read_file(self.get_task_progress_path(session_id, task_id))

    def write_global_memory(self, content: str) -> None:
        self.write_file(self.get_global_memory_path(), content)

    def read_global_memory(self) -> str:
        return self.read_file(self.get_global_memory_path())
