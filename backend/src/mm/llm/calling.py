"""How every provider makes its calls: a few at a time, each given up after a time limit.

The limit covers the whole call, an SDK's own retries included, so no call outlasts
it, and a server shutdown's grace period can count on it.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace

from mm.llm.protocol import CALL_TIMEOUT_S, ModelReply


class CallLimits:
    def __init__(self, concurrency: int = 5, timeout_s: float = CALL_TIMEOUT_S) -> None:
        self.timeout_s = timeout_s
        self._slots = asyncio.Semaphore(concurrency)

    async def run(self, ask: Callable[[], Awaitable[ModelReply]]) -> ModelReply:
        """Ask once a slot is free; a reply that does not come in time is a timeout."""
        async with self._slots:
            started = time.monotonic()
            try:
                async with asyncio.timeout(self.timeout_s):
                    reply = await ask()
            except TimeoutError:
                no_answer = f"no answer within {self.timeout_s:g} seconds"
                reply = ModelReply.failure(no_answer, outcome="timeout")
            return replace(reply, latency_ms=int((time.monotonic() - started) * 1000))
