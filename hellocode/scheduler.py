"""Scheduler engine — cron parsing and background task execution."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Callable

from .storage import Storage

logger = logging.getLogger("hellocode.scheduler")


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    result = set()
    for part in field.split(","):
        part = part.strip()
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                start = min_val
            else:
                start = int(base)
            result.update(range(start, max_val + 1, step))
        elif "-" in part:
            lo, hi = part.split("-", 1)
            result.update(range(int(lo), int(hi) + 1))
        elif part == "*":
            result.update(range(min_val, max_val + 1))
        else:
            result.add(int(part))
    return result


def parse_cron(expr: str) -> Callable[[time.struct_time], bool]:
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression: {expr} (expected 5 fields)")
    minutes = _parse_cron_field(fields[0], 0, 59)
    hours = _parse_cron_field(fields[1], 0, 23)
    days = _parse_cron_field(fields[2], 1, 31)
    months = _parse_cron_field(fields[3], 1, 12)
    weekdays = _parse_cron_field(fields[4], 0, 6)

    def matches(t: time.struct_time) -> bool:
        return (t.tm_min in minutes and t.tm_hour in hours and
                t.tm_mday in days and t.tm_mon in months and
                t.tm_wday in weekdays)

    return matches


def next_cron_time(expr: str, after: float | None = None) -> float:
    check = parse_cron(expr)
    t = (after or time.time() * 1000) / 1000
    tm = time.localtime(t + 60)
    for _ in range(60 * 24 * 7):
        if check(tm):
            return time.mktime(tm) * 1000
        tm = time.localtime(time.mktime(tm) + 60)
    return (after or time.time() * 1000) + 3600000


def next_interval_time(interval: int, after: float | None = None) -> float:
    base = after or time.time() * 1000
    return base + interval * 1000


class Scheduler:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._running = False
        self._task: asyncio.Task | None = None
        self._executors: dict[str, Callable] = {}
        self._running_ids: set[str] = set()

    def register_executor(self, task_type: str, executor: Callable) -> None:
        self._executors[task_type] = executor

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._check_and_run()
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)
            await asyncio.sleep(30)

    async def _check_and_run(self) -> None:
        due = self.storage.get_due_schedules()
        for schedule in due:
            await self._execute_schedule(schedule)

    async def _execute_schedule(self, schedule: dict) -> None:
        schedule_id = schedule["id"]
        if schedule_id in self._running_ids:
            return
        self._running_ids.add(schedule_id)
        try:
            run_id = self.storage.uid()
            self.storage.create_schedule_run(run_id, schedule_id)
            self.storage.update_schedule(schedule_id, last_run_at=self.storage.now())
        except Exception as e:
            logger.error("Failed to create schedule run: %s", e)
            self._running_ids.discard(schedule_id)
            return

        try:
            task_type = schedule["task_type"]
            executor = self._executors.get(task_type)
            if not executor:
                raise ValueError(f"No executor for task type: {task_type}")
            if inspect.iscoroutinefunction(executor):
                result = await executor(schedule)
            else:
                result = executor(schedule)
            self.storage.update_schedule_run(
                run_id, finished_at=self.storage.now(), status="success", result=str(result)[:2000],
            )
            self.storage.update_schedule(schedule_id, last_status="success", last_error=None)
        except Exception as e:
            logger.error("Schedule %s failed: %s", schedule_id, e)
            self.storage.update_schedule_run(
                run_id, finished_at=self.storage.now(), status="error", error_message=str(e),
            )
            self.storage.update_schedule(schedule_id, last_status="error", last_error=str(e))
        finally:
            self._running_ids.discard(schedule_id)

        self._update_next_run(schedule)

    def _update_next_run(self, schedule: dict) -> None:
        now = self.storage.now()
        if schedule.get("cron_expression"):
            try:
                nxt = next_cron_time(schedule["cron_expression"], now)
            except Exception:
                nxt = now + 3600000
        elif schedule.get("interval_seconds"):
            nxt = next_interval_time(schedule["interval_seconds"], now)
        else:
            nxt = now + 3600000
        self.storage.update_schedule(schedule["id"], next_run_at=nxt)
