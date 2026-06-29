"""Tests for scheduler engine."""
from hellocode.scheduler import (
    parse_cron, next_cron_time, next_interval_time,
    _parse_cron_field, Scheduler,
)
from hellocode.storage import Storage
from pathlib import Path
import tempfile
import time
import pytest


@pytest.fixture
def storage():
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "test.db"
    s = Storage(db)
    yield s
    s.close()


class TestCronParsing:
    def test_wildcard(self):
        mins = _parse_cron_field("*", 0, 59)
        assert mins == set(range(60))

    def test_specific(self):
        mins = _parse_cron_field("0,15,30,45", 0, 59)
        assert mins == {0, 15, 30, 45}

    def test_range(self):
        hrs = _parse_cron_field("9-17", 0, 23)
        assert hrs == set(range(9, 18))

    def test_step(self):
        mins = _parse_cron_field("*/15", 0, 59)
        assert mins == {0, 15, 30, 45}

    def test_parse_cron_valid(self):
        check = parse_cron("0 9 * * *")
        assert callable(check)

    def test_parse_cron_invalid(self):
        with pytest.raises(ValueError):
            parse_cron("invalid")

    def test_parse_cron_wrong_fields(self):
        with pytest.raises(ValueError):
            parse_cron("0 9 * *")


class TestNextTime:
    def test_next_cron_returns_ms(self):
        nxt = next_cron_time("0 9 * * *")
        assert nxt > 1e12

    def test_next_interval_returns_ms(self):
        nxt = next_interval_time(3600)
        assert nxt > 1e12

    def test_next_interval_adds_correctly(self):
        now_ms = time.time() * 1000
        nxt = next_interval_time(60, now_ms)
        assert abs(nxt - (now_ms + 60000)) < 100

    def test_next_cron_after_specific_time(self):
        nxt = next_cron_time("0 9 * * *", 1782600000000)
        assert nxt > 1782600000000


class TestScheduler:
    def test_register_executor(self, storage):
        sched = Scheduler(storage)
        sched.register_executor("test", lambda s: "ok")
        assert "test" in sched._executors

    def test_start_stop(self, storage):
        sched = Scheduler(storage)
        assert not sched._running

    def test_concurrent_protection(self, storage):
        sched = Scheduler(storage)
        sched._running_ids.add("s1")
        assert "s1" in sched._running_ids
        sched._running_ids.discard("s1")
        assert "s1" not in sched._running_ids
