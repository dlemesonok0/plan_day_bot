from fastapi import FastAPI

from .telegram_bot import router as telegram_router


def create_app() -> FastAPI:
    app = FastAPI(title="Plan Day Bot")
    app.include_router(telegram_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
