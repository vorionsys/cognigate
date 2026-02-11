"""
Async Logging Queue for Cognigate.

Provides non-blocking async logging to avoid I/O latency
impacting request processing times.

Logs are queued and processed in a background task.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AsyncLogQueue:
    """
    Non-blocking async logging queue.

    Logs are queued and processed by a background task,
    preventing logging I/O from blocking request handlers.
    """

    def __init__(self, max_queue_size: int = 10000, flush_interval: float = 0.1):
        """
        Initialize the async log queue.

        Args:
            max_queue_size: Maximum queue size before dropping logs
            flush_interval: How often to flush logs (seconds)
        """
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._flush_interval = flush_interval
        self._dropped_count: int = 0
        self._processed_count: int = 0
        self._start_time: Optional[float] = None

    async def start(self) -> None:
        """Start the background log processing task."""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._process_logs())
        logger.info(
            "async_logger_started",
            extra={"max_queue_size": self._queue.maxsize}
        )

    async def stop(self) -> None:
        """Stop the background task and flush remaining logs."""
        self._running = False

        if self._task:
            # Wait for task to finish processing remaining logs
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        # Flush any remaining logs synchronously
        while not self._queue.empty():
            try:
                log_entry = self._queue.get_nowait()
                self._write_log(log_entry)
            except asyncio.QueueEmpty:
                break

        logger.info(
            "async_logger_stopped",
            extra={
                "processed": self._processed_count,
                "dropped": self._dropped_count,
            }
        )

    async def _process_logs(self) -> None:
        """Background task that processes queued logs."""
        while self._running:
            try:
                # Process all available logs
                batch = []
                while len(batch) < 100:  # Process in batches of 100
                    try:
                        log_entry = self._queue.get_nowait()
                        batch.append(log_entry)
                    except asyncio.QueueEmpty:
                        break

                # Write batch
                for entry in batch:
                    self._write_log(entry)
                    self._processed_count += 1

                # Sleep if no logs to process
                if not batch:
                    await asyncio.sleep(self._flush_interval)

            except Exception as e:
                logger.error(f"async_logger_error: {e}")
                await asyncio.sleep(self._flush_interval)

    def _write_log(self, entry: dict) -> None:
        """Write a log entry to the configured output."""
        try:
            level = entry.pop("_level", "INFO")
            message = entry.pop("_message", "log")

            # Get the appropriate logger method
            log_method = getattr(logger, level.lower(), logger.info)
            log_method(message, extra=entry)
        except Exception as e:
            # Last resort - print to stderr
            print(f"ASYNC_LOG_ERROR: {e} - {entry}")

    async def info(self, message: str, **kwargs: Any) -> None:
        """Queue an INFO level log."""
        await self._queue_log("INFO", message, **kwargs)

    async def warning(self, message: str, **kwargs: Any) -> None:
        """Queue a WARNING level log."""
        await self._queue_log("WARNING", message, **kwargs)

    async def error(self, message: str, **kwargs: Any) -> None:
        """Queue an ERROR level log."""
        await self._queue_log("ERROR", message, **kwargs)

    async def debug(self, message: str, **kwargs: Any) -> None:
        """Queue a DEBUG level log."""
        await self._queue_log("DEBUG", message, **kwargs)

    async def _queue_log(self, level: str, message: str, **kwargs: Any) -> None:
        """
        Queue a log entry for async processing.

        If queue is full, drops the log and increments counter.
        """
        entry = {
            "_level": level,
            "_message": message,
            "_timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }

        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            self._dropped_count += 1
            if self._dropped_count % 1000 == 0:
                # Log every 1000 drops to avoid log spam
                logger.warning(
                    "async_log_queue_full",
                    extra={"total_dropped": self._dropped_count}
                )

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "max_queue_size": self._queue.maxsize,
            "processed_count": self._processed_count,
            "dropped_count": self._dropped_count,
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
        }


# Global async log queue instance
async_log_queue = AsyncLogQueue()
