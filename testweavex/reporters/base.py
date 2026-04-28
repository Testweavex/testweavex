from __future__ import annotations

from abc import ABC, abstractmethod

from testweavex.events import EventBus


class BaseReporter(ABC):

    @abstractmethod
    def register(self, bus: EventBus) -> None: ...
