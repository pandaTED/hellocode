"""SQLite storage layer with FTS5 full-text search."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import platform
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("hellocode.storage")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS project (
  id TEXT PRIMARY KEY,
  worktree TEXT,
  vcs TEXT,
  name TEXT,
  icon_url TEXT,
  icon_color TEXT,
  sandboards TEXT,
  commands TEXT,
  time_created INTEGER,
  time_updated INTEGER
);

CREATE TABLE IF NOT EXISTS session (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES project(id),
  workspace_id TEXT,
  parent_id TEXT,
  context_from TEXT,
  slug TEXT,
  directory TEXT,
  title TEXT,
  version INTEGER DEFAULT 0,
  share_url TEXT,
  summary_additions INTEGER DEFAULT 0,
  summary_deletions INTEGER DEFAULT 0,
  summary_files INTEGER DEFAULT 0,
  summary_diffs INTEGER DEFAULT 0,
  revert TEXT,
  permission TEXT,
  time_compacting INTEGER,
  time_archived INTEGER,
  last_checkpoint_message_id TEXT,
  time_created INTEGER,
  time_updated INTEGER
);

CREATE TABLE IF NOT EXISTS message (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES session(id),
  agent_id TEXT,
  data TEXT,
  time_created INTEGER,
  time_updated INTEGER
);

CREATE TABLE IF NOT EXISTS part (
  id TEXT PRIMARY KEY,
  message_id TEXT REFERENCES message(id),
  session_id TEXT,
  data TEXT,
  time_created INTEGER,
  time_updated INTEGER
);

CREATE TABLE IF NOT EXISTS task (
  session_id TEXT,
  id TEXT,
  parent_task_id TEXT,
  status TEXT DEFAULT 'open',
  summary TEXT,
  owner TEXT,
  created_at INTEGER,
  last_event_at INTEGER,
  ended_at INTEGER,
  cleanup_after INTEGER,
  PRIMARY KEY (session_id, id)
);

CREATE TABLE IF NOT EXISTS task_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  task_id TEXT,
  at INTEGER,
  kind TEXT,
  summary TEXT,
  FOREIGN KEY (session_id, task_id) REFERENCES task(session_id, id)
);

CREATE TABLE IF NOT EXISTS actor_registry (
  session_id TEXT,
  actor_id TEXT,
  mode TEXT DEFAULT 'peer',
  parent_actor_id TEXT,
  status TEXT DEFAULT 'pending',
  last_outcome TEXT,
  lifecycle TEXT DEFAULT 'ephemeral',
  agent TEXT,
  description TEXT,
  context_mode TEXT DEFAULT 'none',
  context_watermark INTEGER,
  background INTEGER DEFAULT 0,
  tools TEXT,
  last_turn_time INTEGER,
  turn_count INTEGER DEFAULT 0,
  last_error TEXT,
  PRIMARY KEY (session_id, actor_id)
);

CREATE TABLE IF NOT EXISTS inbox (
  id TEXT PRIMARY KEY,
  receiver_session_id TEXT,
  receiver_actor_id TEXT,
  sender_session_id TEXT,
  sender_actor_id TEXT,
  type TEXT DEFAULT 'text',
  content TEXT,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS workflow_run (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  name TEXT,
  status TEXT DEFAULT 'pending',
  running INTEGER DEFAULT 0,
  succeeded INTEGER DEFAULT 0,
  failed INTEGER DEFAULT 0,
  current_phase TEXT,
  parent_actor_id TEXT,
  args TEXT,
  script_sha TEXT,
  agent_timeout_ms INTEGER,
  error TEXT
);

CREATE TABLE IF NOT EXISTS account (
  id TEXT PRIMARY KEY,
  email TEXT,
  url TEXT,
  access_token TEXT,
  refresh_token TEXT,
  token_expiry INTEGER
);

CREATE TABLE IF NOT EXISTS permission (
  project_id TEXT PRIMARY KEY,
  data TEXT
);

CREATE TABLE IF NOT EXISTS event_sequence (
  aggregate_id TEXT PRIMARY KEY,
  seq INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS event (
  id TEXT PRIMARY KEY,
  aggregate_id TEXT REFERENCES event_sequence(aggregate_id),
  seq INTEGER,
  type TEXT,
  data TEXT
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
  path,
  scope,
  scope_id,
  type,
  body,
  content=memory_fts_content,
  content_rowid=rowid
);

CREATE TABLE IF NOT EXISTS memory_fts_content (
  rowid INTEGER PRIMARY KEY,
  path,
  scope,
  scope_id,
  type,
  body,
  fingerprint TEXT DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
  part_id,
  session_id,
  message_id,
  project_id,
  kind,
  tool_name,
  body,
  time_created
);
"""


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()
        logger.info("Storage initialized: %s", db_path)

    def _init_schema(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.executescript(SCHEMA_SQL)
            self._migrate_project_table()
            self._migrate_memory_fts()
            try:
                cur.executescript(FTS_SCHEMA)
            except sqlite3.OperationalError:
                pass
            self.conn.commit()

    def _migrate_memory_fts(self):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT 1 FROM memory_fts LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cur.execute("DROP TABLE IF EXISTS memory_fts")
                cur.execute("DROP TABLE IF EXISTS memory_fts_content")
                cur.executescript(FTS_SCHEMA)
                logger.info("Created memory_fts tables")
            except sqlite3.OperationalError:
                pass

    def _migrate_project_table(self):
        cur = self.conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(project)").fetchall()}
        if "time_initialized" in cols and "time_created" not in cols:
            cur.execute("ALTER TABLE project RENAME COLUMN time_initialized TO time_created")
        if "time_created" not in cols and "time_initialized" not in cols:
            cur.execute("ALTER TABLE project ADD COLUMN time_created INTEGER")
        if "time_updated" not in cols:
            cur.execute("ALTER TABLE project ADD COLUMN time_updated INTEGER")

    def close(self):
        with self._lock:
            self.conn.close()

    def _get_token_key(self) -> bytes:
        machine_id = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
        return hashlib.pbkdf2_hmac("sha256", machine_id.encode(), b"hellocode-tokens", 100000)

    def _encrypt_token(self, token: str) -> str:
        if not token:
            return ""
        key = self._get_token_key()
        token_bytes = token.encode("utf-8")
        # XOR with key bytes (simple obfuscation, not cryptographic security)
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(token_bytes))
        return base64.b64encode(encrypted).decode("ascii")

    def _decrypt_token(self, encrypted: str) -> str:
        if not encrypted:
            return ""
        try:
            key = self._get_token_key()
            decoded = base64.b64decode(encrypted)
            decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(decoded))
            return decrypted.decode("utf-8")
        except Exception:
            return encrypted

    def _execute(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            try:
                rows = self.conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.Error as e:
                logger.error("SQL error: %s | sql=%s", e, sql[:200])
                raise

    def _execute_one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            try:
                r = self.conn.execute(sql, params).fetchone()
                return dict(r) if r else None
            except sqlite3.Error as e:
                logger.error("SQL error: %s | sql=%s", e, sql[:200])
                raise

    def now(self) -> int:
        return int(time.time() * 1000)

    def uid(self) -> str:
        return uuid.uuid4().hex[:16]

    def _d(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    def _r(self, s: str | None) -> Any:
        if s is None:
            return None
        return json.loads(s)

    @staticmethod
    def _safe_column_name(name: str) -> str:
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValueError(f"Invalid column name: {name}")
        return name

    # ── Project ──

    def _get_not_null_columns(self, table: str) -> list[dict]:
        safe_table = self._safe_column_name(table)
        rows = self._execute(f"PRAGMA table_info({safe_table})")
        return [{"name": r["name"], "notnull": r["notnull"], "default": r["dflt_value"]} for r in rows]

    def _fill_defaults(self, table: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        cols = self._get_not_null_columns(table)
        now = self.now()
        defaults = {
            "id": self.uid(),
            "time_created": now,
            "time_updated": now,
            "time_initialized": now,
            "sandboards": "[]",
            "sandboxes": "[]",
            "commands": "[]",
            "vcs": "git",
            "status": "open",
            "version": 0,
        }
        result: dict[str, Any] = {}
        for col in cols:
            name = col["name"]
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
                continue
            if overrides and name in overrides:
                result[name] = overrides[name]
            elif col["notnull"] and col["default"] is None:
                result[name] = defaults.get(name, "")
            elif col["default"] is not None:
                pass
            else:
                result[name] = defaults.get(name)
        return result

    def create_project(self, worktree: str, name: str | None = None, vcs: str = "git") -> dict:
        vals = self._fill_defaults("project", {"worktree": worktree, "name": name, "vcs": vcs})
        cols = [self._safe_column_name(k) for k in vals.keys()]
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(vals))
        with self._lock:
            self.conn.execute(
                f"INSERT INTO project ({cols_str}) VALUES ({placeholders})",
                list(vals.values()),
            )
            self.conn.commit()
        return {"id": vals["id"], "worktree": worktree, "name": name}

    def get_project(self, pid: str) -> dict | None:
        return self._execute_one("SELECT * FROM project WHERE id=?", (pid,))

    def find_project_by_worktree(self, worktree: str) -> dict | None:
        return self._execute_one("SELECT * FROM project WHERE worktree=?", (worktree,))

    # ── Session ──

    def create_session(self, project_id: str, directory: str, title: str = "") -> dict:
        vals = self._fill_defaults("session", {
            "project_id": project_id, "directory": directory, "title": title,
        })
        cols = [self._safe_column_name(k) for k in vals.keys()]
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(vals))
        with self._lock:
            self.conn.execute(
                f"INSERT INTO session ({cols_str}) VALUES ({placeholders})",
                list(vals.values()),
            )
            self.conn.commit()
        return {"id": vals["id"], "project_id": project_id, "title": title}

    def get_session(self, sid: str) -> dict | None:
        return self._execute_one("SELECT * FROM session WHERE id=?", (sid,))

    def update_session(self, sid: str, **kwargs) -> None:
        sets = []
        vals = []
        for k, v in kwargs.items():
            safe_name = self._safe_column_name(k)
            sets.append(f"{safe_name}=?")
            vals.append(v)
        sets.append("time_updated=?")
        vals.append(self.now())
        vals.append(sid)
        with self._lock:
            self.conn.execute(f"UPDATE session SET {','.join(sets)} WHERE id=?", vals)
            self.conn.commit()

    def list_sessions(self, project_id: str, limit: int = 50) -> list[dict]:
        return self._execute(
            "SELECT * FROM session WHERE project_id=? ORDER BY time_updated DESC LIMIT ?",
            (project_id, limit),
        )

    def clear_session(self, sid: str) -> None:
        with self._lock:
            message_ids = [
                r["id"]
                for r in self.conn.execute("SELECT id FROM message WHERE session_id=?", (sid,)).fetchall()
            ]
            if message_ids:
                placeholders = ",".join("?" for _ in message_ids)
                self.conn.execute(f"DELETE FROM part WHERE message_id IN ({placeholders})", message_ids)
            self.conn.execute("DELETE FROM message WHERE session_id=?", (sid,))
            self.conn.execute("DELETE FROM history_fts WHERE session_id=?", (sid,))
            self.conn.execute("DELETE FROM task_event WHERE session_id=?", (sid,))
            self.conn.execute("DELETE FROM task WHERE session_id=?", (sid,))
            self.conn.execute("DELETE FROM actor_registry WHERE session_id=?", (sid,))
            self.conn.execute(
                "DELETE FROM inbox WHERE receiver_session_id=? OR sender_session_id=?",
                (sid, sid),
            )
            self.conn.execute("DELETE FROM workflow_run WHERE session_id=?", (sid,))
            self.conn.execute(
                "UPDATE session SET title=?, time_updated=? WHERE id=?",
                ("New Session", self.now(), sid),
            )
            self.conn.commit()

    def delete_session(self, sid: str) -> None:
        self.clear_session(sid)
        with self._lock:
            self.conn.execute("DELETE FROM session WHERE id=?", (sid,))
            self.conn.commit()

    # ── Message ──

    def create_message(self, session_id: str, agent_id: str, data: dict) -> dict:
        vals = self._fill_defaults("message", {
            "session_id": session_id, "agent_id": agent_id, "data": self._d(data),
        })
        cols = [self._safe_column_name(k) for k in vals.keys()]
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(vals))
        with self._lock:
            self.conn.execute(
                f"INSERT INTO message ({cols_str}) VALUES ({placeholders})",
                list(vals.values()),
            )
            self.conn.commit()
        return {"id": vals["id"], "session_id": session_id, "data": data}

    def get_message(self, mid: str) -> dict | None:
        d = self._execute_one("SELECT * FROM message WHERE id=?", (mid,))
        if not d:
            return None
        d["data"] = self._r(d["data"])
        return d

    def list_messages(self, session_id: str, limit: int = 200) -> list[dict]:
        rows = self._execute(
            """
            SELECT * FROM (
              SELECT message.*, message.rowid AS _message_rowid FROM message
              WHERE session_id=?
              ORDER BY time_created DESC, _message_rowid DESC
              LIMIT ?
            )
            ORDER BY time_created ASC, _message_rowid ASC
            """,
            (session_id, limit),
        )
        for d in rows:
            d.pop("_message_rowid", None)
            d["data"] = self._r(d["data"])
        return rows

    # ── Part ──

    def create_part(self, message_id: str, session_id: str, data: dict) -> str:
        vals = self._fill_defaults("part", {
            "message_id": message_id, "session_id": session_id, "data": self._d(data),
        })
        cols = [self._safe_column_name(k) for k in vals.keys()]
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(vals))
        with self._lock:
            self.conn.execute(
                f"INSERT INTO part ({cols_str}) VALUES ({placeholders})",
                list(vals.values()),
            )
            self.conn.commit()
        return vals["id"]

    def list_parts(self, message_id: str) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM part WHERE message_id=? ORDER BY time_created", (message_id,)
        )
        return [{"id": d["id"], **self._r(d["data"])} for d in rows]

    # ── Task ──

    def create_task(self, session_id: str, summary: str, parent_id: str | None = None, owner: str = "main") -> dict:
        tid = self.uid()
        now = self.now()
        with self._lock:
            self.conn.execute(
                "INSERT INTO task (session_id, id, parent_task_id, status, summary, owner, created_at, last_event_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (session_id, tid, parent_id, "open", summary, owner, now, now),
            )
            self.conn.commit()
        self._add_task_event(session_id, tid, "created", summary)
        return {"id": tid, "status": "open", "summary": summary}

    def update_task(self, session_id: str, task_id: str, status: str | None = None, summary: str | None = None) -> None:
        now = self.now()
        with self._lock:
            if status:
                safe_status = self._safe_column_name("status")
                self.conn.execute(
                    f"UPDATE task SET {safe_status}=?, last_event_at=? WHERE session_id=? AND id=?",
                    (status, now, session_id, task_id),
                )
            if summary:
                safe_summary = self._safe_column_name("summary")
                self.conn.execute(
                    f"UPDATE task SET {safe_summary}=?, last_event_at=? WHERE session_id=? AND id=?",
                    (summary, now, session_id, task_id),
                )
            self.conn.commit()

    def get_task(self, session_id: str, task_id: str) -> dict | None:
        return self._execute_one(
            "SELECT * FROM task WHERE session_id=? AND id=?", (session_id, task_id)
        )

    def list_tasks(self, session_id: str, status: str | None = None) -> list[dict]:
        if status:
            return self._execute(
                "SELECT * FROM task WHERE session_id=? AND status=? ORDER BY created_at",
                (session_id, status),
            )
        else:
            return self._execute(
                "SELECT * FROM task WHERE session_id=? ORDER BY created_at",
                (session_id,),
            )

    def has_open_tasks(self, session_id: str) -> bool:
        r = self._execute_one(
            "SELECT COUNT(*) as c FROM task WHERE session_id=? AND status IN ('open','in_progress','blocked')",
            (session_id,),
        )
        return r["c"] > 0

    def _add_task_event(self, session_id: str, task_id: str, kind: str, summary: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO task_event (session_id, task_id, at, kind, summary) VALUES (?,?,?,?,?)",
                (session_id, task_id, self.now(), kind, summary),
            )
            self.conn.commit()

    def add_task_event(self, session_id: str, task_id: str, kind: str, summary: str) -> None:
        self._add_task_event(session_id, task_id, kind, summary)

    # ── Actor ──

    def register_actor(
        self,
        session_id: str,
        actor_id: str,
        mode: str = "peer",
        parent_actor_id: str | None = None,
        agent: str = "build",
        description: str = "",
        context_mode: str = "none",
        background: bool = False,
        tools: list[str] | None = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO actor_registry "
                "(session_id, actor_id, mode, parent_actor_id, status, lifecycle, agent, description, "
                "context_mode, background, tools, last_turn_time, turn_count) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session_id, actor_id, mode, parent_actor_id, "pending", "ephemeral",
                    agent, description, context_mode, int(background),
                    self._d(tools or []), self.now(), 0,
                ),
            )
            self.conn.commit()

    def update_actor(self, session_id: str, actor_id: str, **kwargs) -> None:
        sets = []
        vals = []
        for k, v in kwargs.items():
            safe_name = self._safe_column_name(k)
            sets.append(f"{safe_name}=?")
            vals.append(self._d(v) if isinstance(v, (list, dict)) else v)
        vals.append(session_id)
        vals.append(actor_id)
        with self._lock:
            self.conn.execute(f"UPDATE actor_registry SET {','.join(sets)} WHERE session_id=? AND actor_id=?", vals)
            self.conn.commit()

    def get_actor(self, session_id: str, actor_id: str) -> dict | None:
        d = self._execute_one(
            "SELECT * FROM actor_registry WHERE session_id=? AND actor_id=?",
            (session_id, actor_id),
        )
        if d:
            d["tools"] = self._r(d["tools"])
        return d

    def list_actors(self, session_id: str, status: str | None = None) -> list[dict]:
        if status:
            rows = self._execute(
                "SELECT * FROM actor_registry WHERE session_id=? AND status=?",
                (session_id, status),
            )
        else:
            rows = self._execute(
                "SELECT * FROM actor_registry WHERE session_id=?", (session_id,)
            )
        for d in rows:
            d["tools"] = self._r(d["tools"])
        return rows

    # ── Inbox ──

    def send_inbox(
        self,
        receiver_session_id: str,
        receiver_actor_id: str,
        sender_session_id: str,
        sender_actor_id: str,
        content: Any,
        msg_type: str = "text",
    ) -> str:
        mid = self.uid()
        with self._lock:
            self.conn.execute(
                "INSERT INTO inbox "
                "(id, receiver_session_id, receiver_actor_id, sender_session_id, sender_actor_id, type, content, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (mid, receiver_session_id, receiver_actor_id, sender_session_id, sender_actor_id,
                 msg_type, self._d(content), self.now()),
            )
            self.conn.commit()
        return mid

    def drain_inbox(self, session_id: str, actor_id: str) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM inbox WHERE receiver_session_id=? AND receiver_actor_id=? ORDER BY created_at",
                (session_id, actor_id),
            ).fetchall()
            result = [dict(r) for r in rows]
            for d in result:
                d["content"] = self._r(d["content"])
            ids = [d["id"] for d in result]
            if ids:
                placeholders = ",".join(["?"] * len(ids))
                self.conn.execute(f"DELETE FROM inbox WHERE id IN ({placeholders})", ids)
                self.conn.commit()
        return result

    # ── Memory FTS ──

    def index_memory(self, path: str, scope: str, scope_id: str, mtype: str, body: str, fingerprint: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM memory_fts WHERE path=?", (path,)
            )
            self.conn.execute(
                "DELETE FROM memory_fts_content WHERE path=?", (path,)
            )
            self.conn.execute(
                "INSERT INTO memory_fts_content (path, scope, scope_id, type, body, fingerprint) VALUES (?,?,?,?,?,?)",
                (path, scope, scope_id, mtype, body, fingerprint),
            )
            try:
                self.conn.execute(
                    "INSERT INTO memory_fts (path, scope, scope_id, type, body) VALUES (?,?,?,?,?)",
                    (path, scope, scope_id, mtype, body),
                )
            except sqlite3.OperationalError:
                pass
            self.conn.commit()

    def load_memory_fingerprints(self) -> dict[str, str]:
        try:
            rows = self._execute("SELECT path, fingerprint FROM memory_fts_content")
            return {d["path"]: d["fingerprint"] for d in rows if d["fingerprint"]}
        except sqlite3.OperationalError:
            return {}

    def search_memory(
        self,
        query: str,
        scope: str | None = None,
        scope_id: str | None = None,
        mtype: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        terms = [t for t in query.split() if t.strip()]
        if not terms:
            return []
        fts_query = " OR ".join(terms)
        conditions = []
        params: list[Any] = []
        if scope:
            conditions.append("scope=?")
            params.append(scope)
        if scope_id:
            conditions.append("scope_id=?")
            params.append(scope_id)
        if mtype:
            conditions.append("type=?")
            params.append(mtype)

        where = ""
        if conditions:
            where = "AND " + " AND ".join(conditions)

        sql = f"""
            SELECT path, scope, scope_id, type, body,
                   rank AS score
            FROM memory_fts
            WHERE memory_fts MATCH ? {where}
            ORDER BY rank
            LIMIT ?
        """
        params = [fts_query] + params + [limit]
        try:
            rows = self._execute(sql, params)
        except sqlite3.DatabaseError:
            self._rebuild_memory_fts()
            try:
                rows = self._execute(sql, params)
            except sqlite3.DatabaseError:
                return []
        results = rows
        if results:
            best_score = abs(results[0]["score"])
            threshold = best_score * 0.15
            results = [r for r in results if abs(r["score"]) >= threshold]
        return results

    def _rebuild_memory_fts(self) -> None:
        with self._lock:
            try:
                self.conn.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
                self.conn.commit()
            except sqlite3.DatabaseError:
                try:
                    self.conn.execute("DROP TABLE IF EXISTS memory_fts")
                    self.conn.execute("DROP TABLE IF EXISTS memory_fts_content")
                    self.conn.executescript(FTS_SCHEMA)
                    self.conn.commit()
                except sqlite3.OperationalError:
                    pass

    # ── History FTS ──

    def index_history(self, part_id: str, session_id: str, message_id: str, project_id: str, kind: str, tool_name: str, body: str) -> None:
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT INTO history_fts (part_id, session_id, message_id, project_id, kind, tool_name, body, time_created) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (part_id, session_id, message_id, project_id, kind, tool_name, body, self.now()),
                )
                self.conn.commit()
        except sqlite3.OperationalError:
            pass

    def search_history(self, query: str, session_id: str | None = None, limit: int = 20) -> list[dict]:
        terms = [t for t in query.split() if t.strip()]
        if not terms:
            return []
        fts_query = " OR ".join(terms)
        if session_id:
            sql = "SELECT * FROM history_fts WHERE history_fts MATCH ? AND session_id=? ORDER BY rank LIMIT ?"
            rows = self._execute(sql, (fts_query, session_id, limit))
        else:
            sql = "SELECT * FROM history_fts WHERE history_fts MATCH ? ORDER BY rank LIMIT ?"
            rows = self._execute(sql, (fts_query, limit))
        return [dict(r) for r in rows]

    # ── Event Sourcing ──

    def append_event(self, aggregate_id: str, event_type: str, data: dict) -> int:
        with self._lock:
            r = self.conn.execute(
                "SELECT seq FROM event_sequence WHERE aggregate_id=?", (aggregate_id,)
            ).fetchone()
            seq = (r["seq"] if r else 0) + 1
            self.conn.execute(
                "INSERT OR REPLACE INTO event_sequence (aggregate_id, seq) VALUES (?,?)",
                (aggregate_id, seq),
            )
            self.conn.execute(
                "INSERT INTO event (id, aggregate_id, seq, type, data) VALUES (?,?,?,?,?)",
                (self.uid(), aggregate_id, seq, event_type, self._d(data)),
            )
            self.conn.commit()
        return seq

    def get_events(self, aggregate_id: str, after_seq: int = 0) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM event WHERE aggregate_id=? AND seq>? ORDER BY seq",
            (aggregate_id, after_seq),
        )
        for d in rows:
            d["data"] = self._r(d["data"])
        return rows

    # ── Workflow ──

    def create_workflow_run(self, session_id: str, name: str, args: dict | None = None, parent_actor_id: str | None = None) -> str:
        wid = self.uid()
        with self._lock:
            self.conn.execute(
                "INSERT INTO workflow_run (id, session_id, name, status, running, args, parent_actor_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (wid, session_id, name, "running", 1, self._d(args or {}), parent_actor_id),
            )
            self.conn.commit()
        return wid

    def update_workflow_run(self, wid: str, **kwargs) -> None:
        sets = []
        vals = []
        for k, v in kwargs.items():
            safe_name = self._safe_column_name(k)
            sets.append(f"{safe_name}=?")
            vals.append(self._d(v) if isinstance(v, (list, dict)) else v)
        vals.append(wid)
        with self._lock:
            self.conn.execute(f"UPDATE workflow_run SET {','.join(sets)} WHERE id=?", vals)
            self.conn.commit()

    # ── Account ──

    def upsert_account(self, account_id: str, email: str = "", url: str = "",
                        access_token: str = "", refresh_token: str = "", token_expiry: int = 0) -> None:
        enc_access = self._encrypt_token(access_token)
        enc_refresh = self._encrypt_token(refresh_token)
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO account (id, email, url, access_token, refresh_token, token_expiry) "
                "VALUES (?,?,?,?,?,?)",
                (account_id, email, url, enc_access, enc_refresh, token_expiry),
            )
            self.conn.commit()

    def get_account(self, account_id: str) -> dict | None:
        d = self._execute_one("SELECT * FROM account WHERE id=?", (account_id,))
        if d:
            d["access_token"] = self._decrypt_token(d.get("access_token", ""))
            d["refresh_token"] = self._decrypt_token(d.get("refresh_token", ""))
        return d

    def delete_account(self, account_id: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM account WHERE id=?", (account_id,))
            self.conn.commit()
