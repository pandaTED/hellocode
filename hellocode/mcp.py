"""MCP (Model Context Protocol) integration."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .config import Config
from .tools.base import ExecuteResult, Tool, ToolContext


class MCPTool(Tool):
    """Wraps an MCP server tool as an internal Tool."""

    def __init__(self, name: str, description: str, server_name: str, input_schema: dict, client: "MCPClient"):
        self.id = f"mcp_{server_name}_{name}"
        self._name = name
        self.description = description
        self._server = server_name
        self._schema = input_schema
        self._client = client

    def parameters_schema(self) -> dict:
        return self._schema

    async def execute(self, args: dict, ctx: ToolContext) -> ExecuteResult:
        result = await self._client.call_tool(self._server, self._name, args)
        return ExecuteResult(title=f"MCP: {self._name}", output=str(result))


class MCPClient:
    def __init__(self, config: Config):
        self.config = config
        self._connections: dict[str, Any] = {}
        self._status: dict[str, str] = {}
        self._request_id = 0

    async def connect_all(self) -> list[Tool]:
        tools: list[Tool] = []
        for name, server_cfg in self.config.mcp.servers.items():
            try:
                server_tools = await self.connect_server(name, server_cfg)
                tools.extend(server_tools)
            except Exception as e:
                self._status[name] = f"failed: {e}"
        return tools

    async def connect_server(self, name: str, cfg: dict) -> list[Tool]:
        transport = cfg.get("transport", "stdio")
        if transport == "stdio":
            return await self._connect_stdio(name, cfg)
        self._status[name] = "unsupported transport"
        return []

    async def _connect_stdio(self, name: str, cfg: dict) -> list[Tool]:
        cmd = cfg.get("command", "")
        args = cfg.get("args", [])
        env = cfg.get("env", {})

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(__import__("os").environ), **env},
            )
            self._connections[name] = {"process": proc, "transport": "stdio"}
            self._status[name] = "connected"

            await self._send_json(name, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hellocode", "version": "0.1.0"},
                },
            })
            resp = await self._recv_json(name)

            await self._send_json(name, {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })

            await self._send_json(name, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            })
            tools_resp = await self._recv_json(name)

            result = tools_resp.get("result", {})
            mcp_tools = result.get("tools", [])

            internal_tools = []
            for t in mcp_tools:
                internal_tools.append(MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    server_name=name,
                    input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
                    client=self,
                ))
            return internal_tools

        except Exception as e:
            self._status[name] = f"failed: {e}"
            return []

    async def call_tool(self, server: str, tool_name: str, arguments: dict) -> Any:
        conn = self._connections.get(server)
        if not conn:
            return {"error": f"Server {server} not connected"}

        self._request_id += 1
        await self._send_json(server, {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        resp = await self._recv_json(server)
        result = resp.get("result", {})
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(texts) if texts else json.dumps(result)

    async def _send_json(self, server: str, data: dict) -> None:
        conn = self._connections.get(server)
        if not conn:
            return
        proc = conn["process"]
        line = json.dumps(data) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()

    async def _recv_json(self, server: str) -> dict:
        conn = self._connections.get(server)
        if not conn:
            return {}
        proc = conn["process"]
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=30)
            return json.loads(line.decode()) if line else {}
        except (asyncio.TimeoutError, json.JSONDecodeError):
            return {}

    def get_status(self) -> dict[str, str]:
        return dict(self._status)

    async def disconnect_all(self) -> None:
        for name, conn in self._connections.items():
            proc = conn.get("process")
            if proc:
                proc.terminate()
        self._connections.clear()
        self._status.clear()
