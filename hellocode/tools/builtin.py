"""Built-in tools: read, write, edit, glob, grep, bash, etc."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .base import ExecuteResult, Tool, ToolContext, _truncate

MAX_OUTPUT = 51200
logger = logging.getLogger("hellocode.tools")

_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\brm\s+-rf\s+~",
    r"\bdel\s+/[sS]\b",
    r"\bformat\s+[a-zA-Z]:",
    r"\bdd\s+if=.*of=/dev/",
    r":(){ :\|:& };:",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+0\b",
    r"\bcurl.*\|\s*(ba)?sh\b",
    r"\bwget.*\|\s*(ba)?sh\b",
]


class ReadTool(Tool):
    id = "read"
    description = "Read a file or directory from the local filesystem."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "Absolute path to file or directory"},
                "offset": {"type": "integer", "description": "Line number to start from (1-indexed)"},
                "limit": {"type": "integer", "description": "Max lines to read (default 2000)"},
            },
            "required": ["filePath"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        import aiofiles
        fp = Path(args["filePath"])
        if not fp.is_absolute():
            fp = ctx.workdir / fp
        if not fp.exists():
            return ExecuteResult(title="Error", output=f"Path not found: {fp}")
        if fp.is_dir():
            entries = []
            for e in sorted(fp.iterdir()):
                prefix = "d" if e.is_dir() else "f"
                entries.append(f"{prefix} {e.name}")
            return ExecuteResult(title="Directory", output="\n".join(entries))
        try:
            async with aiofiles.open(fp, encoding="utf-8", errors="replace") as f:
                content = await f.read()
            lines = content.splitlines()
        except Exception as e:
            return ExecuteResult(title="Error", output=str(e))
        offset = max(0, args.get("offset", 1) - 1)
        limit = args.get("limit", 2000)
        chunk = lines[offset : offset + limit]
        numbered = [f"{i + offset + 1}: {line}" for i, line in enumerate(chunk)]
        output = "\n".join(numbered)
        return ExecuteResult(title=f"Read {fp.name}", output=_truncate(output))


class WriteTool(Tool):
    id = "write"
    description = "Write content to a file, creating directories as needed."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filePath", "content"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        import aiofiles
        fp = Path(args["filePath"])
        if not fp.is_absolute():
            fp = ctx.workdir / fp
        fp.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(fp, "w", encoding="utf-8") as f:
            await f.write(args["content"])
        return ExecuteResult(title=f"Wrote {fp.name}", output=f"File written: {fp} ({len(args['content'])} chars)")


class EditTool(Tool):
    id = "edit"
    description = "Perform exact string replacement in a file."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "oldString": {"type": "string"},
                "newString": {"type": "string"},
                "replaceAll": {"type": "boolean"},
            },
            "required": ["filePath", "oldString", "newString"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        import aiofiles
        fp = Path(args["filePath"])
        if not fp.is_absolute():
            fp = ctx.workdir / fp
        if not fp.exists():
            return ExecuteResult(title="Error", output=f"File not found: {fp}")
        async with aiofiles.open(fp, encoding="utf-8") as f:
            content = await f.read()
        old = args["oldString"]
        new = args["newString"]
        replace_all = args.get("replaceAll", False)
        if old not in content:
            return ExecuteResult(title="Error", output="oldString not found in content")
        if not replace_all and content.count(old) > 1:
            return ExecuteResult(title="Error", output="Found multiple matches. Provide more context or set replaceAll=true.")
        if replace_all:
            content = content.replace(old, new)
        else:
            content = content.replace(old, new, 1)
        async with aiofiles.open(fp, "w", encoding="utf-8") as f:
            await f.write(content)
        return ExecuteResult(title=f"Edited {fp.name}", output="Edit applied successfully")


class GlobTool(Tool):
    id = "glob"
    description = "Find files by glob pattern."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        pattern = args["pattern"]
        base = Path(args.get("path") or ctx.workdir)
        matches = []
        try:
            for p in base.glob(pattern):
                matches.append(str(p.relative_to(base)))
        except Exception as e:
            return ExecuteResult(title="Error", output=str(e))
        matches.sort()
        return ExecuteResult(title="Glob results", output=_truncate("\n".join(matches[:200]) or "No matches"))


class GrepTool(Tool):
    id = "grep"
    description = "Search file contents using regex."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "include": {"type": "string"},
            },
            "required": ["pattern"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        pattern = args["pattern"]
        base = Path(args.get("path") or ctx.workdir)
        include = args.get("include")

        # Try system rg/grep first for performance
        for cmd_name in ("rg", "grep"):
            try:
                if cmd_name == "rg":
                    cmd_args = [cmd_name, "-n", "--max-count=100", "--no-heading"]
                    if include:
                        cmd_args += ["--glob", include]
                else:
                    cmd_args = [cmd_name, "-n", "-r", "-m", "100"]
                    if include:
                        cmd_args += ["--include", include]
                cmd_args += [pattern, str(base)]

                proc = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                if proc.returncode in (0, 1):
                    output = stdout.decode("utf-8", errors="replace").strip()
                    if output:
                        lines = output.splitlines()[:100]
                        return ExecuteResult(title="Grep results", output=_truncate("\n".join(lines)))
                break
            except (FileNotFoundError, asyncio.TimeoutError):
                continue

        # Fallback to Python implementation
        import aiofiles
        compiled = re.compile(pattern)
        results: list[str] = []
        try:
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if include and not fnmatch.fnmatch(p.name, include):
                    continue
                try:
                    async with aiofiles.open(p, encoding="utf-8", errors="replace") as f:
                        text = await f.read()
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if compiled.search(line):
                        rel = p.relative_to(base)
                        results.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(results) >= 100:
                            break
                if len(results) >= 100:
                    break
        except Exception as e:
            return ExecuteResult(title="Error", output=str(e))
        return ExecuteResult(title="Grep results", output=_truncate("\n".join(results) or "No matches"))


class BashTool(Tool):
    id = "bash"
    description = "Execute a shell command."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "Timeout in ms"},
                "workdir": {"type": "string"},
            },
            "required": ["command"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        cmd = args["command"]
        import re as _re
        for pattern in _DANGEROUS_PATTERNS:
            if _re.search(pattern, cmd, _re.IGNORECASE):
                return ExecuteResult(
                    title="Blocked",
                    output=f"Command blocked: matches dangerous pattern '{pattern}'",
                    metadata={"success": False},
                )
        timeout = (args.get("timeout") or 120000) / 1000
        cwd = args.get("workdir") or str(ctx.workdir)
        logger.info("Bash [%s]: %s", cwd, cmd[:200])
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                output = f"Exit code: {proc.returncode}\n{output}\n{err}"
            elif err:
                output = f"{output}\n{err}"
            return ExecuteResult(title="Bash", output=_truncate(output, MAX_OUTPUT))
        except asyncio.TimeoutError:
            return ExecuteResult(title="Bash", output=f"Command timed out after {timeout}s")
        except Exception as e:
            return ExecuteResult(title="Bash Error", output=str(e))


class ChangeDirectoryTool(Tool):
    id = "change_directory"
    description = "Switch the working directory."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        p = Path(args["path"])
        if not p.exists():
            return ExecuteResult(title="Error", output=f"Directory not found: {p}")
        ctx.workdir = p.resolve()
        return ExecuteResult(title="Changed directory", output=f"Now in: {ctx.workdir}")


class WebfetchTool(Tool):
    id = "webfetch"
    description = "Fetch content from a URL."

    _BLOCKED_SCHEMES = frozenset({"file", "ftp", "data", "javascript"})
    _PRIVATE_IP_PREFIXES = ("10.", "127.", "172.16.", "172.17.", "172.18.", "172.19.",
                            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                            "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
                            "192.168.", "169.254.")
    _LOCAL_HOSTNAMES = frozenset({"localhost", "0.0.0.0", "::1", ""})

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "markdown", "html"]},
            },
            "required": ["url", "format"],
        }

    @classmethod
    def _is_safe_url(cls, url: str) -> str | None:
        import ipaddress
        try:
            parsed = urlparse(url)
        except ValueError:
            return "Invalid URL"
        if parsed.scheme.lower() in cls._BLOCKED_SCHEMES:
            return f"Scheme '{parsed.scheme}' is not allowed"
        if parsed.scheme.lower() not in ("http", "https"):
            return f"Only http/https URLs are allowed"
        hostname = parsed.hostname or ""
        if hostname.lower() in cls._LOCAL_HOSTNAMES:
            return "localhost is not allowed"
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return None
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return "Private or local network addresses are not allowed"
        return None

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        url = args["url"]
        safety_error = self._is_safe_url(url)
        if safety_error:
            return ExecuteResult(title="Error", output=safety_error, metadata={"success": False})
        try:
            import aiohttp
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    body = await resp.text()
                    if resp.status >= 400:
                        return ExecuteResult(
                            title=f"HTTP {resp.status}",
                            output=_truncate(body),
                            metadata={"success": False, "status": resp.status},
                        )
                    return ExecuteResult(title=f"Fetched {url}", output=_truncate(body))
        except ImportError:
            return ExecuteResult(title="Error", output="aiohttp not installed. Run: pip install aiohttp", metadata={"success": False})
        except Exception as e:
            return ExecuteResult(title="Error", output=str(e), metadata={"success": False})


class QuestionTool(Tool):
    id = "question"
    description = "Ask the user a question and wait for response."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "header": {"type": "string"},
                "options": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["question", "header", "options"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        return ExecuteResult(
            title="Question",
            output=json.dumps({"question": args["question"], "header": args["header"], "pending": True}),
            metadata={"needs_user_input": True, "question": args},
        )


class TaskTool(Tool):
    id = "task"
    description = "Persistent task lifecycle management."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create", "list", "get", "start", "block", "unblock", "done", "abandon", "rename"]},
                        "id": {"type": "string"},
                        "summary": {"type": "string"},
                        "parent_id": {"type": "string"},
                        "status": {"type": "string"},
                        "event_summary": {"type": "string"},
                        "session_id": {"type": "string"},
                    },
                    "required": ["action"],
                },
            },
            "required": ["operation"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        if not ctx.storage:
            return ExecuteResult(title="Task", output=json.dumps({"error": "No storage available"}))
        op = args["operation"]
        action = op["action"]
        sid = op.get("session_id") or ctx.session_id

        try:
            if action == "create":
                result = ctx.storage.create_task(
                    session_id=sid,
                    summary=op["summary"],
                    parent_id=op.get("parent_id"),
                )
            elif action == "list":
                tasks = ctx.storage.list_tasks(sid, status=op.get("status"))
                result = tasks
            elif action == "get":
                result = ctx.storage.get_task(sid, op["id"])
            elif action == "start":
                ctx.storage.update_task(sid, op["id"], status="in_progress")
                ctx.storage.add_task_event(sid, op["id"], "started", op.get("event_summary", ""))
                result = {"status": "in_progress"}
            elif action == "block":
                ctx.storage.update_task(sid, op["id"], status="blocked")
                ctx.storage.add_task_event(sid, op["id"], "blocked", op.get("event_summary", ""))
                result = {"status": "blocked"}
            elif action == "unblock":
                ctx.storage.update_task(sid, op["id"], status="open")
                ctx.storage.add_task_event(sid, op["id"], "unblocked", op.get("event_summary", ""))
                result = {"status": "open"}
            elif action == "done":
                ctx.storage.update_task(sid, op["id"], status="done")
                ctx.storage.add_task_event(sid, op["id"], "completed", op.get("event_summary", ""))
                result = {"status": "done"}
            elif action == "abandon":
                ctx.storage.update_task(sid, op["id"], status="abandoned")
                ctx.storage.add_task_event(sid, op["id"], "abandoned", op.get("event_summary", ""))
                result = {"status": "abandoned"}
            elif action == "rename":
                ctx.storage.update_task(sid, op["id"], summary=op["summary"])
                result = {"summary": op["summary"]}
            else:
                result = {"error": f"Unknown action: {action}"}
            return ExecuteResult(title="Task", output=json.dumps(result, default=str, ensure_ascii=False))
        except Exception as e:
            return ExecuteResult(title="Task Error", output=json.dumps({"error": str(e)}))


class ActorTool(Tool):
    id = "actor"
    description = "Spawn and manage sub-agents (actors)."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["run", "spawn", "status", "wait", "cancel", "send"]},
                        "subagent_type": {"type": "string"},
                        "description": {"type": "string"},
                        "prompt": {"type": "string"},
                        "actor_id": {"type": "string"},
                        "to_actor_id": {"type": "string"},
                        "content": {"type": "string"},
                        "context": {"type": "string"},
                        "timeout_ms": {"type": "integer"},
                        "task_id": {"type": "string"},
                    },
                    "required": ["action"],
                },
            },
            "required": ["operation"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        if not ctx.actor_manager:
            return ExecuteResult(title="Actor", output=json.dumps({"error": "No actor manager available"}))
        op = args["operation"]
        action = op["action"]
        sid = ctx.session_id

        try:
            if action == "spawn" or action == "run":
                background = action == "spawn"
                actor_id = await ctx.actor_manager.spawn(
                    session_id=sid,
                    prompt=op["prompt"],
                    agent_type=op.get("subagent_type", "explore"),
                    description=op.get("description", ""),
                    background=background,
                    context_mode=op.get("context", "none"),
                )
                result = {"actor_id": actor_id, "status": "spawned"}
            elif action == "wait":
                actor = await ctx.actor_manager.wait(
                    sid, op["actor_id"], timeout=(op.get("timeout_ms") or 600000) / 1000
                )
                result = actor or {"error": "Actor not found"}
            elif action == "cancel":
                ctx.actor_manager.cancel(sid, op["actor_id"])
                result = {"status": "cancelled"}
            elif action == "status":
                actor = ctx.actor_manager.storage.get_actor(sid, op["actor_id"])
                result = actor or {"error": "Actor not found"}
            elif action == "send":
                await ctx.actor_manager.send_message(sid, op["to_actor_id"], op["content"])
                result = {"status": "sent"}
            else:
                result = {"error": f"Unknown action: {action}"}
            return ExecuteResult(title="Actor", output=json.dumps(result, default=str, ensure_ascii=False))
        except Exception as e:
            return ExecuteResult(title="Actor Error", output=json.dumps({"error": str(e)}))


class MemoryTool(Tool):
    id = "memory"
    description = "Search persistent memory using BM25 over markdown bodies."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["search"]},
                "query": {"type": "string"},
                "scope": {"type": "string"},
                "scope_id": {"type": "string"},
                "type": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["operation", "query"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        if not ctx.memory:
            return ExecuteResult(title="Memory", output=json.dumps({"error": "No memory system available"}))
        try:
            results = ctx.memory.search(
                query=args["query"],
                scope=args.get("scope"),
                scope_id=args.get("scope_id"),
                mtype=args.get("type"),
                limit=args.get("limit", 10),
            )
            return ExecuteResult(title="Memory Search", output=json.dumps(results, default=str, ensure_ascii=False))
        except Exception as e:
            return ExecuteResult(title="Memory Error", output=json.dumps({"error": str(e)}))


class WorkflowTool(Tool):
    id = "workflow"
    description = "Execute a workflow script."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["run", "status", "wait", "cancel", "resume"]},
                "name": {"type": "string"},
                "script": {"type": "string"},
                "args": {},
                "run_id": {"type": "string"},
                "workspace": {"type": "string"},
                "timeout_ms": {"type": "integer"},
            },
            "required": ["operation"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        if not ctx.storage:
            return ExecuteResult(title="Workflow", output=json.dumps({"error": "No storage available"}))
        action = args["operation"]
        try:
            if action == "run":
                script = args.get("script", "")
                if not script and args.get("name"):
                    safe_name = json.dumps(args['name'])
                    script = f"meta = {{'name': {safe_name}}}"
                if not script:
                    return ExecuteResult(title="Workflow", output=json.dumps({"error": "No script or name provided"}))
                from ..workflow import WorkflowRunner
                runner = WorkflowRunner(ctx.storage)
                result = await runner.run_workflow(
                    session_id=ctx.session_id,
                    script=script,
                    args=args.get("args"),
                )
                return ExecuteResult(title="Workflow", output=json.dumps(result, default=str, ensure_ascii=False))
            elif action == "status":
                row = ctx.storage._execute_one(
                    "SELECT * FROM workflow_run WHERE id=?", (args["run_id"],)
                )
                result = row if row else {"error": "Run not found"}
                return ExecuteResult(title="Workflow", output=json.dumps(result, default=str, ensure_ascii=False))
            else:
                return ExecuteResult(title="Workflow", output=json.dumps({"error": f"Action {action} not implemented"}))
        except Exception as e:
            return ExecuteResult(title="Workflow Error", output=json.dumps({"error": str(e)}))


class SkillTool(Tool):
    id = "skill"
    description = "Load a specialized skill."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        name = args["name"]
        candidates = [name]
        if ":" in name:
            candidates.append(name.split(":", 1)[1])
        search_paths = [
            Path.home() / ".codex" / "skills" / name / "SKILL.md",
            Path.home() / ".codex" / "skills" / ".system" / name / "SKILL.md",
            ctx.workdir / ".codex" / "skills" / name / "SKILL.md",
            Path.home() / ".config" / "hellocode" / "skills" / name / "SKILL.md",
        ]
        seen: set[Path] = set(search_paths)
        for base in (
            Path.home() / ".codex" / "skills",
            Path.home() / ".codex" / "plugins" / "cache",
        ):
            if not base.exists():
                continue
            try:
                for skill_file in base.rglob("SKILL.md"):
                    if skill_file.parent.name in candidates and skill_file not in seen:
                        search_paths.append(skill_file)
                        seen.add(skill_file)
            except OSError:
                continue
        for p in search_paths:
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
                return ExecuteResult(title=f"Skill: {name}", output=_truncate(content, 10000))
        return ExecuteResult(title="Skill", output=f"Skill '{name}' not found. Searched: {', '.join(str(p) for p in search_paths)}")


class NotebookEditTool(Tool):
    id = "notebook-edit"
    description = "Edit a Jupyter notebook cell."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "notebook_path": {"type": "string"},
                "new_source": {"type": "string"},
                "cell_type": {"type": "string"},
                "notebook_id": {"type": "string"},
            },
            "required": ["notebook_path", "new_source"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        fp = Path(args["notebook_path"])
        if not fp.is_absolute():
            fp = ctx.workdir / fp
        if not fp.exists():
            return ExecuteResult(title="Error", output=f"Notebook not found: {fp}")
        try:
            nb = json.loads(fp.read_text(encoding="utf-8"))
            cells = nb.get("cells", [])
            cell_id = args.get("notebook_id")
            if cell_id is not None:
                cell_idx = int(cell_id)
            else:
                cell_idx = len(cells) - 1
            if 0 <= cell_idx < len(cells):
                cells[cell_idx]["source"] = args["new_source"].splitlines(keepends=True)
            else:
                cells.append({
                    "cell_type": args.get("cell_type", "code"),
                    "source": args["new_source"].splitlines(keepends=True),
                    "metadata": {},
                    "outputs": [],
                })
            nb["cells"] = cells
            fp.write_text(json.dumps(nb, indent=1), encoding="utf-8")
            return ExecuteResult(title="Notebook edited", output="Cell updated")
        except Exception as e:
            return ExecuteResult(title="Error", output=str(e))


class ApplyPatchTool(Tool):
    id = "apply_patch"
    description = "Apply a unified diff patch."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "patch": {"type": "string"},
            },
            "required": ["patch"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        patch_content = args["patch"]
        try:
            # Dry run first
            proc = await asyncio.create_subprocess_exec(
                'patch', '-p1', '--dry-run',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(ctx.workdir),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=patch_content.encode()),
                timeout=10
            )

            if proc.returncode != 0:
                return ExecuteResult(
                    title="Patch Dry-run Failed",
                    output=stderr.decode(errors="replace") or stdout.decode(errors="replace"),
                )

            # Actually apply
            proc = await asyncio.create_subprocess_exec(
                'patch', '-p1',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(ctx.workdir),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=patch_content.encode()),
                timeout=10
            )

            output = stdout.decode(errors="replace")
            err = stderr.decode(errors="replace")
            if proc.returncode == 0:
                return ExecuteResult(title="Apply Patch", output=output or "Patch applied successfully")
            else:
                return ExecuteResult(title="Apply Patch Error", output=f"Exit code: {proc.returncode}\n{output}\n{err}")
        except asyncio.TimeoutError:
            return ExecuteResult(title="Apply Patch Error", output="Command timed out after 10s")
        except FileNotFoundError:
            return ExecuteResult(title="Apply Patch Error", output="'patch' command not found. Install patch or use Git Bash.")
        except Exception as e:
            return ExecuteResult(title="Apply Patch Error", output=str(e))


class KnowledgeTool(Tool):
    id = "knowledge"
    description = "Manage knowledge base: add/remove sources, index files, search documents."
    _engines: dict = {}

    def _get_engine(self, storage, data_dir):
        key = id(storage)
        if key not in self._engines:
            from ..knowledge import KnowledgeEngine
            self._engines[key] = KnowledgeEngine(storage, data_dir)
        return self._engines[key]

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": [
                    "add_source", "remove_source", "list_sources", "index",
                    "search", "get_document", "stats",
                ]},
                "name": {"type": "string", "description": "Source name (for add_source)"},
                "path": {"type": "string", "description": "File or folder path"},
                "source_id": {"type": "string", "description": "Source ID"},
                "query": {"type": "string", "description": "Search query"},
                "document_id": {"type": "string", "description": "Document ID (for get_document)"},
                "file_type": {"type": "string", "description": "Filter by file type"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["operation"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        if not ctx.memory:
            return ExecuteResult(title="Knowledge", output=json.dumps({"error": "No memory system available"}))
        try:
            data_dir = ctx.memory.data_dir.parent
            engine = self._get_engine(ctx.memory.storage, data_dir)
            action = args["operation"]

            if action == "add_source":
                p = Path(args["path"])
                if not p.is_absolute():
                    p = ctx.workdir / p
                name = args.get("name") or p.name
                result = engine.add_source(name, p)
                return ExecuteResult(title="Knowledge", output=json.dumps(result, default=str, ensure_ascii=False))

            elif action == "remove_source":
                engine.remove_source(args["source_id"])
                return ExecuteResult(title="Knowledge", output=json.dumps({"status": "removed"}))

            elif action == "list_sources":
                sources = engine.list_sources()
                return ExecuteResult(title="Knowledge", output=json.dumps(sources, default=str, ensure_ascii=False))

            elif action == "index":
                result = engine.index_source(args["source_id"])
                return ExecuteResult(title="Knowledge", output=json.dumps(result, default=str, ensure_ascii=False))

            elif action == "search":
                results = engine.search(
                    args["query"],
                    source_id=args.get("source_id"),
                    file_type=args.get("file_type"),
                    limit=args.get("limit", 10),
                )
                output = {"query": args["query"], "results": results}
                return ExecuteResult(title="Knowledge Search", output=json.dumps(output, default=str, ensure_ascii=False))

            elif action == "get_document":
                doc = engine.get_document(args["document_id"])
                if not doc:
                    return ExecuteResult(title="Knowledge", output=json.dumps({"error": "Document not found"}))
                chunks = engine.get_document_chunks(args["document_id"])
                doc["chunks"] = chunks
                return ExecuteResult(title="Knowledge", output=json.dumps(doc, default=str, ensure_ascii=False))

            elif action == "stats":
                stats = engine.get_stats()
                return ExecuteResult(title="Knowledge", output=json.dumps(stats, default=str, ensure_ascii=False))

            else:
                return ExecuteResult(title="Knowledge", output=json.dumps({"error": f"Unknown action: {action}"}))
        except Exception as e:
            return ExecuteResult(title="Knowledge Error", output=json.dumps({"error": str(e)}))


class ScheduleTool(Tool):
    id = "schedule"
    description = "Manage scheduled tasks: create, list, enable, disable, delete, view runs."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": [
                    "create", "list", "enable", "disable", "delete", "runs",
                ]},
                "name": {"type": "string", "description": "Schedule name"},
                "task_type": {"type": "string", "enum": ["workflow", "agent_prompt", "shell_command"]},
                "cron_expression": {"type": "string", "description": "5-field cron expression"},
                "interval_seconds": {"type": "integer", "description": "Interval in seconds"},
                "payload": {"type": "string", "description": "Task payload"},
                "agent_name": {"type": "string", "description": "Agent name for agent_prompt type"},
                "schedule_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["operation"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        if not ctx.storage:
            return ExecuteResult(title="Schedule", output=json.dumps({"error": "No storage available"}))
        try:
            action = args["operation"]

            if action == "create":
                if not args.get("name"):
                    return ExecuteResult(title="Schedule", output=json.dumps({"error": "name is required"}))
                if not args.get("task_type"):
                    return ExecuteResult(title="Schedule", output=json.dumps({"error": "task_type is required"}))
                schedule_id = ctx.storage.uid()
                result = ctx.storage.create_schedule(
                    id=schedule_id,
                    name=args["name"],
                    task_type=args["task_type"],
                    payload=args.get("payload", ""),
                    cron_expression=args.get("cron_expression"),
                    interval_seconds=args.get("interval_seconds"),
                    agent_name=args.get("agent_name", "build"),
                    session_id=ctx.session_id,
                    workdir=str(ctx.workdir),
                    description=args.get("description"),
                )
                return ExecuteResult(title="Schedule", output=json.dumps(result, default=str, ensure_ascii=False))

            elif action == "list":
                schedules = ctx.storage.list_schedules()
                return ExecuteResult(title="Schedule", output=json.dumps(schedules, default=str, ensure_ascii=False))

            elif action == "enable":
                if not args.get("schedule_id"):
                    return ExecuteResult(title="Schedule", output=json.dumps({"error": "schedule_id is required"}))
                ctx.storage.update_schedule(args["schedule_id"], enabled=1)
                return ExecuteResult(title="Schedule", output=json.dumps({"status": "enabled"}))

            elif action == "disable":
                if not args.get("schedule_id"):
                    return ExecuteResult(title="Schedule", output=json.dumps({"error": "schedule_id is required"}))
                ctx.storage.update_schedule(args["schedule_id"], enabled=0)
                return ExecuteResult(title="Schedule", output=json.dumps({"status": "disabled"}))

            elif action == "delete":
                if not args.get("schedule_id"):
                    return ExecuteResult(title="Schedule", output=json.dumps({"error": "schedule_id is required"}))
                ctx.storage.delete_schedule(args["schedule_id"])
                return ExecuteResult(title="Schedule", output=json.dumps({"status": "deleted"}))

            elif action == "runs":
                if not args.get("schedule_id"):
                    return ExecuteResult(title="Schedule", output=json.dumps({"error": "schedule_id is required"}))
                runs = ctx.storage.get_schedule_runs(args["schedule_id"], args.get("limit", 20))
                return ExecuteResult(title="Schedule", output=json.dumps(runs, default=str, ensure_ascii=False))

            else:
                return ExecuteResult(title="Schedule", output=json.dumps({"error": f"Unknown action: {action}"}))
        except Exception as e:
            return ExecuteResult(title="Schedule Error", output=json.dumps({"error": str(e)}))
