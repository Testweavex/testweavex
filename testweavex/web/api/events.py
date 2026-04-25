from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

# Production default: 15 s keep-alive pings.
# Override with TW_SSE_KEEPALIVE=0 to emit only the connected event (useful
# for integration tests that need the generator to terminate promptly).
_KEEPALIVE_INTERVAL: float = float(os.environ.get("TW_SSE_KEEPALIVE", "15"))


@router.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint.

    Yields a ``connected`` event on connect, then emits keep-alive comments
    every ``_KEEPALIVE_INTERVAL`` seconds.  Set the ``TW_SSE_KEEPALIVE``
    environment variable to ``0`` to skip the keep-alive loop entirely (handy
    for integration tests where the generator must terminate to return data).
    """

    async def generate() -> AsyncGenerator[str, None]:
        yield 'data: {"event_type": "connected"}\n\n'
        if _KEEPALIVE_INTERVAL <= 0:
            return
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL)
            if await request.is_disconnected():
                break
            yield ": keep-alive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
