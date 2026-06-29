"""Tests for storage layer."""
from pathlib import Path
from hellocode.storage import Storage
import tempfile
import pytest


@pytest.fixture
def storage():
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "test.db"
    s = Storage(db)
    yield s
    s.close()


class TestKnowledgeBase:
    def test_create_source(self, storage):
        src = storage.create_kb_source("s1", "Test", "/tmp/test", "folder")
        assert src["id"] == "s1"
        assert src["name"] == "Test"

    def test_get_source(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp/test", "folder")
        got = storage.get_kb_source("s1")
        assert got["name"] == "Test"

    def test_get_source_by_path(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp/test", "folder")
        got = storage.get_kb_source_by_path("/tmp/test")
        assert got["id"] == "s1"

    def test_list_sources(self, storage):
        storage.create_kb_source("s1", "A", "/a", "folder")
        storage.create_kb_source("s2", "B", "/b", "file")
        ls = storage.list_kb_sources()
        assert len(ls) == 2

    def test_update_source(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp/test", "folder")
        storage.update_kb_source("s1", file_count=42)
        got = storage.get_kb_source("s1")
        assert got["file_count"] == 42

    def test_delete_source_cascade(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp/test", "folder")
        storage.create_kb_document("d1", "s1", "/a.md", "a.md", "md", 100, "h1")
        storage.create_kb_chunk("c1", "d1", 0, "hello")
        storage.delete_kb_source("s1")
        assert storage.get_kb_source("s1") is None
        assert storage.get_kb_document("d1") is None

    def test_create_document(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp", "folder")
        doc = storage.create_kb_document("d1", "s1", "/a.md", "a.md", "md", 100, "h1")
        assert doc["id"] == "d1"

    def test_search_chunks(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp", "folder")
        storage.create_kb_document("d1", "s1", "/a.md", "a.md", "md", 100, "h1")
        storage.create_kb_chunk("c1", "d1", 0, "Python is great for data science")
        storage.index_kb_chunks_fts_batch([("c1", "Python is great for data science", "")])
        results = storage.search_kb_chunks("Python")
        assert len(results) > 0
        assert "Python" in results[0]["content"]

    def test_search_empty_query(self, storage):
        results = storage.search_kb_chunks("")
        assert results == []

    def test_search_special_chars(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp", "folder")
        storage.create_kb_document("d1", "s1", "/a.md", "a.md", "md", 100, "h1")
        storage.create_kb_chunk("c1", "d1", 0, "test/path content")
        storage.index_kb_chunks_fts_batch([("c1", "test/path content", "")])
        results = storage.search_kb_chunks("test/path query")
        assert results == []

    def test_get_stats(self, storage):
        stats = storage.get_kb_stats()
        assert stats["sources"] == 0
        assert stats["documents"] == 0

    def test_batch_chunks(self, storage):
        storage.create_kb_source("s1", "Test", "/tmp", "folder")
        storage.create_kb_document("d1", "s1", "/a.md", "a.md", "md", 100, "h1")
        chunks = [
            {"id": f"c{i}", "document_id": "d1", "chunk_index": i,
             "content": f"chunk {i} content", "page_number": None,
             "heading": None, "char_offset": i * 100}
            for i in range(5)
        ]
        storage.create_kb_chunks_batch(chunks)
        fts = [(f"c{i}", f"chunk {i} content", "") for i in range(5)]
        storage.index_kb_chunks_fts_batch(fts)
        results = storage.search_kb_chunks("chunk")
        assert len(results) == 5


class TestSchedule:
    def test_create_schedule(self, storage):
        sched = storage.create_schedule("s1", "Test", "shell_command", "echo hi")
        assert sched["id"] == "s1"
        assert sched["enabled"] is True

    def test_get_schedule(self, storage):
        storage.create_schedule("s1", "Test", "shell_command", "echo hi")
        got = storage.get_schedule("s1")
        assert got["name"] == "Test"

    def test_list_schedules(self, storage):
        storage.create_schedule("s1", "A", "shell_command", "a")
        storage.create_schedule("s2", "B", "agent_prompt", "b")
        ls = storage.list_schedules()
        assert len(ls) == 2

    def test_update_schedule(self, storage):
        storage.create_schedule("s1", "Test", "shell_command", "echo hi")
        storage.update_schedule("s1", enabled=0)
        got = storage.get_schedule("s1")
        assert got["enabled"] == 0

    def test_delete_schedule(self, storage):
        storage.create_schedule("s1", "Test", "shell_command", "echo hi")
        storage.delete_schedule("s1")
        assert storage.get_schedule("s1") is None

    def test_schedule_run(self, storage):
        storage.create_schedule("s1", "Test", "shell_command", "echo hi")
        run = storage.create_schedule_run("r1", "s1")
        assert run["status"] == "running"
        storage.update_schedule_run("r1", status="success", result="done")
        runs = storage.get_schedule_runs("s1")
        assert len(runs) == 1
        assert runs[0]["status"] == "success"

    def test_due_schedules(self, storage):
        storage.create_schedule("s1", "Test", "shell_command", "echo hi", next_run_at=0)
        due = storage.get_due_schedules()
        assert len(due) == 1

    def test_no_due_schedules(self, storage):
        storage.create_schedule("s1", "Test", "shell_command", "echo hi",
                                next_run_at=9999999999999)
        due = storage.get_due_schedules()
        assert len(due) == 0
