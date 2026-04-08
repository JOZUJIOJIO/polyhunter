from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_db(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PolyHunter API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.api.routes.markets import router as markets_router
    from backend.api.routes.signals import router as signals_router
    from backend.api.routes.trades import router as trades_router
    from backend.api.routes.positions import router as positions_router
    from backend.api.routes.overview import router as overview_router
    from backend.api.routes.auto_trade import router as auto_trade_router

    app.include_router(markets_router, prefix="/api")
    app.include_router(signals_router, prefix="/api")
    app.include_router(trades_router, prefix="/api")
    app.include_router(positions_router, prefix="/api")
    app.include_router(overview_router, prefix="/api")
    app.include_router(auto_trade_router, prefix="/api")

    return app


app = create_app()
