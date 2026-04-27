from __future__ import annotations

import sys

import httpx

from testweavex.events import EventBus, SessionFinished, TestFinished, TWEvent
from testweavex.reporters.base import BaseReporter


class ServerReporter(BaseReporter):

    def __init__(self, base_url: str, token: str | None) -> None:
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )

    def register(self, bus: EventBus) -> None:
        bus.subscribe("test_finished", self._push)
        bus.subscribe("session_finished", self._push)

    def _push(self, event: TWEvent) -> None:
        try:
            self._client.post("/events", json=event.model_dump(mode="json"))
        except Exception as exc:
            print(f"[testweavex] ServerReporter: failed to push event: {exc}", file=sys.stderr)
