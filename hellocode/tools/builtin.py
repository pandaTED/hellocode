"""Built-in tools: read, write, edit, glob, grep, bash, etc."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .base import ExecuteResult, Tool, ToolContext, _truncate

MAX_OUTPUT = 51200


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
            for p in base.rglob("*"):
                if p.match(pattern):
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
        import aiofiles
        pattern = re.compile(args["pattern"])
        base = Path(args.get("path") or ctx.workdir)
        include = args.get("include")
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
                    if pattern.search(line):
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
        timeout = (args.get("timeout") or 120000) / 1000
        cwd = args.get("workdir") or str(ctx.workdir)
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

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "markdown", "html"]},
            },
            "required": ["url", "format"],
        }

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        import aiohttp
        url = args["url"]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    body = await resp.text()
                    return ExecuteResult(title=f"Fetched {url}", output=_truncate(body))
        except Exception as e:
            return ExecuteResult(title="Error", output=str(e))


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
                row = ctx.storage.conn.execute(
                    "SELECT * FROM workflow_run WHERE id=?", (args["run_id"],)
                ).fetchone()
                result = dict(row) if row else {"error": "Run not found"}
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
        search_paths = [
            Path.home() / ".codex" / "skills" / name / "SKILL.md",
            ctx.workdir / ".codex" / "skills" / name / "SKILL.md",
            Path.home() / ".config" / "hellocode" / "skills" / name / "SKILL.md",
        ]
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
        if not fp.exists():
            return ExecuteResult(title="Error", output=f"Notebook not found: {fp}")
        try:
            nb = json.loads(fp.read_text(encoding="utf-8"))
            cell_idx = int(args.get("notebook_id") or len(nb.get("cells", [])) - 1)
            cells = nb.get("cells", [])
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
            import difflib
            from pathlib import Path
            
            # 解析 patch 文件
            patch_lines = patch_content.splitlines()
            files_to_patch = {}
            current_file = None
            current_diff = []
            
            for line in patch_lines:
                if line.startswith('diff --git'):
                    if current_file and current_diff:
                        files_to_patch[current_file] = current_diff
                    # 提取文件名
                    parts = line.split(' ')
                    if len(parts) >= 3:
                        current_file = parts[2].lstrip('a/').lstrip('b/')
                    else:
                        current_file = "unknown"
                    current_diff = [line]
                elif line.startswith('---') or line.startswith('+++'):
                    if current_file:
                        current_diff.append(line)
                elif current_file:
                    current_diff.append(line)
            
            if current_file and current_diff:
                files_to_patch[current_file] = current_diff
            
            if not files_to_patch:
                return ExecuteResult(title="Error", output="No valid patch content found")
            
            # 应用补丁
            import asyncio
            results = []
            for file_path, diff_lines in files_to_patch.items():
                full_path = ctx.workdir / file_path
                if not full_path.exists():
                    results.append(f"Warning: {file_path} not found, skipping")
                    continue
                
                try:
                    # Dry run first
                    proc = await asyncio.create_subprocess_exec(
                        'patch', '-p1', '--dry-run',
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(ctx.workdir),
                    )
                    _, stderr = await asyncio.wait_for(
                        proc.communicate(input=patch_content.encode()),
                        timeout=10
                    )
                    
                    if proc.returncode == 0:
                        # Actually apply
                        proc = await asyncio.create_subprocess_exec(
                            'patch', '-p1',
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            cwd=str(ctx.workdir),
                        )
                        _, stderr = await asyncio.wait_for(
                            proc.communicate(input=patch_content.encode()),
                            timeout=10
                        )
                        if proc.returncode == 0:
                            results.append(f"Successfully patched {file_path}")
                        else:
                            results.append(f"Failed to patch {file_path}: {stderr.decode()}")
                    else:
                        results.append(f"Patch would fail for {file_path}: {stderr.decode()}")
                        
                except asyncio.TimeoutError:
                    results.append(f"Timeout applying patch to {file_path}")
                except Exception as e:
                    results.append(f"Error patching {file_path}: {str(e)}")
            
            return ExecuteResult(title="Apply Patch", output="\n".join(results))
        except Exception as e:
            return ExecuteResult(title="Apply Patch Error", output=str(e))
