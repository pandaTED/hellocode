"""Tests for provider and config."""
from hellocode.config import Config, KnowledgeConfig, _deep_merge
import pytest


class TestConfig:
    def test_default_config(self):
        c = Config()
        assert c.provider.default == "openai"
        assert c.knowledge.chunk_size == 1000
        assert c.knowledge.max_file_size_mb == 50

    def test_deep_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}, "e": 5}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 99
        assert result["b"]["d"] == 3
        assert result["e"] == 5

    def test_from_dict(self):
        d = {
            "provider": {"default": "openai", "openai": {"apiKey": "sk-123"}},
            "knowledge": {"chunk_size": 500},
        }
        c = Config._from_dict(d)
        assert c.provider.default == "openai"
        assert c.knowledge.chunk_size == 500

    def test_get_provider_model_override(self):
        d = {
            "provider": {"default": "openai", "openai": {"model": "gpt-4"}},
            "agent": {"build": {"model": "gpt-4-turbo"}},
        }
        c = Config._from_dict(d)
        assert c.get_provider_model("build") == "gpt-4-turbo"
        assert c.get_provider_model() == "gpt-4"

    def test_knowledge_config_defaults(self):
        kc = KnowledgeConfig()
        assert kc.chunk_overlap < kc.chunk_size
        assert "md" in kc.supported_types
        assert "pdf" in kc.supported_types
