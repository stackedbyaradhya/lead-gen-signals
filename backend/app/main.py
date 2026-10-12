from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.database import create_session_factory
from app.settings import settings


def create_app(database_url: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="Outcome-Calibrated Ranking", version="0.1.0")
    engine, session_factory = create_session_factory(database_url or settings.database_url)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8080"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
