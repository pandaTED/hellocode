"""Configuration system with layered merging."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("hellocode.config")

CONFIG_DIRS = [
    Path.home() / ".config" / "hellocode",
    Path.home() / ".hellocode",
]
CONFIG_FILES = ["hellocode.json", "config.json"]

DEFAULT_PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "model": "gpt-4",
        "base_url": "https://api.openai.com/v1",
        "max_tokens": 16384,
    },
    "openrouter": {
        "model": "openrouter/free",
        "base_url": "https://openrouter.ai/api/v1",
        "max_tokens": 4096,
    },
    "nvidia": {
        "model": "deepseek-v4-pro",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "max_tokens": 4096,
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434/v1",
        "max_tokens": 4096,
    },
}


@dataclass
class ProviderConfig:
    default: str = "openai"
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name in ("default", "providers"):
            raise AttributeError(name)
        return self.providers.get(name, {})

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("default", "providers"):
            object.__setattr__(self, name, value)
        else:
            self.providers[name] = value


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

    def _get_provider_cfg(self) -> dict[str, Any]:
        name = self.provider.default
        return self.provider.providers.get(name, {})

    def get_provider_key(self) -> str:
        return self._get_provider_cfg().get("apiKey", "")

    def get_provider_model(self, agent_name: str | None = None) -> str:
        if agent_name and agent_name in self.agent:
            m = self.agent[agent_name].model
            if m:
                return m
        return self._get_provider_cfg().get("model", "gpt-4")

    def get_provider_base_url(self) -> str | None:
        return self._get_provider_cfg().get("base_url")

    def get_provider_headers(self) -> dict[str, str] | None:
        return self._get_provider_cfg().get("headers")

    def get_provider_max_tokens(self) -> int:
        return self._get_provider_cfg().get("max_tokens", 16384)

    def provider_to_dict(self) -> dict[str, Any]:
        return {
            "default": self.provider.default,
            **self.provider.providers,
        }

    def ensure_provider(self, name: str) -> dict[str, Any]:
        provider = self.provider.providers.setdefault(name, {})
        for key, value in DEFAULT_PROVIDER_PRESETS.get(name, {}).items():
            provider.setdefault(key, value)
        return provider

    def save_provider_config(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        current: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    current = loaded
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read existing config %s: %s", path, e)
        current["provider"] = self.provider_to_dict()
        path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, workdir: Path | None = None) -> Config:
        merged: dict[str, Any] = {}

        for d in CONFIG_DIRS:
            for f in CONFIG_FILES:
                p = d / f
                if p.exists():
                    try:
                        _deep_merge(merged, json.loads(p.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError) as e:
                        logger.warning("Failed to parse %s: %s", p, e)

        env_config = os.environ.get("HELLOCODE_CONFIG")
        if env_config:
            try:
                _deep_merge(merged, json.loads(env_config))
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse HELLOCODE_CONFIG: %s", e)

        if workdir:
            for f in CONFIG_FILES:
                p = workdir / f
                if p.exists():
                    try:
                        _deep_merge(merged, json.loads(p.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError) as e:
                        logger.warning("Failed to parse %s: %s", p, e)
            mc = workdir / ".hellocode"
            if mc.is_dir():
                for f in mc.glob("*.json"):
                    try:
                        _deep_merge(merged, json.loads(f.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError) as e:
                        logger.warning("Failed to parse %s: %s", f, e)

        env_content = os.environ.get("HELLOCODE_CONFIG_CONTENT")
        if env_content:
            try:
                _deep_merge(merged, json.loads(env_content))
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse HELLOCODE_CONFIG_CONTENT: %s", e)

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            if "provider" not in merged or not isinstance(merged["provider"], dict):
                merged["provider"] = {"default": "openai"}
            pname = merged["provider"].get("default", "openai")
            if pname not in merged["provider"]:
                merged["provider"][pname] = {}
            merged["provider"][pname]["apiKey"] = api_key

        return cls._from_dict(merged)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> Config:
        prov_raw = d.get("provider", {})
        providers = {}
        for k, v in prov_raw.items():
            if k != "default" and isinstance(v, dict):
                providers[k] = v
        prov = ProviderConfig(
            default=prov_raw.get("default", "openai"),
            providers=providers,
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
