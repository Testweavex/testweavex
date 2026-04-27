from __future__ import annotations

import pytest


def test_base_reporter_cannot_be_instantiated_directly():
    from testweavex.reporters.base import BaseReporter
    with pytest.raises(TypeError):
        BaseReporter()  # abstract


def test_concrete_reporter_must_implement_register():
    from testweavex.reporters.base import BaseReporter

    class NoRegister(BaseReporter):
        pass

    with pytest.raises(TypeError):
        NoRegister()


def test_concrete_reporter_is_instantiable_when_register_implemented():
    from testweavex.reporters.base import BaseReporter
    from testweavex.events import EventBus

    class OkReporter(BaseReporter):
        def register(self, bus: EventBus) -> None:
            pass

    r = OkReporter()
    assert r is not None
