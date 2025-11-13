import asyncio
import contextlib
import logging

from fastapi import FastAPI

from .config import get_settings
from .telegram_bot import poll_updates, router as telegram_router


if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
else:
    logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Plan Day Bot")
    logger.debug("FastAPI application instance created")
    app.include_router(telegram_router)

    @app.get("/health")
    async def health() -> dict:
        logger.debug("Health check requested")
        return {"status": "ok"}

    @app.on_event("startup")
    async def start_polling() -> None:
        logger.info("Application startup: initializing polling task")
        settings = get_settings()
        logger.debug("Settings loaded for polling")
        app.state.poller = asyncio.create_task(poll_updates(settings))
        logger.info("Polling task started")

    @app.on_event("shutdown")
    async def stop_polling() -> None:
        logger.info("Application shutdown: stopping polling task")
        poller = getattr(app.state, "poller", None)
        if poller:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller
            logger.info("Polling task successfully stopped")
        else:
            logger.debug("No polling task found during shutdown")

    return app


app = create_app()
