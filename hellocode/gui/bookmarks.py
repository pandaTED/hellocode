"""Session bookmarks/favorites functionality."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QMenu,
)

from .i18n import t


class BookmarkEntry:
    """Represents a bookmarked message."""

    def __init__(self, session_id: str, message_content: str, role: str,
                 timestamp: str = "", note: str = ""):
        self.session_id = session_id
        self.message_content = message_content[:200]
        self.role = role
        self.timestamp = timestamp
        self.note = note
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "message_content": self.message_content,
            "role": self.role,
            "timestamp": self.timestamp,
            "note": self.note,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BookmarkEntry":
        entry = cls(
            session_id=data.get("session_id", ""),
            message_content=data.get("message_content", ""),
            role=data.get("role", ""),
            timestamp=data.get("timestamp", ""),
            note=data.get("note", ""),
        )
        entry.created_at = data.get("created_at", entry.created_at)
        return entry


class BookmarkManager:
    """Manages bookmarks persistence."""

    def __init__(self, storage):
        self._storage = storage
        self._bookmarks: list[BookmarkEntry] = []
        self._load()

    def _load(self):
        try:
            data = self._storage.get_setting("bookmarks")
            if data:
                import json
                items = json.loads(data) if isinstance(data, str) else data
                self._bookmarks = [BookmarkEntry.from_dict(d) for d in items]
        except Exception:
            self._bookmarks = []

    def _save(self):
        import json
        data = json.dumps([b.to_dict() for b in self._bookmarks], ensure_ascii=False)
        self._storage.set_setting("bookmarks", data)

    def add(self, session_id: str, message_content: str, role: str,
            timestamp: str = "", note: str = "") -> BookmarkEntry:
        entry = BookmarkEntry(session_id, message_content, role, timestamp, note)
        self._bookmarks.insert(0, entry)
        self._save()
        return entry

    def remove(self, index: int):
        if 0 <= index < len(self._bookmarks):
            self._bookmarks.pop(index)
            self._save()

    def get_all(self) -> list[BookmarkEntry]:
        return list(self._bookmarks)

    def search(self, query: str) -> list[BookmarkEntry]:
        query_lower = query.lower()
        return [b for b in self._bookmarks
                if query_lower in b.message_content.lower()
                or query_lower in b.note.lower()]
