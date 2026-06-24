"""Configuration system with layered merging."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_DIRS = [
    Path.home() / ".config" / "hellocode",
    Path.home() / ".hellocode",
]
CONFIG_FILES = ["hellocode.json", "config.json"]


@dataclass
class ProviderConfig:
    default: str = "openai"
    openai: dict[str, Any] = field(default_factory=lambda: {
        "apiKey": "", "model": "gpt-4", "max_tokens": 32768
    })


@dataclass
class AgentConfig:
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class MCPConfig:
    servers: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    agent: dict[str, AgentConfig] = field(default_factory=dict)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    plugin_paths: list[str] = field(default_factory=list)
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "hellocode")
    raw: dict[str, Any] = field(default_factory=dict)

    def get_provider_key(self) -> str:
        name = self.provider.default
        return self.provider.__dict__.get(name, {}).get("apiKey", "")

    def get_provider_model(self, agent_name: str | None = None) -> str:
        if agent_name and agent_name in self.agent:
            m = self.agent[agent_name].model
            if m:
                return m
        name = self.provider.default
        return self.provider.__dict__.get(name, {}).get("model", "gpt-4")

    def get_provider_base_url(self) -> str | None:
        name = self.provider.default
        return self.provider.__dict__.get(name, {}).get("base_url")

    def get_provider_headers(self) -> dict[str, str] | None:
        name = self.provider.default
        return self.provider.__dict__.get(name, {}).get("headers")

    def get_provider_max_tokens(self) -> int:
        name = self.provider.default
        return self.provider.__dict__.get(name, {}).get("max_tokens", 16384)

    @classmethod
    def load(cls, workdir: Path | None = None) -> Config:
        merged: dict[str, Any] = {}

        for d in CONFIG_DIRS:
            for f in CONFIG_FILES:
                p = d / f
                if p.exists():
                    _deep_merge(merged, json.loads(p.read_text(encoding="utf-8")))

        env_config = os.environ.get("MIMOCODE_CONFIG")
        if env_config:
            try:
                _deep_merge(merged, json.loads(env_config))
            except json.JSONDecodeError:
                pass

        if workdir:
            for f in CONFIG_FILES:
                p = workdir / f
                if p.exists():
                    _deep_merge(merged, json.loads(p.read_text(encoding="utf-8")))
            mc = workdir / ".hellocode"
            if mc.is_dir():
                for f in mc.glob("*.json"):
                    _deep_merge(merged, json.loads(f.read_text(encoding="utf-8")))

        env_content = os.environ.get("MIMOCODE_CONFIG_CONTENT")
        if env_content:
            try:
                _deep_merge(merged, json.loads(env_content))
            except json.JSONDecodeError:
                pass

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key and "provider" in merged:
            pname = merged["provider"].get("default", "openai")
            if pname in merged["provider"]:
                merged["provider"][pname]["apiKey"] = api_key

        return cls._from_dict(merged)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> Config:
        prov_raw = d.get("provider", {})
        prov = ProviderConfig(
            default=prov_raw.get("default", "openai"),
            openai=prov_raw.get("openai", {}),
        )
        agents = {}
        for name, acfg in d.get("agent", {}).items():
            if isinstance(acfg, dict):
                agents[name] = AgentConfig(**acfg)
        mcp = MCPConfig(servers=d.get("mcp", {}).get("servers", {}))
        return cls(
            provider=prov,
            agent=agents,
            mcp=mcp,
            plugin_paths=d.get("plugin", {}).get("paths", []),
            raw=d,
        )


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
