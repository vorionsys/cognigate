# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the async logging queue.
"""

import asyncio
import pytest

from app.core.async_logger import AsyncLogQueue


@pytest.mark.anyio
class TestAsyncLogQueue:
    """Test async log queue lifecycle and operations."""

    async def test_initial_state(self):
        q = AsyncLogQueue()
        assert q._running is False
        assert q._processed_count == 0
        assert q._dropped_count == 0

    async def test_start_and_stop(self):
        q = AsyncLogQueue()
        await q.start()
        assert q._running is True
        assert q._task is not None
        await q.stop()
        assert q._running is False

    async def test_start_idempotent(self):
        q = AsyncLogQueue()
        await q.start()
        task1 = q._task
        await q.start()  # Second call should be no-op
        assert q._task is task1
        await q.stop()

    async def test_queue_info_log(self):
        q = AsyncLogQueue()
        await q.start()
        await q.info("test message", key="value")
        # Give the background task time to process
        await asyncio.sleep(0.3)
        assert q._processed_count >= 1
        await q.stop()

    async def test_queue_warning_log(self):
        q = AsyncLogQueue()
        await q.start()
        await q.warning("warn message")
        await asyncio.sleep(0.3)
        assert q._processed_count >= 1
        await q.stop()

    async def test_queue_error_log(self):
        q = AsyncLogQueue()
        await q.start()
        await q.error("error message")
        await asyncio.sleep(0.3)
        assert q._processed_count >= 1
        await q.stop()

    async def test_queue_debug_log(self):
        q = AsyncLogQueue()
        await q.start()
        await q.debug("debug message")
        await asyncio.sleep(0.3)
        assert q._processed_count >= 1
        await q.stop()

    async def test_get_stats(self):
        q = AsyncLogQueue()
        stats = q.get_stats()
        assert stats["running"] is False
        assert stats["queue_size"] == 0
        assert stats["processed_count"] == 0
        assert stats["dropped_count"] == 0

        await q.start()
        stats = q.get_stats()
        assert stats["running"] is True
        assert stats["uptime_seconds"] >= 0
        await q.stop()

    async def test_queue_full_drops(self):
        q = AsyncLogQueue(max_queue_size=2)
        # Don't start processing - queue will fill up
        await q._queue_log("INFO", "msg1")
        await q._queue_log("INFO", "msg2")
        await q._queue_log("INFO", "msg3")  # Should be dropped
        assert q._dropped_count == 1

    async def test_stop_flushes_remaining(self):
        q = AsyncLogQueue()
        # Queue logs without starting processor
        await q._queue_log("INFO", "flush_test")
        assert q._queue.qsize() == 1
        # Stop should flush
        await q.stop()
        assert q._queue.qsize() == 0

    async def test_batch_processing(self):
        q = AsyncLogQueue()
        await q.start()
        # Queue multiple logs
        for i in range(10):
            await q.info(f"batch log {i}")
        await asyncio.sleep(0.5)
        assert q._processed_count >= 10
        await q.stop()
