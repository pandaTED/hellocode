"""Tests for knowledge engine."""
from pathlib import Path
from hellocode.storage import Storage
from hellocode.knowledge import KnowledgeEngine, _chunk_text, _file_hash
import tempfile
import pytest


@pytest.fixture
def engine():
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "test.db"
    s = Storage(db)
    e = KnowledgeEngine(s, tmp)
    yield e
    s.close()


class TestChunkText:
    def test_empty(self):
        assert _chunk_text("") == []
        assert _chunk_text("   ") == []

    def test_short(self):
        chunks = _chunk_text("hi", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0]["content"] == "hi"

    def test_normal(self):
        text = "a" * 2000
        chunks = _chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_overlap_protection(self):
        chunks = _chunk_text("hello", chunk_size=5, overlap=10)
        assert len(chunks) >= 1


class TestFileHash:
    def test_normal(self, tmp_path):
        fp = tmp_path / "test.txt"
        fp.write_text("hello")
        h = _file_hash(fp)
        assert len(h) == 32

    def test_deleted_file(self, tmp_path):
        fp = tmp_path / "gone.txt"
        h = _file_hash(fp)
        assert h == ""


class TestKnowledgeEngine:
    def test_add_source(self, engine, tmp_path):
        src = engine.add_source("Docs", tmp_path)
        assert src["id"]
        assert engine.list_sources()

    def test_add_source_nonexistent(self, engine):
        with pytest.raises(FileNotFoundError):
            engine.add_source("Bad", Path("/nonexistent"))

    def test_add_source_duplicate(self, engine, tmp_path):
        src1 = engine.add_source("Docs", tmp_path)
        src2 = engine.add_source("Docs", tmp_path)
        assert src1["id"] == src2["id"]

    def test_remove_source(self, engine, tmp_path):
        src = engine.add_source("Docs", tmp_path)
        engine.remove_source(src["id"])
        assert engine.list_sources() == []

    def test_index_source(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        (d / "readme.md").write_text("# Title\n\nContent here.")
        (d / "notes.txt").write_text("Meeting notes.")
        src = engine.add_source("Docs", d)
        result = engine.index_source(src["id"])
        assert result["indexed"] == 2
        assert result["errors"] == 0

    def test_index_skip_unchanged(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        (d / "a.md").write_text("hello")
        src = engine.add_source("Docs", d)
        engine.index_source(src["id"])
        result2 = engine.index_source(src["id"])
        assert result2["skipped"] == 1

    def test_search(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        (d / "a.md").write_text("Python is a programming language")
        src = engine.add_source("Docs", d)
        engine.index_source(src["id"])
        results = engine.search("Python")
        assert len(results) > 0
        assert "Python" in results[0]["content"]

    def test_search_empty(self, engine):
        results = engine.search("")
        assert results == []

    def test_stats(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        (d / "a.md").write_text("hello")
        src = engine.add_source("Docs", d)
        engine.index_source(src["id"])
        stats = engine.get_stats()
        assert stats["documents"] == 1
        assert stats["chunks"] >= 1

    def test_index_nonexistent_source(self, engine):
        with pytest.raises(ValueError):
            engine.index_source("nonexistent")

    def test_get_document(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        (d / "a.md").write_text("hello")
        src = engine.add_source("Docs", d)
        engine.index_source(src["id"])
        docs = engine.list_documents(src["id"])
        assert len(docs) == 1
        doc = engine.get_document(docs[0]["id"])
        assert doc is not None
        chunks = engine.get_document_chunks(docs[0]["id"])
        assert len(chunks) >= 1

    def test_extractors(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        (d / "a.json").write_text('{"key": "value"}')
        (d / "b.csv").write_text("col1,col2\n1,2\n3,4")
        (d / "c.yaml").write_text("key: value")
        src = engine.add_source("Docs", d)
        result = engine.index_source(src["id"])
        assert result["indexed"] == 3

    def test_large_file_skip(self, engine, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        big = d / "big.txt"
        big.write_text("x" * (60 * 1024 * 1024))
        (d / "small.md").write_text("hello")
        src = engine.add_source("Docs", d)
        result = engine.index_source(src["id"])
        assert result["indexed"] == 1
        assert result["total"] == 1
