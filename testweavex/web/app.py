from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from testweavex.core.config import TestWeaveXConfig, load_config
from testweavex.events import EventBus
from testweavex.storage.sqlite import SQLiteRepository

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: TestWeaveXConfig | None = None) -> FastAPI:
    if config is None:
        config = load_config()

    db_dir = Path.cwd() / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    repo = SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")
    bus = EventBus()

    app = FastAPI(title="TestWeaveX", version="0.1.0")
    app.state.repo = repo
    app.state.bus = bus
    app.state.config = config

    from testweavex.web.api.dashboard import router as dashboard_router
    from testweavex.web.api.runs import router as runs_router
    from testweavex.web.api.test_cases import router as test_cases_router
    from testweavex.web.api.gaps import router as gaps_router
    from testweavex.web.api.settings import router as settings_router
    from testweavex.web.api.events import router as events_router

    app.include_router(dashboard_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(test_cases_router, prefix="/api")
    app.include_router(gaps_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(events_router, prefix="/api")

    if _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

    return app
