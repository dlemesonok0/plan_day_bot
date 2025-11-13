import asyncio
import contextlib

from fastapi import FastAPI

from .config import get_settings
from .telegram_bot import poll_updates, router as telegram_router


def create_app() -> FastAPI:
    app = FastAPI(title="Plan Day Bot")
    app.include_router(telegram_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.on_event("startup")
    async def start_polling() -> None:
        settings = get_settings()
        app.state.poller = asyncio.create_task(poll_updates(settings))

    @app.on_event("shutdown")
    async def stop_polling() -> None:
        poller = getattr(app.state, "poller", None)
        if poller:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller

    return app


app = create_app()
